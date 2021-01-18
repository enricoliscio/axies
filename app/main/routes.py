import random
from flask import flash

from flask import (current_app, jsonify, redirect, render_template, request,
                   session, url_for)

from app import db, explorator, consolidator
from app.main import bp
from app.main.forms import AddValueForm, EditProfileForm
from app.models import *
from flask_login import current_user, login_required


@bp.route('/', methods=['GET', 'POST'])
@bp.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    return render_template('index.html', title='Home')


@bp.route('/set_context', methods=['POST'])
@login_required
def set_context():
    current_user.working_context_id = request.json['context_id']
    db.session.commit()
    # flash("Working context changed to: " + request.json['context_name'])
    return jsonify(context_name=request.json['context_name'])


@bp.route('/explore')
@login_required
def explore():
    # Check if a context is selected
    if current_user.working_context_id is None:
        flash('You must select a context (from the navbar) before starting exploration!')
        return render_template('index.html', title='Home')

    # Check for exploration permission
    current_user_context = UserContext.get_user_context(current_user.id, current_user.working_context_id)
    if current_user_context.can_explore is False:
        flash('You do not have explore permission for this working context! Please contact the admin')
        return render_template('index.html', title='Home')

    choices = Choice.query.filter_by(context_id=current_user.working_context_id).all()
    if len(choices) != 0:
        if 'similar_value_id' in session and session['similar_value_id'] is not None:
            # Get a motivation that is similar to the value, as per user request
            motivation, uc_motivation = explorator.get_next_motivation(
                    Context, UserContext, UserContextMotivation, Value, Motivation, Choice,
                    similar_value_id=session['similar_value_id'])
            db.session.add(uc_motivation)
            session.pop('similar_value_id')
        else:
            # Check if the user was already viewing a motivation from earlier that
            # is unfinished/unannotated
            seen_motivations = current_user_context.seen_motivations.all()
            annotated_motivations = AnnotationAction.query.filter_by(completed_by=current_user_context.id).all()
            seen_motivation_ids = [x.motivation_id for x in seen_motivations]
            annotated_motivations_ids = [x.shown_motivation for x in annotated_motivations]
            unannotated_seen_motivations_ids = set(seen_motivation_ids) - set(annotated_motivations_ids)
            if len(unannotated_seen_motivations_ids) > 0:
                # Get a motivation that was seen, but not annotated
                current_app.logger.info("Showing seen motivation that was previously unannotated")
                motivation_id = unannotated_seen_motivations_ids.pop()
                motivation = Motivation.query.filter_by(id=motivation_id).first()
            else:
                # Get a new motivation
                current_app.logger.info("Showing new motivation")
                motivation, uc_motivation = explorator.get_next_motivation(
                        Context, UserContext, UserContextMotivation, Value, Motivation, Choice)
                db.session.add(uc_motivation)

        db.session.commit()
        session['current_motivation_id'] = motivation.id
        choice = Choice.query.filter_by(id=motivation.choice_id).first()
    else:
        motivation = None
    value_form = AddValueForm()
    return render_template('explore.html', title='Explore', choice=choice,
        motivation=motivation, value_form=value_form)


