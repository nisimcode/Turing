"""Probe why the contract check fails for a given HTML file (runtime diagnostics).

    uv run --with playwright python probe_hook.py <file.html>
"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

p = Path(sys.argv[1]).resolve()
with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page()
    cons, errs = [], []
    pg.on("console", lambda m: cons.append((m.type, m.text)))
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(p.as_uri(), wait_until="load")
    pg.wait_for_timeout(800)
    for expr in [
        "typeof window.__wordle",
        "window.__wordle ? Object.keys(window.__wordle) : null",
        "typeof (window.__wordle && window.__wordle.guess)",
        "typeof (window.__wordle && window.__wordle.setAnswer)",
    ]:
        print(f"{expr}  =>  {pg.evaluate(expr)}")
    print("pageerrors:", errs)
    print("console errors:", [c for c in cons if c[0] == 'error'][:5])
    b.close()
