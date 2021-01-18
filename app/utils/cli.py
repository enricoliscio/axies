import csv
import yaml
import click

from pathlib import Path

from app import db
from app.models import User, UserContext, Context, Choice, Motivation, ConsolidationValue, ConsolidationKeyword


def parse_csv(filename, choices):
    """
    Parse a .csv file containing PVE data to insert in the database.
    """
    with open(filename, newline='') as motivations_file:
        reader = csv.DictReader(motivations_file)
        for i, row in enumerate(reader):
            db.session.add(Motivation(
                    pve_idx=i,
                    motivation_en=row['motivation_en'],
                    motivation_nl=row['motivation_nl'],
                    choice_id=choices[int(row['choice_id']) - 1].id
                ))

def parse_yaml(filename, choices):
    """
    Parse a .yaml file containing PVE data to insert in the database.
    """
    with open(filename, newline='') as motivations_file:
        motivation_dict = yaml.load(motivations_file, Loader=yaml.Loader)
        gen = zip(motivation_dict['english'], motivation_dict['dutch'], motivation_dict['project'])
        for i, item in enumerate(gen):
            db.session.add(Motivation(
                pve_idx=i,
                motivation_en=item[0],
                motivation_nl=item[1],
                choice_id=choices[int(item[2]) - 1].id
            ))

def load_file(filename, choices):
    """
    Load a file into the database, with either the .csv or the .yaml extension
    """
    suffix = Path(filename).suffix
    if suffix == '.csv':
        parse_csv(filename, choices)
    elif suffix == '.yaml':
        parse_yaml(filename, choices)
    else:
        raise ValueError('Unknown data insert file format, please use .yaml or .csv!')


def register(app):
    @app.cli.command()
    @click.argument('username')
    @click.argument('group_id')
    def assign_user(username, group_id):
        """Command for inserting a user in a group."""
        user = User.query.filter_by(username=username).first()
        user_contexts = UserContext.query.filter_by(user_id=user.id).all()
        for user_context in user_contexts:
           user_context.group_id = int(group_id)

        db.session.commit()


    @app.cli.command()
    @click.argument('destination')
    def dump_consolidation_values(destination):
        """Command for dumping consolidation values to YAML format."""
        import yaml
        data_dict = {'corona' : {}, 'swf' : {}}
        for context_id in range(1, 3):
            context_name = 'corona' if context_id == 1 else 'swf'
            for group_id in range(1, 3):
                data_dict[context_name][f'group_{group_id}'] = []
                values = ConsolidationValue.query.filter_by(group_id=group_id, context_id=context_id).all()
                for value in values:
                    value_dict = {}
                    value_dict['value_name']    = value.name
                    value_dict['defining_goal'] = value.defining_goal
                    keywords = ConsolidationKeyword.query.filter_by(
                            group_id=group_id, context_id=context_id, value=value.id).all()
                    value_dict['keywords'] = [keyword.name for keyword in keywords]
                    data_dict[context_name][f'group_{group_id}'].append(value_dict)

        with open(destination, 'w') as outfile:
            yaml.dump(data_dict, outfile, default_flow_style=False, sort_keys=False)


    @app.cli.group()
    def datainsert():
        """Commands about inserting static data to the database."""
        pass

    @datainsert.command()
    @click.argument('motivations_filename')
    def corona_pve(motivations_filename):
        """Insert static data to Context, Choice, and Motivation for the COVID Exit PVE."""
        context = Context(context_name_en='PVE: COVID Exit', context_name_nl='PVE: COVID Exit')
        db.session.add(context)
        db.session.commit()

        choices = [
            Choice(choice_order=1, choice_name_en='Nursing homes allow visitors again',
                   choice_name_nl='Verpleeg- en verzorgingstehuizen staan bezoek toe', context_id=context.id),
            Choice(choice_order=2, choice_name_en='Reopen companies (horeca and contact professions are still closed)',
                   choice_name_nl='Bedrijven anders dan horeca en contactberoepen gaan open', context_id=context.id),
            Choice(choice_order=3, choice_name_en='Workers in contact professions can work again',
                   choice_name_nl='Contactberoepen (o.a. kapper) gaan open', context_id=context.id),
            Choice(choice_order=4, choice_name_en='Young people do not need to maintain 1.5 meter distance among each others',
                   choice_name_nl='Jongeren hoeven onderling geen 1,5 meter afstand te bewaren', context_id=context.id),
            Choice(choice_order=5, choice_name_en='All restrictions are lifted for persons who are immune',
                   choice_name_nl='Opheffing beperkingen voor mensen met immuniteit', context_id=context.id),
            Choice(choice_order=6, choice_name_en='Restrictions are lifted in Friesland, Groningen and Drenthe',
                   choice_name_nl='Opheffen beperkingen Friesland, Groningen en Drenthe', context_id=context.id),
            Choice(choice_order=7, choice_name_en='Direct family members do not need to maintain 1.5 meter distance',
                   choice_name_nl='Geen 1,5 meter afstand voor directe familieleden ander huishouden', context_id=context.id),
            Choice(choice_order=8, choice_name_en='Horeca and entertainment re-open',
                   choice_name_nl='Horeca en entertainment gaan open', context_id=context.id),
        ]
        db.session.add_all(choices)
        db.session.commit()
        load_file(motivations_filename, choices)
        db.session.commit()

    @datainsert.command()
    @click.argument('motivations_filename')
    def swf_pve(motivations_filename):
        """Insert static data to Context, Choice, and Motivation for the SWF PVE."""
        context = Context(context_name_en='PVE: SWF', context_name_nl='PVE: SWF')
        db.session.add(context)
        db.session.commit()

        choices = [
            Choice(choice_order=1, choice_name_en='The municipality takes the lead and unburdens you',
                   choice_name_nl='De gemeente neemt de leiding en ontzorgt', context_id=context.id),
            Choice(choice_order=2, choice_name_en='Inhabitants do it themselves',
                   choice_name_nl='Inwoners doen het zelf', context_id=context.id),
            Choice(choice_order=3, choice_name_en='The market determines what is coming',
                   choice_name_nl='De markt bepaalt wat er komt', context_id=context.id),
            Choice(choice_order=4, choice_name_en='Large-scale energy generation will occur in a small number of places',
                   choice_name_nl='Op een klein aantal plekken komt grootschalige energieopwekking', context_id=context.id),
            Choice(choice_order=5, choice_name_en='Betting on storage',
                   choice_name_nl='Inzetten op opslag', context_id=context.id),
            Choice(choice_order=6, choice_name_en='Becoming an energy supplier in the Netherlands',
                   choice_name_nl='Energieleverancier van Nederland worden', context_id=context.id),
        ]
        db.session.add_all(choices)
        db.session.commit()
        load_file(motivations_filename, choices)
        db.session.commit()

    @datainsert.command()
    @click.argument('motivations_filename')
    def max_motivation_length(motivations_filename):
        """Print the max length of en and nl motivations."""
        with open(motivations_filename, newline='') as motivations_file:
            motivation_dict = yaml.load(motivations_file, Loader=yaml.Loader)
            gen = zip(motivation_dict['english'], motivation_dict['dutch'], motivation_dict['project'])
            max_length_en = 0
            max_length_nl = 0
            for item in gen:
                if len(item[0]) > max_length_en:
                    max_length_en = len(item[0])
                if len(item[1]) > max_length_nl:
                    max_length_nl = len(item[1])
            print('Max length EN: ' + str(max_length_en))
            print('Max length NL: ' + str(max_length_nl))
