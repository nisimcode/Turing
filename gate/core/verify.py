"""The single entry point: verify(artifact) -> Verdict.

Replaces a dozen ad-hoc research scripts, each with its own copy of the browser
setup, key loading and check logic. Everything runs sandboxed by default.
"""

from __future__ import annotations

from pathlib import Path

from .checks import runtime_floor
from .config import Verdict, get_logger
from .sandbox import sandboxed_page
from .telemetry import record

log = get_logger("gate.verify")


def verify(artifact, functional=None, extra_files=None,
           vertical: str = "") -> Verdict:
    """Gate one HTML artifact.

    artifact    -- path to a self-contained HTML file
    functional  -- optional callable(page) -> list[check dicts], the
                   vertical-specific correctness layer (oracle comparison,
                   acceptance criteria). Without it you only get the floor,
                   which cannot see correctness.
    """
    artifact = Path(artifact)
    console_errors: list[str] = []
    page_errors: list[str] = []
    checks: list[dict] = []

    try:
        with sandboxed_page(artifact, extra_files=extra_files) as page:
            page.on("console",
                    lambda m: console_errors.append(m.text)
                    if m.type == "error" else None)
            page.on("pageerror", lambda e: page_errors.append(str(e)))
            # Re-read after listeners attach: errors raised during initial load
            # are captured by re-running the page's own scripts is not possible,
            # so we also surface anything already recorded by the context.
            checks = runtime_floor(page, console_errors, page_errors)

            if functional:
                try:
                    checks.extend(functional(page) or [])
                except Exception as exc:                      # noqa: BLE001
                    checks.append({"name": "functional", "ok": False,
                                   "detail": f"hook raised: {exc!r}"})
    except Exception as exc:                                  # noqa: BLE001
        checks.append({"name": "loads", "ok": False,
                       "detail": f"{type(exc).__name__}: {str(exc)[:120]}"})

    passed = bool(checks) and all(c["ok"] for c in checks)
    v = Verdict(passed=passed, checks=checks, artifact=str(artifact))
    log.info("%s -> %s", artifact.name, v.summary())
    record("verify", vertical=vertical, artifact=artifact.name,
           passed=passed, failed=v.failed_checks())
    return v


def print_verdict(v: Verdict) -> None:
    print(f"\n{v.artifact}")
    print(f"  VERDICT: {'PASS' if v.passed else 'FAIL'}")
    for c in v.checks:
        mark = "ok " if c["ok"] else "XX "
        detail = f"  ({c['detail']})" if c.get("detail") else ""
        print(f"    [{mark}] {c['name']}{detail}")
