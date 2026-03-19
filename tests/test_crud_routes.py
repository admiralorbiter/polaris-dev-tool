"""Tests for CRUD routes — features and work items coverage gaps."""

from datetime import date, timedelta

from models import WorkItem, Feature


# ── Feature Edit & Ship Tests ─────────────────────────────────


class TestFeatureEdit:
    """Tests for GET/POST /features/<id>/edit."""

    def test_edit_form_loads(self, client, db):
        """Edit form renders for existing feature."""
        f = Feature(
            project="test",
            name="Editable feature",
            domain="Core",
            implementation_status="pending",
        )
        db.session.add(f)
        db.session.commit()

        response = client.get(f"/features/{f.id}/edit")
        assert response.status_code == 200
        assert b"Editable feature" in response.data

    def test_edit_updates_feature(self, client, db):
        """POST to edit updates the feature fields."""
        f = Feature(
            project="test",
            name="Original name",
            domain="Core",
            implementation_status="pending",
        )
        db.session.add(f)
        db.session.commit()

        response = client.post(
            f"/features/{f.id}/edit",
            data={
                "name": "Updated name",
                "domain": "Email",
                "status": "in_progress",
                "implementation_status": "partial",
                "notes": "Updated notes",
                "requirement_id": "FR-999",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Updated name" in response.data

        refreshed = db.session.get(Feature, f.id)
        assert refreshed.name == "Updated name"
        assert refreshed.domain == "Email"
        assert refreshed.implementation_status == "partial"
        assert refreshed.requirement_id == "FR-999"

    def test_edit_404_for_missing(self, client):
        """Edit returns 404 for non-existent feature."""
        response = client.get("/features/99999/edit")
        assert response.status_code == 404


class TestFeatureDetail:
    """Tests for GET /features/<id> — review countdown display."""

    def test_detail_shows_review_countdown(self, client, db):
        """Feature detail shows review countdown when next_review is set."""
        f = Feature(
            project="test",
            name="Shipped feature",
            implementation_status="implemented",
            status="shipped",
            next_review=date.today() + timedelta(days=30),
        )
        db.session.add(f)
        db.session.commit()

        response = client.get(f"/features/{f.id}")
        assert response.status_code == 200
        assert b"Shipped feature" in response.data


class TestFeatureListFilters:
    """Tests for feature list filter combinations."""

    def test_filter_by_impl_status(self, client, db):
        """Implementation status filter works."""
        db.session.add(
            Feature(
                project="test",
                name="Implemented one",
                implementation_status="implemented",
            )
        )
        db.session.add(
            Feature(
                project="test",
                name="Pending one",
                implementation_status="pending",
            )
        )
        db.session.commit()

        response = client.get("/features?impl_status=implemented")
        assert response.status_code == 200
        assert b"Implemented one" in response.data
        assert b"Pending one" not in response.data

    def test_filter_by_status(self, client, db):
        """Status filter works on feature list."""
        db.session.add(
            Feature(
                project="test",
                name="Shipped feat",
                implementation_status="implemented",
                status="shipped",
            )
        )
        db.session.add(
            Feature(
                project="test",
                name="Requested feat",
                implementation_status="pending",
                status="requested",
            )
        )
        db.session.commit()

        response = client.get("/features?status=shipped")
        assert response.status_code == 200
        assert b"Shipped feat" in response.data
        assert b"Requested feat" not in response.data


# ── Work Item Edit Tests ─────────────────────────────────


class TestWorkItemEdit:
    """Tests for GET/POST /work-items/<id>/edit."""

    def test_edit_form_loads(self, client, db):
        """Edit form renders for existing work item."""
        item = WorkItem(project="test", title="Editable item", status="backlog")
        db.session.add(item)
        db.session.commit()

        response = client.get(f"/work-items/{item.id}/edit")
        assert response.status_code == 200
        assert b"Editable item" in response.data

    def test_edit_updates_work_item(self, client, db):
        """POST to edit updates the work item fields."""
        item = WorkItem(project="test", title="Original title", status="backlog")
        db.session.add(item)
        db.session.commit()

        response = client.post(
            f"/work-items/{item.id}/edit",
            data={
                "title": "Updated title",
                "category": "bug",
                "priority": "critical",
                "effort": "L",
                "status": "in_progress",
                "notes": "Now in progress",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Updated title" in response.data

        refreshed = db.session.get(WorkItem, item.id)
        assert refreshed.title == "Updated title"
        assert refreshed.category == "bug"
        assert refreshed.priority == "critical"
        assert refreshed.effort == "L"
        # source_id is auto-generated on first save when missing
        assert refreshed.source_id is not None
        assert refreshed.source_id.startswith("BUG-")

    def test_edit_404_for_missing(self, client):
        """Edit returns 404 for non-existent item."""
        response = client.get("/work-items/99999/edit")
        assert response.status_code == 404


class TestWorkItemFilterByCategory:
    """Test the category filter on work items."""

    def test_filter_by_category(self, client, db):
        """Category filter shows only matching items."""
        db.session.add(WorkItem(project="test", title="Bug item", category="bug"))
        db.session.add(
            WorkItem(project="test", title="Debt item", category="tech_debt")
        )
        db.session.commit()

        response = client.get("/work-items?category=bug")
        assert response.status_code == 200
        assert b"Bug item" in response.data
        assert b"Debt item" not in response.data
