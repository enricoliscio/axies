import enum

from app import db, login_manager
from werkzeug.security import generate_password_hash, check_password_hash
from flask import current_app
from flask_login import UserMixin
import jwt
from time import time


class UserContextMotivation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_context_id = db.Column(db.Integer, db.ForeignKey('user_context.id'))
    motivation_id = db.Column(db.Integer, db.ForeignKey('motivation.id'))
    fft_distance = db.Column(db.Float)
    similarity_distance = db.Column(db.Float)


class UserContext(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    context_id = db.Column(db.Integer, db.ForeignKey('context.id'))
    group_id = db.Column(db.Integer)
    can_explore = db.Column(db.Boolean, default=False)
    can_consolidate = db.Column(db.Boolean, default=False)
    consolidation_started = db.Column(db.Boolean, default=False)
    seen_motivations = db.relationship('UserContextMotivation', backref='motivation',
                                    primaryjoin=(id == UserContextMotivation.user_context_id), lazy='dynamic')

    def __repr__(self):
        return '<UserContextPrivilege {}: {}>'.format(self.user_id, self.context_id)

    @staticmethod
    def get_user_context(user_id, context_id):
        return UserContext.query.filter(UserContext.user_id == user_id).filter(
            UserContext.context_id == context_id).first()


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    consent = db.Column(db.Boolean)
    contexts = db.relationship('UserContext', backref='context',
                               primaryjoin=(id == UserContext.user_id), lazy='dynamic')
    working_context_id = db.Column(db.Integer, db.ForeignKey('context.id'))

    def __repr__(self):
        return '<User {}>'.format(self.username)

    @login_manager.user_loader
    def load_user(id):
        return User.query.get(int(id))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_reset_password_token(self, expires_in=600):
        return jwt.encode(
            {'reset_password': self.id, 'exp': time() + expires_in},
            current_app.config['SECRET_KEY'], algorithm='HS256').decode('utf-8')

    @staticmethod
    def verify_reset_password_token(token):
        try:
            id = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])['reset_password']
        except:
            return
        return User.query.get(id)

    def contexts_assigned(self):
        return Context.query.join(UserContext, Context.id == UserContext.context_id).filter(
            self.id == UserContext.user_id).add_columns(Context.id, Context.context_name_en, Context.context_name_nl,
                                                        UserContext.id.label("user_context_id"), UserContext.can_explore,
                                                        UserContext.can_consolidate)

    def get_working_context(self):
        if self.working_context_id is None:
            return None
        else:
            return Context.load_context(self.working_context_id)


class Context(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    context_name_en = db.Column(db.String(128), index=True, unique=True)
    context_name_nl = db.Column(db.String(128), index=True, unique=True)
    choices = db.relationship('Choice', backref='context', lazy='dynamic')
    users = db.relationship('UserContext', backref='user', primaryjoin=(id == UserContext.context_id), lazy='dynamic')

    def __repr__(self):
        return '<Context {}>'.format(self.context_name_en)

    def load_context(id):
        return Context.query.get(int(id))


class Choice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    choice_order = db.Column(db.Integer)
    choice_name_en = db.Column(db.String(256))
    choice_name_nl = db.Column(db.String(256))
    context_id = db.Column(db.Integer, db.ForeignKey('context.id'))
    motivations = db.relationship('Motivation', backref='choice', lazy='dynamic')

    def __repr__(self):
        return '<Choice {}>'.format(self.choice_name_en)


class Motivation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pve_idx = db.Column(db.Integer)  # Index of motivation inside pve dataset, used as index for vectors
    motivation_en = db.Column(db.String(6000))
    motivation_nl = db.Column(db.String(6000))
    choice_id = db.Column(db.Integer, db.ForeignKey('choice.id'))
    user_contexts = db.relationship('UserContextMotivation', backref='user_context',
                                    primaryjoin=(id == UserContextMotivation.motivation_id), lazy='dynamic')

    def __repr__(self):
        return '<Motivation {}>'.format(self.motivation_en)


class Value(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128))
    submitted_by = db.Column(db.Integer, db.ForeignKey('user_context.id'))
    center = db.Column(db.String(128))
    shown_similar = db.Column(db.Integer, default=0)

    def __repr__(self):
        return '<Value {}>'.format(self.name)

    def as_dict(self):
        return {'name': self.name, 'submitted_by': self.submitted_by, 'id': self.id}


class Keyword(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128))
    submitted_by = db.Column(db.Integer, db.ForeignKey('user_context.id'))
    value = db.Column(db.Integer, db.ForeignKey('value.id'))

    def __repr__(self):
        return '<Keyword {} for Value {}>'.format(self.name, self.value)

    def as_dict(self):
        return {'name': self.name, 'submitted_by': self.submitted_by, 'value': self.value, 'id': self.id}


class Action(enum.Enum):
    # WARNING: adding to this enum requires you to clear out the database and
    # init a new one, preventing migrations like normal.
    ADD_VALUE = 0
    REMOVE_VALUE = 1
    ADD_KEYWORD = 2
    REMOVE_KEYWORD = 3
    SKIP_MOTIVATION_UNCOMPREHENSIBLE = 4
    SKIP_MOTIVATION_NO_VALUE = 5
    SKIP_MOTIVATION_ALREADY_PRESENT = 6


