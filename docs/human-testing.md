# Human testing handoff

Human review begins only after deterministic automation is exhausted. The
reviewer judges meaning and usability; they do not compensate for failed code,
missing evidence, unresolved oracle cases, or inadequate mutation coverage.

## 1. Mandatory automated checkpoint

Run from `gate/`:

```bash
uv run --with anthropic --with playwright --with pillow \
  python offline_all_check.py
```

It must finish with `OFFLINE PRE-HUMAN CHECKPOINT: PASS` and `$0` API spend.
This covers review/audit behavior, revision lifecycle, domain ambiguity,
mutation scoring, correct and known-broken functional controls, and the
four-vector exfiltration fixture.

For a generated candidate, every automated release check in its review packet
must also say `PASS`:

- baseline implementation passes;
- buggy control is rejected and demonstrably diverges;
- oracle contains cases with zero unresolved disputes;
- domain has zero unresolved clarifications;
- mutation target is met (100%, at least five execution-validated mutants).

The review API refuses `approved` while any check is missing or failed.

## 2. Inspect the exact candidate

```bash
uv run python review_cli.py list
uv run python review_cli.py list --eligible
uv run python review_cli.py show REVIEW_ID
```

The evidence packet is immutable and SHA-256-bound to the displayed revision.
Review exactly these questions:

1. Does the sharpened behavior describe what the user requested, without adding
   or silently removing important behavior?
2. Does the machine-readable domain match both the prose domain and what the UI
   can actually produce?
3. Are all oracle expectations correct under that behavior?
4. Does the scaffold expose the same function the visible UI uses?
5. Is the UI understandable and operable for the requested task?
6. If the specification contradicts a familiar convention, is that deviation
   intentional and unmistakable?

Do not re-test mechanical facts already marked `PASS` unless the dossier itself
looks inconsistent.

## 3. Record one auditable decision

```bash
uv run python review_cli.py resolve REVIEW_ID \
  --disposition approved \
  --reviewer-seconds 120 \
  --note "What was checked and why it is acceptable"
```

Use:

- `approved` only when the exact revision is suitable for production;
- `clarified` when the specification must change—this forces regeneration and a
  new revision;
- `rejected` when the candidate should not proceed.

Empty notes, approval of provisional findings, top-tier failures, failed
automated checks, and mismatched evidence are rejected by code.

For Q25, add any finding flags that occurred:

```bash
--unanimous-wrong-oracle
--spec-domain-mismatch
--ui-hook-divergence
--post-approval-failure
```

Omit a flag only when that issue was not observed. After all ten decisions:

```bash
uv run python review_cli.py q25-report
```

## 4. Prove release eligibility

```bash
uv run python review_cli.py status VERTICAL REVISION

uv run --with playwright --with pillow python verify_cli.py \
  --vertical VERTICAL --revision REVISION --require-approved ARTIFACT.html
```

Only `approved` permits the release path. Pending, unreviewed, stale,
clarified/rebuild-required, rejected, corrupt, or tampered states fail closed.

## 5. First human validation sample

Review at least ten current-format generated verticals before unattended use.
Record:

- approval / clarification / rejection;
- any wrong unanimous oracle value;
- any spec/domain mismatch;
- any UI-to-hook divergence;
- reviewer time;
- post-approval failures found later.

Stop unattended rollout immediately on any false accept, evidence/revision
mismatch, or unanimous wrong oracle. Revisit the automated gate before expanding
traffic. Small-sample results remain directional, not proof.
