"""Flask application factory."""

import os
from pathlib import Path
from flask import Flask


def create_app(test_config=None):
    app = Flask(__name__)
    root = Path(__file__).resolve().parent.parent

    # Application and database configuration
    app.config.update(
        # Local SQLite database
        DATABASE=os.environ.get(
            "SETWISE_DB",
            str(root / "setwise.db")
        ),

        # Choose between SQLite and DynamoDB
        DATABASE_BACKEND=os.environ.get(
            "DATABASE_BACKEND",
            "sqlite"
        ),

        # AWS DynamoDB configuration
        DYNAMODB_TABLE=os.environ.get(
            "DYNAMODB_TABLE",
            "n11761776-setwise-data"
        ),

        AWS_REGION=os.environ.get(
            "AWS_REGION",
            "ap-southeast-2"
        ),

        # Flask session security
        SECRET_KEY=os.environ.get(
            "SETWISE_SECRET_KEY",
            "local-demo-only-change-in-production"
        ),
    )

    # Override settings during testing
    if test_config:
        app.config.update(test_config)

    # Register Flask routes
    from app.routes.main import bp
    app.register_blueprint(bp)

    # Preserve endpoint names used by the HTML template
    app.add_url_rule(
        "/",
        endpoint="home",
        view_func=app.view_functions["main.home"]
    )

    app.add_url_rule(
        "/action",
        endpoint="action",
        view_func=app.view_functions["main.action"],
        methods=["POST"]
    )

    return app
