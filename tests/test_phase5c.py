"""Tests for Phase 5c: Work Discovery.

Covers:
- Smart priority scoring (utils/priority_score.py)
- Initiative CRUD routes (routes/initiatives.py)
- Priority field validation (models.WorkItem)
"""

from datetime import datetime, timezone, timedelta

import pytest

from models import WorkItem, Initiative, SessionLog


class TestPriorityScore:
    """Tests for utils/priority_score.py scoring engine."""

    def _make_item(self, db_session, **overrides):
        """Create a WorkItem with sensible defaults."""
        defaults = {
            "project": "vms",
            "title": "Test Item",
            "category": "tech_debt",
            "priority": "medium",
            "status": "backlog",
            "created_at": datetime.now(timezone.utc).replace(tzinfo=None)
            - timedelta(days=10),
        }
        defaults.update(overrides)
        item = WorkItem(**defaults)
        db_session.session.add(item)
        db_session.session.commit()
        return item

    def test_score_critical_higher_than_low(self, app, db):
        """Critical items should score higher than low items."""
        from utils.priority_score import score_item

        critical = self._make_item(db, priority="critical", source_id="T-001")
        low = self._make_item(db, priority="low", source_id="T-002")

        s_crit = score_item(critical)
        s_low = score_item(low)

        assert s_crit["score"] > s_low["score"]
        assert "critical priority" in s_crit["explanation"]

    def test_score_bug_higher_than_feature(self, app, db):
        """Bugs should score higher than features (same priority)."""
        from utils.priority_score import score_item

        bug = self._make_item(db, category="bug", source_id="T-003", priority="medium")
        feature = self._make_item(
            db, category="feature", source_id="T-004", priority="medium"
        )

        s_bug = score_item(bug)
        s_feat = score_item(feature)

        assert s_bug["score"] > s_feat["score"]

    def test_initiative_alignment_boost(self, app, db):
        """Items matching active initiative should score higher."""
        from utils.priority_score import score_item

        init = Initiative(name="Test Init", slug="test-init")
        db.session.add(init)
        db.session.commit()

        aligned = self._make_item(db, initiative_id=init.id, source_id="T-005")
        unaligned = self._make_item(db, source_id="T-006")

        s_aligned = score_item(aligned, active_initiative_id=init.id)
        s_unaligned = score_item(unaligned, active_initiative_id=init.id)

        assert s_aligned["score"] > s_unaligned["score"]
        assert "matches session focus" in s_aligned["explanation"]

    def test_older_items_score_higher(self, app, db):
        """Older items should score higher than brand-new ones."""
        from utils.priority_score import score_item

        old = self._make_item(
            db,
            source_id="T-007",
            created_at=datetime.now(timezone.utc).replace(tzinfo=None)
            - timedelta(days=60),
        )
        new = self._make_item(
            db,
            source_id="T-008",
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )

        assert score_item(old)["score"] > score_item(new)["score"]

    def test_quick_win_effort_boost(self, app, db):
        """XS effort items should score higher than XL (same priority)."""
        from utils.priority_score import score_item

        xs = self._make_item(db, effort="XS", source_id="T-009")
        xl = self._make_item(db, effort="XL", source_id="T-010")

        assert score_item(xs)["score"] > score_item(xl)["score"]
        assert "quick win" in score_item(xs)["explanation"]

    def test_rank_items_returns_sorted(self, app, db):
        """rank_items should return items sorted by score descending."""
        from utils.priority_score import rank_items

        self._make_item(db, priority="low", source_id="T-011")
        self._make_item(db, priority="critical", source_id="T-012")
        self._make_item(db, priority="medium", source_id="T-013")

        ranked = rank_items(project="vms", limit=3)

        assert len(ranked) == 3
        scores = [r["score"] for r in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_rank_items_respects_limit(self, app, db):
        """rank_items should not return more than the limit."""
        from utils.priority_score import rank_items

        for i in range(10):
            self._make_item(db, source_id=f"T-{100 + i}")

        ranked = rank_items(project="vms", limit=3)
        assert len(ranked) == 3

    def test_rank_items_excludes_done(self, app, db):
        """rank_items should not include done or archived items."""
        from utils.priority_score import rank_items

        self._make_item(db, status="done", source_id="T-120")
        self._make_item(db, status="backlog", source_id="T-121")
        self._make_item(db, status="backlog", is_archived=True, source_id="T-122")

        ranked = rank_items(project="vms", limit=10)
        assert len(ranked) == 1
        assert ranked[0]["item"].source_id == "T-121"

    def test_score_range_0_to_100(self, app, db):
        """All scores should fall within 0-100 range."""
        from utils.priority_score import score_item

        item = self._make_item(
            db,
            priority="critical",
            category="bug",
            effort="XS",
            source_id="T-130",
            created_at=datetime.now(timezone.utc).replace(tzinfo=None)
            - timedelta(days=200),
        )

        result = score_item(item)
        assert 0 <= result["score"] <= 100

    def test_get_active_initiative_id(self, app, db):
        """get_active_initiative_id returns the active session's initiative."""
        from utils.priority_score import get_active_initiative_id

        init = Initiative(name="Active Init", slug="active-init")
        db.session.add(init)
        db.session.commit()

        session = SessionLog(
            project="vms",
            started_at=datetime.now(timezone.utc).replace(tzinfo=None),
            initiative_id=init.id,
        )
        db.session.add(session)
        db.session.commit()

        assert get_active_initiative_id("vms") == init.id

    def test_get_active_initiative_id_none(self, app, db):
        """get_active_initiative_id returns None when no active session."""
        from utils.priority_score import get_active_initiative_id

        assert get_active_initiative_id("vms") is None


class TestInitiativeDelete:
    """Tests for initiative delete route."""

    def test_delete_unlinks_work_items(self, client, db):
        """Deleting an initiative unlinks its work items, doesn't delete them."""
        init = Initiative(name="Doomed", slug="doomed")
        db.session.add(init)
        db.session.commit()

        item = WorkItem(
            project="vms",
            title="Linked Item",
            source_id="DEL-001",
            initiative_id=init.id,
        )
        db.session.add(item)
        db.session.commit()

        resp = client.post(f"/initiatives/{init.id}/delete", follow_redirects=True)
        assert resp.status_code == 200

        # Initiative should be gone
        assert Initiative.query.get(init.id) is None

        # Work item should still exist but unlinked
        reloaded = WorkItem.query.filter_by(source_id="DEL-001").first()
        assert reloaded is not None
        assert reloaded.initiative_id is None

    def test_delete_nonexistent_404(self, client, db):
        """Deleting a nonexistent initiative returns 404."""
        resp = client.post("/initiatives/99999/delete")
        assert resp.status_code == 404

    def test_delete_redirects_to_list(self, client, db):
        """Successful delete redirects to initiative list."""
        init = Initiative(name="Temp", slug="temp")
        db.session.add(init)
        db.session.commit()

        resp = client.post(f"/initiatives/{init.id}/delete")
        assert resp.status_code == 302
        assert "/initiatives" in resp.headers["Location"]


class TestPriorityValidation:
    """Tests for WorkItem priority field validation."""

    def test_valid_priorities_accepted(self, app, db):
        """All valid priorities should be accepted."""
        for p in ("critical", "high", "medium", "low"):
            item = WorkItem(
                project="vms",
                title=f"Test {p}",
                priority=p,
                source_id=f"VP-{p}",
            )
            db.session.add(item)
        db.session.commit()

    def test_invalid_priority_raises(self, app, db):
        """Invalid priority values should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid priority"):
            WorkItem(
                project="vms",
                title="Bad Priority",
                priority="2026",
            )

    def test_priority_normalized_lowercase(self, app, db):
        """Priority values should be normalized to lowercase."""
        item = WorkItem(
            project="vms",
            title="Uppercase Test",
            priority="HIGH",
            source_id="VP-upper",
        )
        assert item.priority == "high"

    def test_none_priority_defaults_to_medium(self, app, db):
        """None priority should default to 'medium'."""
        item = WorkItem(
            project="vms",
            title="No Priority",
            priority=None,
            source_id="VP-none",
        )
        assert item.priority == "medium"
