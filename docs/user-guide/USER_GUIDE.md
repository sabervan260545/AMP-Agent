# AMP-Agent Platform — User Guide

## Table of Contents

1. [Quick start](#quick-start)
2. [Architecture and deployment prerequisites](#architecture-and-deployment-prerequisites)
3. [Tool Orchestrator](#tool-orchestrator)
4. [Usage scenarios](#usage-scenarios)
5. [Quality gate: the Evals system](#quality-gate-the-evals-system)
6. [Troubleshooting](#troubleshooting)

---

## Quick start

### Minimal bring-up (three steps)

```bash
# 1. Start every microservice (always do this first)
cd <project_root>
docker compose up -d

# 2. Health-check
curl http://localhost:5000/api/health

# 3. Launch the frontend
cd frontend && npm run dev
```

Access the UI at `http://localhost:3000`.

---

## Architecture and deployment prerequisites

### Critical concept: deployment vs orchestration

These two ideas are often conflated; getting them wrong prevents the agent from running at all.

| Concept       | Purpose                                          | When it runs           | Required?             |
| ------------- | ------------------------------------------------ | ---------------------- | --------------------- |
| Deployment    | Creates Docker containers, networks, and volumes | Once, before use       | Mandatory             |
| Orchestration | Starts and stops containers on demand            | Automatically at runtime | Optimization layer   |

Analogy:

- **Deployment** is laying the wiring and plumbing in a house.
- **Orchestration** is the smart-home system that turns lights on and off automatically.
- Without the wiring, the smart switches have nothing to control.

---

### Deployment inventory (eight microservices)

After `docker compose up -d`, the following containers exist:

```
$ docker compose ps

NAME            STATUS          PORTS
amp-backend     Up              :5000
amp-designer    Up              :8000
amp-macrel      Up              :8001
amp-mic         Up (idle)       :8002
amp-hemolysis   Up (idle)       :8003
amp-cpp         Up (idle)       :8004
amp-structure   Up (idle)       :8005
amp-diff-amp    Up (idle)       :8006
amp-hydramp     Up (idle)       :8007
```

#### 1. Always-on services

- `amp-backend` — Flask API (the brain).
- `amp-designer` — baseline AMP generator.
- `amp-macrel` — AMP-activity predictor.

Startup time: < 5 seconds. Low resource footprint. Always online.

#### 2. On-demand services

- `amp-mic` — MIC prediction (GPU, ≈ 8 GB VRAM).
- `amp-hemolysis` — hemolysis prediction (GPU, ≈ 6 GB VRAM).
- `amp-cpp` — cell-penetration prediction (GPU, ≈ 6 GB VRAM).
- `amp-structure` — ESMFold (GPU, ≈ 10 GB VRAM).

Startup: 5–15 seconds. Heavier footprint. Auto-stopped when idle.

#### 3. Mutually exclusive services

- `amp-diff-amp` — structure-guided generator (heavy GPU).
- `amp-hydramp` — helicity-biased generator (heavy GPU).

**These two cannot run simultaneously** — doing so triggers OOM.

---

## Tool Orchestrator

### How it works

The Tool Orchestrator is the core scheduling component of AMP-Agent. It can only operate after deployment is complete.

```python
from agent.tool_orchestrator import ToolOrchestrator

# 1. Initialize (connects to the Docker API)
orchestrator = ToolOrchestrator()
# ^ requires the Docker containers to already exist.

# 2. Execute a tool call
result = orchestrator.execute(
    fn_name="design_new_amps",
    args={"target": "E. coli", "num_samples": 5},
)
# ^ auto-starts dependencies (e.g. amp-mic, amp-hemolysis) as needed.
```

### Strategies

**1. Intelligent start/stop**

```
User: "design 5 peptides against E. coli"
Agent detects MIC / Hemolysis evaluation is needed
  → starts amp-mic and amp-hemolysis
  → runs the design task
  → stops idle services after 10 minutes (VRAM savings)
```

**2. Mutual exclusion**

```
User: "use Diff-AMP to generate structure-optimized sequences"
Agent checks whether HydrAMP is running
  → if so, stops it first
  → starts Diff-AMP
  → runs the task
  → returns to the default state afterwards
```

**3. Resource-footprint management**

```python
if gpu_memory_used > threshold:
    stop_service("amp-cpp")
    stop_service("amp-hemolysis")
```

---

### Manual control (optional)

Full auto-orchestration is recommended, but manual intervention is always available.

#### Python API

```python
from agent.tool_orchestrator import ToolOrchestrator

orchestrator = ToolOrchestrator()

# List active services
print(f"Active tools: {orchestrator.active_tools}")
# => {'amp-designer', 'amp-macrel'}

# Start a specific service
orchestrator.start_service("mic")

# Stop a specific service
orchestrator.stop_service("hemolysis")

# Reset to the default state (only baseline services alive)
orchestrator.reset_to_default_state()
```

#### Docker CLI

```bash
# Inspect all services
docker compose ps

# Start a single service
docker compose up -d amp-mic

# Stop a single service
docker compose stop amp-hemolysis

# Start several at once
docker compose up -d amp-mic amp-hemolysis amp-cpp

# Restart a service
docker compose restart amp-structure
```

---

## Usage scenarios

### Scenario 1 — Rapid design (default mode)

**Goal**: quickly obtain a batch of candidate AMPs.

```
User: "Design 10 AMPs against Gram-negative bacteria"

Execution:
├── ReAct loop parses intent
├── Tool Orchestrator auto-starts:
│   ├── amp-designer (already up)
│   ├── amp-mic (cold start, ~12 s)
│   └── amp-macrel (already up)
├── Generates 10 sequences
├── Evaluates MIC + Macrel in parallel
├── Returns the Pareto-optimal top 10
└── Shuts down amp-mic after 10 min idle

Total time: ~25 s
Peak VRAM: ~12 GB
```

---

### Scenario 2 — Multi-property optimization (full evaluation)

**Goal**: balance activity, toxicity, and cell permeability.

```
User: "Design 5 potent AMPs with low toxicity and high cell permeability"

Execution:
├── Parse requirements (MIC + Hemolysis + CPP)
├── Tool Orchestrator starts:
│   ├── amp-designer ✓
│   ├── amp-mic (~12 s)
│   ├── amp-hemolysis (~8 s)
│   └── amp-cpp (~8 s)
├── Generate → Evaluate → Rank
└── Return the Pareto-optimal solutions

Total time: ~35 s
Peak VRAM: ~18 GB
```

---

### Scenario 3 — Structure-based verification

**Goal**: design informed by 3D structure.

```
User: "Design AMPs targeting E. coli membrane using structure-based approach"

Execution:
├── Detect keywords: "structure-based", "ESMFold", "PGAT"
├── Tool Orchestrator with mutual exclusion:
│   ├── Stop HydrAMP if running
│   ├── Start amp-diff-amp (~15 s)
│   ├── Start amp-structure / ESMFold (~20 s)
│   └── Start amp-pgat-abpp / PGAT classifier (~5 s)
├── Structure-discrimination pipeline:
│   ├── Generate candidates
│   ├── ESMFold predicts 3D structures
│   ├── PGAT-ABPp graph classifier
│   │   ├── Phase 1: antimicrobial probability (Score ≥ 0.5 = active)
│   │   └── Phase 2: mechanism label (Membrane disruption vs Non-membrane)
│   └── MIC / Hemolysis / CPP evaluation
└── Return sequences that pass PGAT with stable folds

Total time: ~60 s
Peak VRAM: ~24 GB (Diff-AMP + ESMFold + PGAT concurrent)
```

**Key PGAT-ABPp metrics**:

- **Phase 1 score** — antimicrobial probability (0–1), recommended threshold ≥ 0.5.
- **Phase 2 prediction** — mechanism:
  - `Membrane disruption` — membrane disruption.
  - `Non-membrane` — intracellular target.
- **Why it matters** — unlike a pure Macrel score, PGAT also explains the likely mechanism.

---

### Scenario 3b — Full structure-aware generation

**Goal**: de-novo design of AMPs with stable 3D structures.

```
User: "Generate 10 AMPs with stable 3D structures using structure-based design"

Execution:
├── ReAct loop recognises structure-discrimination keywords:
│   ├── "structure-based" → ESMFold
│   ├── "stable structure" → PGAT classifier
│   └── "generate" → Diff-AMP as the generator
├── Tool Orchestrator starts a service chain:
│   ├── amp-diff-amp (~15 s)
│   ├── amp-structure (~20 s)
│   ├── amp-pgat-abpp (~5 s)
│   ├── amp-mic (~12 s)
│   └── amp-hemolysis (~8 s)
├── Three-stage filtering pipeline:
│   ├── Stage 1 — generate candidates (Diff-AMP → 50 sequences)
│   ├── Stage 2 — structural feasibility
│   │   ├── ESMFold predicts 3D structure
│   │   └── PGAT-ABPp Phase 1 (Score ≥ 0.5)
│   │       └── Rejection rate: ~60 % (≈ 20 sequences remain)
│   ├── Stage 3 — functional evaluation
│   │   ├── MIC (Gram-negative / Gram-positive)
│   │   ├── Hemolysis
│   │   └── CPP
│   └── Multi-objective Pareto ranking
├── Return Top-10 sequences, each with:
│   ├── FASTA sequence
│   ├── PDB structure file
│   ├── PGAT score + mechanism label
│   ├── MIC / Hemolysis / CPP predictions
│   └── Pareto-front rank
│   + visualizations (3D view + radar chart)
└── Idle heavy services shut down after 10 min

Total time: ~90 s (includes structure prediction + classification)
Peak VRAM: ~26 GB (Diff-AMP + ESMFold + PGAT + MIC concurrent)
```

**Highlights**:

- End-to-end loop from sequence to structure verification.
- PGAT provides both "is it antimicrobial?" and "what mechanism?".
- Structure-first strategy — verify folding feasibility before spending compute on function evaluation.
- Outputs are interpretable (sequence + 3D structure + mechanism).

**When to use**:

- Need AMPs with known 3D structure (for docking / simulations).
- Studying membrane vs intracellular mechanism.
- Improving structural stability of existing peptides.

**When not to use**:

- Rapid high-throughput screening — the standard pipeline is cheaper.

---

### Scenario 4 — Benchmarking multiple generators

**Goal**: fair comparison of generator performance.

```
User: "Compare Diff-AMP, HydrAMP, and Designer for generating AMPs"

Execution:
├── Detect comparison intent
├── Tool Orchestrator schedules sequentially:
│   ├── Start amp-designer → generate 20 → evaluate → stop
│   ├── Start amp-diff-amp  → generate 20 → evaluate → stop
│   └── Start amp-hydramp   → generate 20 → evaluate → stop
├── Aggregate metrics per generator
├── Produce an HTML comparison table
└── Return to the default state

Total time: ~2 min
Peak VRAM: ~15 GB (only one heavy generator at a time)
```

---

## Quality gate: the Evals system

AMP-Agent ships with an **offline evaluation and regression-testing system** called Evals. It turns the question "did this prompt / tool change help or hurt?" into a push-button, quantitative, reproducible engineering metric. **Run the smoke suite before merging any change that affects agent behaviour.**

### One-minute tour

1. Open `http://localhost:3000` → left sidebar → **Evals**.
2. Click **Trigger Run**. Set `Mode=live`, `Suite=smoke`, `Concurrency=2`, then **Start Run**.
3. In about 6 s a run row appears: `passed=3/3`, `avg=1.000`, green badge.

### Capability overview

| Capability              | Solves                                                                                               | Entry point                      |
| ----------------------- | ---------------------------------------------------------------------------------------------------- | -------------------------------- |
| Snapshot baseline       | Pins a run as reference so any future change can be one-click diffed                                  | Runs table → Mark Ref            |
| Diff                    | Case-level comparison with seven severities                                                          | Runs table → Diff vs Ref         |
| LLM-as-judge            | Qwen scores open-ended answers 0–1 with fail-closed semantics                                        | YAML `scorer: llm_judge`         |
| Replay                  | Re-score historical responses with the current scorers (~366× speedup, no LLM cost)                  | Runs table → Replay              |
| Prompt fingerprint      | Every run logs the system-prompt sha256 + length                                                      | Detail modal (purple tag)        |
| Concurrency             | Run live cases in parallel (1 / 2 / 4 / 8)                                                           | Trigger Run modal                |

### Typical usages

**PR gate (≈ 30 s)**

```bash
python -m agent.evals.runner --live --suite smoke --concurrency 2
# exit 0 = pass, non-zero = block the merge
```

**Regression confirmation after a prompt change**

1. Before the change, pin the nightly run as reference.
2. After the change, trigger a new run and click **Diff vs Ref**.
3. Verify `summary.regressions = 0` and that `meta.env.prompt.sha256_12` updated.

**Iterate on scorers without spending tokens**

Edit the YAML `expected_behaviors`, click **Replay** on a historical live run, and diff the two runs.

### HTTP API cheat sheet

```bash
GET    /api/evals/cases                  # all cases
GET    /api/evals/runs                   # all runs (with is_reference flag)
POST   /api/evals/run                    # trigger a run
GET    /api/evals/reference              # current baseline
POST   /api/evals/reference              # mark baseline
DELETE /api/evals/reference              # clear baseline
GET    /api/evals/diff?a=...&b=...       # case-level diff
POST   /api/evals/replay                 # re-score an existing run
```

### Full reference

Full feature reference, API docs, scorer spec, troubleshooting, and YAML authoring rules live in [`docs/EVALS_SYSTEM_GUIDE.md`](../EVALS_SYSTEM_GUIDE.md).

---

## Troubleshooting

### Issue 1 — "Tool Orchestrator initialization failed"

Symptoms:

```
Error: Docker client initialization failed
Connection refused to /var/run/docker.sock
```

Root cause: the backend was started before `docker compose up -d`.

Fix:

```bash
docker compose down
docker compose up -d
docker compose ps          # verify containers exist
docker compose restart backend
```

---

### Issue 2 — "Service start timed out"

Symptom: `Timeout waiting for amp-mic to start (elapsed: 30s)`.

Possible causes:

- GPU VRAM exhausted.
- Docker network misconfiguration.
- Corrupted image.

Fix:

```bash
nvidia-smi                    # check VRAM
docker compose build amp-mic  # rebuild the image
docker network prune -f       # clean up networks
docker compose up -d amp-mic
```

---

### Issue 3 — Mutually exclusive services running together → OOM

Symptom:

```
CUDA out of memory. Tried to allocate 2.5 GiB
GPU 0: Diff-AMP + HydrAMP both running!
```

Root cause: a bug in the Tool Orchestrator failed to enforce mutual exclusion.

Quick fix:

```bash
docker compose stop amp-hydramp
```

Long-term fix: verify `GENERATOR_GROUP` in `tool_orchestrator.py` and the mutex check in `start_service`.

```python
self.GENERATOR_GROUP = ["diff_amp", "hydramp"]
```

---

### Issue 4 — "First call is slow"

Symptom: the first request takes 20–30 s, subsequent ones 3–5 s.

Root cause: cold-start cost for on-demand services.

Option A (recommended): pre-warm the commonly used services.

```bash
docker compose up -d amp-mic amp-hemolysis
```

Option B: accept the first-call latency (more energy-efficient).

---

## Performance reference

### Deployment phase

| Operation              | Time      | Notes                          |
| ---------------------- | --------- | ------------------------------ |
| `docker compose up -d` | 30–60 s   | Creates all containers         |
| Health check           | ≈ 5 s     | Verifies every service is up   |

### Runtime (on-demand services)

| Service       | Start time | VRAM  | RAM  |
| ------------- | ---------- | ----- | ---- |
| amp-designer  | always on  | 0.5 GB | 2 GB |
| amp-mic       | ~12 s      | 8 GB   | 4 GB |
| amp-hemolysis | ~8 s       | 6 GB   | 3 GB |
| amp-cpp       | ~8 s       | 6 GB   | 3 GB |
| amp-structure | ~20 s      | 10 GB  | 6 GB |
| amp-diff-amp  | ~15 s      | 12 GB  | 8 GB |
| amp-hydramp   | ~10 s      | 10 GB  | 6 GB |

### Typical task budget

| Task                         | Total time | Peak VRAM |
| ---------------------------- | ---------- | --------- |
| Rapid design (5 sequences)   | ~25 s      | ~12 GB    |
| Full evaluation (MIC/Hemo/CPP) | ~35 s    | ~18 GB    |
| Structure verification       | ~50 s      | ~22 GB    |
| Multi-generator comparison   | ~2 min     | ~15 GB    |

---

## Related documents

- Quick start: `<project_root>/QUICKSTART.md`
- Evals system: [`docs/EVALS_SYSTEM_GUIDE.md`](../EVALS_SYSTEM_GUIDE.md)
- Architecture: [`docs/architecture/PROJECT_ARCHITECTURE.md`](../architecture/PROJECT_ARCHITECTURE.md)
- Skills guide: [`docs/SKILLS_GUIDE.md`](../SKILLS_GUIDE.md)
- Structure discrimination pipeline: [`docs/STRUCTURE_DISCRIMINATION_PIPELINE.md`](../STRUCTURE_DISCRIMINATION_PIPELINE.md)

---

**Version**: v1.0  
**Maintainer**: Chinfo Lab
