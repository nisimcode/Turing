"""Fail-closed lifecycle state for generated verticals.

Human approval is meaningful only for the exact spec/oracle/scaffold revision
that was reviewed. This module projects the append-only review queue into a
small release state machine and refuses production use unless every review for
that revision is resolved as approved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .identity import revision_digest
from .review import list_reviews


class ApprovalRequired(RuntimeError):
    """Raised when a vertical revision is not approved for production use."""


@dataclass(frozen=True)
class VerticalState:
    vertical: str
    revision: str
    status: str
    allowed: bool
    review_ids: list[str] = field(default_factory=list)
    detail: str = ""


def vertical_state(vertical: str, revision: str,
                   path: Path | None = None) -> VerticalState:
    """Fold review events into a fail-closed state for one exact revision."""
    if not vertical.strip():
        raise ValueError("vertical is required")
    if not revision.strip():
        raise ValueError("revision is required")

    all_items = [
        item for item in list_reviews(status=None, path=path)
        if item.get("vertical") == vertical
    ]
    matching = [
        item for item in all_items
        if item.get("revision") == revision
    ]
    ids = [item["id"] for item in matching]

    if not matching:
        status = "stale_revision" if all_items else "unreviewed"
        detail = (
            "reviews exist for another revision"
            if all_items else "no review exists for this revision"
        )
        return VerticalState(vertical, revision, status, False, [], detail)

    pending = [item for item in matching if item["status"] == "pending"]
    if pending:
        return VerticalState(
            vertical,
            revision,
            "pending",
            False,
            [item["id"] for item in pending],
            f"{len(pending)} review(s) still pending",
        )

    for item in matching:
        context = item.get("context") or {}
        material = context.get("review_material")
        if context.get("is_new_vertical") and (
            not material or revision_digest(material) != revision
        ):
            return VerticalState(
                vertical, revision, "invalid_revision", False, ids,
                "new-vertical review material is missing or does not match "
                "the recorded revision",
            )

    dispositions = [
        item["resolution"]["disposition"] for item in matching
        if item.get("resolution")
    ]
    if "rejected" in dispositions:
        return VerticalState(
            vertical, revision, "rejected", False, ids,
            "at least one review rejected this revision",
        )
    if "clarified" in dispositions:
        return VerticalState(
            vertical, revision, "needs_rebuild", False, ids,
            "the specification was clarified; regenerate and review a new "
            "revision",
        )
    if dispositions and len(dispositions) == len(matching) \
            and all(value == "approved" for value in dispositions):
        return VerticalState(
            vertical, revision, "approved", True, ids,
            "all reviews for this exact revision are approved",
        )
    return VerticalState(
        vertical, revision, "blocked", False, ids,
        "review history is incomplete or invalid",
    )


def require_approved(vertical: str, revision: str,
                     path: Path | None = None) -> VerticalState:
    """Return approved state or raise with a production-safe explanation."""
    state = vertical_state(vertical, revision, path=path)
    if not state.allowed:
        raise ApprovalRequired(
            f"{vertical}@{revision[:12]} is {state.status}: {state.detail}"
        )
    return state
