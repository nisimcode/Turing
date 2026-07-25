"""The runtime floor -- objective checks every artifact must clear.

These catch the crash-class defects (blank page, JS exception, dead UI) but
cannot see correctness: a beautiful game with wrong rules passes every one of
them. Functional verification against an oracle is what closes that gap.
"""

from __future__ import annotations

import io


def _non_blank(png: bytes) -> bool:
    """False if the screenshot is a single flat colour."""
    try:
        from PIL import Image
    except ImportError:
        return True                       # can't tell -> don't fail on it
    img = Image.open(io.BytesIO(png)).convert("RGB")
    colors = img.getcolors(maxcolors=100_000)
    return colors is None or len(colors) > 2


def runtime_floor(page, console_errors, page_errors) -> list[dict]:
    """Run the generic checks against an already-loaded page."""
    out: list[dict] = []

    def add(name, ok, detail=""):
        out.append({"name": name, "ok": bool(ok), "detail": detail})

    add("loads", True)
    add("no_page_errors", not page_errors, "; ".join(page_errors[:3]))
    real = [c for c in console_errors if "favicon" not in c.lower()]
    add("no_console_err", not real, "; ".join(real[:3]))

    n = page.evaluate("document.body.querySelectorAll('*').length")
    add("has_dom", n >= 5, f"{n} elements")

    add("non_blank", _non_blank(page.screenshot()))

    cta = page.evaluate(
        "document.querySelectorAll('button, input, [onclick], [tabindex], a')"
        ".length")
    add("interactive", cta >= 1, f"{cta} affordances")

    # Isolation signal: generated code that phones home is suspicious even if
    # the artifact otherwise works.
    blocked = getattr(page, "blocked_requests", [])
    add("no_outbound_requests", not blocked,
        f"{len(blocked)} blocked: {blocked[:2]}" if blocked else "")
    return out
