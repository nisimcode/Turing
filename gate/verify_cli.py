"""Single entry point for gating artifacts.

    uv run --with playwright --with pillow python verify_cli.py <file.html> [...]
    uv run ... python verify_cli.py --vertical wordle fixtures/wordle_broken.html

Verticals register their functional (correctness) layer here; without one you
get the runtime floor only, which cannot see correctness.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gate.core import print_verdict, verify            # noqa: E402

VERTICALS = {}


def _load_vertical(name):
    """Import a vertical's functional checks lazily (keeps startup cheap)."""
    if name in VERTICALS:
        return VERTICALS[name]
    here = Path(__file__).resolve().parent
    sys.path.insert(0, str(here))
    mod = __import__(f"{name}_spec")
    fn = getattr(mod, "functional_checks", None)
    if fn is None:
        sys.exit(f"vertical '{name}' has no functional_checks()")
    VERTICALS[name] = fn
    return fn


def main() -> int:
    ap = argparse.ArgumentParser(description="Gate generated HTML artifacts.")
    ap.add_argument("artifacts", nargs="+", help="HTML file(s) to verify")
    ap.add_argument("--vertical", help="functional layer, e.g. wordle, "
                                       "game2048, billsplit, calc")
    args = ap.parse_args()

    functional = _load_vertical(args.vertical) if args.vertical else None
    if not functional:
        print("note: no --vertical given; running the runtime FLOOR only.\n"
              "      The floor cannot see correctness -- a working-looking "
              "artifact with wrong logic will pass.\n")

    failures = 0
    for a in args.artifacts:
        v = verify(a, functional=functional)
        print_verdict(v)
        failures += 0 if v.passed else 1

    print(f"\n{len(args.artifacts) - failures}/{len(args.artifacts)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
