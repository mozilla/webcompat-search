from flask import Flask

from webcompat_domains import views


def create_app(config_object='webcompat_domains.settings'):
    """Flask app factory

    :param config_object: The configuration object to use.
    """

    app = Flask('webcompat_domains')
    app.config.from_object(config_object)

    # Register app blueprints
    app.register_blueprint(views.blueprint)

    return app
