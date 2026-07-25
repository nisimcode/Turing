"""Inspect and resolve the local human-review queue.

    uv run python review_cli.py list
    uv run python review_cli.py resolve <id> --disposition clarified --note "..."
    uv run python review_cli.py export --output review-queue.html
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gate.core.review import (DISPOSITIONS, list_eligible_reviews,     # noqa: E402
                              list_reviews, render_html, resolve_review)
from gate.core.lifecycle import vertical_state  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Turing human-review queue")
    commands = parser.add_subparsers(dest="command", required=True)

    listing = commands.add_parser("list", help="list review items")
    listing.add_argument("--all", action="store_true",
                         help="include resolved items")
    listing.add_argument("--json", action="store_true",
                         help="emit machine-readable JSON")
    listing.add_argument("--eligible", action="store_true",
                         help="show only packets that passed every automated "
                              "human-review prerequisite")

    resolving = commands.add_parser("resolve", help="resolve one pending item")
    resolving.add_argument("review_id")
    resolving.add_argument("--disposition", choices=sorted(DISPOSITIONS),
                           required=True)
    resolving.add_argument("--note", required=True)
    resolving.add_argument("--reviewer-seconds", type=float)
    resolving.add_argument("--unanimous-wrong-oracle", action="store_true")
    resolving.add_argument("--spec-domain-mismatch", action="store_true")
    resolving.add_argument("--ui-hook-divergence", action="store_true")
    resolving.add_argument("--post-approval-failure", action="store_true")

    exporting = commands.add_parser("export", help="write an HTML queue view")
    exporting.add_argument("--output", default="review-queue.html")
    exporting.add_argument("--eligible", action="store_true")

    commands.add_parser(
        "q25-report",
        help="summarize completed eligible-dossier human reviews",
    )
    handoff = commands.add_parser(
        "q25-handoff",
        help="materialize the ten eligible dossiers and runnable UIs",
    )
    handoff.add_argument("--output", default="q25-handoff")

    status = commands.add_parser(
        "status", help="show release state for an exact vertical revision"
    )
    status.add_argument("vertical")
    status.add_argument("revision")

    showing = commands.add_parser(
        "show", help="show the complete evidence packet for one review"
    )
    showing.add_argument("review_id")
    showing.add_argument("--json", action="store_true")

    args = parser.parse_args()
    if args.command == "list":
        if args.eligible:
            rows = list_eligible_reviews(
                status=None if args.all else "pending"
            )
        else:
            rows = list_reviews(status=None if args.all else "pending")
        if args.json:
            print(json.dumps(rows, indent=2, ensure_ascii=False))
        elif not rows:
            print("No review items.")
        else:
            for item in rows:
                state = "PROVISIONAL" if item["provisional"] else "review"
                print(f"{item['id']}  {item['status']:8}  {state:11}  "
                      f"{item['vertical']}")
                for reason in item["reasons"]:
                    print(f"  - {reason}")
                if item.get("resolution"):
                    decision = item["resolution"]
                    print(f"  => {decision['disposition']}: {decision['note']}")
        return 0

    if args.command == "resolve":
        try:
            resolve_review(
                args.review_id,
                disposition=args.disposition,
                note=args.note,
                findings={
                    **(
                        {"reviewer_seconds": args.reviewer_seconds}
                        if args.reviewer_seconds is not None else {}
                    ),
                    "unanimous_wrong_oracle":
                        args.unanimous_wrong_oracle,
                    "spec_domain_mismatch": args.spec_domain_mismatch,
                    "ui_hook_divergence": args.ui_hook_divergence,
                    "post_approval_failure":
                        args.post_approval_failure,
                },
            )
        except (KeyError, ValueError) as exc:
            parser.error(str(exc))
        print(f"Resolved {args.review_id}: {args.disposition}")
        return 0

    if args.command == "q25-report":
        rows = [
            item for item in list_eligible_reviews(status=None)
            if item["status"] == "resolved"
        ]
        dispositions = {
            name: sum(
                item["resolution"]["disposition"] == name for item in rows
            )
            for name in sorted(DISPOSITIONS)
        }
        findings = [
            item["resolution"].get("findings") or {} for item in rows
        ]
        seconds = [
            item.get("reviewer_seconds") for item in findings
            if item.get("reviewer_seconds") is not None
        ]
        print(f"Q25 human reviews: {len(rows)}/10")
        print(
            "  dispositions: "
            + ", ".join(f"{name}={count}"
                        for name, count in dispositions.items())
        )
        for name in (
            "unanimous_wrong_oracle",
            "spec_domain_mismatch",
            "ui_hook_divergence",
            "post_approval_failure",
        ):
            print(f"  {name}: {sum(bool(row.get(name)) for row in findings)}")
        print(
            f"  reviewer time: {sum(seconds):.1f}s across "
            f"{len(seconds)}/{len(rows)} timed review(s)"
        )
        return 0 if len(rows) >= 10 and len(seconds) == len(rows) else 1

    if args.command == "q25-handoff":
        rows = list_eligible_reviews(status="pending")
        if len(rows) < 10:
            parser.error(
                f"need 10 eligible pending dossiers, found {len(rows)}"
            )
        output = Path(args.output).resolve()
        output.mkdir(parents=True, exist_ok=True)
        index = [
            "# Q25 human review handoff",
            "",
            "Review the runnable UI and dossier for each row. Then record the "
            "decision with `review_cli.py resolve`, including "
            "`--reviewer-seconds` and any finding flags.",
            "",
            "| # | Review | Vertical | UI | Dossier |",
            "|---:|---|---|---|---|",
        ]
        for number, item in enumerate(rows[:10], start=1):
            context = item["context"]
            material = context["review_material"]
            scaffold = material["scaffold"]
            implementation = material["implementation"]
            marker = "/*__LOGIC_SLOT__*/"
            if scaffold.count(marker) != 1:
                parser.error(
                    f"{item['id']} scaffold does not contain one logic slot"
                )
            slug = re.sub(
                r"[^a-z0-9]+",
                "-",
                item["vertical"].lower(),
            ).strip("-")
            stem = f"{number:02d}-{slug}-{item['id']}"
            ui_name = stem + ".html"
            dossier_name = stem + ".json"
            (output / ui_name).write_text(
                scaffold.replace(marker, implementation, 1),
                encoding="utf-8",
            )
            (output / dossier_name).write_text(
                json.dumps(item, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            index.append(
                f"| {number} | `{item['id']}` | {item['vertical']} | "
                f"[open]({ui_name}) | [inspect]({dossier_name}) |"
            )
        index.extend([
            "",
            "Review questions: spec matches request; prose/domain/UI agree; "
            "oracle values are correct; UI and hook use the same function; "
            "UI is understandable; convention deviations are unmistakable.",
            "",
            "After all ten decisions run `uv run python review_cli.py "
            "q25-report`.",
        ])
        (output / "INDEX.md").write_text(
            "\n".join(index) + "\n",
            encoding="utf-8",
        )
        print(output / "INDEX.md")
        return 0

    if args.command == "status":
        state = vertical_state(args.vertical, args.revision)
        print(f"{state.vertical}@{state.revision[:12]}: {state.status}")
        print(f"  production allowed: {'yes' if state.allowed else 'NO'}")
        print(f"  {state.detail}")
        if state.review_ids:
            print(f"  reviews: {', '.join(state.review_ids)}")
        return 0 if state.allowed else 1

    if args.command == "show":
        matches = [
            item for item in list_reviews(status=None)
            if item["id"] == args.review_id
        ]
        if not matches:
            parser.error(f"unknown review id {args.review_id!r}")
        item = matches[0]
        if args.json:
            print(json.dumps(item, indent=2, ensure_ascii=False))
            return 0
        print(f"{item['id']}  {item['vertical']}@"
              f"{(item.get('revision') or '—')[:12]}")
        print(f"status: {item['status']}  provisional: "
              f"{'yes' if item.get('provisional') else 'no'}")
        print("reasons:")
        for reason in item["reasons"]:
            print(f"  - {reason}")
        context = item.get("context") or {}
        print("automated checks:")
        for name, ok in sorted(
            (context.get("automated_checks") or {}).items()
        ):
            print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        print("review material:")
        print(json.dumps(
            context.get("review_material") or {},
            indent=2,
            ensure_ascii=False,
        ))
        return 0

    output = Path(args.output).resolve()
    output.write_text(
        render_html(eligible_only=args.eligible),
        encoding="utf-8",
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
