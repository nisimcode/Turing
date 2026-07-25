# Escalation dry run

A low-cost smoke test to decide whether the **cheap→expensive escalation** idea
is worth pursuing — before building anything larger.

It runs 8 small Python coding problems (easy→hard) through three approaches and
measures each objectively (the generated code is *run against tests*):

1. **Cheap only** — Haiku 4.5 does everything
2. **Expensive only** — Opus 4.8 does everything (the baseline to beat)
3. **Escalation** — Haiku first; if its code fails the tests, retry with Opus

For each approach you get: tasks passed, total cost, avg latency, and
**cost per passed task** (the headline number — it catches a "cheap" approach
that only looks cheap because it's shipping failures).

## Run it

```
cd E:\Turing\eval
pip install -r requirements.txt
python run_eval.py
```

The API key is read automatically from `E:\Turing\.env` (`CLAUDE_API_KEY=...`),
or from the `ANTHROPIC_API_KEY` / `CLAUDE_API_KEY` environment variables.

Expected cost: roughly a few cents to ~$0.10 for the whole run.

## Reading the result

The script prints a **verdict** at the end. The question it answers: did
escalation match the expensive baseline's pass rate at meaningfully lower cost?
If yes, there's something here worth building. If no, you've spent ~$0.10 to
learn that before investing weeks.

This is a directional smoke test (one attempt per task), not a statistically
powered study.
