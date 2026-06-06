# AMP Agent Evals

Regression testing harness for the AMP Agent (Step 1 skeleton).

## Goals

1. Quantify Agent behavior across prompt / tool / skill changes.
2. Provide a baseline that future changes can be diffed against.
3. Act as reproducibility evidence for Nature Communications submission.

## Structure

```
evals/
├── __init__.py
├── README.md              <-- this file
├── schema.py              <-- dataclasses (TestCase, CaseResult, RunResult)
├── golden_prompts.yaml    <-- benchmark prompts
├── scorers.py             <-- generic scoring utilities
├── runner.py              <-- CLI entry point
└── results/               <-- per-run JSON (baseline.json after first real run)
```

## Quick start

Dry run (no real Agent call, validates skeleton only):

```bash
docker exec amp-backend python -m agent.evals.runner --dry-run
```

Expected output: a summary printed to stdout and a JSON file written to
`agent/evals/results/dryrun_YYYYMMDD_HHMMSS.json`.

## Design principles

- **Pure addition**: no existing file is modified.
- **Progressive**: Step 1 = skeleton + mock runner. Step 2 = real Agent API
  binding. Step 3 = REST endpoints. Step 4 = frontend Dashboard.
- **Language consistent**: all code comments and messages are in English,
  following the project-wide Python comment convention.

## Scoring model

Each `TestCase` declares `expected_behaviors`. Scorers inspect the Agent
response + tool-call trace and emit a `{pass: bool, score: float 0-1,
reason: str}` verdict per behavior. The case-level score is the mean of
all its behavior scores.

## Status

Step 1 (skeleton only) — see [runner.py](runner.py) `--dry-run`.
Next: Step 2 wires runner into the real Agent HTTP API.
