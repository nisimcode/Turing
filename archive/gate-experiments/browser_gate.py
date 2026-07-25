"""ARCHIVED PREDECESSOR: Phase 1 standalone browser gate.

Loads an HTML file in headless Chromium and runs generic, objective checks that
catch the most common ways a generated app is broken:

  * loads          -- the page navigates without throwing
  * no_page_errors -- no uncaught JS exceptions (pageerror)
  * no_console_err -- no console.error output (favicon noise filtered)
  * has_dom        -- the body actually rendered real elements
  * non_blank      -- the screenshot isn't a single flat color
  * interactive    -- there is *some* interactive affordance (buttons / inputs /
                      key handling) -- a game with no way to play is broken

These are the CORRECTNESS FLOOR for this vertical: cheap, deterministic, and
tuned so a pass means "it at least runs and can be played." Game-specific
functional checks (e.g. Wordle coloring) are the next layer (acceptance criteria)
and plug in via the `functional` hook.

Run on the two real Wordle builds we already generated:
    uv run --with playwright --with pillow python browser_gate.py

(One-time browser download first:
    uv run --with playwright python -m playwright install chromium)
"""

import io
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

SETTLE_MS = 600  # let inline JS run / initial render happen


def _non_blank(png_bytes) -> bool:
    """True if the screenshot has more than a couple of distinct colors."""
    try:
        from PIL import Image
    except ImportError:
        return True  # can't check -> don't fail on it
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    colors = img.getcolors(maxcolors=100000)
    return colors is None or len(colors) > 2


def gate_html(path, functional=None) -> dict:
    """Verify a single-file HTML app. `functional(page)` -> list[check] optional."""
    path = Path(path).resolve()
    checks = []
    console_errors, page_errors = [], []

    def add(name, ok, detail=""):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.on("pageerror", lambda e: page_errors.append(str(e)))

        try:
            page.goto(path.as_uri(), wait_until="load", timeout=10000)
            page.wait_for_timeout(SETTLE_MS)
            add("loads", True)
        except Exception as e:
            add("loads", False, str(e)[:120])
            browser.close()
            return _finalize(str(path), checks)

        add("no_page_errors", not page_errors,
            "; ".join(page_errors[:3]))
        real_console = [c for c in console_errors if "favicon" not in c.lower()]
        add("no_console_err", not real_console, "; ".join(real_console[:3]))

        dom_nodes = page.evaluate("document.body.querySelectorAll('*').length")
        add("has_dom", dom_nodes >= 5, f"{dom_nodes} elements")

        add("non_blank", _non_blank(page.screenshot()))

        interactive = page.evaluate(
            "document.querySelectorAll('button, input, [onclick], [tabindex], a')"
            ".length"
        )
        add("interactive", interactive >= 1, f"{interactive} affordances")

        if functional:
            try:
                for c in functional(page) or []:
                    checks.append(c)
            except Exception as e:
                add("functional", False, f"functional hook raised: {e!r}")

        browser.close()

    return _finalize(str(path), checks)


def _finalize(path, checks):
    passed = all(c["ok"] for c in checks)
    return {"path": path, "passed": passed, "checks": checks}


def print_verdict(v):
    print(f"\n{v['path']}")
    print(f"  VERDICT: {'PASS' if v['passed'] else 'FAIL'}")
    for c in v["checks"]:
        mark = "ok " if c["ok"] else "XX "
        detail = f"  ({c['detail']})" if c["detail"] else ""
        print(f"    [{mark}] {c['name']}{detail}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args:
        targets = [Path(a) for a in args]
    else:
        art = Path(__file__).resolve().parent / "fixtures"
        targets = sorted(art.glob("wordle_*.html"))
    if not targets:
        sys.exit("No HTML targets found. Pass file paths explicitly, or add "
                 "HTML to gate/fixtures/.")
    for t in targets:
        print_verdict(gate_html(t))
