# AMP-Agent — Developer Guide

> Aimed at engineers who are joining the project. Read this first to grasp
> the architecture and start contributing quickly.

---

## 1. Project Overview

AMP-Agent is an **end-to-end AI-driven platform for autonomous antimicrobial
peptide (AMP) design**. A large language model (Qwen3.6-Plus) acts as the
central reasoning engine and orchestrates a fleet of specialized
microservices (generation, evaluation, structural prediction) to realise a
fully automated loop:

> *Natural-language brief → candidate sequences → multi-dimensional
>  evaluation → Pareto ranking → structural validation → knowledge feedback.*

**Highlights:**
- Multi-generator ensemble (AMP-Designer / HydrAMP / Diff-AMP).
- Four-dimensional evaluation (MIC / hemolysis / CPP / AMP probability).
- 3D Pareto non-dominated ranking + 6D weighted composite score.
- Dual-channel retrieval (Vector RAG + Graph RAG).
- ESMFold 3D-structure prediction.
- ReAct reasoning loop + Auto-Debug fault tolerance.
- Closed-loop round-to-round feedback.
- **Evals regression system** (Snapshot Baseline · Diff · LLM-as-judge ·
  Replay · parallel execution · prompt-version tracking).

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (React 19)                  │
│              Ant Design 6 · Plotly · 3Dmol.js           │
└──────────────────────┬──────────────────────────────────┘
                       │ REST + SSE
┌──────────────────────▼──────────────────────────────────┐
│                  Backend (Flask 3.0)                    │
│           app.py · database.py · graph_rag.py           │
└───────┬──────────────┬──────────────────┬───────────────┘
        │              │                  │
   ┌────▼────┐   ┌─────▼─────┐   ┌───────▼───────┐
   │  Agent  │   │ PostgreSQL│   │   Scheduler   │
   │  (V3)   │   │ +pgvector │   │ (Redis Queue) │
   └────┬────┘   └───────────┘   └───────────────┘
        │
        │  HTTP calls to microservices
        ▼
