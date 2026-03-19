"""CRUD routes for Initiatives — thematic work groupings."""

import re

from flask import Blueprint, render_template, request, redirect, url_for

from models import db, Initiative, WorkItem

initiatives_bp = Blueprint("initiatives", __name__)


def _slugify(text: str) -> str:
    """Convert text to a URL-friendly slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug[:50]


@initiatives_bp.route("/initiatives")
def initiative_list():
    """List all initiatives with progress bars."""
    initiatives = Initiative.query.order_by(Initiative.name).all()
    return render_template("initiative_list.html", initiatives=initiatives)


@initiatives_bp.route("/initiatives/new", methods=["GET", "POST"])
def initiative_create():
    """Create a new initiative."""
    if request.method == "POST":
        name = request.form["name"]
        initiative = Initiative(
            name=name,
            slug=request.form.get("slug", "").strip() or _slugify(name),
            description=request.form.get("description") or None,
        )
        target = request.form.get("target_date", "").strip()
        if target:
            from datetime import date

            try:
                initiative.target_date = date.fromisoformat(target)
            except ValueError:
                pass

        db.session.add(initiative)
        db.session.commit()
        return redirect(url_for("initiatives.initiative_detail", init_id=initiative.id))

    return render_template("initiative_form.html", initiative=None, mode="create")


@initiatives_bp.route("/initiatives/<int:init_id>")
def initiative_detail(init_id):
    """Show initiative detail with linked work items."""
    initiative = Initiative.query.get_or_404(init_id)
    work_items = (
        initiative.work_items.filter_by(is_archived=False)
        .order_by(WorkItem.priority, WorkItem.status)
        .all()
    )
    return render_template(
        "initiative_detail.html", initiative=initiative, work_items=work_items
    )


@initiatives_bp.route("/initiatives/<int:init_id>/edit", methods=["GET", "POST"])
def initiative_edit(init_id):
    """Edit an existing initiative."""
    initiative = Initiative.query.get_or_404(init_id)

    if request.method == "POST":
        initiative.name = request.form["name"]
        slug = request.form.get("slug", "").strip()
        if slug:
            initiative.slug = slug
        initiative.description = request.form.get("description") or None

        target = request.form.get("target_date", "").strip()
        if target:
            from datetime import date

            try:
                initiative.target_date = date.fromisoformat(target)
            except ValueError:
                pass
        else:
            initiative.target_date = None

        db.session.commit()
        return redirect(url_for("initiatives.initiative_detail", init_id=initiative.id))

    return render_template("initiative_form.html", initiative=initiative, mode="edit")


@initiatives_bp.route("/initiatives/<int:init_id>/delete", methods=["POST"])
def initiative_delete(init_id):
    """Delete an initiative, unlinking its work items first."""
    initiative = Initiative.query.get_or_404(init_id)

    # Unlink work items (don't delete them)
    WorkItem.query.filter_by(initiative_id=init_id).update({"initiative_id": None})

    db.session.delete(initiative)
    db.session.commit()
    return redirect(url_for("initiatives.initiative_list"))
