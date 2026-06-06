# AMP-Agent

**An End-to-End LLM-Driven Platform for Autonomous Antimicrobial Peptide Design**

AMP-Agent couples a large language model (Qwen) with a fleet of specialized
microservices to transform natural-language design requirements into
Pareto-ranked antimicrobial peptide (AMP) candidates with 3D structural
evidence — fully autonomously.

---

## ⚠️ About This Release — Minimal Release Mode

This repository is the **public release edition** of AMP-Agent, shipped in
**Minimal Release Mode**:

- The **coordination layer** — Flask backend, React frontend, PostgreSQL
  ontology store, knowledge-base builder, agent / orchestrator / RAG /
  evals code — is shipped in full and is runnable out of the box.
- The nine **AMP prediction / generation microservices** under
  `services/*/` are shipped as **directory placeholders**. Each contains
  only an `IMPLEMENTATION.md` that documents the upstream model, the
  expected API contract, the model weights and step-by-step restore
  instructions. No `app.py`, `Dockerfile`, weights or third-party source
  are included.

### Why
Every microservice wraps a third-party model (ESM-2, ESMFold, HydrAMP,
Macrel, HemoPI2, CPPpred, PGAT-ABPp, …) governed by its own upstream
licence. To keep this release licence-unambiguous and lightweight
(~17 MB total), the upstream code and weights are **not redistributed**.
Deployers fetch them on demand from the original sources referenced in
each `services/*/IMPLEMENTATION.md`.

### What you can do right now
- Boot the coordination layer (`docker compose up -d`) — starts backend,
  frontend, Postgres and the knowledge-base builder.
- Inspect every API contract, architecture document and pipeline spec.
- Rebuild the vector knowledge base
  (`python knowledge_builder/rebuild_index.py`) and query it.
- Review the full agent / orchestrator / evals / Pareto ranker code.

### What requires re-deployment by you
Anything that hits a microservice route: AMP generation, MIC /
hemolysis / CPP scoring, structure prediction, HydrAMP / Diff-AMP
sampling, PGAT-ABPp classification. Each `services/*/IMPLEMENTATION.md`
has a 5-step recipe (clone upstream → fetch weights → provide
`app.py` → un-comment the `docker-compose.yml` block → rebuild).

See [`QUICKSTART.md`](QUICKSTART.md) → *Minimal Release Mode* for the
full operating model.

---

## ✨ Key Features (in the full deployment)

> ℹ️ Features marked *[microservice]* require restoring the corresponding
> `services/*/` entry as described above.

- **Multi-Generator Ensemble** *[microservice]* — AMP-Designer, HydrAMP,
  and Diff-AMP orchestrated behind a unified interface.
- **Four-Dimensional Evaluation** *[microservice]* — MIC, hemolysis,
  cell-penetration (CPP), and AMP probability, each provided by a
  dedicated microservice.
- **3D Pareto Ranking + 6D Weighted Composite Score** — transparent
  multi-objective selection of candidates (coordination layer).
- **Hybrid Retrieval-Augmented Generation** — Vector RAG + Graph RAG
  over a curated AMP knowledge base (coordination layer).
- **ESMFold Structural Validation** *[microservice]* — 3D folding +
  helicity metrics on demand.
- **ReAct Reasoning Loop + Auto-Debug** — robust agent with self-healing
  tool-use errors (coordination layer).
- **Closed-Loop Feedback** — per-round results are injected back into
  the next system prompt (coordination layer).
- **Evals Regression System** — snapshot baseline · diff · LLM-as-judge ·
  replay · parallel execution · prompt-version tracking (coordination
  layer).

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Frontend (React 19)                    │   ← shipped
│           Ant Design · Plotly · 3Dmol.js                │
└──────────────────────┬──────────────────────────────────┘
                       │ REST + SSE
