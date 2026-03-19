"""Session history routes — view past briefings and receipts."""

import json

from flask import Blueprint, render_template

from models import SessionLog

sessions_bp = Blueprint("sessions", __name__)


@sessions_bp.route("/sessions")
def session_list():
    """List all sessions, most recent first."""
    sessions = SessionLog.query.order_by(SessionLog.started_at.desc()).limit(50).all()

    # Enrich with file counts
    for s in sessions:
        s._file_count = 0
        if s.files_changed:
            try:
                s._file_count = len(json.loads(s.files_changed))
            except (json.JSONDecodeError, TypeError):
                pass

    return render_template("sessions.html", sessions=sessions)


@sessions_bp.route("/sessions/<int:session_id>")
def session_detail(session_id):
    """View a single session's briefing and receipt."""
    session = SessionLog.query.get_or_404(session_id)

    briefing = {}
    if session.briefing_json:
        try:
            briefing = json.loads(session.briefing_json)
        except (json.JSONDecodeError, TypeError):
            pass

    receipt = {}
    if session.receipt_json:
        try:
            receipt = json.loads(session.receipt_json)
        except (json.JSONDecodeError, TypeError):
            pass

    return render_template(
        "session_detail.html",
        session=session,
        briefing=briefing,
        receipt=receipt,
    )
