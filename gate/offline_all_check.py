"""One-command, zero-API checkpoint before human review begins.

This composes every deterministic regression and controlled bad artifact. It
must pass before spending credits or asking a person to judge a new vertical.

    uv run --with anthropic --with playwright --with pillow \
        python offline_all_check.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gate.core import verify
from offline_benchmark_check import main as benchmark_check
from offline_lifecycle_check import main as lifecycle_check
from offline_manifest_check import main as manifest_check
from offline_q21_check import main as q21_check
from offline_q24_check import main as q24_check
from offline_q25_check import main as q25_check
from offline_q26_check import main as q26_check
from offline_review_check import main as review_check
from wordle_spec import functional_checks as wordle_checks

HERE = Path(__file__).resolve().parent


def controlled_artifacts() -> None:
    correct = verify(
        HERE / "fixtures" / "wordle_correct.html",
        functional=wordle_checks,
        vertical="wordle",
    )
    broken = verify(
        HERE / "fixtures" / "wordle_broken.html",
        functional=wordle_checks,
        vertical="wordle",
    )
    exfiltration = verify(
        HERE / "fixtures" / "exfiltrate.html",
        vertical="sandbox_probe",
    )
    assert correct.passed, correct.summary()
    assert not broken.passed
    assert "wordle_logic" in broken.failed_checks()
    assert not exfiltration.passed
    assert exfiltration.failed_checks() == ["no_outbound_requests"]


def main() -> int:
    assert review_check() == 0
    assert lifecycle_check() == 0
    assert manifest_check() == 0
    assert benchmark_check([]) == 0
    assert q21_check() == 0
    assert q24_check() == 0
    assert q25_check() == 0
    assert q26_check() == 0
    controlled_artifacts()
    print("OFFLINE PRE-HUMAN CHECKPOINT: PASS")
    print("  review workflow + lifecycle: PASS")
    print("  public manifest + three adoption demos: PASS")
    print("  paired multi-domain benchmark: PASS")
    print("  domain ambiguity + mutation scoring: PASS")
    print("  Q25 dossier preparation controls: PASS")
    print("  Q26 paired economics + hidden holdouts: PASS")
    print("  correct Wordle accepted; broken Wordle rejected")
    print("  exfiltration fixture rejected (4/4 requests blocked)")
    print("  API spend: $0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
