"""Execution-validated mechanical-fault benchmark. Deterministic and zero-API."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gate.core.domain import validate_args
from gate.core.manifest import ManifestError, load_manifest, values_equal
from gate.core.mutation import generic_source_mutants, run_many
from gate.offline_benchmark_check import (
    DEFAULT_INDEX,
    BenchmarkError,
    load_index,
)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROBES = ROOT / "benchmarks" / "mutation-probes-v1.json"
START = "/* BENCHMARK_CORRECT_START */"
END = "/* BENCHMARK_CORRECT_END */"
SLOT = "/* BENCHMARK_MUTATION_SLOT */"
INVOKE = "(a) => window.benchmark.correct.apply(null, a)"
MAX_CANDIDATES_PER_DOMAIN = 40


def _decode(value):
    if not isinstance(value, str) or value.startswith("ERR:"):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _args_key(args: list) -> str:
    return json.dumps(args, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _load_probes(path: str | Path) -> tuple[str, dict[str, list[dict]]]:
    probe_path = Path(path).resolve()
    if not probe_path.is_file():
        raise BenchmarkError(f"mutation probe file not found: {probe_path}")
    try:
        data = json.loads(probe_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BenchmarkError(
            f"invalid mutation probe JSON at line {exc.lineno}: {exc.msg}"
        ) from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise BenchmarkError("mutation probe schema_version must be 1")
    name = data.get("name")
    domains = data.get("domains")
    if not isinstance(name, str) or not name.strip():
        raise BenchmarkError("mutation probe name must be non-empty")
    if not isinstance(domains, list) or not domains:
        raise BenchmarkError("mutation probe domains must be a non-empty array")

    result: dict[str, list[dict]] = {}
    for domain_index, domain in enumerate(domains):
        if not isinstance(domain, dict):
            raise BenchmarkError(f"domains[{domain_index}] must be an object")
        subject = domain.get("subject")
        probes = domain.get("probes")
        if not isinstance(subject, str) or not subject.strip():
            raise BenchmarkError(
                f"domains[{domain_index}].subject must be non-empty"
            )
        if subject in result:
            raise BenchmarkError(f"duplicate mutation probe subject: {subject}")
        if not isinstance(probes, list) or not probes:
            raise BenchmarkError(f"{subject} probes must be a non-empty array")
        checked = []
        seen = set()
        for probe_index, probe in enumerate(probes):
            if not isinstance(probe, dict):
                raise BenchmarkError(
                    f"{subject} probes[{probe_index}] must be an object"
                )
            args = probe.get("args")
            if not isinstance(args, list) or "expected" not in probe:
                raise BenchmarkError(
                    f"{subject} probes[{probe_index}] requires args and expected"
                )
            key = _args_key(args)
            if key in seen:
                raise BenchmarkError(f"{subject} has a duplicate independent probe")
            seen.add(key)
            checked.append({"args": args, "expected": probe["expected"]})
        result[subject] = checked
    return name.strip(), result


def _extract_correct(artifact: Path) -> tuple[str, str]:
    source = artifact.read_text(encoding="utf-8")
    if source.count(START) != 1 or source.count(END) != 1:
        raise BenchmarkError(
            f"{artifact} must contain exactly one ordered mutation marker pair"
        )
    start = source.index(START) + len(START)
    end = source.index(END)
    if end <= start:
        raise BenchmarkError(f"{artifact} mutation markers are out of order")
    implementation = source[start:end].strip()
    if not implementation:
        raise BenchmarkError(f"{artifact} marked implementation is empty")
    scaffold = source[:start] + "\n    " + SLOT + "\n    " + source[end:]
    if scaffold.count(SLOT) != 1:
        raise BenchmarkError(f"{artifact} mutation slot is ambiguous")
    return implementation, scaffold


def _matches(raw, expected, tolerance: float) -> bool:
    if isinstance(raw, str) and raw.startswith("ERR:"):
        return False
    return values_equal(_decode(raw), expected, tolerance)


def run_mutation_benchmark(
    index_path: str | Path = DEFAULT_INDEX,
    probe_path: str | Path = DEFAULT_PROBES,
    *,
    want_per_domain: int = 5,
    minimum_per_domain: int = 2,
) -> dict:
    benchmark_name, subjects = load_index(index_path)
    probe_name, probes_by_subject = _load_probes(probe_path)
    correct_subjects = {
        subject["id"]: subject for subject in subjects
        if subject["expected"] == "pass"
    }
    if set(probes_by_subject) != set(correct_subjects):
        missing = sorted(set(correct_subjects) - set(probes_by_subject))
        extra = sorted(set(probes_by_subject) - set(correct_subjects))
        raise BenchmarkError(
            f"mutation probe subjects mismatch; missing={missing}, extra={extra}"
        )

    started = time.perf_counter()
    rows = []
    for subject_id, subject in correct_subjects.items():
        try:
            manifest = load_manifest(subject["manifest"])
        except ManifestError as exc:
            raise BenchmarkError(f"{subject_id} manifest is invalid: {exc}") from exc
        if manifest.hook != "window.benchmark.correct":
            raise BenchmarkError(
                f"{subject_id} must expose window.benchmark.correct"
            )
        probes = probes_by_subject[subject_id]
        scored_keys = {_args_key(case["args"]) for case in manifest.cases}
        for probe_index, probe in enumerate(probes):
            if manifest.domain_schema is not None:
                errors = validate_args(probe["args"], manifest.domain_schema)
                if errors:
                    raise BenchmarkError(
                        f"{subject_id} probe {probe_index + 1} is outside "
                        f"domain_schema: {'; '.join(errors)}"
                    )
            if _args_key(probe["args"]) in scored_keys:
                raise BenchmarkError(
                    f"{subject_id} independent probe {probe_index + 1} "
                    "duplicates a scored manifest case"
                )

        implementation, scaffold = _extract_correct(manifest.artifact)
        combined = (
            [probe["args"] for probe in probes]
            + [case["args"] for case in manifest.cases]
        )
        expected = (
            [probe["expected"] for probe in probes]
            + [case["expected"] for case in manifest.cases]
        )
        try:
            baseline = run_many(scaffold, implementation, SLOT, combined, INVOKE)
        except Exception as exc:  # noqa: BLE001
            raise BenchmarkError(
                f"{subject_id} baseline could not execute: {exc}"
            ) from exc
        for value_index, (raw, wanted) in enumerate(zip(baseline, expected)):
            if not _matches(raw, wanted, manifest.number_tolerance):
                source = "probe" if value_index < len(probes) else "scored case"
                raise BenchmarkError(
                    f"{subject_id} correct baseline failed {source} "
                    f"{value_index + 1}: expected {wanted!r}, got {_decode(raw)!r}"
                )

        candidates = []
        seen = {implementation}
        for code, kind in generic_source_mutants(implementation):
            if code not in seen:
                seen.add(code)
                candidates.append((code, kind))
            if len(candidates) >= MAX_CANDIDATES_PER_DOMAIN:
                break

        validated = []
        candidates_executed = 0
        for code, kind in candidates:
            candidates_executed += 1
            try:
                actual = run_many(scaffold, code, SLOT, combined, INVOKE)
            except Exception:  # a malformed candidate is not a validated fault
                continue
            if actual and all(
                isinstance(value, str) and value.startswith("ERR:")
                for value in actual
            ):
                continue
            witness = next(
                (
                    index for index, (raw, probe) in enumerate(
                        zip(actual[:len(probes)], probes)
                    )
                    if not _matches(
                        raw, probe["expected"], manifest.number_tolerance
                    )
                ),
                None,
            )
            if witness is None:
                continue
            scored_actual = actual[len(probes):]
            detected = next(
                (
                    index for index, (raw, case) in enumerate(
                        zip(scored_actual, manifest.cases)
                    )
                    if not _matches(
                        raw, case["expected"], manifest.number_tolerance
                    )
                ),
                None,
            )
            record = {
                "kind": kind,
                "witness_args": probes[witness]["args"],
                "witness_expected": probes[witness]["expected"],
                "witness_actual": _decode(actual[witness]),
                "killed": detected is not None,
                "detected_by": (
                    manifest.cases[detected]["label"]
                    if detected is not None else None
                ),
            }
            validated.append(record)
            if len(validated) >= want_per_domain:
                break

        killed = sum(mutant["killed"] for mutant in validated)
        rows.append({
            "subject": subject_id,
            "independent_probes": len(probes),
            "scored_cases": len(manifest.cases),
            "candidates_generated": len(candidates),
            "candidates_executed": candidates_executed,
            "validated_mutants": len(validated),
            "killed": killed,
            "survivors": len(validated) - killed,
            "score": killed / len(validated) if validated else None,
            "minimum_met": len(validated) >= minimum_per_domain,
            "mutants": validated,
        })

    validated_total = sum(row["validated_mutants"] for row in rows)
    killed_total = sum(row["killed"] for row in rows)
    survivors_total = validated_total - killed_total
    coverage_passed = all(row["minimum_met"] for row in rows)
    return {
        "schema_version": 1,
        "name": probe_name,
        "paired_benchmark": benchmark_name,
        "coverage_passed": coverage_passed,
        "perfect": coverage_passed and survivors_total == 0,
        "summary": {
            "domains": len(rows),
            "independent_probes": sum(
                row["independent_probes"] for row in rows
            ),
            "scored_cases": sum(row["scored_cases"] for row in rows),
            "validated_mutants": validated_total,
            "killed": killed_total,
            "survivors": survivors_total,
            "score": (
                killed_total / validated_total if validated_total else None
            ),
            "duration_ms": round((time.perf_counter() - started) * 1_000, 1),
            "api_spend_usd": 0,
        },
        "domains": rows,
    }


def _print_report(report: dict) -> None:
    for row in report["domains"]:
        score = "n/a" if row["score"] is None else f"{row['score']:.0%}"
        mark = "PASS" if row["minimum_met"] and row["survivors"] == 0 else "GAP"
        print(
            f"  [{mark}] {row['subject']}: probes={row['independent_probes']}, "
            f"mutants={row['validated_mutants']}, killed={row['killed']}, "
            f"survivors={row['survivors']}, score={score}"
        )
        for mutant in row["mutants"]:
            if not mutant["killed"]:
                print(
                    f"    survivor: {mutant['kind']} "
                    f"(witness={mutant['witness_args']!r})"
                )
    summary = report["summary"]
    score = "n/a" if summary["score"] is None else f"{summary['score']:.0%}"
    status = "PASS" if report["perfect"] else "GAPS FOUND"
    print(
        f"MECHANICAL BENCHMARK {status}: "
        f"{summary['killed']}/{summary['validated_mutants']} killed, "
        f"survivors={summary['survivors']}, score={score}, "
        f"{summary['duration_ms']:.1f}ms"
    )
    print("  validation witnesses are disjoint from scored manifest cases")
    print("  API spend: $0")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", default=str(DEFAULT_INDEX))
    parser.add_argument("--probes", default=str(DEFAULT_PROBES))
    parser.add_argument("--want-per-domain", type=int, default=5)
    parser.add_argument("--minimum-per-domain", type=int, default=2)
    parser.add_argument(
        "--require-perfect",
        action="store_true",
        help="fail if any execution-validated mutant survives",
    )
    parser.add_argument(
        "--json", action="store_true", help="emit machine-readable results"
    )
    args = parser.parse_args(argv)
    if args.want_per_domain < 1 or args.minimum_per_domain < 1:
        parser.error("mutation counts must be positive")
    if args.minimum_per_domain > args.want_per_domain:
        parser.error("minimum-per-domain cannot exceed want-per-domain")
    try:
        report = run_mutation_benchmark(
            args.index,
            args.probes,
            want_per_domain=args.want_per_domain,
            minimum_per_domain=args.minimum_per_domain,
        )
    except BenchmarkError as exc:
        print(f"MECHANICAL BENCHMARK CONFIG ERROR: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_report(report)
    passed = report["coverage_passed"]
    if args.require_perfect:
        passed = passed and report["perfect"]
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
