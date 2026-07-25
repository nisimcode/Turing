"""Zero-API regression for revision-bound, fail-closed vertical approval."""

from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import json
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gate.core.identity import revision_digest
from gate.core.lifecycle import (ApprovalRequired, require_approved,
                                 vertical_state)
from gate.core.policy import assess
from gate.core.review import open_review, resolve_review
from gate.core.config import Verdict
import gate.review_cli as review_cli
import gate.verify_cli as verify_cli


PASSING_CHECKS = {
    "baseline_passes": True,
    "buggy_control_rejected": True,
    "control_execution_diverges": True,
    "oracle_has_cases": True,
    "oracle_zero_disputes": True,
    "domain_zero_clarifications": True,
    "mutation_target_met": True,
}


def blocked(vertical: str, revision: str, expected: str) -> None:
    state = vertical_state(vertical, revision)
    assert not state.allowed and state.status == expected, state
    try:
        require_approved(vertical, revision)
    except ApprovalRequired:
        pass
    else:
        raise AssertionError(f"{vertical}@{revision[:12]} was not blocked")


def main() -> int:
    previous = os.environ.get("GATE_REVIEW_QUEUE_PATH")
    try:
        with tempfile.TemporaryDirectory(prefix="gate-lifecycle-") as tmp:
            queue = Path(tmp) / "reviews.jsonl"
            os.environ["GATE_REVIEW_QUEUE_PATH"] = str(queue)

            material_a = {
                "spec": "returns x + 1",
                "oracle": [[0, 1], [1, 2]],
            }
            revision_a = revision_digest(material_a)
            review = assess(
                vertical="increment",
                is_new_vertical=True,
                revision=revision_a,
                automated_checks=PASSING_CHECKS,
                review_material=material_a,
            )
            assert review.review_id
            blocked("increment", revision_a, "pending")

            resolve_review(
                review.review_id,
                disposition="approved",
                note="Spec and oracle checked against the stated domain.",
            )
            approved = require_approved("increment", revision_a)
            assert approved.allowed and approved.status == "approved"

            output = io.StringIO()
            with patch.object(
                sys,
                "argv",
                ["review_cli.py", "status", "increment", revision_a],
            ), contextlib.redirect_stdout(output):
                assert review_cli.main() == 0
            assert "approved" in output.getvalue()

            output = io.StringIO()
            with patch.object(
                sys,
                "argv",
                ["review_cli.py", "show", review.review_id],
            ), contextlib.redirect_stdout(output):
                assert review_cli.main() == 0
            assert "returns x + 1" in output.getvalue()

            fake_verdict = Verdict(
                passed=True,
                checks=[{"name": "fake", "ok": True}],
                artifact="candidate.html",
            )
            with patch.object(
                sys,
                "argv",
                [
                    "verify_cli.py",
                    "--vertical", "increment",
                    "--revision", revision_a,
                    "--require-approved",
                    "candidate.html",
                ],
            ), patch.object(
                verify_cli, "_load_vertical", return_value=lambda _page: []
            ), patch.object(
                verify_cli, "verify", return_value=fake_verdict
            ) as verify_mock, patch.object(
                verify_cli, "print_verdict"
            ), contextlib.redirect_stdout(io.StringIO()):
                assert verify_cli.main() == 0
            assert verify_mock.call_args.kwargs["vertical"] == "increment"

            revision_b = revision_digest({
                "spec": "returns x + 2",
                "oracle": [[0, 2], [1, 3]],
            })
            blocked("increment", revision_b, "stale_revision")
            with patch.object(
                sys,
                "argv",
                [
                    "verify_cli.py",
                    "--vertical", "increment",
                    "--revision", revision_b,
                    "--require-approved",
                    "candidate.html",
                ],
            ), contextlib.redirect_stderr(io.StringIO()):
                assert verify_cli.main() == 2

            failed_checks = {**PASSING_CHECKS, "mutation_target_met": False}
            unsafe_material = {"spec": "unsafe"}
            unsafe = assess(
                vertical="unsafe",
                is_new_vertical=True,
                revision=revision_digest(unsafe_material),
                automated_checks=failed_checks,
                review_material=unsafe_material,
            )
            try:
                resolve_review(
                    unsafe.review_id,
                    disposition="rejected",
                    note="   ",
                )
            except ValueError as exc:
                assert "must not be empty" in str(exc)
            else:
                raise AssertionError("empty audit note was accepted")
            try:
                resolve_review(
                    unsafe.review_id,
                    disposition="approved",
                    note="Attempted override.",
                )
            except ValueError as exc:
                assert "mutation_target_met" in str(exc)
            else:
                raise AssertionError("failed automated checks were approved")

            try:
                assess(
                    vertical="mismatch",
                    is_new_vertical=True,
                    revision=revision_a,
                    automated_checks=PASSING_CHECKS,
                    review_material={"different": "material"},
                )
            except ValueError as exc:
                assert "does not match" in str(exc)
            else:
                raise AssertionError("mismatched review material was accepted")

            provisional = assess(
                vertical="ambiguous",
                revision=revision_digest({"spec": "ambiguous"}),
                spec_clarifications=[{"reason": "undefined empty input"}],
            )
            try:
                resolve_review(
                    provisional.review_id,
                    disposition="approved",
                    note="Attempted provisional approval.",
                )
            except ValueError as exc:
                assert "provisional" in str(exc)
            else:
                raise AssertionError("provisional review was approved")
            resolve_review(
                provisional.review_id,
                disposition="clarified",
                note="Specify empty-input behavior and regenerate.",
            )
            blocked(
                "ambiguous",
                revision_digest({"spec": "ambiguous"}),
                "needs_rebuild",
            )

            rejected_revision = revision_digest({"spec": "rejected"})
            rejected = open_review(
                vertical="rejected",
                revision=rejected_revision,
                reasons=["manual policy conflict"],
                provisional=False,
            )
            resolve_review(
                rejected["id"],
                disposition="rejected",
                note="Conflicts with product policy.",
            )
            blocked("rejected", rejected_revision, "rejected")

            top_revision = revision_digest({"spec": "top-tier-failed"})
            top = assess(
                vertical="top-tier-failed",
                revision=top_revision,
                top_tier_failed=True,
            )
            try:
                resolve_review(
                    top.review_id,
                    disposition="approved",
                    note="Attempted unsafe override.",
                )
            except ValueError as exc:
                assert "top-tier" in str(exc)
            else:
                raise AssertionError("top-tier failure was approved")

            tampered = Path(tmp) / "tampered.jsonl"
            rows = [
                json.loads(line)
                for line in queue.read_text(encoding="utf-8").splitlines()
            ]
            for row in rows:
                if row.get("id") == review.review_id \
                        and row.get("event") == "opened":
                    row["context"]["review_material"]["spec"] = "tampered"
            tampered.write_text(
                "\n".join(json.dumps(row) for row in rows) + "\n",
                encoding="utf-8",
            )
            tampered_state = vertical_state(
                "increment", revision_a, path=tampered
            )
            assert tampered_state.status == "invalid_revision"
            assert not tampered_state.allowed

            corrupt = Path(tmp) / "corrupt.jsonl"
            corrupt.write_text("{not json}\n", encoding="utf-8")
            try:
                vertical_state("anything", "revision", path=corrupt)
            except ValueError as exc:
                assert "corrupt" in str(exc)
            else:
                raise AssertionError("corrupt audit queue failed open")
    finally:
        if previous is None:
            os.environ.pop("GATE_REVIEW_QUEUE_PATH", None)
        else:
            os.environ["GATE_REVIEW_QUEUE_PATH"] = previous

    print("OFFLINE LIFECYCLE: PASS")
    print("  approval bound to exact revision")
    print("  show/status/release CLI integration enforced")
    print("  pending/stale/clarified/rejected revisions blocked")
    print("  failed automated checks cannot be human-approved")
    print("  provisional findings require clarification/rebuild")
    print("  empty notes and top-tier overrides rejected")
    print("  mismatched/tampered/corrupt audit history fails closed")
    print("  API spend: $0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