class AnnotationAction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    completed_by = db.Column(db.Integer, db.ForeignKey(UserContext.id))
    shown_motivation = db.Column(db.Integer, db.ForeignKey('motivation.id'))
    created_on = db.Column(db.DateTime, server_default=db.func.now())
    value = db.Column(db.Integer, db.ForeignKey('value.id'))
    keyword = db.Column(db.Integer, db.ForeignKey('keyword.id'))
    action = db.Column(db.Enum(Action))

    def __repr__(self):
        if self.keyword is not None:
            return f'<User {self.completed_by} Motivation {self.shown_motivation} Action {self.action} Value {self.value} Keyword {self.keyword}>'
        elif self.value is not None:
            return f'<User {self.completed_by} Motivation {self.shown_motivation} Action {self.action} Value {self.value}>'
        else:
            return f'<User {self.completed_by} Motivation {self.shown_motivation} Action {self.action}'

# -- Consolidation Models
class ValueConsolidationValue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    value_id = db.Column(db.Integer, db.ForeignKey('value.id'))
    consolidation_value_id = db.Column(db.Integer, db.ForeignKey('consolidation_value.id'))

    def as_dict(self):
        return {'value_id': self.value_id, 'consolidation_value_id': self.consolidation_value_id, 'id': self.id}


class ConsolidationValue(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(128))
    group_id = db.Column(db.Integer)
    context_id = db.Column(db.Integer, db.ForeignKey('context.id'))
    center = db.Column(db.String(128))
    source_values = db.relationship('ValueConsolidationValue', backref='value',
                                    primaryjoin=(id == ValueConsolidationValue.consolidation_value_id), lazy='dynamic')
    defining_goal = db.Column(db.String(2048))

    def __repr__(self):
        return '<ConsolidationValue {}>'.format(self.name)

    def as_dict(self):
        return {'name': self.name, 'group_id': self.group_id, 'id': self.id}


class ConsolidationKeyword(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128))
    group_id = db.Column(db.Integer)
    context_id = db.Column(db.Integer, db.ForeignKey('context.id'))
    value = db.Column(db.Integer, db.ForeignKey(ConsolidationValue.id))

    def __repr__(self):
        return '<ConsolidationKeyword {} for Value {}>'.format(self.name, self.value)

    def as_dict(self):
        return {'name': self.name, 'group_id': self.group_id, 'value': self.value, 'id': self.id}


class ShownValueCouple(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer)
    value_couple_id = db.Column(db.Integer, db.ForeignKey('value_couple.id'))
    distance = db.Column(db.Float)


class ValueCouple(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    value_id_0 = db.Column(db.Integer, db.ForeignKey('consolidation_value.id'))
    value_id_1 = db.Column(db.Integer, db.ForeignKey('consolidation_value.id'))
    distance = db.Column(db.Float)
    already_shown = db.Column(db.Boolean, default=False)
    annotated = db.Column(db.Boolean, default=False)

    @staticmethod
    def from_context_group(context_id, group_id):
        values = ConsolidationValue.query.filter_by(context_id=context_id, group_id=group_id)
        value_ids = [value.id for value in values.all()]
        return ValueCouple.query.filter(
                (ValueCouple.value_id_0.in_(value_ids)) | (ValueCouple.value_id_1.in_(value_ids)))

    @staticmethod
    def containing_value(value_id):
        return ValueCouple.query.filter(
                (ValueCouple.value_id_0 == value_id) | (ValueCouple.value_id_1 == value_id))

class CSDAction(enum.Enum):
    # WARNING: adding to this enum requires you to clear out the database and
    # init a new one, preventing migrations like normal.
    ADD_VALUE = 0
    REMOVE_VALUE = 1
    ADD_KEYWORD = 2
    REMOVE_KEYWORD = 3
    SKIP_COUPLE = 4
    MERGE_COUPLE = 5


class ConsolidationAction(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    group_id = db.Column(db.Integer)
    context_id = db.Column(db.Integer, db.ForeignKey('context.id'))
    shown_couple = db.Column(db.Integer, db.ForeignKey(ShownValueCouple.id))
    created_on = db.Column(db.DateTime, server_default=db.func.now())
    value = db.Column(db.Integer, db.ForeignKey('consolidation_value.id'))
    keyword = db.Column(db.Integer, db.ForeignKey('consolidation_keyword.id'))
    csd_action = db.Column(db.Enum(CSDAction))

    def __repr__(self):
        if self.keyword is not None:
            return f'<CSD User {self.completed_by} Couple {self.shown_couple} Action {self.csd_action} Value {self.value} Keyword {self.keyword}>'
        elif self.value is not None:
            return f'<CSD User {self.completed_by} Couple {self.shown_couple} Action {self.csd_action} Value {self.value}>'
        else:
            if self.csd_action == CSDAction.MERGE_COUPLE:
                return f'<CSD User {self.completed_by} Couple {self.shown_couple} Action {self.csd_action} MergedValue {self.value}'
            else:
                return f'<CSD User {self.completed_by} Couple {self.shown_couple} Action {self.csd_action}'