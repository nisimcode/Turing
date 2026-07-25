"""Zero-API end-to-end check for the productization review queue."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gate.core.policy import assess
from gate.core.review import list_reviews, render_html, resolve_review


def main() -> int:
    previous = os.environ.get("GATE_REVIEW_QUEUE_PATH")
    try:
        with tempfile.TemporaryDirectory(prefix="gate-review-offline-") as tmp:
            queue = Path(tmp) / "reviews.jsonl"
            os.environ["GATE_REVIEW_QUEUE_PATH"] = str(queue)

            first = assess(
                vertical="luhn<script>",
                spec_clarifications=[{"args": [""], "domain_errors": ["x"]}],
            )
            second = assess(
                vertical="luhn<script>",
                spec_clarifications=[{"args": [""], "domain_errors": ["x"]}],
            )
            assert first.required and first.provisional and first.review_id
            assert second.review_id == first.review_id

            pending = list_reviews(status="pending")
            assert len(pending) == 1, "identical pending reviews were duplicated"
            page = render_html()
            assert "luhn&lt;script&gt;" in page
            assert "luhn<script>" not in page

            resolve_review(
                first.review_id,
                disposition="clarified",
                note="Domain is 2-19 ASCII digits; empty input is excluded.",
                findings={
                    "reviewer_seconds": 12.5,
                    "spec_domain_mismatch": True,
                    "unanimous_wrong_oracle": False,
                },
            )
            assert list_reviews(status="pending") == []
            all_items = list_reviews(status=None)
            assert len(all_items) == 1
            assert all_items[0]["resolution"]["disposition"] == "clarified"
            assert all_items[0]["resolution"]["findings"][
                "reviewer_seconds"
            ] == 12.5
            assert len(queue.read_text(encoding="utf-8").splitlines()) == 2
    finally:
        if previous is None:
            os.environ.pop("GATE_REVIEW_QUEUE_PATH", None)
        else:
            os.environ["GATE_REVIEW_QUEUE_PATH"] = previous

    print("OFFLINE REVIEW WORKFLOW: PASS")
    print("  policy trigger -> stable review ID")
    print("  duplicate pending trigger -> deduplicated")
    print("  HTML view -> escaped")
    print("  CLI semantics -> append-only resolution")
    print("  audit events: 2 (opened, resolved)")
    print("  API spend: $0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
