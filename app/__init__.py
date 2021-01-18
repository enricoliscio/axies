from app.utils.backbone.explorator import Explorator
from app.utils.backbone.consolidator import Consolidator
from app.utils.backbone.utils import get_embedding_models

from flask import Flask
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
import logging
from logging.handlers import RotatingFileHandler
import os
from flask_bootstrap import Bootstrap
from flask_wtf.csrf import CSRFProtect


db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
mail = Mail()
bootstrap = Bootstrap()

# Load utils.backbone
expansion_model, embedding_model = get_embedding_models(lang='en')
explorator_config = {
    'corona-vectors': './static/models/corona_vectors.npy',
    'swf-vectors': './static/models/swf_vectors.npy',
    'corona-context': 'PVE: COVID Exit',
    'swf-context': 'PVE: SWF',
}
explorator = Explorator(embedding_model, expansion_model, explorator_config)
consolidator = Consolidator(embedding_model)


def create_app(config_class=Config):
    app = Flask(
        __name__,
        static_folder=os.path.abspath('static')
    )
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    bootstrap.init_app(app)

    csrf = CSRFProtect()
    csrf.init_app(app)

    from app.errors import bp as errors_bp
    app.register_blueprint(errors_bp)

    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    if not app.debug and not app.testing:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler('logs/axies.log', maxBytes=5 * 1024 ** 2, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s '
            '[in %(pathname)s:%(lineno)d]'))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)

        app.logger.setLevel(logging.INFO)
        app.logger.info('Axies startup')

    return app


from app import models
