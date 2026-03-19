"""Doc management routes — list and detail views for managed docs."""

from flask import Blueprint, render_template
from models import ManagedDoc, ExportLog

docs_bp = Blueprint("docs", __name__)


@docs_bp.route("/docs")
def docs_list():
    """List all managed documents with status."""
    docs = ManagedDoc.query.order_by(ManagedDoc.tier, ManagedDoc.title).all()

    # Count dirty docs for the badge
    dirty_count = ManagedDoc.query.filter_by(is_dirty=True).count()

    return render_template("docs_list.html", docs=docs, dirty_count=dirty_count)


@docs_bp.route("/docs/<doc_key>")
def doc_detail(doc_key):
    """Detail view for a single managed doc."""
    doc = ManagedDoc.query.filter_by(doc_key=doc_key).first_or_404()

    # Get export history
    exports = (
        ExportLog.query.filter_by(project=doc.project, target=doc.doc_key)
        .order_by(ExportLog.exported_at.desc())
        .limit(10)
        .all()
    )

    # Slot info for hybrid docs
    slots = []
    if doc.tier == "hybrid" and doc.template_path:
        try:
            from pathlib import Path
            from exporters.hybrid_exporter import HybridDocExporter

            exporter = HybridDocExporter()
            template_text = Path(doc.template_path).read_text(encoding="utf-8")
            slots = exporter.extract_slots(template_text)
        except Exception:
            pass  # Template not found or unreadable — that's OK

    return render_template("doc_detail.html", doc=doc, exports=exports, slots=slots)
