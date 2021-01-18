from app import create_app, db, explorator, consolidator
from app.models import *
from app.utils import cli

app = create_app()
cli.register(app)


@app.shell_context_processor
def make_shell_context():
    return {
        'db': db,
        'User': User,
        'UserContext': UserContext,
        'Context': Context,
        'Value': Value,
        'Motivation': Motivation,
        'Keyword': Keyword,
        'AnnotationAction': AnnotationAction,
        'ConsolidationAction': ConsolidationAction,
        'ConsolidationValue': ConsolidationValue,
        'ConsolidationKeyword': ConsolidationKeyword,
        'explorator': explorator,
        'consolidator': consolidator
    }