┌───────────────────────────────────────────────────────┐
│              Microservice Cluster (Docker)            │
│                                                       │
│  Generator · Macrel · MIC · Hemolysis · CPP           │
│  Structure (ESMFold) · HydrAMP · Diff-AMP · PGAT-ABPP │
│                                                       │
│  (port / GPU bindings live in docker-compose.yml)     │
└───────────────────────────────────────────────────────┘
```

**Data flow:**
1. The user submits a natural-language request from the frontend.
2. The backend relays it to the Agent over SSE (streaming).
3. The Agent (ReAct loop) parses the intent, invokes tools, and orchestrates
   the microservices.
4. Results are persisted to SQLite / PostgreSQL.
5. Closed-loop feedback is injected into the next-round system prompt.

---

## 3. Repository Layout

```
amp-agent/
├── agent/                      # AI agent core
│   ├── amp_agent_v3.py         # Main Agent class (2438 lines), ReAct loop
│   ├── tools.py                # 15 tool functions (2774 lines)
│   ├── app.py                  # Streamlit UI (fallback frontend)
│   ├── context_engine.py       # System-prompt builder + feedback injection
│   ├── tool_orchestrator.py    # Dynamic Docker orchestration (generator mutex)
│   ├── auto_debugger.py        # Three-tier fault recovery (pattern/LLM/log)
│   ├── structured_output.py    # Structured output for reasoning + citations
│   ├── peptide_visualizer.py   # Physchem visualization (helical wheel /
│   │                           # radar / hydrophobicity curve)
│   ├── knowledge_retriever.py  # ChromaDB vector-retrieval wrapper
│   ├── evals/                  # Offline eval + regression testing
│   │   ├── runner.py           # Main entry point (747 lines)
│   │   ├── scorers.py          # 4 built-in scorers (270 lines)
│   │   ├── schema.py           # TestCase / CaseResult / RunResult
│   │   ├── golden_prompts.yaml # Primary test suite
│   │   ├── smoke_live.yaml     # CI smoke suite
│   │   └── results/            # Run artefacts (run-<id>.json, _reference.json)
│   ├── docker_utils.py         # Docker API helpers
│   └── tool_call_logger.py     # Tool-call logging
│
├── backend/                    # Flask backend API
│   ├── app.py                  # 25+ REST endpoints (1349 lines)
│   ├── database.py             # DB management (SQLite + PostgreSQL, 1101 lines)
│   ├── graph_rag.py            # Graph-RAG query interface (347 lines)
│   └── migrate_ontology_to_postgres.py  # Ontology migration script
│
├── frontend/                   # React frontend
│   ├── src/
│   │   ├── App.jsx             # Main router (6 pages)
│   │   └── components/
│   │       ├── ChatPanel.jsx           # SSE streaming chat (549 lines)
│   │       ├── SequencePanel.jsx       # Sequence library (615 lines)
│   │       ├── ServiceHealth.jsx       # Microservice health (488 lines)
│   │       ├── LogViewer.jsx           # Tool-call log viewer (955 lines)
│   │       ├── GraphRAGTest.jsx        # Hybrid-RAG query (768 lines)
│   │       └── StructureDemoGuide.jsx  # User guide (629 lines)
│   ├── package.json            # React 19 + Ant Design 6 + Plotly
│   └── vite.config.js          # Dev proxy to localhost:5000
│
├── services/                   # Microservice cluster (independent images)
│   ├── 01-amp-designer/        # GPT sequence generator (GPU 3)
│   ├── 02-esm2/                # ESM-2 embedding service
│   ├── 03-macrel/              # AMP classification screen (CPU)
│   ├── 04-mic/                 # MIC regression (GPU 3, ensemble)
│   ├── 05-hemolysis/           # Hemolysis estimation (GPU 2)
│   ├── 06-cpp/                 # Cell-penetrating peptide prediction (GPU 2)
│   ├── 07-structure/           # ESMFold 3D structure prediction (GPU 1)
│   ├── 09-hydramp/             # VAE conditional generator (CPU, on-demand)
│   ├── 10-diff-amp/            # GAN+RL generator (CPU, on-demand)
│   └── 11-pgat-abpp/           # Graph-attention structural discriminator (CPU)
│
├── knowledge_builder/          # Knowledge-base builders
│   ├── literature_processor.py    # Literature parser (sequence/MIC/mechanism)
│   ├── prepare_raw_json.py        # PDF → JSON pre-processing
│   ├── integrated_knowledge_base/ # Build artefacts
│   └── raw_literature/            # Raw literature input
│
├── amp_knowledge_base/         # Knowledge-base configuration
│   ├── code_rag.json           # Code-example library
│   ├── data_rag.json           # Experimental datasets
│   └── spell_agent_config.json # Agent configuration
│
├── data/                       # Runtime data
│   ├── amp_platform.db         # SQLite database
│   ├── models/                 # Shared model weights
│   └── pgat_runs/              # Structure-discrimination runs
│
├── docker-compose.yml          # Whole-stack orchestration
└── .env                        # Environment variables (DASHSCOPE_API_KEY, ...)
```

---

## 4. Technology Stack

| Layer | Technology | Version / Notes |
|-------|------------|-----------------|
| **Frontend** | React | 19.2 |
| | Ant Design | 6.1 |
| | Plotly.js | Interactive charts |
| | 3Dmol.js | 3D molecule visualization |
| | Vite | Dev server + build |
| **Backend** | Flask | 3.0.0 |
| | SQLAlchemy | ORM (optional) |
| | SSE | Streaming protocol |
| **AI engine** | Qwen3.6-Plus | 1 M-token context, DashScope API |
| **Vector retrieval** | ChromaDB | Local vector DB |
| | Sentence Transformers | all-mpnet-base-v2, 768-dim |
| **Graph DB** | PostgreSQL + pgvector | Ontology + vector retrieval |
| **Containers** | Docker Compose | Whole-stack orchestration |
| **Task queue** | Redis | Async job scheduling |
| **Deep learning** | PyTorch / TensorFlow | Microservice model inference |

---

## 5. Microservice Topology

| Service | Container | Startup |
|---------|-----------|---------|
| AMP-Designer | amp-designer | Always on |
| Macrel | macrel | Always on |
| MIC prediction | mic | Always on |
| Hemolysis | hemolysis | Always on |
| CPP | cpp | Always on |
| ESMFold | structure | Always on |
| HydrAMP | hydramp | **On-demand** |
| Diff-AMP | diff-amp | **On-demand** |
| PGAT-ABPP | pgat-abpp | On-demand |

> **Port & GPU bindings** are defined in `docker-compose.yml`; adjust them
> to match your deployment hardware.
>
> **Mutex rule:** HydrAMP and Diff-AMP cannot run concurrently (VRAM
> protection). `ToolOrchestrator` manages start/stop automatically.

---

## 6. Core Modules

### 6.1 Agent Core (`amp_agent_v3.py`)

**Class sketch:**
```python
class AMPAgentV3:
    def __init__(self):
        # Init Qwen client, tool registry, database, orchestrator

    def chat(user_input, max_iterations=10):
        # Main entry: ReAct loop (Think → Tool → Observe → repeat)

    def _handle_design_pipeline(args):
        # Full design pipeline: generate → evaluate → rank → visualize

    def _handle_analyze_pipeline(args):
        # Single-sequence analysis: physchem → structure → SAR explanation

    def _handle_mutate_pipeline(args):
        # Mutation optimization: rule-based mutation → re-eval → comparison

    def _execute_tool_with_retry(func, name, params, max_retries=3):
        # Tool execution with Auto-Debugger recovery