┌──────────────────────▼──────────────────────────────────┐
│                  Backend (Flask 3.0)                    │   ← shipped
└───────┬──────────────┬──────────────────┬───────────────┘
        │              │                  │
   ┌────▼────┐   ┌─────▼─────┐   ┌───────▼───────┐
   │  Agent  │   │ PostgreSQL│   │   Scheduler   │        ← shipped
   │  (V3)   │   │ +pgvector │   │ (Redis Queue) │
   └────┬────┘   └───────────┘   └───────────────┘
        │  HTTP calls
        ▼
┌───────────────────────────────────────────────────────┐
│      Microservice Cluster (placeholder directories)   │   ← placeholders
│                                                       │
│  Generator · Macrel · MIC · Hemolysis · CPP           │
│  Structure (ESMFold) · HydrAMP · PGAT-ABPp            │
│                                                       │
│  See services/<name>/IMPLEMENTATION.md to restore     │
└───────────────────────────────────────────────────────┘
```

See [`DEVELOPER_GUIDE.md`](DEVELOPER_GUIDE.md) for the full architecture
walk-through and [`CORE_ALGORITHMS.md`](CORE_ALGORITHMS.md) for the
mathematical core.

---

## 🚀 Quick Start

### Prerequisites

- **Docker** 24+ and **Docker Compose** v2
- **Node.js** 18+ (for the frontend dev server)
- A **DashScope API key** or any OpenAI-compatible endpoint
  *(only if you will exercise the Agent)*
- **NVIDIA GPU** (≥ 10 GB VRAM) — **only required once you restore the
  GPU-bound microservices** (ESMFold, MIC, Hemolysis, CPP).

### 1. Clone and configure

```bash
git clone <THIS_REPOSITORY_URL>
cd amp-agent

# Populate environment variables (real keys are kept out of the repo)
cp .env.example .env || true
cp agent/.env.example agent/.env || true
```

Edit both `.env` files and replace `your-dashscope-api-key-here` with
your own key from the
[DashScope console](https://dashscope.console.aliyun.com/apiKey).

### 2. Boot the coordination layer

```bash
docker compose up -d                  # backend + frontend + postgres + knowledge-builder

curl http://localhost:5000/api/health
# → {"service":"AMP-Agent Backend","status":"ok","version":"3.0"}
```

Open `http://localhost:3000` in your browser (or `http://localhost`
if the frontend is served by its own Nginx container).

### 3. Build the knowledge-base index (first-time only)

```bash
python knowledge_builder/rebuild_index.py
```

This populates `knowledge_builder/integrated_knowledge_base/vector_store/`
(~82 MB), which is git-ignored by design. Takes ~3–10 min on CPU.

### 4. (Optional) Restore one or more microservices

Pick a service directory, read its `IMPLEMENTATION.md`, follow the
5-step recipe, and un-comment the matching block in
`docker-compose.yml`. Example:

```bash
# Restore the generator (AMP-Designer / AMP-GPT)
less services/01-amp-designer/IMPLEMENTATION.md
# … clone upstream, drop in app.py, download weights …
sed -i 's/^  # generator:/  generator:/' docker-compose.yml   # illustrative
docker compose build generator
docker compose up -d generator
```

For a more detailed startup / troubleshooting / production-deployment
guide, see [`QUICKSTART.md`](QUICKSTART.md).

---

## 📁 Repository Layout

| Path | Purpose | Shipped in this release? |
|------|---------|--------------------------|
| `agent/` | ReAct agent, tool registry, orchestrator, skills, evals | ✅ Full source |
| `backend/` | Flask API, SSE streaming, database, Graph-RAG layer | ✅ Full source |
| `frontend/` | React 19 + Ant Design UI | ✅ Full source |
| `services/*/` | Nine AMP microservices (generators + evaluators) | 🧭 Placeholder (IMPLEMENTATION.md only) |
| `knowledge_builder/` | AMP knowledge-base construction pipelines | ✅ Full source |
| `amp_knowledge_base/` | Curated AMP literature + ontology data | ✅ Full source |
| `docs/` | Architecture, pipelines, evals, user guides | ✅ Full source |
| `tests/` | Unit + integration tests (for the coordination layer) | ✅ Full source |

