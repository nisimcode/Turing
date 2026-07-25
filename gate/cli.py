"""Public, no-API command line for Turing Gate."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from importlib import metadata, resources
from pathlib import Path

from .core.doctor import doctor_report
from .core.manifest import ManifestError, verify_manifest
from .core.starter import create_starter_manifest
from .core.verify import print_verdict

DEMOS = {
    "wordle": "manifest_cases",
    "calculator": "manifest_cases",
    "exfiltration": "no_outbound_requests",
}


def _version() -> str:
    try:
        return metadata.version("turing-gate")
    except metadata.PackageNotFoundError:
        from . import __version__
        return __version__


def _browser_missing(verdict) -> bool:
    return any(
        check["name"] == "loads"
        and "executable doesn't exist" in check.get("detail", "").lower()
        for check in verdict.checks
    )


def _result_json(manifest, verdict) -> str:
    return json.dumps(
        {
            "schema_version": 1,
            "name": manifest.name,
            "manifest": str(manifest.path),
            "artifact": str(manifest.artifact),
            "runtime_only": manifest.runtime_only,
            "passed": verdict.passed,
            "checks": verdict.checks,
        },
        ensure_ascii=False,
        indent=2,
    )


def _verify(args) -> int:
    manifest, verdict = verify_manifest(args.manifest)
    if args.json:
        print(_result_json(manifest, verdict))
    else:
        print(f"Turing Gate {_version()} — {manifest.name}")
        if manifest.description:
            print(manifest.description)
        if manifest.runtime_only:
            print(
                "WARNING: runtime-only manifest; this checks execution and "
                "containment, not functional correctness."
            )
        print_verdict(verdict)
    if _browser_missing(verdict):
        print(
            "\nBrowser missing. Run: turing-gate install-browser",
            file=sys.stderr,
        )
        return 2
    return 0 if verdict.passed else 1


def _demo(args) -> int:
    selected = list(DEMOS) if args.name == "all" else [args.name]
    failures = 0
    demo_root = resources.files("gate.demos")
    with resources.as_file(demo_root) as root:
        for name in selected:
            print(f"\n=== {name.upper()} DEMO ===")
            manifest, verdict = verify_manifest(Path(root) / f"{name}.json")
            print_verdict(verdict)
            if _browser_missing(verdict):
                print(
                    "\nBrowser missing. Run: turing-gate install-browser",
                    file=sys.stderr,
                )
                return 2
            expected_failure = DEMOS[name]
            caught = (
                not verdict.passed
                and expected_failure in verdict.failed_checks()
            )
            if caught:
                print(f"  DEMO PASS: caught {expected_failure}")
            else:
                failures += 1
                print(
                    f"  DEMO FAIL: expected rejection on {expected_failure}",
                    file=sys.stderr,
                )
    print(
        f"\n{len(selected) - failures}/{len(selected)} demonstrations "
        "caught the intended defect"
    )
    return 1 if failures else 0


def _doctor(args) -> int:
    report = doctor_report(_version())
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Turing Gate {_version()} environment")
        for check in report["checks"]:
            mark = "ok " if check["ok"] else "XX "
            print(f"  [{mark}] {check['name']}: {check['detail']}")
            if check.get("fix"):
                print(f"         fix: {check['fix']}")
        print(
            "\nREADY: verification can run."
            if report["ready"]
            else "\nNOT READY: resolve the failed setup checks above."
        )
    return 0 if report["ready"] else 2


def _install_browser(args) -> int:
    print("Installing the Playwright Chromium runtime...")
    command = [sys.executable, "-m", "playwright", "install"]
    if args.with_deps:
        command.append("--with-deps")
    command.append("chromium")
    return subprocess.run(
        command,
        check=False,
    ).returncode


def _init(args) -> int:
    result = create_starter_manifest(
        args.artifact,
        output_value=args.output,
        name=args.name,
        description=args.description,
        hook=args.hook,
        case_values=args.case,
        domain_schema_value=args.domain_schema,
        number_tolerance=args.number_tolerance,
        force=args.force,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(f"Created {result['manifest']}")
    if result["runtime_only"]:
        print(
            "Mode: runtime-only — execution and containment only; "
            "functional correctness is not yet checked."
        )
        print(
            "Next: rerun with --hook and one or more explicit --case values, "
            "or edit the manifest."
        )
    else:
        print(f"Mode: functional — {result['cases']} explicit case(s).")
    print(f"Verify: turing-gate verify \"{result['manifest']}\"")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="turing-gate",
        description=(
            "Fail-closed verification for generated, self-contained HTML/JS."
        ),
    )
    parser.add_argument("--version", action="version", version=_version())
    sub = parser.add_subparsers(dest="command", required=True)

    initializing = sub.add_parser(
        "init",
        help="create a validated starter manifest beside an HTML artifact",
    )
    initializing.add_argument("artifact", help="path to a local HTML artifact")
    initializing.add_argument(
        "--output",
        help="manifest path (default: turing.json beside the artifact)",
    )
    initializing.add_argument("--name", help="manifest name")
    initializing.add_argument("--description", help="manifest description")
    initializing.add_argument(
        "--hook",
        help="dotted browser function, for example window.__tool.calculate",
    )
    initializing.add_argument(
        "--case",
        action="append",
        default=[],
        metavar="JSON",
        help=(
            "repeatable JSON object with args and expected; requires --hook"
        ),
    )
    initializing.add_argument(
        "--domain-schema",
        metavar="JSON",
        help="optional supported argument-domain schema; requires --hook",
    )
    initializing.add_argument(
        "--number-tolerance",
        type=float,
        help="optional absolute numeric comparison tolerance; requires --hook",
    )
    initializing.add_argument(
        "--force",
        action="store_true",
        help="replace an existing output manifest",
    )
    initializing.add_argument(
        "--json", action="store_true", help="emit machine-readable results"
    )
    initializing.set_defaults(run=_init)

    verifying = sub.add_parser(
        "verify", help="verify an artifact from a deterministic JSON manifest"
    )
    verifying.add_argument("manifest", help="path to turing.json")
    verifying.add_argument(
        "--json", action="store_true", help="emit machine-readable results"
    )
    verifying.set_defaults(run=_verify)

    demo = sub.add_parser(
        "demo", help="run bundled known-bad artifacts and prove they are rejected"
    )
    demo.add_argument(
        "name",
        nargs="?",
        default="all",
        choices=["all", *DEMOS],
    )
    demo.set_defaults(run=_demo)

    doctor = sub.add_parser(
        "doctor", help="diagnose local setup without making API calls"
    )
    doctor.add_argument(
        "--json", action="store_true", help="emit machine-readable diagnostics"
    )
    doctor.set_defaults(run=_doctor)

    installing = sub.add_parser(
        "install-browser", help="install the Chromium runtime used for isolation"
    )
    installing.add_argument(
        "--with-deps",
        action="store_true",
        help="also install Linux browser system dependencies",
    )
    installing.set_defaults(run=_install_browser)
    return parser


def main(argv: list[str] | None = None) -> int:
    # Public CLI telemetry is local to the user's current project. Nothing is
    # transmitted; the override avoids writing inside an installed wheel.
    os.environ.setdefault(
        "GATE_TELEMETRY_PATH",
        str(Path.cwd() / ".turing" / "telemetry.jsonl"),
    )
    try:
        args = _parser().parse_args(argv)
        return args.run(args)
    except ManifestError as exc:
        print(f"CONFIG ERROR: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
