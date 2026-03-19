"""Smart Priority Scoring — data-driven work item ranking.

Scores open work items on a 0–100 scale using five weighted factors:
  1. Priority weight  (35%) — critical=100, high=75, medium=40, low=15
  2. Age bonus        (20%) — older items score higher (max at 90 days)
  3. Category boost   (15%) — bugs score highest, then tech_debt
  4. Initiative match (20%) — boost if item matches active session initiative
  5. Effort ease      (10%) — smaller effort items get a nudge (quick wins)
"""

from __future__ import annotations

from datetime import datetime, timezone

from models import WorkItem, SessionLog

# ── Weight configuration ──────────────────────────────────────

WEIGHTS = {
    "priority": 0.35,
    "age": 0.20,
    "category": 0.15,
    "initiative": 0.20,
    "effort": 0.10,
}

PRIORITY_SCORES = {
    "critical": 100,
    "high": 75,
    "medium": 40,
    "low": 15,
}

CATEGORY_SCORES = {
    "bug": 100,
    "tech_debt": 70,
    "review": 50,
    "cleanup": 40,
    "feature": 30,
}

EFFORT_SCORES = {
    "XS": 100,
    "S": 80,
    "M": 50,
    "L": 30,
    "XL": 15,
}


# ── Core scoring function ─────────────────────────────────────


def score_item(item: WorkItem, active_initiative_id: int | None = None) -> dict:
    """Score a single work item.

    Args:
        item: WorkItem to score.
        active_initiative_id: ID of the current session's initiative (if any).

    Returns:
        dict with 'score' (0-100), 'factors' breakdown, and 'explanation' text.
    """
    factors = {}

    # 1. Priority
    factors["priority"] = PRIORITY_SCORES.get(item.priority, 30)

    # 2. Age — days since created (capped at 90)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if item.created_at:
        age_days = (now - item.created_at).days
    elif item.identified_date:
        age_days = (now.date() - item.identified_date).days
    else:
        age_days = 0
    factors["age"] = min(age_days / 90.0 * 100, 100)

    # 3. Category boost
    factors["category"] = CATEGORY_SCORES.get(item.category, 30)

    # 4. Initiative alignment
    if active_initiative_id and item.initiative_id == active_initiative_id:
        factors["initiative"] = 100
    elif item.initiative_id:
        factors["initiative"] = 30  # has an initiative, just not the active one
    else:
        factors["initiative"] = 0

    # 5. Effort ease (quick wins)
    factors["effort"] = EFFORT_SCORES.get(item.effort, 50) if item.effort else 50

    # Weighted score
    score = sum(factors[k] * WEIGHTS[k] for k in WEIGHTS)
    score = round(min(score, 100), 1)

    # Human-readable explanation
    explanation = _build_explanation(item, factors, active_initiative_id)

    return {
        "score": score,
        "factors": factors,
        "explanation": explanation,
    }


def rank_items(
    project: str = "vms",
    active_initiative_id: int | None = None,
    limit: int = 5,
) -> list[dict]:
    """Rank open work items by smart priority score.

    Args:
        project: Project key.
        active_initiative_id: Initiative to boost (from active session).
        limit: Max items to return.

    Returns:
        List of dicts: {'item': WorkItem, 'score': float, 'factors': dict, 'explanation': str}
    """
    # Get all open, non-archived items
    items = (
        WorkItem.query.filter(
            WorkItem.is_archived == False,  # noqa: E712
            WorkItem.status.in_(["backlog", "in_progress"]),
        )
        .filter_by(project=project)
        .all()
    )

    scored = []
    for item in items:
        result = score_item(item, active_initiative_id)
        scored.append(
            {
                "item": item,
                **result,
            }
        )

    # Sort by score descending
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:limit]


def get_active_initiative_id(project: str = "vms") -> int | None:
    """Get the initiative_id from the active session, if any."""
    active = (
        SessionLog.query.filter_by(project=project, ended_at=None)
        .order_by(SessionLog.started_at.desc())
        .first()
    )
    return active.initiative_id if active else None


# ── Helpers ────────────────────────────────────────────────────


def _build_explanation(
    item: WorkItem, factors: dict, active_initiative_id: int | None
) -> str:
    """Build a short human-readable explanation of the score."""
    parts = []

    # Priority
    if item.priority in ("critical", "high"):
        parts.append(f"{item.priority} priority")

    # Age
    age = factors["age"]
    if age >= 80:
        parts.append("aging item")
    elif age >= 40:
        parts.append("moderately old")

    # Category
    if item.category == "bug":
        parts.append("bug fix")

    # Initiative
    if active_initiative_id and item.initiative_id == active_initiative_id:
        parts.append("matches session focus")
    elif not active_initiative_id and item.initiative_id:
        parts.append("has initiative")

    # Effort
    if item.effort in ("XS", "S"):
        parts.append("quick win")

    return ", ".join(parts) if parts else "standard item"
