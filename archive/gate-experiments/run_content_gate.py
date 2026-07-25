"""ARCHIVED EXPERIMENT: objective limits on content/UI pages.

Games and tools reduce to a pure function with an oracle, so the gate can be
decisive. A landing page cannot. This builds a ladder of landing-page defects --
from crash to "ugly but valid" -- and measures which ones objective checks catch.

The interesting result is the BOUNDARY: the defect classes that pass every
objective check while still being bad work. Those are what a judge (or a human)
would have to cover, and they define the product's real scope.

    uv run --with playwright --with pillow python run_content_gate.py
"""

from pathlib import Path

from browser_gate import gate_html
from content_spec import make_checks

HERE = Path(__file__).resolve().parent
CDIR = HERE / "fixtures" / "content"
GOOD = CDIR / "landing_good.html"
SECTIONS = ["about", "pricing", "contact"]

# (name, description, mutation, expectation)
DEFECTS = [
    ("D0_good", "the reference page, no defect", lambda h: h, "should PASS"),
    ("D1_blank", "renders nothing (script wipes the body)",
     lambda h: h.replace("</body>",
                         "<script>document.body.innerHTML='';</script></body>"),
     "objective"),
    ("D2_missing_section", "the whole Pricing section is absent",
     lambda h: h[:h.index('<section id="pricing">')]
               + h[h.index('<section id="contact">'):],
     "objective"),
    ("D3_mobile_overflow", "fixed 1200px block breaks mobile layout",
     lambda h: h.replace('<section id="about">',
                         '<section id="about" style="width:1200px">'),
     "objective"),
    ("D4_low_contrast", "body text is near-invisible on the background",
     lambda h: h.replace("--ink:#241c17;", "--ink:#efe9e1;"),
     "objective"),
    ("D5_overlap", "hero and about sections collide on top of each other",
     lambda h: h.replace('<section id="about">',
                         '<section id="about" style="position:absolute;top:120px;'
                         'left:0;right:0;background:#fff">'),
     "objective"),
    # Garish on purpose, but every colour pair still clears WCAG AA -- so this
    # isolates pure TASTE, with no accessibility violation to hide behind.
    ("D6_ugly_valid", "garish clashing design, but readable and well-formed",
     lambda h: h.replace("--paper:#faf6f0;", "--paper:#00ff00;")
                .replace("--accent:#a8442a;", "--accent:#6b008b;")
                .replace("font-family:Georgia, serif;",
                         "font-family:'Comic Sans MS',cursive;")
                .replace("background:#fff;", "background:#ffff00;"),
     "SUBJECTIVE"),
    ("D7_vague_copy", "all copy replaced with contentless marketing filler",
     lambda h: h.replace(
         "We roast in twelve-kilo batches three mornings a week, so the bag on your\n"
         "       shelf is rarely more than four days off the drum.",
         "We deliver best-in-class solutions that leverage synergy to maximise "
         "value for our stakeholders.")
      .replace("Ember &amp; Oak began in a converted garage in 2019 and now supplies\n"
               "       thirty cafés across the region. We buy directly from growers.",
               "Our mission is to empower experiences through innovative, "
               "customer-centric excellence."),
     "SUBJECTIVE"),
]


def main():
    good = GOOD.read_text(encoding="utf-8")
    checks = make_checks(SECTIONS)
    results = []

    for name, desc, mutate, expectation in DEFECTS:
        path = CDIR / f"{name}.html"
        path.write_text(mutate(good), encoding="utf-8")
        v = gate_html(path, functional=checks)
        failed = [c["name"] for c in v["checks"] if not c["ok"]]
        results.append((name, desc, expectation, v["passed"], failed))
        status = "PASS" if v["passed"] else "FAIL"
        print(f"\n{name:20} gate={status}")
        print(f"    {desc}")
        if failed:
            for c in v["checks"]:
                if not c["ok"]:
                    print(f"    caught by: {c['name']}  ({c['detail']})")

    print("\n=== the objective boundary ===")
    print(f"  {'defect':20} {'expected':11} {'gate':6} caught by")
    for name, _, exp, passed, failed in results:
        print(f"  {name:20} {exp:11} {'PASS' if passed else 'FAIL':6} "
              f"{', '.join(failed) if failed else '-'}")

    obj = [r for r in results if r[2] == "objective"]
    subj = [r for r in results if r[2] == "SUBJECTIVE"]
    good_r = [r for r in results if r[2] == "should PASS"]
    caught = sum(1 for r in obj if not r[3])
    leaked = sum(1 for r in subj if r[3])
    fr = sum(1 for r in good_r if not r[3])

    print(f"\n  objectively-checkable defects caught: {caught}/{len(obj)}")
    print(f"  subjective defects that passed:       {leaked}/{len(subj)}")
    print(f"  false rejects on the good page:       {fr}/{len(good_r)}")

    print("\n=== read ===")
    print("  Structural and perceptual faults -- crash, missing section, mobile")
    print("  overflow, unreadable contrast, collision -- are objectively catchable,")
    print("  so a content gate CAN guarantee a page that works and is usable.")
    print("  What it cannot judge is whether the page is any GOOD: taste and copy")
    print("  quality pass every check. For content/UI the gate is a floor, not a")
    print("  quality bar -- the opposite of the tool/game verticals, where the")
    print("  oracle decides correctness outright.")


if __name__ == "__main__":
    main()