```

**ReAct loop:**
1. Build system prompt (knowledge context + closed-loop feedback).
2. The LLM emits Thought + Tool-call JSON.
3. Parse tool name & params → route to the corresponding function in `tools.py`.
4. Append the execution result as Observation.
5. Repeat until the LLM emits the final answer or `max_iterations` is hit.

### 6.2 Tool Library (`tools.py`)

**15 registered tools:**

| Category | Function | Purpose |
|----------|----------|---------|
| **Generation** | `tool_generate_amp` | Generator call + automatic 4D evaluation |
| | `tool_generate_sequences_only` | Generate only, skip evaluation |
| **Evaluation** | `tool_batch_evaluate` | Batch evaluation (Macrel + MIC + Hemo + CPP) |
| | `tool_predict_mic_only` | MIC only |
| | `tool_predict_hemolysis_only` | Hemolysis only |
| | `tool_predict_cpp_only` | CPP only |
| **Ranking** | `tool_rank_sequences` | Pareto / MIC-only / Balanced ranking |
| **Structure** | `tool_predict_structure` | ESMFold 3D prediction |
| **Visualization** | `tool_visualize_peptide_structure` | Helical wheel + radar + hydrophobicity |
| | `tool_visualize_generator_comparison` | Generator comparison plot |
| **Knowledge** | `tool_search_knowledge` | Vector-RAG literature search |
| | `tool_query_ontology` | Ontology overview |
| | `tool_query_mechanisms_for_target` | Target → mechanism reasoning |
| | `tool_query_principles_for_mechanism` | Mechanism → design-principle reasoning |

**Two ranking algorithms:**
- **Classic pipeline** `_apply_pareto_ranking`: 3D Pareto non-dominated
  ranking (MIC / Hemo / CPP); non-frontier sequences are re-ranked by the
  weighted sum (MIC 0.50, Hemo 0.30, CPP 0.20).
- **Structural pipeline** `_balanced_multidim_rank`: 6D weighted composite
  score (MIC 0.40, Hemo 0.25, CPP 0.15, Helix 0.10, pLDDT 0.05,
  Compactness 0.05).

### 6.3 Context Engine (`context_engine.py`)

**Responsibilities:**
- `build_system_prompt(language, feedback)` — dynamically build the prompt.
  - Role definition (AMP design expert + multi-tool orchestrator).
  - Safety disclaimer (every metric is a **model prediction**, not an
    experimental measurement).
  - Knowledge-first policy (RAG results > LLM parametric knowledge).
  - Tool-call discipline (strict JSON format).
  - **Closed-loop feedback** — the previous round's avg MIC / Hemo /
    CPP / AMP probability.

### 6.4 Auto-Debugger (`auto_debugger.py`)

**Three-tier fault recovery:**
1. **Pattern match** (fast path): `type_mismatch` → auto type conversion;
   `missing_param` → default value fill-in.
2. **LLM repair**: ship the error to Qwen and let the model fix the params.
3. **Logging**: every failure is written to a log for later inspection.

### 6.5 Knowledge Base

**Vector RAG (ChromaDB):**
- 5 collections: `literature_knowledge` / `mic_data` / `cpp_data` /
  `hemolysis_data` / `motif_patterns`.
- 575 literature chunks + 482 MIC records.
- Embeddings: `all-mpnet-base-v2`, 768-dim.

**Graph RAG (PostgreSQL + pgvector):**
- 327 entities / 856 relations / 4 entity types.
- Entity types: Target, Mechanism, Principle, Design.
- Relation types: `mentions` / `targets` / `guides`.
- Multi-hop reasoning supported: Target → Mechanism → Principle.

### 6.6 Database (`database.py`)

**Core columns in `sequences`:**

| Column | Type | Description |
|--------|------|-------------|
| sequence | TEXT NOT NULL | Amino-acid sequence |
| generator | TEXT NOT NULL | Source generator |
| session_id | TEXT | Session identifier |
| mic_value | REAL | Predicted MIC (μM) |
| hemolysis_score | REAL | Hemolysis score (0–1) |
| cpp_score | REAL | CPP probability |
| amp_score | REAL | AMP probability |
| is_pareto_optimal | INTEGER | Pareto-frontier flag |
| helix_fraction | REAL | α-helix fraction |
| mean_plddt | REAL | Fold confidence |
| verified | INTEGER | Experimentally verified flag |
| experimental_mic | REAL | Experimental MIC value |
| exported_to_ontology | INTEGER | Exported-to-KB flag |

**Unique constraint:** `(sequence, generator, session_id)` — idempotent storage.

### 6.7 Evals System (`agent/evals/`)

**Purpose**: offline regression + baseline snapshots + behavioural
assertion. Run the smoke suite before every Agent / prompt / tool change to
guarantee no behaviour regression.

**Three execution modes:**

| Mode | Real LLM | Latency / case | Use case |
|------|----------|----------------|----------|
| `live` | ✅ | ~5 s | PR gating / regression checks |
| `mock` | ❌ (stub response) | ~50 ms | CI smoke / scorer development |
| `replay` | ❌ (replay past outputs) | ~0.02 s | Tune scorers without burning tokens |

**Six capabilities:**

| Capability | Implementation | Artefact |
|------------|----------------|----------|
| Snapshot Baseline | `/api/evals/reference` marks any run as the gold standard | `results/_reference.json` sidecar |
| Diff | 7 severities (new_failure / regression / improvement / new_pass / only_in_a / only_in_b / unchanged) | `GET /api/evals/diff?a=&b=` |
| LLM-as-judge | Qwen scores 0–1 against a rubric; `on_error ∈ {fail, skip, pass_with_warning}` | `scorers.py::llm_judge` |
| Prompt version tracking | Each run persists `env.prompt.sha256_12` | `runner.py::capture_env_fingerprint` |
| Replay | Reuse previous live outputs, re-run scorers only | `POST /api/evals/replay` |
| Parallel execution | `ThreadPoolExecutor`, concurrency clamped to `[1,16]` | `runner.py::run` |

**4 built-in scorers:** `tool_name_count` / `response_contains_any` /
`always_pass` / `llm_judge`. A case's `passed` is `all(scorers_passed)`.

**Frontend entry**: sidebar **Evals Dashboard** (`/evals`).
**CLI entry**: `python -m agent.evals.runner --live --suite smoke --concurrency 2`.
**Full doc**: [`docs/EVALS_SYSTEM_GUIDE.md`](./docs/EVALS_SYSTEM_GUIDE.md)
(17-chapter guide).
**Algorithmic details**:
[`CORE_ALGORITHMS.md §11 — Evals System`](./CORE_ALGORITHMS.md).

---

## 7. API Endpoint Cheat Sheet

### Core chat
| Method | Route | Purpose |
|--------|-------|---------|
| POST | `/api/chat` | SSE streaming chat (main entry) |
| GET  | `/api/health` | Service health check |

### Sequence management
| Method | Route | Purpose |
|--------|-------|---------|
| GET  | `/api/sequences` | Query sequence library (pagination / filter) |
| GET  | `/api/sequences/statistics` | Population statistics plots |
| POST | `/api/visualize` | Single-sequence visualization |
| GET  | `/api/sequences/export/<format>` | Export CSV / Excel / FASTA |
| GET  | `/api/sequences/<seq>/download-package` | Download full ZIP package |
| POST | `/api/sequences/mark_verified` | Tag experimental validation |
| POST | `/api/sequences/export_to_ontology` | Export to knowledge ontology |

### Knowledge retrieval
| Method | Route | Purpose |
|--------|-------|---------|
| GET | `/api/knowledge/search` | Vector-RAG search |
| GET | `/api/ontology/overview` | Ontology overview |
| GET | `/api/graph_rag/mechanisms_for_target` | Target → mechanism query |
| GET | `/api/graph_rag/principles_for_mechanism` | Mechanism → principle query |

### Operations
| Method | Route | Purpose |
|--------|-------|---------|
| GET | `/api/services/health` | Microservice cluster health |
| GET | `/api/logs` | Tool-call logs |
| GET | `/api/database/stats` | Database statistics |
| GET | `/api/debug/failures` | Failure analytics |

### Evals (10 endpoints)
| Method | Route | Purpose |
|--------|-------|---------|
| GET    | `/api/evals/health` | Service heartbeat |
| GET    | `/api/evals/cases` | List discoverable suites & cases |
| GET    | `/api/evals/runs` | Run history |
| GET    | `/api/evals/runs/<id>` | Run details |
| POST   | `/api/evals/run` | Trigger a new run (mode / suite / concurrency / retry) |
| GET    | `/api/evals/reference` | Query the baseline |
| POST   | `/api/evals/reference` | Mark the baseline |
| DELETE | `/api/evals/reference` | Clear the baseline |
| GET    | `/api/evals/diff?a=&b=` | Diff between two runs |
| POST   | `/api/evals/replay` | Replay a historical run |

---

## 8. Deployment & Startup

### 8.1 Requirements

- Docker & Docker Compose
- NVIDIA GPU(s) recommended when running the GPU-bound microservices
  (ESMFold / MIC / Hemolysis / CPP / AMP-Designer); exact device
  assignment is configured in `docker-compose.yml`.
- DashScope API key (for Qwen model calls)

### 8.2 Environment variables

Set in the root-level `.env`:

```bash
DASHSCOPE_API_KEY=your-dashscope-api-key-here
```

PostgreSQL credentials (already wired in `docker-compose.yml`):

```
POSTGRES_USER=amp_user
POSTGRES_PASSWORD=your_password_here
POSTGRES_DB=amp_ontology
```

### 8.3 Start-up steps

```bash
# 1. Clone the project
cd <PROJECT_ROOT>