@bp.route('/consolidate')
@login_required
def consolidate():
    # Check if a context is selected
    if current_user.working_context_id is None:
        flash('You must select a context (from the navbar) before continuing with consolidation!')
        return render_template('index.html', title='Home')

    # Check for consolidation permission
    current_user_context = UserContext.get_user_context(current_user.id, current_user.working_context_id)
    if current_user_context.can_consolidate is False:
        flash('You do not have explore permission for consolidating this working context! Please contact the admin')
        return render_template('index.html', title='Home')

    # Check if the Consolidation has already been started
    others_ucs = UserContext.query.filter_by(group_id=current_user_context.group_id, context_id=current_user.working_context_id).all()
    group_others_status = [x.consolidation_started for x in others_ucs]
    group_members = [User.query.get(x.user_id).username for x in others_ucs]
    if (current_user_context.consolidation_started is None or not current_user_context.consolidation_started) and not any(group_others_status):
        return render_template('consolidate_warning.html', title='Consolidate prestart', group_members=group_members)

    # Templated form for adding new values
    value_form = AddValueForm()

    # Get unannotated seen value couples
    unannotated_seen_value_couples = ValueCouple.from_context_group(current_user.working_context_id, current_user_context.group_id).filter_by(already_shown=True, annotated=False).all()

    # Get next value couple to be shown.
    if 'next_couple_id' in session and session['next_couple_id'] is not None:
        # Get the preloaded ValueCouple as requested by user
        value_couple = ValueCouple.query.get(session['next_couple_id'])
        session['next_couple_id'] = None
        value_couple.already_shown = True
        current_app.logger.info("Showing requested ValueCouple")
    elif len(unannotated_seen_value_couples) > 0:
        current_app.logger.info("Showing previously unannotated ValueCouple")
        # Get a ValueCouple that is seen, but not annotated yet
        value_couple = unannotated_seen_value_couples.pop()
    else:
        # Get a new unseen ValueCouple
        current_app.logger.info("Showing a new ValueCouple")
        value_couple = consolidator.get_next_value_couple(ValueCouple, UserContext)
    db.session.commit()
    # Catch if value_couple is None or one of the internal values is None
    if value_couple is None:
        session['current_shown_couple_id'] = None
        return render_template('consolidate.html', title='Consolidate', value_pair=[None, None], value_form=value_form, triggers=[[], []])

    # Create ShownValueCouple.
    shown_value_couple = ShownValueCouple(group_id=current_user_context.group_id,
            value_couple_id=value_couple.id, distance=value_couple.distance)
    db.session.add(shown_value_couple)
    db.session.commit()
    session['current_shown_couple_id'] = shown_value_couple.id

    value_pair = [ConsolidationValue.query.get(value_couple.value_id_0),
                  ConsolidationValue.query.get(value_couple.value_id_1)]
    value_pair[0].original_author = lookup_author(value_couple.value_id_0)
    value_pair[1].original_author = lookup_author(value_couple.value_id_1)
    mots_0 = consolidator.get_trigger_sentences(value_couple.value_id_0, ValueConsolidationValue, AnnotationAction, Action, Motivation)
    mots_1 = consolidator.get_trigger_sentences(value_couple.value_id_1, ValueConsolidationValue, AnnotationAction, Action, Motivation)
    trigger_sentences = [mots_0, mots_1]

    return render_template('consolidate.html', title='Consolidate', value_pair=value_pair, value_form=value_form, triggers=trigger_sentences)