---

## 📦 Model Weights & Upstream Code

No third-party model weights or upstream source are redistributed in
this repository. For each microservice, `services/<name>/IMPLEMENTATION.md`
lists:

- Original paper and author
- Upstream GitHub / Zenodo / HuggingFace URL
- Exact filenames of the required weights
- Target mount paths expected by `docker-compose.yml`
- Licence of the upstream project

For a convenience script that pulls every weight into the expected
locations, see `scripts/` (add your own once you have picked which
models to restore).

---

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| [`QUICKSTART.md`](QUICKSTART.md) | Minimal Release Mode, startup, commands, ports, troubleshooting |
| [`DEVELOPER_GUIDE.md`](DEVELOPER_GUIDE.md) | Full developer onboarding |
| [`CORE_ALGORITHMS.md`](CORE_ALGORITHMS.md) | Mathematical core (Pareto, RAG, agent loop) |
| `docs/architecture/PROJECT_ARCHITECTURE.md` | Module-by-module architecture |
| `docs/EVALS_SYSTEM_GUIDE.md` | Evals regression framework |
| `docs/STRUCTURE_PIPELINE_QUICKSTART.md` | Structure discrimination pipeline |
| `services/*/IMPLEMENTATION.md` | Per-service restore recipe |

---

## 🔐 Security & Secrets

This repository ships with **placeholder credentials only**:

- `.env` / `agent/.env` contain `your-dashscope-api-key-here`
- `docker-compose.yml` contains `your_password_here` for PostgreSQL

Before running, replace every placeholder with your own values. **Never
commit real secrets**; `.gitignore` already excludes `.env`, `agent/.env`,
all common credential filename patterns, the runtime Chroma vector store,
and every `*.pickle` / `*.sqlite3` cache file.

> **Privacy note**: the Agent by default calls an external LLM endpoint
> (DashScope / any OpenAI-compatible API), so your prompts and generated
> sequences leave the host. **If privacy or IP isolation is a hard
> requirement, point the Agent at a local LLM deployment instead**
> — e.g. Ollama, vLLM, llama.cpp or SGLang serving a model of your choice
> behind an OpenAI-compatible endpoint at `http://localhost:<port>/v1`,
> then update `DASHSCOPE_API_KEY` / `OPENAI_BASE_URL` in `.env` accordingly.

---

## 📄 License

The coordination layer (code written by the AMP-Agent authors) in this
repository is licensed under the [MIT License](LICENSE).

Third-party microservice implementations that you restore into
`services/*/` remain governed by **their own upstream licences**. See
each `services/<name>/IMPLEMENTATION.md` for the licence attached to the
upstream model / code. You are responsible for verifying redistribution
compatibility when bundling a restored microservice with this release.

---

## 📖 Citation

If you use AMP-Agent in academic work, please cite as described in
[`CITATION.cff`](CITATION.cff):

```bibtex
@software{amp_agent_2026,
  title  = {An Autonomous Artificial Intelligence Scientist for Antimicrobial Peptide Discovery},
  author = {Chinfo Lab},
  year   = {2026},
  url    = {<THIS_REPOSITORY_URL>}
}
```

When you cite results obtained from a restored microservice (e.g. MIC
regression, ESMFold structures, HydrAMP samples), please also cite the
original paper listed in the corresponding `IMPLEMENTATION.md`.

---

## 🤝 Contributing

Issues and pull requests for the **coordination layer** are welcome.
Please read [`DEVELOPER_GUIDE.md`](DEVELOPER_GUIDE.md) for the codebase
tour and coding conventions before submitting a PR. For contributions
that touch upstream third-party models, please open the PR against the
upstream repository first and then update the matching
`services/<name>/IMPLEMENTATION.md` here.
