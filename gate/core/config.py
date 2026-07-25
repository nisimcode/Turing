"""Shared configuration -- one place for keys, tiers, pricing and limits.

Replaces the copy-pasted load_api_key()/PRICING blocks that each research script
carried its own version of.
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent      # repo root
GATE = ROOT / "gate"

# --- model tiers, cheapest first -------------------------------------------
CHEAP = "claude-haiku-4-5"
MID = "claude-sonnet-5"
STRONG = "claude-opus-4-8"

# price per 1M tokens: (input, output)
PRICING = {
    CHEAP: (1.00, 5.00),
    MID: (3.00, 15.00),
    STRONG: (5.00, 25.00),
}

# The strong tier is the oracle authority (D23): cheap tiers revert to their
# training prior on specs that contradict convention.
ORACLE_MODEL = STRONG

# Oracle ensemble must be tier-DIVERSE (D22): N samples of one model are one
# opinion, not N. Disagreement is a tripwire, never a vote (D21).
ORACLE_ENSEMBLE = (CHEAP, CHEAP, MID, STRONG)

# --- limits ----------------------------------------------------------------
PAGE_TIMEOUT_MS = 10_000
SETTLE_MS = 600


@dataclass(frozen=True)
class Verdict:
    """Result of gating one artifact."""
    passed: bool
    checks: list[dict]
    artifact: str = ""

    def failed_checks(self) -> list[str]:
        return [c["name"] for c in self.checks if not c["ok"]]

    def summary(self) -> str:
        head = "PASS" if self.passed else "FAIL"
        bad = self.failed_checks()
        return f"{head}" + (f" ({', '.join(bad)})" if bad else "")


def load_api_key() -> str:
    """ANTHROPIC_API_KEY / CLAUDE_API_KEY env, else CLAUDE_API_KEY from .env."""
    for var in ("ANTHROPIC_API_KEY", "CLAUDE_API_KEY"):
        if os.environ.get(var):
            return os.environ[var]
    for env_path in (ROOT / ".env", GATE / ".env"):
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith(("CLAUDE_API_KEY=", "ANTHROPIC_API_KEY=")):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("No API key. Set CLAUDE_API_KEY in .env (see .env.example).")


def get_logger(name: str = "gate") -> logging.Logger:
    log = logging.getLogger(name)
    if not log.handlers:
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)-5s %(name)s: "
                                         "%(message)s", "%H:%M:%S"))
        log.addHandler(h)
        log.setLevel(os.environ.get("GATE_LOG", "INFO").upper())
    return log
