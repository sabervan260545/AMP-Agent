# AMP-Agent Evals System Guide

> **TL;DR**: Evals turns agent regression and quality evaluation from "grep through logs and eyeball diffs" into a push-button, quantitative, and reproducible workflow.

---

## Table of Contents

1. [Overview & use cases](#1-overview--use-cases)
2. [Core concepts](#2-core-concepts)
3. [Quick start](#3-quick-start)
4. [Dashboard guide](#4-dashboard-guide)
5. [Snapshot baseline (reference run)](#5-snapshot-baseline)
6. [Diff](#6-diff)
7. [Scorers](#7-scorers)
8. [LLM-as-judge scorer](#8-llm-as-judge-scorer)
9. [Prompt fingerprint tracking](#9-prompt-fingerprint-tracking)
10. [Replay mode](#10-replay-mode)
11. [Concurrency](#11-concurrency)
12. [HTTP API reference](#12-http-api-reference)
13. [CLI usage](#13-cli-usage)
14. [Golden-prompt YAML authoring](#14-golden-prompt-yaml-authoring)
15. [Typical workflows](#15-typical-workflows)
16. [Troubleshooting](#16-troubleshooting)
17. [File layout](#17-file-layout)

---

## 1. Overview & use cases

### What it is

Evals is the **offline evaluation and regression-testing infrastructure** for AMP-Agent — think of it as unit tests + regression tests for the agent. It turns the fuzzy question "did this prompt/tool/model change help or hurt?" into objective, push-button, archivable metrics.

### Problems it solves

| Pain point                              | Traditional approach             | With Evals                                      |
| --------------------------------------- | -------------------------------- | ----------------------------------------------- |
| Regress a prompt change                 | Grep backend logs for evidence   | One click runs 14 cases; red / green at a glance |
| Judge "is the answer good?"             | Read outputs manually            | LLM-as-judge + rule scorers auto-score          |
| PR quality gate                         | Human review                     | Smoke suite < 30 s, CI-friendly                 |
| Reproduce a run from N days ago         | Virtually impossible             | env fingerprint + replay reproduce exactly      |
| Iterative optimization                  | Gut feel                         | Diff vs reference run pinpoints regressions     |

### When to use

- Confirm no regression after changing the system prompt / context engine / tools.
- Add an automated quality gate to every PR (smoke suite < 30 s).
- Iterate scorer logic without rerunning the agent (use replay).
- Track agent behaviour over time (nightly run + diff vs reference).
- Provide reproducible experiment evidence for papers and reports.

---

## 2. Core concepts

| Concept         | Meaning                                                                                               |
| --------------- | ----------------------------------------------------------------------------------------------------- |
| **Case**        | A single test: `{id, prompt, language, category, suite, expected_behaviors[]}`.                       |
| **Suite**       | A grouping (`smoke`, `nightly`, `release`) based on runtime budget.                                   |
| **Category**    | Business classification (`smoke`, `gen`, `rag`, `struct`, `mut`, `edge`).                             |
| **Behavior**    | One evaluation dimension — `scorer + params + weight`.                                                |
| **Scorer**      | Evaluator `(response, tool_calls, params)` → `(passed, score 0–1, reason)`.                           |
| **Run**         | Execution result: `{run_id, mode, total_cases, passed_cases, avg_score, cases[], meta}`.              |
| **Reference**   | A run pinned as baseline for later diffs.                                                             |
| **Diff**        | Case-level comparison between two runs (severity + delta).                                            |
| **Replay**      | Re-score an existing run's responses with current scorers — no agent calls, completes in seconds.     |

---

## 3. Quick start

### Step 1 — confirm the backend is running

```bash
curl http://localhost:5000/api/health
# {"service":"AMP Scientist Backend","status":"ok","version":"3.0"}
```

If it is not, bring it up with `docker compose up -d backend` (see `QUICKSTART.md`).

### Step 2 — open the dashboard

Navigate to `http://localhost:3000` and click the **Evals** tab in the left sidebar.

### Step 3 — trigger a dryrun (no API cost, ~0.4 s)

Click **Trigger Run** → mode `dryrun`, suite `smoke` → **Start Run**. A new row should appear with `passed=3/3`.

### Step 4 — upgrade to a live smoke run

Same modal, change mode to `live`, concurrency to `2` → **Start Run**. ~6 s later you will see three cases that actually exercise the agent.

### Step 5 — mark a reference and diff

On the fresh row click 🚩 **Mark Ref**. On the next run click **Diff vs Ref** to see the case-level comparison.

That closes the evaluation loop.

---

## 4. Dashboard guide

Source: [`frontend/src/components/EvalsDashboard.jsx`](../frontend/src/components/EvalsDashboard.jsx).

### Top stats cards

| Card        | Meaning                                                         |
| ----------- | --------------------------------------------------------------- |
| Total Cases | Number of cases in the YAML.                                    |
| Total Runs  | Total historical runs.                                          |
| Last Run    | Pass rate and average score of the latest run.                  |
| Reference   | Currently pinned baseline `run_id` (click to jump).             |

### Cases table

Filter by category / suite to decide which cases to run. Click a case to see its expected behaviours.

### Runs table (main action panel)

| Column / button | Purpose                                                                                             |
| --------------- | --------------------------------------------------------------------------------------------------- |
| Mode tag        | `dryrun` = grey, `live` = green, `replay` = purple.                                                 |
| Status          | Pass-rate badge; reference rows also show 🚩.                                                       |
| **Detail**      | Modal with env fingerprint + per-case score / verdicts / response preview.                          |
| **Mark Ref** 🚩 | Pin this row as the reference (overrides the previous one).                                        |
| **Diff vs Ref** | Case-level comparison against the current reference.                                                |
| **Replay**      | Re-score this row's responses with current scorers (no agent calls, ~2 s).                          |

### Trigger Run modal

| Field         | Default | Notes                                                                                |
| ------------- | ------- | ------------------------------------------------------------------------------------ |
| Mode          | dryrun  | `dryrun` = fixture-driven, `live` = real agent.                                      |
| Categories    | all     | Multi-select; empty means all.                                                       |
| Suite         | all     | Multi-select; commonly `smoke` for PR gating.                                        |
| Retry         | 0       | Per-case retry on failure, clamp `[0, 5]`.                                           |
| Concurrency   | 1       | Parallel workers (1/2/4/8). Live runs: keep ≤ 4 to respect DashScope rate limits.    |

> Live + concurrency > 1 shows a yellow warning banner about DashScope rate limits.

### Detail modal

- **Env card** — python version, platform, git commit, and a purple `prompt sha256_12` tag (hover for the full fingerprint).
- **Cases list** — expand a row to see all verdicts (one line per behaviour: score, reason, scorer name).
- **Response preview** — truncated display; the full response lives in `response_full` for replay.

### Diff modal

- Top statistics: avg delta, regressions, improvements, unchanged, `A∖B`.
- Cases table sorted by severity (worst first); each row shows `[severity tag] case_id a_score → b_score (Δ)`.
- Expand a case to see per-behaviour score changes.

---

## 5. Snapshot baseline

### Purpose

Pin the run that represents "today's release is green" as the golden baseline. Any future change can be diffed against it in one click to guarantee **no regression**.

### Implementation

The reference is a small sidecar file `_reference.json` stored under `agent/evals/runs/`:

```json
{
  "run_id": "20260501_112238",
  "marked_at": "2026-05-01T11:22:43.772213",
  "note": "v3.1 release baseline",
  "source_mode": "live",
  "source_set_file": "golden_prompts.yaml"
}
```

**Only one reference is active at a time.** Marking a new one overwrites the previous.

### Three operations

#### 5.1 Mark a reference

Frontend: click 🚩 **Mark Ref** on a run row.

API:

```bash
curl -X POST http://localhost:5000/api/evals/reference \
     -H 'Content-Type: application/json' \
     -d '{"run_id":"20260501_112238","note":"v3.1 baseline"}'
```

Python:

```python
from backend import evals_api
evals_api.set_reference("20260501_112238", note="v3.1 baseline")
```

#### 5.2 Inspect the reference

Frontend: the **Reference** stats card at the top.

API:

```bash
curl http://localhost:5000/api/evals/reference
# {
#   "reference": {"run_id": "...", "marked_at": "...", "note": "..."},
#   "summary":   {"run_id": "...", "mode": "live", "avg_score": 1.0, ...}
# }
```

#### 5.3 Clear the reference

Frontend: click the highlighted 🚩 again to toggle it off.

API:

```bash
curl -X DELETE http://localhost:5000/api/evals/reference
# {"reference": null}
```

### Recommended cadence

- Mark a reference manually before every release.
- Run nightly evaluations and diff against the reference; page the team on regressions.
- Before a large prompt/tool change, mark the current run as reference so the post-change comparison is meaningful.

---

## 6. Diff

### Seven severities (ordered by severity)

| Severity       | Colour | Trigger                              | Meaning                                |
| -------------- | ------ | ------------------------------------ | -------------------------------------- |
| `new_failure`  | red    | A passed, B failed                   | New regression (most severe)           |
| `regression`   | orange | Both passed, `B.score < A.score`     | Score dropped                          |
| `only_in_a`    | blue   | Exists in A only                     | Case removed from YAML                 |
| `only_in_b`    | blue   | Exists in B only                     | Case newly added                       |
| `improvement`  | green  | Both passed, `B.score > A.score`     | Score improved                         |
| `new_pass`     | green  | A failed, B passed                   | Previously failing case was fixed      |
| `unchanged`    | grey   | Identical verdicts                   | No change                              |

### Delta

`delta = B.score - A.score` — positive = improvement, negative = regression.

### How to trigger

Frontend: **Diff vs Ref** button — automatically uses the reference as A and the current row as B.

API:

```bash
curl 'http://localhost:5000/api/evals/diff?a=20260501_112238&b=20260501_112243'
```

Response:

```json
{
  "a": {"run_id":"...", "mode":"live", "avg_score":1.0, "total_cases":3, "passed_cases":3, "set_file":"golden_prompts.yaml"},
  "b": {"run_id":"...", "mode":"replay", "avg_score":1.0, "total_cases":3, "passed_cases":3, "set_file":"golden_prompts.yaml"},
  "avg_delta": 0.0,
  "summary":   {"regressions":0, "improvements":0, "unchanged":3, "only_in_a":0, "only_in_b":0, "total":3},
  "cases":     [{"case_id":"...", "severity":"unchanged", "delta":0.0, "a":{...}, "b":{...}}]
}
```

### Reading a diff

- Check `summary.regressions + summary.new_failures` first — both should be `0`.
- `avg_delta` is a macro signal but hides case-level swings; **the per-case severity is the real evidence**.
- The top row after sorting is the worst regression — attack it first.

---

## 7. Scorers

Source: [`agent/evals/scorers.py`](../agent/evals/scorers.py).

Every scorer takes the same three inputs and returns the same triple:

```python
def scorer(response: str, tool_calls: list, params: dict) -> tuple[bool, float, str]:
    ...  # returns (passed, score, reason)
```

Register with `@register("name")`. Adding a new scorer does not require runner changes — the YAML picks it up automatically.

### Built-in scorers

| Name                     | Purpose                       | Key params                                    |
| ------------------------ | ----------------------------- | --------------------------------------------- |
| `tool_name_count`        | Check how often a tool fired  | `tool` (str), `min_count` (int, default 1)    |
| `response_contains_any`  | Keyword matching              | `any_of` / `all_of` / `case_sensitive`        |
| `always_pass`            | Debug placeholder             | —                                             |
| `llm_judge`              | LLM semantic scoring          | See next section                              |

### Common behaviour block

```yaml
expected_behaviors:
  - name: invokes_search
    scorer: tool_name_count
    params: { tool: search_knowledge, min_count: 1 }
    weight: 1.0

  - name: mentions_mechanisms
    scorer: response_contains_any
    params:
      any_of: ["barrel-stave", "toroidal pore", "carpet"]
      case_sensitive: false
    weight: 1.0
```

### Case scoring

`case.score = Σ(behavior.score × behavior.weight) / Σ(behavior.weight)`.

`case.passed` is `True` only if **every** behaviour passes — any single failing behaviour fails the case (strict "all green" semantics).

---

## 8. LLM-as-judge scorer

### Use cases

Semantic situations where keyword matching is insufficient:

- "Does the answer correctly explain membrane-disruption mechanisms?"
- "Does it sidestep the user's real question?"
- "Does the code example follow PEP 8?"

### Example

```yaml
- name: semantic_judge_membrane_mechanism
  scorer: llm_judge
  params:
    rubric: |
      Pass if the response correctly explains at least two of the three classical
      AMP membrane-disruption mechanisms (barrel-stave, toroidal pore, carpet model)
      with brief mechanism details. Penalize hallucinations and unrelated content.
    threshold: 0.7
    model: qwen-plus
    on_error: fail
  weight: 1.0
```

### Parameters

| Param                | Type  | Default    | Notes                                                               |
| -------------------- | ----- | ---------- | ------------------------------------------------------------------- |
| `rubric`             | str   | required   | Judgement criteria (natural language).                              |
| `threshold`          | float | 0.7        | 0–1 pass threshold.                                                 |
| `model`              | str   | qwen-plus  | DashScope model name.                                               |
| `on_error`           | str   | fail       | `fail` / `skip` / `pass_with_warning`.                              |
| `user_prompt`        | str   | auto       | Runner injects `case.prompt` automatically.                          |
| `max_response_chars` | int   | 4000       | Truncate long responses to protect the judge's context window.       |

### `on_error` semantics

| Value                | passed | score | Notes                                                                 |
| -------------------- | ------ | ----- | --------------------------------------------------------------------- |
| `fail` (default)     | False  | 0.0   | Production default — infra failures must not hide regressions.        |
| `skip`               | True   | 0.0   | Temporarily skip; does not count against pass rate.                   |
| `pass_with_warning`  | True   | 0.5   | Compromise — keeps CI green but leaves a warning.                     |

### Runtime requirements

The backend container must have `DASHSCOPE_API_KEY` available (already plumbed via `docker-compose.yml`). The judge call uses:

- `temperature=0.0` — reproducible verdicts.
- `max_tokens=256` — bounded cost.
- `timeout=30s`.

### Example output

```
llm_judge score=1.00 (thr=0.70) :: Response correctly identifies all three mechanisms
(barrel-stave, toroidal pore, carpet) with accurate mechanism details. No hallucinations.
```

---

## 9. Prompt fingerprint tracking

### Purpose

Avoid the classic "the prompt we passed last time is whatever it is now" problem — every run records a fingerprint of the current system prompt.

### Where it lives

`run.meta.env.prompt`:

```json
{
  "source": "source-hash:context_engine.py,context_engine.py,__init__.py",
  "sha256_12": "53c5342962b0",
  "length": 56017,
  "version": null
}
```

### Dual strategy (`runner.capture_env_fingerprint`)

- **Strategy A** — try to `import build_system_prompt` from the known candidate paths, invoke it once, hash the assembled prompt.
- **Strategy B (fallback)** — hash the key source files directly: `utils/context_engine.py` + `context_engine.py` + `core/__init__.py`.

Both strategies produce the same structure; only the `source` field indicates which path was used.

### Optional: manual semantic version

Inject a semantic version via environment variable:

```bash
EVALS_PROMPT_VERSION=v3.1.2 docker compose restart backend
```

Every subsequent run records `meta.env.prompt.version = "v3.1.2"`, making it trivial to map runs to git tags.

### Frontend surface

The Detail modal's env card shows a purple tag — `prompt sha256_12=53c5342962b0`. Hover for the full source / length / version.

### Recommended usage

- After changing the prompt, rerun evals and verify `sha256_12` changed.
- If a diff shows different `sha256_12`, that explains the behavioural change.
- Track `sha256_12` drift in nightly runs — alert on unexpected changes.

---

## 10. Replay mode

### Purpose

Re-score existing runs after editing the YAML (new behaviours, new scorers, tuned thresholds) **without calling the agent again**.

### Speedup

- Typical: 5.8 s source live run → 0.02 s replay (~366×).
- Full 14-case live run: 25 s → 2.2 s replay (~11×).

### Mechanism

Since P1 each case persists `response_full` and `tool_calls`. Replay:

1. Loads the source run's cases.
2. Loads the current YAML's expected behaviours (which may differ from the original run).
3. Feeds each case's stored response / tool calls back into the current scorers.
4. Writes a new run with `meta.replay_of` pointing at the source.

### How to trigger

Frontend: **Replay** button (purple) on any run row.

API:

```bash
curl -X POST http://localhost:5000/api/evals/replay \
     -H 'Content-Type: application/json' \
     -d '{"source_run_id":"20260501_112238"}'
```

Optionally pass `set_file` to replay with a different YAML.

### New run meta

```json
{
  "replay_of":      "20260501_112238",
  "source_mode":    "live",
  "fallback_count": 0,
  "env":            { "...": "..." }
}
```

`fallback_count` counts cases without `response_full` (older runs might not have stored the full text — replay falls back to `response_preview`, which is noted for accuracy tracking).

### Typical recipe

1. Add a new behaviour to the YAML (for example, a `llm_judge` entry).
2. Find a historical live run and click **Replay**.
3. A new run appears within seconds with the new behaviour scored.
4. **Diff** the old run against the replay to see how the new behaviour performs on historical data.

Zero LLM calls, zero agent calls, seconds to execute.

---

## 11. Concurrency

### Motivation

In `live` mode each case calls the agent (tools + LLM), typically 5–15 s per case. Running 14 cases sequentially takes 100 s+; parallelism keeps it under 30 s.

### Measured speedup (dryrun, 14 cases)

| Mode                 | Duration | Speedup |
| -------------------- | -------- | ------- |
| seq (concurrency=1)  | 0.78 s   | 1×      |
| par (concurrency=4)  | 0.22 s   | 3.5×    |
| par (concurrency=8)  | 0.12 s   | 6.5×    |

### Configuration

Frontend: Trigger Run modal → concurrency dropdown (1/2/4/8).

API:

```bash
curl -X POST http://localhost:5000/api/evals/run \
     -H 'Content-Type: application/json' \
     -d '{"mode":"live","suites":["smoke"],"concurrency":4}'
```

CLI:

```bash
python -m agent.evals.runner --live --concurrency 4
```

### Implementation notes (`runner.run`)

- `concurrency=1` (default) keeps the original sequential path for backward compatibility.
- `concurrency>1` uses `ThreadPoolExecutor`: `as_completed` with index-preserving writes so case order is stable.
- Argument is clamped to `[1, 16]`.
- `meta.concurrency` is only set when `concurrency>1` — old runs are untouched.

### Caveats

- Live mode should stay at **concurrency ≤ 4** to avoid DashScope rate limits.
- Heavy GPU tools (structure, generator) may overlap VRAM usage — keep an eye on memory.
- The agent's ReAct loop inside a single case is still sequential.

---

## 12. HTTP API reference

| Method | Path                            | Purpose                                           | Body / Query                         |
| ------ | ------------------------------- | ------------------------------------------------- | ------------------------------------ |
| GET    | `/api/evals/health`             | Module availability                               | —                                    |
| GET    | `/api/evals/cases`              | List all cases                                    | —                                    |
| GET    | `/api/evals/runs`               | List all runs (with `is_reference` flag)          | —                                    |
| GET    | `/api/evals/runs/<run_id>`      | Run details                                       | —                                    |
| POST   | `/api/evals/run`                | Trigger a new run (synchronous)                   | See below                            |
| GET    | `/api/evals/reference`          | Get current reference                             | —                                    |
| POST   | `/api/evals/reference`          | Mark reference                                    | `{run_id, note?}`                    |
| DELETE | `/api/evals/reference`          | Clear reference                                   | —                                    |
| GET    | `/api/evals/diff`               | Case-level diff                                   | `?a=<run_id>&b=<run_id>`             |
| POST   | `/api/evals/replay`             | Re-score an existing run                          | `{source_run_id, set_file?}`         |

### `POST /api/evals/run` body

| Field          | Type    | Default     | Notes                                             |
| -------------- | ------- | ----------- | ------------------------------------------------- |
| `mode`         | str     | `dryrun`    | `dryrun` / `live`.                                |
| `categories`   | str[]   | all         | Filter by category.                               |
| `case_ids`     | str[]   | all         | Filter by explicit case ids.                      |
| `suites`       | str[]   | all         | Filter by suite.                                  |
| `set_file`     | str     | YAML default| Override the YAML path.                           |
| `api_base`     | str     | self        | Live only — override backend URL.                 |
| `retry`        | int     | 0           | Clamp `[0, 5]`; per-case retry on failure.        |
| `concurrency`  | int     | 1           | Clamp `[1, 16]`; parallel workers.                |

> This endpoint is synchronous. A full live run can take minutes — configure client timeouts to ≥ 10 minutes.

### Run-detail object (key fields)

```json
{
  "run_id":           "20260501_112238",
  "mode":             "live",
  "started_at":       "...",
  "duration_seconds": 5.8,
  "total_cases":      3,
  "passed_cases":     3,
  "avg_score":        1.0,
  "cases": [{
    "case_id":          "smoke_001_greeting",
    "passed":           true,
    "score":            1.0,
    "duration_ms":      2465,
    "verdicts":         [{"name":"greets_back", "scorer":"...", "passed":true, "score":1.0, "reason":"..."}],
    "response_preview": "Hello! ...",
    "response_full":    "Hello! ...",
    "tool_calls":       []
  }],
  "meta": {
    "set_file":    "golden_prompts.yaml",
    "concurrency": 2,
    "api_base":    "http://localhost:5000",
    "env": {
      "python_version": "3.10.x",
      "platform":       "Linux-...",
      "git_commit":     "...",
      "prompt": {"sha256_12":"53c5342962b0", "length":56017, "source":"...", "version":null}
    }
  }
}
```

---

## 13. CLI usage

Source: [`agent/evals/runner.py`](../agent/evals/runner.py).

```bash
python -m agent.evals.runner [options]
```

| Option                    | Default                   | Notes                                 |
| ------------------------- | ------------------------- | ------------------------------------- |
| `--set <path>`            | `golden_prompts.yaml`     | Case YAML.                            |
| `--dry-run` / `--live`    | `--dry-run`               | Mode.                                 |
| `--api-base <url>`        | `http://localhost:5000`   | Backend URL for live mode.            |
| `--category <name>`       | all                       | Repeatable.                           |
| `--case-id <id>`          | all                       | Repeatable.                           |
| `--suite <name>`          | all                       | Repeatable.                           |
| `--retry <n>`             | 0                         | Per-case retry on failure.            |
| `--concurrency <n>`       | 1                         | Parallel workers.                     |

### Common invocations

```bash
# Full dryrun — no API key required, sub-second feedback
python -m agent.evals.runner --dry-run

# Smoke suite on the live agent, with parallelism (PR-gate recommended)
python -m agent.evals.runner --live --suite smoke --concurrency 2

# Debug a single case with retry
python -m agent.evals.runner --live --case-id rag_001_membrane_mechanism --retry 2

# Nightly full run with parallelism
python -m agent.evals.runner --live --suite nightly --concurrency 4
```

Results land in `agent/evals/runs/<run_id>.json`; the CLI prints a PASS/FAIL summary.

---

## 14. Golden-prompt YAML authoring

Source: [`agent/evals/golden_prompts.yaml`](../agent/evals/golden_prompts.yaml).

### Full case template

```yaml
- id: rag_001_membrane_mechanism
  prompt: "Explain the membrane-disruption mechanisms of antimicrobial peptides."
  language: en               # en / zh
  category: rag              # smoke / gen / rag / struct / mut / edge
  suite: smoke               # smoke / nightly / release
  timeout_sec: 60            # optional; default 60
  expected_behaviors:
    - name: uses_search_knowledge
      scorer: tool_name_count
      params: { tool: search_knowledge, min_count: 1 }
      weight: 1.0

    - name: mentions_mechanisms
      scorer: response_contains_any
      params:
        any_of: ["barrel-stave", "toroidal pore", "carpet"]
        case_sensitive: false
      weight: 1.0

    - name: semantic_judge_membrane_mechanism
      scorer: llm_judge
      params:
        rubric: |
          Pass if the response correctly explains at least two classical
          AMP membrane-disruption mechanisms (barrel-stave, toroidal pore,
          carpet model) with brief mechanism details.
        threshold: 0.7
        on_error: fail
      weight: 1.0
```

### Authoring guidelines

- Every case should have at least two behaviours: one tool-call check + one content check.
- Keep the smoke suite to 3–5 cases aiming for < 30 s total.
- Prefer cheap and stable scorers (`tool_name_count`, `response_contains_any`). Reserve `llm_judge` for genuinely semantic dimensions.
- Write rubrics in English — DashScope/Qwen handle both languages, but English rubrics reproduce better.
- Do not put answers inside the rubric — it coaches the judge into handing out free points and kills discrimination.

---

## 15. Typical workflows

### A — PR gate (≈ 30 s)

```bash
# Runs locally or in CI
python -m agent.evals.runner --live --suite smoke --concurrency 2
echo $?   # 0 = all pass, non-zero = at least one failure
```

Wire this into GitHub Actions; smoke failure blocks merge.

### B — Confirming no regression after a prompt change

1. Before the change, the current nightly run is already marked as reference.
2. Change the prompt → `docker compose restart backend`.
3. Trigger a new nightly run (UI: Trigger Run, suite `nightly`, concurrency 4).
4. Click **Diff vs Ref** on the new row — case-level evidence immediately.
5. Verify `summary.regressions = 0` and that `meta.env.prompt.sha256_12` changed — safe to merge.

### C — Iterating on scorer logic (zero LLM spend)

1. Pick a historical live run that still has `response_full`.
2. Edit a behaviour in the YAML (e.g. tweak a `llm_judge` rubric).
3. Click **Replay** on that row — a new run appears in ~2 s, scored with the updated YAML.
4. **Diff** the two runs to see exactly which cases are affected.

### D — Release gold-standard flow

```bash
# 1. Full live run
python -m agent.evals.runner --live --concurrency 4

# 2. Verify all green, then mark the reference (UI or API)
curl -X POST http://localhost:5000/api/evals/reference \
     -H 'Content-Type: application/json' \
     -d '{"run_id":"20260501_xxxxxx","note":"v3.2.0 release baseline"}'

# 3. git tag v3.2.0 and record the run_id in the release notes
```

---

## 16. Troubleshooting

### Q1 — "evals module not available" when triggering a run

**Root cause**: the backend failed to import `agent/evals/`.

**Diagnosis**:

```bash
docker compose logs backend --tail 50 | grep -i eval
docker exec amp-backend python -c "from agent.evals import runner; print('ok')"
```

**Common causes**:

- Edited `agent/evals/*.py` without restarting the backend (`docker compose restart backend`).
- New dependency missing from `backend/requirements.txt` — rebuild the image (`docker compose build backend`).

### Q2 — Live run cannot reach `http://localhost:5000/api/chat`

**Root cause**: the runner cannot call the backend from within the container.

**Diagnosis**:

```bash
docker exec amp-backend curl -s http://localhost:5000/api/health
```

It should return HTTP 200. If not, the backend process likely crashed — check logs.

### Q3 — Every `llm_judge` fails with `DASHSCOPE_API_KEY missing`

**Root cause**: the environment variable is not reaching the container.

**Fix**:

```bash
# 1. Confirm the key exists in .env
grep DASHSCOPE <project_root>/.env

# 2. Confirm docker-compose.yml forwards it
grep -A 3 "environment:" <project_root>/docker-compose.yml | grep DASHSCOPE

# 3. Restart so the container picks up the new env
docker compose up -d backend
```

### Q4 — `meta.concurrency` is always `None`

**Root cause**: the backend is running stale code.

**Fix**:

```bash
docker compose restart backend
sleep 5
curl http://localhost:5000/api/health
# Trigger a new run — meta.concurrency should now be recorded.
```

### Q5 — Replay reports a high `fallback_count`

**Root cause**: the source run predates P1 and did not store `response_full`.

**Fix**: trigger a fresh live run (which stores the full response) and replay against that new run instead.

### Q6 — Diff shows many `only_in_b` cases

Expected when new cases were added but the reference is older. Either:

- Rerun and re-mark the reference, or
- Accept the `only_in_b` entries — they do not fail the diff, they are informational.

### Q7 — Vite reports a parse error in `EvalsDashboard.jsx`

Hard reload with `Ctrl+Shift+R`. If the error persists, clear the Vite cache:

```bash
rm -rf <project_root>/frontend/node_modules/.vite
lsof -ti:3000 | xargs kill -9
cd <project_root>/frontend && npm run dev
```

---

## 17. File layout

```
amp-generator-platform/
├── agent/evals/
│   ├── runner.py            # Core runner (ThreadPool + env fingerprint)
│   ├── scorers.py           # Scorer registry
│   ├── schema.py            # TestCase / CaseResult / RunResult models
│   ├── golden_prompts.yaml  # All case definitions
│   └── runs/                # Persisted history
│       ├── <run_id>.json
│       └── _reference.json  # Reference sidecar
├── backend/
│   ├── app.py               # /api/evals/* endpoints
│   └── evals_api.py         # list_runs / set_reference / diff_runs / replay_run
├── frontend/src/components/
│   └── EvalsDashboard.jsx   # Dashboard (Stats + Cases + Runs + Modals)
└── docs/
    └── EVALS_SYSTEM_GUIDE.md  # This document
```

---

## Related documents

- Services bring-up: [`QUICKSTART.md`](../QUICKSTART.md)
- User guide (includes the Evals entry): [`docs/user-guide/USER_GUIDE.md`](user-guide/USER_GUIDE.md)

---

**Version**: v1.0  
**Maintainer**: Chinfo Lab
