from flask import Flask

from webcompat_search import commands, views


def create_app(config_object="webcompat_search.settings"):
    """Flask app factory

    :param config_object: The configuration object to use.
    """

    app = Flask("webcompat_search")
    app.config.from_object(config_object)

    # Register app blueprints
    app.register_blueprint(views.blueprint)

    # Register custom commands
    app.cli.add_command(commands.fetch_issues)
    app.cli.add_command(commands.last_updated)
    app.cli.add_command(commands.fetch_issues_by_range)
    app.cli.add_command(commands.reindex_prototype_dashboard_data)
    return app