# 2. Populate environment variables
cp .env.example .env      # if present; edit .env directly otherwise

# 3. One-shot start of every service
docker compose up -d

# 4. Inspect service status
docker compose ps

# 5. Tail backend logs
docker compose logs -f backend
```

### 8.4 Service health checks

After startup, hit the following endpoints to confirm readiness:

```bash
# Backend API
curl http://localhost:5000/api/health

# Microservice cluster (via the backend proxy)
curl http://localhost:5000/api/services/health

# Frontend
curl http://localhost:80
```

### 8.5 Run the dev stack standalone

```bash
# Frontend dev server (hot reload)
cd frontend && npm install && npm run dev
# → http://localhost:5173, API proxy to localhost:5000

# Backend dev
cd backend && pip install -r requirements.txt && python app.py
# → http://localhost:5000
```

---

## 9. Contributing Conventions

### 9.1 Code style

- **Python**: PEP 8 + type annotations on function signatures.
- **JavaScript / React**: ESLint config, function components + hooks.
- **SSE streaming messages**: throttle rendering with `requestAnimationFrame`
  to avoid performance issues from high-frequency `setState`.

### 9.2 Feature-development checklists

**Adding a new generator:**
1. Create `services/0X-name/` as a FastAPI service.
2. Register the container + port + GPU in `docker-compose.yml`.
3. Register the tool-to-container mapping in `agent/tool_orchestrator.py`.
4. Add a `tool_generate_xxx()` function in `agent/tools.py`.
5. Update the generator options in `agent/context_engine.py`.

**Adding a new evaluation metric:**
1. Create `services/0X-metric/` prediction service.
2. Add `tool_predict_xxx_only()` in `agent/tools.py`.
3. Integrate the new metric into `tool_batch_evaluate()`.
4. Add visualization in `agent/peptide_visualizer.py`.
5. Add a column to the `sequences` table in `backend/database.py`.

**Extending the knowledge base:**
1. Drop new literature into `knowledge_builder/raw_literature/`.
2. Run `python knowledge_builder/run_pdf_processing.py`.
3. ChromaDB re-indexes automatically; RAG queries work immediately.

### 9.3 Evaluation metric ranges

| Metric | Range | Direction | Description |
|--------|-------|-----------|-------------|
| MIC | 0–100 μM | ↓ lower is better | Minimum inhibitory concentration |
| Hemolysis | 0–1 | ↓ lower is better | Hemolysis score (not a percentage) |
| CPP | 0–1 | ↑ higher is better | Cell-penetration probability |
| AMP prob | 0–1 | ↑ higher is better | AMP classification probability |
| pLDDT | 0–100 | ↑ higher is better | Fold-confidence score |

---

## 10. Current Status

### Completed ✅

- [x] Three-generator ensemble (AMP-Designer / HydrAMP / Diff-AMP).
- [x] Four-dimensional evaluation pipeline (MIC / Hemo / CPP / AMP).
- [x] 3D Pareto non-dominated ranking + 6D weighted composite score.
- [x] ESMFold structure prediction + 3Dmol.js visualization.
- [x] Dual-channel knowledge base (Vector RAG + Graph RAG,
      327 entities / 856 relations).
- [x] ReAct reasoning loop + three-tier Auto-Debug recovery.
- [x] Round-to-round closed-loop feedback.
- [x] Sequence library (2,847 sequences / 28,470 prediction records).
- [x] Experimental-validation tagging + ontology-export round-trip.
- [x] React frontend (6 feature modules + SSE streaming).
- [x] Docker Compose whole-stack orchestration.
- [x] Multi-format export (CSV / Excel / FASTA / ZIP).
- [x] Generator mutex management (VRAM protection).
- [x] Structural discrimination pipeline (PGAT-ABPP supplementary check).
- [x] **Evals regression system** (Snapshot Baseline / Diff / LLM-as-judge /
      Replay / parallel execution / prompt-version tracking, 10 HTTP endpoints).

### Stage

The project is **feature-complete and in the manuscript phase** (NSR
submission). Core functionality is implemented and stable.

---

## 11. FAQ

**Q: Why does the structural pipeline not use Pareto ranking?**
A: It involves six dimensions (MIC / Hemo / CPP / Helix / pLDDT /
Compactness). High-dimensional Pareto suffers from the "curse of
dimensionality" — almost every solution becomes non-dominated, which
destroys the discriminative value. A weighted composite score is used
instead.

**Q: Why can HydrAMP and Diff-AMP not run concurrently?**
A: They share GPU resources; loading both simultaneously blows the VRAM
budget. `ToolOrchestrator` enforces mutex groups and stops the unused
service automatically when the other is activated.

**Q: How do I inspect the Agent's reasoning trace?**
A: The **Tool Logs** page in the frontend records every tool call with
inputs, outputs, latency, and status. The same data is available from
`/api/logs`.

**Q: Are all the evaluation metrics model predictions?**
A: Yes — MIC / Hemo / CPP / AMP are **model predictions**, not
experimental measurements. The system prompt states this explicitly.
Experimental values are captured separately via `mark_verified`.

**Q: I changed a prompt / agent logic; how do I confirm no regression?**
A: Run the Evals smoke suite —
`python -m agent.evals.runner --live --suite smoke --concurrency 2` —
then open **Evals Dashboard** in the frontend and diff against the
baseline (Mark Ref → Diff vs Ref). Any case with severity
`regression` or `new_failure` must be fixed before merging. See
[`CORE_ALGORITHMS.md §11`](./CORE_ALGORITHMS.md) for details.