@bp.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm(current_user.username)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        db.session.commit()
        flash('Your changes have been saved.')
        return redirect(url_for('main.edit_profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me
    return render_template('edit_profile.html', title='Edit Profile', form=form)


def parse_action(action, value=None, keyword=None):
    """
    Store the action made by the user, but require manual commit after.
    """
    current_user_context = UserContext.get_user_context(current_user.id, current_user.working_context_id)
    annotation_action = AnnotationAction(
        completed_by=current_user_context.id,
        value=value,
        keyword=keyword,
        action=action,
        shown_motivation=session['current_motivation_id']
    )
    db.session.add(annotation_action)

def csd_parse_action(action, value=None, keyword=None, annotate_vc=False):
    """
    Store the action made by the user during Consolidation, but require manual commit after.

    If annotate_vc is set to True, register the value couple as annotated.
    """
    current_user_context = UserContext.get_user_context(current_user.id, current_user.working_context_id)
    current_couple = session['current_shown_couple_id'] if 'current_shown_couple_id' in session else None

    if annotate_vc and current_couple is not None:
        vc_id = ShownValueCouple.query.get(current_couple).value_couple_id
        vc = ValueCouple.query.get(vc_id)
        if vc is not None:
            vc.annotated = True

    annotation_action = ConsolidationAction(
        group_id=current_user_context.group_id,
        context_id=current_user.working_context_id,
        value=value,
        keyword=keyword,
        csd_action=action,
        shown_couple=current_couple
    )
    db.session.add(annotation_action)


@bp.route('/add_value')
@login_required
def add_value():
    value_name = request.args.get('value', 'default', type=str)
    changed = False
    suggestions = {}
    user_context_id = UserContext.get_user_context(current_user.id, current_user.working_context_id).id
    if len(value_name) > 0:
        # First commit the value
        v = Value(name=value_name, submitted_by=user_context_id)
        db.session.add(v)
        db.session.commit()
        # Now value has an id, also commit the action
        parse_action(Action.ADD_VALUE, value=v.id)
        explorator.compute_center(v.id, Value, Keyword)
        db.session.commit()
        suggestions = {
            'text': ",".join(explorator.get_word_expansions(value_name)),
            'id': v.id
        }
        changed = True

    vvs = Value.query.filter_by(submitted_by=user_context_id).all()
    values = [value.as_dict() for value in vvs]
    return jsonify(result=values, changed=changed, suggestions=suggestions)


@bp.route('/remove_value')
@login_required
def remove_value():
    value_id = request.args.get('value_id', 0, type=int)
    if value_id > 0:
        # Only allow values to be deleted that were originally submitted by
        # the same user, and also remove all associated keywords
        user_context_id = UserContext.get_user_context(current_user.id, current_user.working_context_id).id
        v = Value.query.filter_by(id=value_id, submitted_by=user_context_id)
        ks = Keyword.query.filter_by(submitted_by=user_context_id, value=value_id)
        parse_action(Action.REMOVE_VALUE, value=value_id)
        ks.delete()
        v.delete()
        db.session.commit()
    return jsonify(success=True)


@bp.route('/add_keyword')
@login_required
def add_keyword():
    keyword_name = request.args.get('keyword_name', '', type=str)
    value_id = request.args.get('value_id', 0, type=int)
    changed = False
    suggestions = {}
    user_context_id = UserContext.get_user_context(current_user.id, current_user.working_context_id).id
    if len(keyword_name) > 0 and value_id > 0:
        # First add and commit the new keyword to get an id
        k = Keyword(name=keyword_name, submitted_by=user_context_id, value=value_id)
        db.session.add(k)
        db.session.commit()
        # Now also commit the action
        parse_action(Action.ADD_KEYWORD, value=value_id, keyword=k.id)
        explorator.compute_center(value_id, Value, Keyword)
        db.session.commit()
        suggestions = {
            'text': ",".join(explorator.get_word_expansions(keyword_name)),
            'id': value_id
        }
        changed = True

    kks = Keyword.query.filter_by(submitted_by=user_context_id, value=value_id).all()
    keywords = [keyword.as_dict() for keyword in kks]
    return jsonify(result=keywords, changed=changed, suggestions=suggestions)


@bp.route('/remove_keyword')
@login_required
def remove_keyword():
    keyword_id = request.args.get('keyword_id', 0, type=int)
    user_context_id = UserContext.get_user_context(current_user.id, current_user.working_context_id).id
    if keyword_id > 0:
        # Only allow keywords to be deleted that were originally submitted by
        # the same user
        k = Keyword.query.filter_by(id=keyword_id, submitted_by=user_context_id)
        keyword_item = k.first()
        if keyword_item is not None:
            parse_action(Action.REMOVE_KEYWORD, value=keyword_item.value, keyword=keyword_item.id)
            k.delete()
        explorator.compute_center(keyword_item.value, Value, Keyword)
        db.session.commit()
    return jsonify(success=True)

@bp.route('/skip_motivation')
@login_required
def skip_motivation():
    skip_reason_id = request.args.get('skip_reason', 0, type=int)
    if skip_reason_id > 0:
        reason_to_action = [
            Action.SKIP_MOTIVATION_UNCOMPREHENSIBLE,
            Action.SKIP_MOTIVATION_NO_VALUE,
            Action.SKIP_MOTIVATION_ALREADY_PRESENT
        ]
        # Check if there are (somehow) any actions for the current motivation by
        # this user. If there are, it is not possible to skip
        prev_actions = AnnotationAction.query.filter_by(completed_by=current_user.id, shown_motivation=session['current_motivation_id']).all()
        if len(prev_actions) == 0:
            parse_action(reason_to_action[skip_reason_id - 1])
        else:
            current_app.logger.warning(f"User {current_user.id} is skipping motivation {session['current_motivation_id']}, but there are already actions: {prev_actions}")
        db.session.commit()
    return jsonify(success=True)

@bp.route('/get_history')
@login_required
def get_history():
    hist = explorator.get_history(UserContext, UserContextMotivation, Motivation, Action, AnnotationAction)
    return jsonify(history=hist)


@bp.route('/preload_next')
@login_required
def preload_next_motivation():
    value_id = request.args.get('value_id', 0, type=int)
    if value_id > 0:
        # Get motivation similar to the value {value_id}
        session['similar_value_id'] = value_id
    return jsonify(success=True)


# --- Consolidation

@bp.route('/start_consolidation')
@login_required
def start_consolidation():
    # Create consolidation values.
    expl_values, cons_values = consolidator.make_consolidation_values(UserContext, Value, ConsolidationValue)
    for value in cons_values:
        db.session.add(value)
    db.session.commit()

    # Create ValueConsolidationValue table.
    for exp_value, cons_value in zip(expl_values, cons_values):
        db.session.add(ValueConsolidationValue(value_id=exp_value.id, consolidation_value_id=cons_value.id))
    db.session.commit()

    # Create consolidation keywords.
    consolidation_keywords = consolidator.make_consolidation_keywords(UserContext, ConsolidationValue, Keyword, ConsolidationKeyword)
    for keyword in consolidation_keywords:
        db.session.add(keyword)
    db.session.commit()

    # Create value couples.
    value_couples = consolidator.make_value_couples(ValueCouple, cons_values)
    for couple in value_couples:
        db.session.add(couple)

    # Flag the consolidation as started
    uc = UserContext.get_user_context(current_user.id, current_user.working_context_id)
    uc.consolidation_started = True
    db.session.commit()
    return jsonify(success=True)


def lookup_author(value_id):
    vcvs = ValueConsolidationValue.query.filter_by(consolidation_value_id=value_id).all()
    if len(vcvs) == 1:
        author_uc_id = Value.query.get(vcvs[0].value_id).submitted_by
        author_id = UserContext.query.get(author_uc_id).user_id
        author_name = User.query.get(author_id).username
        return "in Exploration by: " + author_name
    else:
        return "in Consolidation by: group"

@bp.route('/csd_get_values')
@login_required
def csd_get_values():
    group_id = UserContext.get_user_context(current_user.id, current_user.working_context_id).group_id
    vvs = ConsolidationValue.query.filter_by(group_id=group_id, context_id=current_user.working_context_id).all()
    values = []
    for value in vvs:
        value_dict = value.as_dict()
        # Lookup if the value has an original author from Exploration phase
        if 'original_author' not in value_dict:
            value_dict['original_author'] = lookup_author(value.id)
        values.append(value_dict)
    return jsonify(values=values)

@bp.route('/csd_add_value')
@login_required
def csd_add_value():
    value_name = request.args.get('value', '', type=str)
    if len(value_name) > 0:
        user_context = UserContext.get_user_context(current_user.id, current_user.working_context_id)
        v = ConsolidationValue(name=value_name, group_id=user_context.group_id, context_id=current_user.working_context_id)
        db.session.add(v)
        db.session.commit()

        # Now that the value has an id, we can compute the center.
        consolidator.compute_center(v.id, ConsolidationValue, ConsolidationKeyword)
        db.session.commit()

        # Make new value couples with the new consolidation value.
        value_couples = consolidator.make_new_value_couples(v.id, UserContext, ValueCouple, ConsolidationValue)
        session['next_couple_id'] = None
        for couple in value_couples:
            db.session.add(couple)
        db.session.commit()

        csd_parse_action(CSDAction.ADD_VALUE, value=v.id)
        db.session.commit()
        value_dict = v.as_dict()
        # Lookup if the value has an original author from Exploration phase
        if 'original_author' not in value_dict:
            value_dict['original_author'] = lookup_author(v.id)

        return jsonify(success=True, value_obj=value_dict)
    else:
        return jsonify(success=False, value_obj=None)

@bp.route('/csd_remove_value')
@login_required
def csd_remove_value():
    value_id = request.args.get('value_id', 0, type=int)
    success = False
    if value_id > 0:
        user_context = UserContext.get_user_context(current_user.id, current_user.working_context_id)
        v = ConsolidationValue.query.filter_by(id=value_id, group_id=user_context.group_id)
        ks = ConsolidationKeyword.query.filter_by(group_id=user_context.group_id, value=value_id)

        csd_parse_action(CSDAction.REMOVE_VALUE, value=value_id)
        # Delete all couples containing the deleted value.
        consolidator.delete_value_couples(ValueCouple, value_id)
        session['next_couple_id'] = None
        # Delete all connections to the original Value
        vcvs = ValueConsolidationValue.query.filter_by(consolidation_value_id=value_id)
        ks.delete()
        v.delete()
        vcvs.delete()
        db.session.commit()

        success = True
    return jsonify(success=success)

@bp.route('/csd_get_keywords')
@login_required
def csd_get_keywords():
    value_id = request.args.get('value_id', 0, type=int)
    keywords = []
    if value_id > 0:
        group_id = UserContext.get_user_context(current_user.id, current_user.working_context_id).group_id
        kks = ConsolidationKeyword.query.filter_by(group_id=group_id, value=value_id).all()
        keywords = [keyword.as_dict() for keyword in kks]
    return jsonify(keywords=keywords)

@bp.route('/csd_add_keyword')
@login_required
def csd_add_keyword():
    keyword_name = request.args.get('keyword_name', '', type=str)
    value_id = request.args.get('value_id', 0, type=int)
    if len(keyword_name) > 0 and value_id > 0:
        group_id = UserContext.get_user_context(current_user.id, current_user.working_context_id).group_id
        k = ConsolidationKeyword(name=keyword_name, group_id=group_id, value=value_id, context_id=current_user.working_context_id)
        db.session.add(k)
        db.session.commit()

        # Update value and value couples containing the value.
        consolidator.update_value_couples(value_id, ValueCouple, ConsolidationValue, ConsolidationKeyword)
        session['next_couple_id'] = None
        db.session.commit()

        csd_parse_action(CSDAction.ADD_KEYWORD, value=value_id, keyword=k.id)
        db.session.commit()

        return jsonify(success=True, keyword_obj=k.as_dict())
    else:
        return jsonify(success=False, keyword_obj=None)


@bp.route('/csd_remove_keyword')
@login_required
def csd_remove_keyword():
    keyword_id = request.args.get('keyword_id', 0, type=int)
    success = False
    if keyword_id > 0:
        group_id = UserContext.get_user_context(current_user.id, current_user.working_context_id).group_id
        k = ConsolidationKeyword.query.filter_by(id=keyword_id, group_id=group_id)
        keyword_item = k.first()
        if keyword_item is not None:
            value_id = keyword_item.value
            csd_parse_action(CSDAction.REMOVE_KEYWORD, value=value_id, keyword=keyword_item.id)
            k.delete()
            db.session.commit()

            # Update value and value couples containing the value.
            consolidator.update_value_couples(value_id, ValueCouple, ConsolidationValue, ConsolidationKeyword)
            session['next_couple_id'] = None
            db.session.commit()
            success = True

    return jsonify(success=success)


@bp.route('/csd_merge_pair')
@login_required
def csd_merge_pair():
    value_id_0 = request.args.get('value_id_0', 0, type=int)
    value_id_1 = request.args.get('value_id_1', 0, type=int)
    merged_value_name = request.args.get('merged_value_name', '', type=str)
    if value_id_0 > 0 and value_id_1 > 0 and len(merged_value_name) > 0:
        user_context = UserContext.get_user_context(current_user.id, current_user.working_context_id)
        v0 = ConsolidationValue.query.filter_by(id=value_id_0, group_id=user_context.group_id)
        v1 = ConsolidationValue.query.filter_by(id=value_id_1, group_id=user_context.group_id)
        # Add merged value
        merged_v = ConsolidationValue(name=merged_value_name, group_id=user_context.group_id, context_id=current_user.working_context_id)
        db.session.add(merged_v)
        db.session.commit()
        k0 = ConsolidationKeyword.query.filter_by(value=v0.first().id)
        k1 = ConsolidationKeyword.query.filter_by(value=v1.first().id)
        keywords = k0.all() + k1.all()
        # Add all keywords
        merged_keywords = []
        for keyword in keywords:
            k = ConsolidationKeyword(name=keyword.name, group_id=user_context.group_id, value=merged_v.id, context_id=current_user.working_context_id)
            db.session.add(k)
            merged_keywords.append(k)

        # Delete all couples containing the deleted values.
        consolidator.delete_value_couples(ValueCouple, v0.first().id)
        consolidator.delete_value_couples(ValueCouple, v1.first().id)
        session['next_couple_id'] = None

        # Delete values and keywords.
        v0.delete()
        v1.delete()
        k0.delete()
        k1.delete()
        db.session.commit()

        # Create new ValueConsolidationValue tables.
        source_vcvs = ValueConsolidationValue.query.filter(
                ValueConsolidationValue.consolidation_value_id.in_([value_id_0, value_id_1]))
        source_ids = [source_vcv.value_id for source_vcv in source_vcvs.all()]
        for value_id in source_ids:
            db.session.add(ValueConsolidationValue(value_id=value_id, consolidation_value_id=merged_v.id))
        ValueConsolidationValue.query.filter_by(consolidation_value_id=value_id_0).delete()
        ValueConsolidationValue.query.filter_by(consolidation_value_id=value_id_1).delete()
        db.session.commit()

        # Now that the new merged value has an id, we can compute its center.
        consolidator.compute_center(merged_v.id, ConsolidationValue, ConsolidationKeyword)
        db.session.commit()

        # Make new value couples with the new consolidation value.
        value_couples = consolidator.make_new_value_couples(merged_v.id, UserContext, ValueCouple, ConsolidationValue)
        for couple in value_couples:
            db.session.add(couple)
        db.session.commit()

        csd_parse_action(CSDAction.MERGE_COUPLE, value=merged_v.id, annotate_vc=True)
        db.session.commit()

        return jsonify(success=True, merged_value=merged_v.as_dict(), merged_keywords=[k.as_dict() for k in merged_keywords])
    else:
        return jsonify(success=False)


@bp.route('/csd_skip_pair')
@login_required
def csd_skip_pair():
    csd_parse_action(CSDAction.SKIP_COUPLE, annotate_vc=True)
    db.session.commit()
    return jsonify(success=True)


@bp.route('/csd_get_history')
@login_required
def csd_get_history():
    hist = consolidator.get_history(UserContext, CSDAction, ConsolidationAction, ShownValueCouple)
    return jsonify(success=True, history=hist)


@bp.route('/csd_preload_next_couple')
@login_required
def csd_preload_next_couple():
    value_id_0 = request.args.get('value_id_0', 0, type=int)
    value_id_1 = request.args.get('value_id_1', 0, type=int)
    if value_id_0 > 0 and value_id_1 > 0 and value_id_1 != value_id_0:
        next_value_couple = ValueCouple.query.filter(
                ((ValueCouple.value_id_0 == value_id_0) & (ValueCouple.value_id_1 == value_id_1)) |
                ((ValueCouple.value_id_0 == value_id_1) & (ValueCouple.value_id_1 == value_id_0)))
        next_value_couple = next_value_couple.filter_by(already_shown=False).all()
        if len(next_value_couple) == 1:
            session['next_couple_id'] = next_value_couple[0].id
            return jsonify(success=True)
    return jsonify(success=False)

@bp.route('/get_defining_goal')
@login_required
def get_defining_goal():
    value_id = request.args.get('value_id', 0, type=int)
    if value_id > 0:
        dg = ConsolidationValue.query.get(value_id).defining_goal
        return jsonify(success=True, defining_goal=dg)
    return jsonify(success=False)


@bp.route('/add_defining_goal')
@login_required
def add_defining_goal():
    defining_goal = request.args.get('defining_goal', "", type=str)
    value_id = request.args.get('value_id', 0, type=int)
    if len(defining_goal) > 0 and value_id > 0:
        ConsolidationValue.query.get(value_id).defining_goal = defining_goal
        db.session.commit()
        return jsonify(success=True)
    return jsonify(success=False)

