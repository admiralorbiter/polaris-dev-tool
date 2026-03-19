"""Feature CRUD routes — feature lifecycle tracking."""

from datetime import date, timedelta

from flask import Blueprint, render_template, request, redirect, url_for

from models import db, Feature, ManagedDoc

features_bp = Blueprint("features", __name__)

# Status symbol mapping (matches VMS development_status_tracker.md)
STATUS_SYMBOLS = {
    "implemented": "✅",
    "partial": "🔧",
    "pending": "📋",
    "future": "🔮",
    "na": "➖",
}


def _mark_status_tracker_dirty(project="vms"):
    """Mark the status_tracker ManagedDoc as dirty after Feature changes."""
    doc = ManagedDoc.query.filter_by(project=project, doc_key="status_tracker").first()
    if doc:
        doc.is_dirty = True


@features_bp.route("/features")
def feature_list():
    """Feature lifecycle — filterable list of all features."""
    # Read filters
    domain = request.args.get("domain", "")
    status = request.args.get("status", "")
    impl_status = request.args.get("impl_status", "")
    review_filter = request.args.get("review", "")

    query = Feature.query

    if domain:
        query = query.filter_by(domain=domain)
    if status:
        query = query.filter_by(status=status)
    if impl_status:
        query = query.filter_by(implementation_status=impl_status)

    # Review queue filter: show features due within 14 days or overdue
    if review_filter == "due":
        cutoff = date.today() + timedelta(days=14)
        query = query.filter(
            Feature.next_review.isnot(None),
            Feature.next_review <= cutoff,
        )

    features = query.order_by(Feature.domain, Feature.requirement_id).all()

    # Unique values for filter dropdowns
    all_domains = (
        db.session.query(Feature.domain)
        .filter(Feature.domain.isnot(None))
        .distinct()
        .order_by(Feature.domain)
        .all()
    )
    all_statuses = (
        db.session.query(Feature.status).distinct().order_by(Feature.status).all()
    )
    all_impl_statuses = (
        db.session.query(Feature.implementation_status)
        .distinct()
        .order_by(Feature.implementation_status)
        .all()
    )

    # Compute review countdowns
    today = date.today()
    for f in features:
        if f.next_review:
            delta = (f.next_review - today).days
            f._review_days = delta
        else:
            f._review_days = None

    return render_template(
        "features.html",
        features=features,
        filters={
            "domain": domain,
            "status": status,
            "impl_status": impl_status,
        },
        domains=[d[0] for d in all_domains if d[0]],
        statuses=[s[0] for s in all_statuses if s[0]],
        impl_statuses=[i[0] for i in all_impl_statuses if i[0]],
        status_symbols=STATUS_SYMBOLS,
    )


@features_bp.route("/features/new", methods=["GET", "POST"])
def feature_create():
    """Create a new feature."""
    if request.method == "POST":
        feature = Feature(
            project=request.form.get("project", "vms"),
            name=request.form["name"],
            domain=request.form.get("domain") or None,
            status=request.form.get("status", "requested"),
            implementation_status=request.form.get("implementation_status", "pending"),
            notes=request.form.get("notes") or None,
        )

        req_id = request.form.get("requirement_id", "").strip()
        if req_id:
            feature.requirement_id = req_id

        db.session.add(feature)
        _mark_status_tracker_dirty(feature.project)
        db.session.commit()
        return redirect(url_for("features.feature_detail", feature_id=feature.id))

    return render_template(
        "feature_form.html",
        feature=None,
        mode="create",
        status_symbols=STATUS_SYMBOLS,
    )


@features_bp.route("/features/<int:feature_id>")
def feature_detail(feature_id):
    """View a single feature."""
    feature = Feature.query.get_or_404(feature_id)

    # Compute review countdown
    today = date.today()
    review_days = None
    if feature.next_review:
        review_days = (feature.next_review - today).days

    return render_template(
        "feature_detail.html",
        feature=feature,
        review_days=review_days,
        status_symbols=STATUS_SYMBOLS,
    )


@features_bp.route("/features/<int:feature_id>/edit", methods=["GET", "POST"])
def feature_edit(feature_id):
    """Edit a feature."""
    feature = Feature.query.get_or_404(feature_id)

    if request.method == "POST":
        feature.name = request.form["name"]
        feature.domain = request.form.get("domain") or None
        feature.status = request.form.get("status", feature.status)
        feature.implementation_status = request.form.get(
            "implementation_status", feature.implementation_status
        )
        feature.notes = request.form.get("notes") or None

        req_id = request.form.get("requirement_id", "").strip()
        if req_id:
            feature.requirement_id = req_id

        _mark_status_tracker_dirty(feature.project)
        db.session.commit()
        return redirect(url_for("features.feature_detail", feature_id=feature.id))

    return render_template(
        "feature_form.html",
        feature=feature,
        mode="edit",
        status_symbols=STATUS_SYMBOLS,
    )


@features_bp.route("/features/<int:feature_id>/ship", methods=["POST"])
def feature_ship(feature_id):
    """Mark a feature as shipped (auto-sets 90-day review date)."""
    feature = Feature.query.get_or_404(feature_id)
    feature.ship()
    _mark_status_tracker_dirty(feature.project)
    db.session.commit()
    return redirect(url_for("features.feature_detail", feature_id=feature.id))
