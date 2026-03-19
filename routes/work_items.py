"""WorkItem CRUD routes — work board for tech debt, bugs, and tasks."""

from flask import Blueprint, render_template, request, redirect, url_for

from models import db, WorkItem

work_items_bp = Blueprint("work_items", __name__)


@work_items_bp.route("/work-items")
def work_item_list():
    """Work board — filterable list of all work items."""
    # Read filter params
    status = request.args.get("status", "")
    priority = request.args.get("priority", "")
    category = request.args.get("category", "")
    show_archived = request.args.get("archived", "") == "1"

    # Base query
    query = WorkItem.query

    # Archive filter (default: hide archived)
    if not show_archived:
        query = query.filter_by(is_archived=False)

    # Apply filters
    if status:
        query = query.filter_by(status=status)
    if priority:
        query = query.filter_by(priority=priority)
    if category:
        query = query.filter_by(category=category)

    # Sort: in_progress first, then by priority rank, then source_id
    priority_order = db.case(
        {"critical": 0, "high": 1, "medium": 2, "low": 3},
        value=WorkItem.priority,
        else_=4,
    )
    status_order = db.case(
        {"in_progress": 0, "backlog": 1, "deferred": 2, "done": 3},
        value=WorkItem.status,
        else_=4,
    )
    items = query.order_by(status_order, priority_order, WorkItem.source_id).all()

    # Collect unique values for filter dropdowns
    all_statuses = (
        db.session.query(WorkItem.status).distinct().order_by(WorkItem.status).all()
    )
    all_priorities = (
        db.session.query(WorkItem.priority).distinct().order_by(WorkItem.priority).all()
    )
    all_categories = (
        db.session.query(WorkItem.category).distinct().order_by(WorkItem.category).all()
    )

    return render_template(
        "work_items.html",
        items=items,
        filters={
            "status": status,
            "priority": priority,
            "category": category,
            "archived": show_archived,
        },
        statuses=[s[0] for s in all_statuses if s[0]],
        priorities=[p[0] for p in all_priorities if p[0]],
        categories=[c[0] for c in all_categories if c[0]],
    )


@work_items_bp.route("/work-items/new", methods=["GET", "POST"])
def work_item_create():
    """Create a new work item.

    Supports pre-population via query params (for finding→WorkItem pipeline):
        ?from_finding=1&title=...&priority=...&category=...&notes=...&source_id=...
    """
    if request.method == "POST":
        item = WorkItem(
            project=request.form.get("project", "vms"),
            title=request.form["title"],
            category=request.form.get("category", "tech_debt"),
            priority=request.form.get("priority", "medium"),
            effort=request.form.get("effort") or None,
            status=request.form.get("status", "backlog"),
            notes=request.form.get("notes") or None,
        )

        # Optional source_id
        source_id = request.form.get("source_id", "").strip()
        if source_id:
            item.source_id = source_id

        db.session.add(item)
        db.session.commit()
        return redirect(url_for("work_items.work_item_detail", item_id=item.id))

    # Pre-populate from query params (finding→WorkItem pipeline)
    prefill = None
    if request.args.get("from_finding"):
        prefill = WorkItem(
            title=request.args.get("title", ""),
            category=request.args.get("category", "review"),
            priority=request.args.get("priority", "medium"),
            notes=request.args.get("notes", ""),
            source_id=request.args.get("source_id", ""),
        )

    return render_template("work_item_form.html", item=prefill, mode="create")


@work_items_bp.route("/work-items/<int:item_id>")
def work_item_detail(item_id):
    """View a single work item."""
    item = WorkItem.query.get_or_404(item_id)
    return render_template("work_item_detail.html", item=item)


@work_items_bp.route("/work-items/<int:item_id>/edit", methods=["GET", "POST"])
def work_item_edit(item_id):
    """Edit a work item."""
    item = WorkItem.query.get_or_404(item_id)

    if request.method == "POST":
        item.title = request.form["title"]
        item.category = request.form.get("category", item.category)
        item.priority = request.form.get("priority", item.priority)
        item.effort = request.form.get("effort") or None
        item.status = request.form.get("status", item.status)
        item.notes = request.form.get("notes") or None

        source_id = request.form.get("source_id", "").strip()
        if source_id:
            item.source_id = source_id

        db.session.commit()
        return redirect(url_for("work_items.work_item_detail", item_id=item.id))

    return render_template("work_item_form.html", item=item, mode="edit")


@work_items_bp.route("/work-items/<int:item_id>/complete", methods=["POST"])
def work_item_complete(item_id):
    """Mark a work item as done."""
    item = WorkItem.query.get_or_404(item_id)
    item.complete()
    db.session.commit()
    return redirect(url_for("work_items.work_item_detail", item_id=item.id))


@work_items_bp.route("/work-items/<int:item_id>/archive", methods=["POST"])
def work_item_archive(item_id):
    """Archive a work item."""
    item = WorkItem.query.get_or_404(item_id)
    item.archive()
    db.session.commit()
    return redirect(url_for("work_items.work_item_list"))
