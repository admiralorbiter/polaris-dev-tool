"""API routes — health check and data endpoints."""

from flask import Blueprint, jsonify

from models import db

api_bp = Blueprint("api", __name__)


@api_bp.route("/health")
def health():
    """Health check endpoint.

    Returns:
        JSON with status and basic system info.
    """
    try:
        # Verify DB connection
        db.session.execute(db.text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"

    return jsonify(
        {
            "status": "ok" if db_status == "ok" else "degraded",
            "database": db_status,
            "version": "0.1.0",
        }
    )
