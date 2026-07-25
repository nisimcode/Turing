"""Phase 2 kill check (first cut): does the gate hold on REAL generated games?

Generates N Wordle builds from the cheap tier WITH the contract in the prompt,
gates each, and reports:
  * contract conformance rate (do models actually expose window.__wordle?) --
    low => the contract gate FALSE-REJECTS good games
  * functional pass rate among conformant builds (cheap tier's real reliability, Q5)
  * overall gate pass rate

Then gates a "sneaky" fixture (correct hook, non-functional game) to expose
whether the gate's acceptance criteria have COVERAGE GAPS (false-accept risk).

    uv run --with anthropic --with playwright --with pillow python kill_check.py
"""

import os
import re
import sys
from pathlib import Path

import anthropic

from browser_gate import gate_html
import wordle_spec

N = 6
MODEL = "claude-haiku-4-5"
HERE = Path(__file__).resolve().parent
CORPUS = HERE / "corpus"

PROMPT = (
    "Build a complete, working Wordle game as a SINGLE self-contained HTML file "
    "(inline CSS and JavaScript, no external assets): a fixed 5-letter secret "
    "word, up to 6 guesses, color each letter green/yellow/gray with correct "
    "duplicate-letter handling, detect win and loss.\n\n"
    "ADDITIONALLY, expose a testable hook on window:\n"
    "  window.__wordle = {\n"
    "    setAnswer(word),           // force the secret (5 letters, any case)\n"
    "    guess(word) -> string      // 5 chars of 'G'/'Y'/'B', correct duplicate handling\n"
    "  }\n"
    "'G'=right letter right spot, 'Y'=in word wrong spot (limited by remaining "
    "counts after greens), 'B'=absent.\n\n"
    "Return ONLY the HTML in a single code block."
)


def load_api_key() -> str:
    for var in ("ANTHROPIC_API_KEY", "CLAUDE_API_KEY"):
        if os.environ.get(var):
            return os.environ[var]
    for env_path in (HERE / ".env", HERE.parent / ".env"):
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith(("CLAUDE_API_KEY=", "ANTHROPIC_API_KEY=")):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("No API key found (set CLAUDE_API_KEY in E:\\Turing\\.env).")


client = anthropic.Anthropic(api_key=load_api_key())


def generate():
    resp = client.messages.create(
        model=MODEL, max_tokens=8192,
        messages=[{"role": "user", "content": PROMPT}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    m = re.search(r"```(?:html)?\s*\n(.*?)```", text, re.DOTALL)
    return m.group(1) if m else text


def check(v, name):
    return next((c for c in v["checks"] if c["name"] == name), None)


def main():
    CORPUS.mkdir(exist_ok=True)
    print(f"Generating {N} Wordle builds from {MODEL} with the contract...\n")
    print(f"{'build':10} {'floor':6} {'contract':9} {'logic':6} overall")
    print("-" * 45)

    results = []
    for i in range(N):
        html = generate()
        p = CORPUS / f"gen_{i}.html"
        p.write_text(html, encoding="utf-8")
        v = gate_html(p, functional=wordle_spec.functional_checks)
        results.append(v)
        floor = all(c["ok"] for c in v["checks"]
                    if c["name"] not in ("contract", "wordle_logic"))
        con = check(v, "contract")
        logic = check(v, "wordle_logic")
        print(f"gen_{i:<6} "
              f"{'ok' if floor else 'FAIL':6} "
              f"{('ok' if con and con['ok'] else 'MISSING'):9} "
              f"{('ok' if logic and logic['ok'] else ('FAIL' if logic else '-')):6} "
              f"{'PASS' if v['passed'] else 'FAIL'}")

    conformant = [v for v in results if (check(v, "contract") or {}).get("ok")]
    logic_ok = [v for v in conformant
                if (check(v, "wordle_logic") or {}).get("ok")]
    overall = [v for v in results if v["passed"]]

    print("\n=== rates (first cut, N={}) ===".format(N))
    print(f"  contract conformance:      {len(conformant)}/{N}")
    print(f"  coloring correct (of conformant): {len(logic_ok)}/{len(conformant) or 0}")
    print(f"  overall gate PASS:         {len(overall)}/{N}")

    # --- coverage-gap probe: correct hook, non-functional game ---
    print("\n=== coverage probe: sneaky fixture (correct hook, dead game) ===")
    sneaky = gate_html(HERE / "fixtures" / "wordle_hook_only.html",
                       functional=wordle_spec.functional_checks)
    print(f"  wordle_hook_only.html -> {'PASS' if sneaky['passed'] else 'FAIL'}")
    if sneaky["passed"]:
        print("  => FALSE ACCEPT: a non-playable game passed because the gate only")
        print("     checks the hook + runtime floor, not that the UI actually plays.")
        print("     Coverage gap -> acceptance criteria must expand (win/lose, board")
        print("     updates via real UI). This is the next layer of gate work.")


if __name__ == "__main__":
    main()
