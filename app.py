"""Flask application factory for Polaris DevTools."""

import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask
from sqlalchemy import event
from sqlalchemy.engine import Engine

from config import config_map
from models import db


def create_app(config_name=None):
    """Create and configure the Flask application.

    Args:
        config_name: Config key ('development', 'testing', 'production').
                     Defaults to FLASK_ENV or 'development'.
    """
    load_dotenv()

    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config_map.get(config_name, config_map["default"]))

    # Ensure instance directory exists for SQLite
    instance_dir = Path(__file__).parent / "instance"
    instance_dir.mkdir(exist_ok=True)

    # Initialize extensions
    db.init_app(app)

    # Register blueprints
    _register_blueprints(app)

    # Register template filters
    _register_filters(app)

    # Create tables (dev convenience)
    with app.app_context():
        db.create_all()

    return app


def _register_filters(app):
    """Register custom Jinja template filters."""
    import markdown as md_lib
    from markupsafe import Markup

    @app.template_filter("md")
    def markdown_filter(text):
        """Render markdown text to safe HTML."""
        if not text:
            return ""
        html = md_lib.markdown(
            text,
            extensions=["fenced_code", "tables", "nl2br"],
        )
        return Markup(html)


def _register_blueprints(app):
    """Register all Flask blueprints."""
    from routes.dashboard import dashboard_bp
    from routes.api import api_bp
    from routes.scans import scans_bp
    from routes.work_items import work_items_bp
    from routes.features import features_bp
    from routes.sessions import sessions_bp
    from routes.initiatives import initiatives_bp
    from routes.docs import docs_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(scans_bp)
    app.register_blueprint(work_items_bp)
    app.register_blueprint(features_bp)
    app.register_blueprint(sessions_bp)
    app.register_blueprint(initiatives_bp)
    app.register_blueprint(docs_bp)


# --- SQLite WAL mode ---


@event.listens_for(Engine, "connect")
def set_sqlite_wal(dbapi_connection, connection_record):
    """Enable WAL mode for SQLite connections.

    Prevents 'database is locked' errors when running CLI
    scans alongside the web dashboard.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# --- Entry point ---

if __name__ == "__main__":
    app = create_app()
    port = app.config.get("DEVTOOLS_PORT", 5001)
    print(f"\n  Polaris DevTools running on http://localhost:{port}\n")
    app.run(port=port, debug=True)
