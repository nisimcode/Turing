"""gate.core -- the reusable verification module.

    from gate.core import verify
    v = verify("build.html", functional=wordle_checks)
    print(v.passed, v.failed_checks())

Everything runs sandboxed (network-isolated, ephemeral origin, fresh context).

Verification does NOT require the Anthropic SDK -- only generation does, so the
`llm` helpers are imported lazily. That keeps `verify()` usable in a minimal
environment (CI, a container with just Playwright).
"""

from .config import (CHEAP, MID, ORACLE_ENSEMBLE, ORACLE_MODEL, PRICING, STRONG,
                     TIERS, Verdict, get_logger, load_api_key)
from .sandbox import sandboxed_page
from .verify import print_verdict, verify

_LAZY = {"call", "extract_code", "cost_report", "reset_cost", "total_cost",
         "client"}

__all__ = [
    "verify", "print_verdict", "Verdict", "sandboxed_page",
    "CHEAP", "MID", "STRONG", "TIERS", "PRICING",
    "ORACLE_MODEL", "ORACLE_ENSEMBLE", "load_api_key", "get_logger",
    *sorted(_LAZY),
]


def __getattr__(name):
    """Import the LLM helpers only when actually used (PEP 562)."""
    if name in _LAZY:
        from . import llm
        return getattr(llm, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
