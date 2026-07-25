"""Durable, append-only human-review queue.

Policy triggers open deduplicated review items. Resolution appends a second
event rather than rewriting history, leaving an auditable creation-to-decision
trail that can later move behind a service without changing the semantics.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .config import ROOT
from .identity import revision_digest

DEFAULT_QUEUE_PATH = ROOT / "gate" / "review-queue.jsonl"
DISPOSITIONS = {"approved", "clarified", "rejected"}
REQUIRED_RELEASE_CHECKS = {
    "baseline_passes",
    "buggy_control_rejected",
    "control_execution_diverges",
    "oracle_has_cases",
    "oracle_zero_disputes",
    "domain_zero_clarifications",
    "mutation_target_met",
}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def queue_path() -> Path:
    override = os.environ.get("GATE_REVIEW_QUEUE_PATH")
    return Path(override) if override else DEFAULT_QUEUE_PATH


def _append(row: dict, path: Path | None = None) -> dict:
    target = path or queue_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    return row


def _events(path: Path | None = None) -> list[dict]:
    target = path or queue_path()
    if not target.exists():
        return []
    events = []
    for number, line in enumerate(
        target.read_text(encoding="utf-8").splitlines(), start=1
    ):
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"review queue is corrupt at line {number}"
            ) from exc
        if not isinstance(event, dict) or event.get("event") not in {
            "opened", "resolved"
        } or not event.get("id"):
            raise ValueError(
                f"review queue has an invalid event at line {number}"
            )
        events.append(event)
    return events


def list_reviews(status: str | None = "pending",
                 path: Path | None = None) -> list[dict]:
    """Fold queue events into current review items."""
    items: dict[str, dict] = {}
    order = []
    for event in _events(path):
        review_id = event.get("id")
        if not review_id:
            continue
        if event.get("event") == "opened":
            items[review_id] = {
                **event,
                "status": "pending",
                "resolution": None,
            }
            order.append(review_id)
        elif event.get("event") == "resolved" and review_id in items:
            items[review_id]["status"] = "resolved"
            items[review_id]["resolution"] = {
                "disposition": event.get("disposition"),
                "note": event.get("note", ""),
                "resolved_at": event.get("ts"),
                "findings": event.get("findings") or {},
            }
    rows = [items[review_id] for review_id in order if review_id in items]
    if status is not None:
        rows = [row for row in rows if row["status"] == status]
    return rows


def review_is_eligible(item: dict) -> bool:
    """Whether a current-format new-vertical packet may reach a human."""
    context = item.get("context") or {}
    checks = context.get("automated_checks") or {}
    material = context.get("review_material")
    try:
        return bool(
            context.get("is_new_vertical")
            and not item.get("provisional")
            and REQUIRED_RELEASE_CHECKS <= set(checks)
            and all(checks.get(name) is True for name in REQUIRED_RELEASE_CHECKS)
            and material
            and revision_digest(material) == item.get("revision")
        )
    except (TypeError, ValueError):
        # A malformed or manually edited packet must disappear from the eligible
        # sample instead of crashing the reviewer workflow.
        return False


def list_eligible_reviews(status: str | None = "pending",
                          path: Path | None = None) -> list[dict]:
    return [
        item for item in list_reviews(status=status, path=path)
        if review_is_eligible(item)
    ]


def open_review(*, vertical: str, reasons: list[str], provisional: bool,
                revision: str | None = None,
                context: dict | None = None,
                path: Path | None = None) -> dict:
    """Open one review, deduplicating identical pending triggers."""
    fingerprint_source = json.dumps(
        {
            "vertical": vertical,
            "revision": revision,
            "reasons": reasons,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    fingerprint = hashlib.sha256(
        fingerprint_source.encode("utf-8")
    ).hexdigest()
    for item in list_reviews(status="pending", path=path):
        if item.get("fingerprint") == fingerprint:
            return item
    row = {
        "schema_version": 1,
        "ts": _timestamp(),
        "event": "opened",
        "id": uuid.uuid4().hex[:12],
        "fingerprint": fingerprint,
        "vertical": vertical,
        "revision": revision,
        "reasons": reasons,
        "provisional": provisional,
        "context": context or {},
    }
    _append(row, path)
    return {**row, "status": "pending", "resolution": None}


def resolve_review(review_id: str, *, disposition: str, note: str,
                   findings: dict | None = None,
                   path: Path | None = None) -> dict:
    if disposition not in DISPOSITIONS:
        raise ValueError(
            f"disposition must be one of {sorted(DISPOSITIONS)}"
        )
    if not note.strip():
        raise ValueError("resolution note must not be empty")
    pending = {
        item["id"]: item for item in list_reviews(status="pending", path=path)
    }
    if review_id not in pending:
        raise KeyError(f"no pending review with id {review_id!r}")
    item = pending[review_id]
    context = item.get("context") or {}
    if disposition == "approved":
        if item.get("provisional"):
            raise ValueError(
                "a provisional review cannot be approved; clarify/rebuild or "
                "reject it"
            )
        if context.get("top_tier_failed"):
            raise ValueError("a top-tier gate failure cannot be approved")
        if context.get("is_new_vertical"):
            checks = context.get("automated_checks") or {}
            material = context.get("review_material")
            if not material or revision_digest(material) != item.get(
                "revision"
            ):
                raise ValueError(
                    "new vertical cannot be approved without review material "
                    "matching its revision"
                )
            missing = sorted(REQUIRED_RELEASE_CHECKS - set(checks))
            failed = sorted(name for name, ok in checks.items() if not ok)
            if missing or failed:
                detail = []
                if missing:
                    detail.append("missing " + ", ".join(missing))
                if failed:
                    detail.append("failed " + ", ".join(failed))
                raise ValueError(
                    "new vertical cannot be approved until automated release "
                    "checks pass: " + "; ".join(detail)
                )
    findings = findings or {}
    if "reviewer_seconds" in findings and (
        isinstance(findings["reviewer_seconds"], bool)
        or not isinstance(findings["reviewer_seconds"], (int, float))
        or findings["reviewer_seconds"] <= 0
    ):
        raise ValueError("reviewer_seconds must be a positive number")
    for name in (
        "unanimous_wrong_oracle",
        "spec_domain_mismatch",
        "ui_hook_divergence",
        "post_approval_failure",
    ):
        if name in findings and not isinstance(findings[name], bool):
            raise ValueError(f"{name} must be boolean")
    return _append({
        "schema_version": 1,
        "ts": _timestamp(),
        "event": "resolved",
        "id": review_id,
        "disposition": disposition,
        "note": note,
        "findings": findings,
    }, path)


def render_html(path: Path | None = None,
                eligible_only: bool = False) -> str:
    """Render the current queue as a self-contained, read-only HTML view."""
    reviews = (
        list_eligible_reviews(status=None, path=path)
        if eligible_only else list_reviews(status=None, path=path)
    )
    rows = []
    for item in reviews:
        reasons = "<br>".join(html.escape(reason) for reason in item["reasons"])
        resolution = item.get("resolution") or {}
        decision = resolution.get("disposition", "—")
        note = resolution.get("note", "")
        revision = item.get("revision") or "—"
        checks = (item.get("context") or {}).get("automated_checks") or {}
        check_text = "<br>".join(
            f"{'PASS' if ok else 'FAIL'} {html.escape(name)}"
            for name, ok in sorted(checks.items())
        ) or "—"
        rows.append(
            "<tr>"
            f"<td><code>{html.escape(item['id'])}</code></td>"
            f"<td>{html.escape(item.get('vertical', ''))}</td>"
            f"<td><code>{html.escape(revision[:12])}</code></td>"
            f"<td><span class='{item['status']}'>{item['status']}</span></td>"
            f"<td>{'yes' if item.get('provisional') else 'no'}</td>"
            f"<td>{reasons}</td>"
            f"<td>{check_text}</td>"
            f"<td>{html.escape(decision)}"
            f"{'<br>' + html.escape(note) if note else ''}</td>"
            "</tr>"
        )
    body = "\n".join(rows) or (
        "<tr><td colspan='8'>No review items.</td></tr>"
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Turing review queue</title>
<style>
body{{font:14px system-ui;margin:32px;background:#f6f7fb;color:#172033}}
table{{border-collapse:collapse;width:100%;background:white}}
th,td{{border:1px solid #d9deea;padding:10px;text-align:left;vertical-align:top}}
th{{background:#eef1f7}} .pending{{color:#9a5b00;font-weight:700}}
.resolved{{color:#157347;font-weight:700}} code{{font-size:12px}}
</style></head><body><h1>Turing review queue</h1>
<p>Generated {time.strftime("%Y-%m-%d %H:%M:%S")} · {len(reviews)} item(s)</p>
<table><thead><tr><th>ID</th><th>Vertical</th><th>Revision</th><th>Status</th>
<th>Provisional</th><th>Reasons</th><th>Automated checks</th>
<th>Decision</th></tr></thead>
<tbody>{body}</tbody></table></body></html>"""
