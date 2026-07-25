"""Paired, multi-domain gate benchmark. Deterministic and zero-API."""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gate.core.manifest import ManifestError, verify_manifest

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INDEX = ROOT / "benchmarks" / "logic-tools-v1.json"


class BenchmarkError(ValueError):
    """The benchmark index is unsafe or internally inconsistent."""


def _inside(base: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute():
        raise BenchmarkError("benchmark manifest paths must be relative")
    resolved = (base / candidate).resolve()
    try:
        resolved.relative_to(base.resolve())
    except ValueError as exc:
        raise BenchmarkError(
            "benchmark manifest paths must stay inside the benchmark directory"
        ) from exc
    if not resolved.is_file():
        raise BenchmarkError(f"benchmark manifest not found: {resolved}")
    return resolved


def load_index(path: str | Path) -> tuple[str, list[dict]]:
    index_path = Path(path).resolve()
    if not index_path.is_file():
        raise BenchmarkError(f"benchmark index not found: {index_path}")
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BenchmarkError(
            f"invalid benchmark JSON at line {exc.lineno}: {exc.msg}"
        ) from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise BenchmarkError("benchmark schema_version must be 1")
    name = data.get("name")
    subjects = data.get("subjects")
    if not isinstance(name, str) or not name.strip():
        raise BenchmarkError("benchmark name must be a non-empty string")
    if not isinstance(subjects, list) or not subjects:
        raise BenchmarkError("benchmark subjects must be a non-empty array")

    validated = []
    seen = set()
    for index, subject in enumerate(subjects):
        if not isinstance(subject, dict):
            raise BenchmarkError(f"subjects[{index}] must be an object")
        subject_id = subject.get("id")
        category = subject.get("category")
        expected = subject.get("expected")
        manifest = subject.get("manifest")
        if not isinstance(subject_id, str) or not subject_id.strip():
            raise BenchmarkError(f"subjects[{index}].id must be non-empty")
        if subject_id in seen:
            raise BenchmarkError(f"duplicate benchmark subject id: {subject_id}")
        seen.add(subject_id)
        if not isinstance(category, str) or not category.strip():
            raise BenchmarkError(f"subjects[{index}].category must be non-empty")
        if expected not in {"pass", "reject"}:
            raise BenchmarkError(
                f"subjects[{index}].expected must be pass or reject"
            )
        if not isinstance(manifest, str) or not manifest.strip():
            raise BenchmarkError(f"subjects[{index}].manifest must be non-empty")

        expected_check = subject.get("expected_check")
        diagnostic = subject.get("diagnostic_contains")
        if expected == "reject" and (
            not isinstance(expected_check, str)
            or not expected_check.strip()
            or not isinstance(diagnostic, str)
            or not diagnostic.strip()
        ):
            raise BenchmarkError(
                f"subjects[{index}] reject controls require expected_check "
                "and diagnostic_contains"
            )
        validated.append({
            "id": subject_id,
            "category": category,
            "expected": expected,
            "manifest": _inside(index_path.parent, manifest),
            "expected_check": expected_check,
            "diagnostic_contains": diagnostic,
        })
    if {subject["expected"] for subject in validated} != {"pass", "reject"}:
        raise BenchmarkError(
            "benchmark must contain both pass and reject controls"
        )
    return name.strip(), validated


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def run_benchmark(path: str | Path = DEFAULT_INDEX) -> dict:
    name, subjects = load_index(path)
    previous_telemetry = os.environ.get("GATE_TELEMETRY_PATH")
    rows = []

    try:
        with tempfile.TemporaryDirectory(prefix="turing-benchmark-") as folder:
            os.environ["GATE_TELEMETRY_PATH"] = str(
                Path(folder) / "telemetry.jsonl"
            )
            for subject in subjects:
                started = time.perf_counter()
                try:
                    _, verdict = verify_manifest(subject["manifest"])
                except ManifestError as exc:
                    raise BenchmarkError(
                        f"{subject['id']} has an invalid manifest: {exc}"
                    ) from exc
                duration_ms = (time.perf_counter() - started) * 1_000
                actual = "pass" if verdict.passed else "reject"
                decision_correct = actual == subject["expected"]

                diagnostic_ok = None
                diagnostic_detail = ""
                if subject["expected"] == "reject":
                    matching = next(
                        (
                            check for check in verdict.checks
                            if check["name"] == subject["expected_check"]
                        ),
                        None,
                    )
                    diagnostic_detail = (
                        str(matching.get("detail", "")) if matching else ""
                    )
                    diagnostic_ok = bool(
                        matching
                        and not matching["ok"]
                        and subject["diagnostic_contains"].casefold()
                        in diagnostic_detail.casefold()
                    )

                rows.append({
                    "id": subject["id"],
                    "category": subject["category"],
                    "expected": subject["expected"],
                    "actual": actual,
                    "decision_correct": decision_correct,
                    "diagnostic_ok": diagnostic_ok,
                    "expected_check": subject["expected_check"],
                    "failed_checks": verdict.failed_checks(),
                    "diagnostic_detail": diagnostic_detail,
                    "duration_ms": round(duration_ms, 1),
                })
    finally:
        if previous_telemetry is None:
            os.environ.pop("GATE_TELEMETRY_PATH", None)
        else:
            os.environ["GATE_TELEMETRY_PATH"] = previous_telemetry

    correct_controls = sum(row["expected"] == "pass" for row in rows)
    broken_controls = len(rows) - correct_controls
    false_accepts = sum(
        row["expected"] == "reject" and row["actual"] == "pass" for row in rows
    )
    false_rejects = sum(
        row["expected"] == "pass" and row["actual"] == "reject" for row in rows
    )
    diagnostic_hits = sum(row["diagnostic_ok"] is True for row in rows)
    durations = [row["duration_ms"] for row in rows]

    category_rows: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        category_rows[row["category"]].append(row)
    categories = {
        category: {
            "subjects": len(items),
            "correct_decisions": sum(
                item["decision_correct"] for item in items
            ),
            "false_accepts": sum(
                item["expected"] == "reject" and item["actual"] == "pass"
                for item in items
            ),
            "false_rejects": sum(
                item["expected"] == "pass" and item["actual"] == "reject"
                for item in items
            ),
        }
        for category, items in sorted(category_rows.items())
    }
    passed = (
        false_accepts == 0
        and false_rejects == 0
        and diagnostic_hits == broken_controls
    )
    return {
        "schema_version": 1,
        "name": name,
        "passed": passed,
        "summary": {
            "subjects": len(rows),
            "correct_controls": correct_controls,
            "broken_controls": broken_controls,
            "correct_decisions": sum(row["decision_correct"] for row in rows),
            "false_accepts": false_accepts,
            "false_rejects": false_rejects,
            "diagnostic_hits": diagnostic_hits,
            "diagnostic_rate": diagnostic_hits / broken_controls,
            "total_ms": round(sum(durations), 1),
            "median_ms": round(statistics.median(durations), 1),
            "p95_ms": round(_percentile(durations, 0.95), 1),
        },
        "categories": categories,
        "subjects": rows,
    }


def _index_guard_regression() -> None:
    """Prove an index cannot reach a manifest outside its own directory."""
    with tempfile.TemporaryDirectory(prefix="turing-benchmark-index-") as folder:
        root = Path(folder)
        index = root / "escape.json"
        index.write_text(
            json.dumps({
                "schema_version": 1,
                "name": "escape-control",
                "subjects": [{
                    "id": "escape",
                    "category": "control",
                    "manifest": "../outside.json",
                    "expected": "pass",
                }],
            }),
            encoding="utf-8",
        )
        try:
            load_index(index)
        except BenchmarkError as exc:
            if "stay inside" not in str(exc):
                raise AssertionError(str(exc)) from exc
        else:
            raise AssertionError("benchmark index directory escape was accepted")


def _print_report(report: dict) -> None:
    summary = report["summary"]
    for row in report["subjects"]:
        mark = "PASS" if (
            row["decision_correct"] and row["diagnostic_ok"] is not False
        ) else "FAIL"
        diagnostic = (
            ""
            if row["diagnostic_ok"] is None
            else f", diagnostic={'hit' if row['diagnostic_ok'] else 'miss'}"
        )
        print(
            f"  [{mark}] {row['id']}: expected={row['expected']}, "
            f"actual={row['actual']}{diagnostic}, {row['duration_ms']:.1f}ms"
        )
    print(
        f"BENCHMARK {'PASS' if report['passed'] else 'FAIL'}: "
        f"{summary['correct_decisions']}/{summary['subjects']} decisions, "
        f"false accepts={summary['false_accepts']}, "
        f"false rejects={summary['false_rejects']}, "
        f"diagnostics={summary['diagnostic_hits']}/"
        f"{summary['broken_controls']}, "
        f"median={summary['median_ms']:.1f}ms, p95={summary['p95_ms']:.1f}ms"
    )
    print("  API spend: $0")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--index",
        default=str(DEFAULT_INDEX),
        help="path to a version-1 benchmark index",
    )
    parser.add_argument(
        "--json", action="store_true", help="emit machine-readable results"
    )
    args = parser.parse_args(argv)
    try:
        _index_guard_regression()
        report = run_benchmark(args.index)
    except BenchmarkError as exc:
        print(f"BENCHMARK CONFIG ERROR: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_report(report)
        print("  benchmark index escape: rejected")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
