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

    # Create tables (dev convenience)
    with app.app_context():
        db.create_all()

    return app


def _register_blueprints(app):
    """Register all Flask blueprints."""
    from routes.dashboard import dashboard_bp
    from routes.api import api_bp
    from routes.scans import scans_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(scans_bp)


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
