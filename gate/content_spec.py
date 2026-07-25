"""Q13b: objective checks for content/UI pages -- and where they run out.

Games and tools reduce to a pure function with an oracle. A landing page does
not: much of its value is aesthetic. This module implements everything that CAN
be checked objectively for a content page, so we can measure exactly where the
objective surface ends and judgement has to take over.

Checks:
  required_sections -- every requested section is present (heading text match)
  mobile_no_overflow-- no horizontal scroll at 375px (the most common real defect)
  contrast          -- body text meets a WCAG-ish contrast ratio against its bg
  no_overlap        -- major blocks don't visually collide
  has_cta           -- a call-to-action control exists
"""

MOBILE_W = 375
MIN_CONTRAST = 4.5          # WCAG AA for normal text


def _contrast_js():
    return """
() => {
  const lum = (c) => {
    const m = c.match(/\\d+(\\.\\d+)?/g); if (!m) return null;
    const [r,g,b] = m.slice(0,3).map(Number);
    const f = (v) => { v/=255; return v<=0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055,2.4); };
    return 0.2126*f(r)+0.7152*f(g)+0.0722*f(b);
  };
  const bgOf = (el) => {
    let n = el;
    while (n && n !== document.documentElement) {
      const bg = getComputedStyle(n).backgroundColor;
      if (bg && !/rgba\\(0, 0, 0, 0\\)|transparent/.test(bg)) return bg;
      n = n.parentElement;
    }
    return getComputedStyle(document.body).backgroundColor || 'rgb(255,255,255)';
  };
  let worst = 99, sample = '';
  const els = [...document.querySelectorAll('p,li,span,a,h1,h2,h3,button')]
    .filter(e => e.textContent.trim().length > 8 && e.offsetParent !== null);
  for (const e of els) {
    const fg = lum(getComputedStyle(e).color), bg = lum(bgOf(e));
    if (fg === null || bg === null) continue;
    const hi = Math.max(fg,bg), lo = Math.min(fg,bg);
    const ratio = (hi + 0.05) / (lo + 0.05);
    if (ratio < worst) { worst = ratio; sample = e.textContent.trim().slice(0,28); }
  }
  return {worst: worst === 99 ? null : Math.round(worst*100)/100, sample};
}
"""


def _overlap_js():
    return """
() => {
  const blocks = [...document.querySelectorAll('section,header,footer,main>div,article')]
    .filter(e => e.offsetParent !== null);
  for (let i=0;i<blocks.length;i++) for (let j=i+1;j<blocks.length;j++){
    const a = blocks[i], b = blocks[j];
    if (a.contains(b) || b.contains(a)) continue;
    const r1 = a.getBoundingClientRect(), r2 = b.getBoundingClientRect();
    const ox = Math.min(r1.right,r2.right) - Math.max(r1.left,r2.left);
    const oy = Math.min(r1.bottom,r2.bottom) - Math.max(r1.top,r2.top);
    if (ox > 8 && oy > 8) return {overlap:true, a:a.tagName+'.'+a.className,
                                  b:b.tagName+'.'+b.className};
  }
  return {overlap:false};
}
"""


def make_checks(required_sections):
    """Return a `functional(page)` hook that runs the content checks."""
    def checks(page):
        out = []

        # A section counts as present only if a HEADING names it -- a nav link
        # mentioning the word is not a section.
        heads = page.evaluate(
            "() => [...document.querySelectorAll('h1,h2,h3')]"
            ".map(e => (e.textContent||'').trim().toLowerCase())")
        missing = [s for s in required_sections
                   if not any(s.lower() in h for h in heads)]
        out.append({"name": "required_sections", "ok": not missing,
                    "detail": ("all present" if not missing
                               else "missing heading: " + ", ".join(missing))})

        page.set_viewport_size({"width": MOBILE_W, "height": 800})
        page.wait_for_timeout(120)
        ov = page.evaluate("() => ({sw: document.documentElement.scrollWidth,"
                           " cw: document.documentElement.clientWidth})")
        overflow = ov["sw"] - ov["cw"]
        out.append({"name": "mobile_no_overflow", "ok": overflow <= 2,
                    "detail": f"scrollWidth-clientWidth={overflow}px @{MOBILE_W}"})
        page.set_viewport_size({"width": 1280, "height": 900})
        page.wait_for_timeout(120)

        c = page.evaluate(_contrast_js())
        ok = c["worst"] is None or c["worst"] >= MIN_CONTRAST
        out.append({"name": "contrast", "ok": ok,
                    "detail": f"worst={c['worst']} on {c['sample']!r}"})

        o = page.evaluate(_overlap_js())
        out.append({"name": "no_overlap", "ok": not o["overlap"],
                    "detail": ("none" if not o["overlap"]
                               else f"{o.get('a')} over {o.get('b')}")})

        n_cta = page.evaluate(
            "() => document.querySelectorAll('button, a.cta, [role=button], "
            "input[type=submit]').length")
        out.append({"name": "has_cta", "ok": n_cta >= 1,
                    "detail": f"{n_cta} cta element(s)"})
        return out
    return checks
