# Logic-tool benchmark

This corpus is a deterministic regression benchmark for the public manifest
gate. It does not call a model or claim to measure market adoption.

`logic-tools-v1.json` contains six domains and twelve subjects:

- Shipping threshold and duration calculations.
- Email validation.
- Slug and CSV formatting.
- Tic-tac-toe winner rules.

Each domain uses one artifact exposing `correct` and deliberately `broken`
hooks. Its paired manifests invoke those hooks against the same cases. This
keeps the artifact, runtime floor, domain declaration, and oracle fixed while
the implementation changes.

Run the human-readable report:

```bash
uv run python gate/offline_benchmark_check.py
```

Or consume stable JSON:

```bash
uv run python gate/offline_benchmark_check.py --json
```

The checkpoint passes only when:

- Every correct control is accepted.
- Every broken control is rejected.
- Every rejection fails the expected check.
- The failure detail identifies the intended edge case.

It reports false accepts, false rejects, diagnostic hits, total runtime, median
runtime, and p95 runtime, with category rollups. The index is directory-confined
and its escape control is exercised on every run.

## Mechanical-fault challenge

`mutation-probes-v1.json` supplies exact inputs that are disjoint from every
scored manifest case. For each correct subject,
`offline_benchmark_mutation_check.py`:

1. Checks the correct implementation against both independent probes and scored
   cases.
2. Generates local one-site source mutations without a model call.
3. Counts a mutant only when execution demonstrates a wrong result on an
   independent probe.
4. Reports whether the existing manifest cases kill it, including every
   survivor.

Run it with the release requirement:

```bash
uv run python gate/offline_benchmark_mutation_check.py --require-perfect
```

The first run killed 22/27 validated mutants (81%). It exposed two missing
email-anchor checks and three missing bottom-row game checks. Distinct scored
values—not the validation witnesses—were added, after which 27/27 were killed.
This history is retained because the initial gap is the useful evidence.

## Interpretation limit

The paired faults and cases are hand-authored together. The mechanical faults
are generated separately and validated on exact-disjoint probes, but still come
from a small fixed operator set over six toy domains. A perfect result proves
stable coverage of these controls; it does not estimate production error rates
or guarantee detection of arbitrary defects. Hosted CI results are setup and
regression evidence, not users in the 20/5/3 adoption target.

## Adding a domain

1. Add one self-contained HTML artifact with correct and broken hooks.
2. Bind both hooks to identical cases in paired manifests.
3. Include at least one ordinary case before the intended edge defect.
4. Add both subjects to `logic-tools-v1.json`.
5. Require the broken subject’s expected failed check and diagnostic substring.
6. Mark the correct implementation with the two
   `BENCHMARK_CORRECT_START/END` comments.
7. Add exact-disjoint independent probes to `mutation-probes-v1.json`.
8. Run both benchmarks and the full zero-credit checkpoint.
