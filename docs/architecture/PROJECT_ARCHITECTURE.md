# AMP-Agent Platform — Project Architecture

## Project Overview

The **AMP-Agent Platform** is an AI-driven platform for Antimicrobial Peptide (AMP) design and evaluation. It integrates multiple deep-learning models to provide an end-to-end pipeline covering sequence generation, property prediction, and 3D structure analysis.

### Key Features

- **Multi-generator support** — integrates AMP-Designer, Diff-AMP, and HydrAMP.
- **Conversational Agent** — Qwen-based dialogue agent that orchestrates services.
- **Closed-loop optimization** — multi-round iterative refinement that auto-adjusts the design strategy.
- **Auto-Debug** — self-healing error recovery at the tool-call layer.
- **Graph RAG** — PostgreSQL + `pgvector` knowledge graph with triple-based reasoning.
- **Structure discrimination stack** — ESMFold + PGAT-ABPp for structure-aware filtering.
- **Comprehensive evaluation** — MIC, hemolysis, cell-penetration, and AMP probability.
- **Offline knowledge retrieval** — ChromaDB vector search backed by curated literature.

---

## System Architecture

### High-level diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (React)                        │
│                  http://<host>:3000                          │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Chat Interface │ Sequence Library │ Service Health │   │
│  └──────────────────────────────────────────────────────┘   │
└───────────────────────┬─────────────────────────────────────┘
                        │ HTTP + SSE
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                     Backend (Flask)                          │
│                  http://localhost:5000                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │          AMPAgentV3 (Qwen-based Agent)              │   │
│  │  ┌────────────────────────────────────────────────┐ │   │
│  │  │  Tool Orchestrator  │  Knowledge Retriever    │ │   │
│  │  └────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────┘   │
└───────────────────────┬─────────────────────────────────────┘
                        │ Docker Network (amp-net)
        ┌───────────────┼───────────────┬─────────────┐
        ▼               ▼               ▼             ▼
┌──────────────┐ ┌──────────────┐ ┌──────────┐ ┌──────────┐
│  Generator   │ │  MIC/Macrel  │ │ Hemo/CPP │ │Structure │
│   Services   │ │   Services   │ │ Services │ │ Service  │
│   (GPU 0)    │ │   (GPU 0)    │ │ (GPU 2)  │ │ (GPU 1)  │
└──────────────┘ └──────────────┘ └──────────┘ └──────────┘
```

---

## Technology Stack

### Frontend

| Component            | Version | Purpose                            |
| -------------------- | ------- | ---------------------------------- |
| React                | 19.2.0  | UI framework                       |
| Vite                 | 7.2.4   | Build tool and dev server          |
| Ant Design           | 6.1.4   | UI component library               |
| Axios                | 1.13.2  | HTTP client                        |
| Plotly.js            | 3.3.1   | Data visualization                 |
| React Router         | 7.11.0  | Routing                            |

Highlights:

- Server-Sent Events (SSE) for streaming chat responses.
- Responsive layout with mobile support.
- Real-time service-health indicators.

### Backend

| Component             | Version  | Purpose                        |
| --------------------- | -------- | ------------------------------ |
| Flask                 | 3.0.0    | Web framework                  |
| OpenAI SDK            | 1.3.0    | DashScope-compatible client    |
| sentence-transformers | ≥5.0.0   | Text embedding models          |
| ChromaDB              | 0.4.18   | Vector database                |
| Plotly                | 5.18.0   | Chart generation               |
| Pandas                | ≥2.0.3   | Data manipulation              |
| Docker SDK            | 6.1.3    | Container orchestration        |

Highlights:

- RESTful API with SSE streaming.
- Dynamic microservice orchestration.
- Offline knowledge-base retrieval.

### AI & ML

| Model / Service       | Role                                      | Device      |
| --------------------- | ----------------------------------------- | ----------- |
| Qwen-Plus             | Dialogue agent core                       | API         |
| AMP-Designer          | Default sequence generator                | GPU 0       |
| Diff-AMP              | Exploratory diffusion generator           | GPU 0       |
| HydrAMP               | RL-guided generator                       | GPU 0       |
| Macrel                | AMP probability                           | GPU 0       |
| MIC Ensemble          | Activity prediction (BiLSTM + CNN + MBM)  | GPU 0       |
| HemoPi2               | Hemolysis prediction                      | GPU 2       |
| CPPpred               | Cell-penetration prediction               | GPU 2       |
| ESMFold               | 3D structure prediction                   | GPU 1       |
| all-mpnet-base-v2     | 768-dim text embeddings                   | CPU         |

### Infrastructure

| Component        | Technology                             | Notes                        |
| ---------------- | -------------------------------------- | ---------------------------- |
| Containerization | Docker Compose                         | Microservice orchestration   |
| Networking       | Docker bridge                          | Inter-service communication  |
| Storage          | Volume mounts                          | Model and data persistence   |
| GPU scheduling   | NVIDIA Container Toolkit               | Multi-GPU allocation         |
| Knowledge store  | ChromaDB + Sentence-Transformers       | Offline vector retrieval     |

---

## Repository Layout

```
amp-generator-platform/
├── frontend/                    # React frontend
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatPanel.jsx         # Chat UI
│   │   │   ├── SequencePanel.jsx     # Sequence library
│   │   │   └── ServiceHealth.jsx     # Service status
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── vite.config.js
│   └── package.json
│
├── backend/                     # Flask backend
│   ├── app.py                   # Flask entry point
│   ├── requirements.txt
│   └── Dockerfile
│
├── agent/                       # AI agent core
│   ├── amp_agent_v3.py          # Main agent logic
│   ├── auto_debugger.py         # Auto-Debug engine
│   ├── context_engine.py        # System prompt + closed-loop feedback
│   ├── tools.py                 # Tool functions
│   ├── tool_orchestrator.py     # Service orchestrator
│   ├── knowledge_retriever.py   # Knowledge retrieval
│   ├── language_texts.py        # Localized strings
│   └── tools/
│       └── search_knowledge.py
│
├── services/                    # Microservices
│   ├── 01-amp-designer/         # AMP-Designer generator
│   ├── 02-esm2/                 # ESM-2 embeddings
│   ├── 03-macrel/               # AMP probability
│   ├── 04-mic/                  # MIC prediction
│   ├── 05-hemolysis/            # Hemolysis prediction
│   ├── 06-cpp/                  # Cell-penetration prediction
│   ├── 07-structure/            # ESMFold
│   ├── 09-hydramp/              # HydrAMP
│   └── 10-diff-amp/             # Diff-AMP
│
├── knowledge_builder/           # Knowledge-base pipeline
│   ├── integrated_knowledge_base/
│   │   ├── 01_literature_knowledge/
│   │   ├── 02_cpp_data/
│   │   ├── 03_mic_data/
│   │   ├── 04_hemolysis_data/
│   │   ├── 05_statistics/
│   │   ├── 06_motif_patterns/
│   │   └── vector_store/
│   └── build_integrated_knowledge.py
│
├── data/                        # Data and models
│   └── models/
│       ├── amp-prompt/          # AMP-Designer
│       ├── amp-gan/             # Diff-AMP
│       ├── hydramp/             # HydrAMP
│       ├── macrel/              # Macrel
│       ├── esmfold/             # ESMFold
│       ├── hemolysis/           # HemoPi2
│       └── cpp/                 # CPPpred
│
├── docker-compose.yml           # Service composition
├── .env.example                 # Environment template
└── start.sh                     # Convenience launcher
```

---

## Core Components

### 1. Frontend (React + Vite)

Why this stack:

- Vite delivers fast HMR and an excellent developer experience.
- React 19 provides modern concurrent features.
- Ant Design 6 supplies enterprise-grade components out of the box.

Streaming handler:

```javascript
const response = await fetch('/api/chat', {
  method: 'POST',
  body: JSON.stringify({ message }),
});
const reader = response.body.getReader();
while (true) {
  const { value, done } = await reader.read();
  if (done) break;
  // parse SSE frames
}
```

Dev server configuration:

```javascript
// vite.config.js
export default {
  server: {
    host: '0.0.0.0',
    port: 3000,
    proxy: {
      '/api': 'http://localhost:5000',
    },
  },
};
```

### 2. Backend (Flask + Agent)

Layered architecture:

```
Flask API
   ↓
AMPAgentV3 (Qwen-based)
   ↓
Tool Orchestrator
   ↓
Docker-hosted microservices
```

Agent workflow:

1. Receive user input and parse intent.
2. Build an execution plan and select tools.
3. Call microservices, starting containers on demand.
4. Aggregate results and generate visualizations.
5. Stream responses back to the frontend via SSE.

Key capabilities:

- Dynamic service scheduling (start containers only when needed).
- Batch execution to avoid GPU OOM.
- Multi-generator switching driven by agent parameters.
- Knowledge-augmented decisions via vector retrieval.
- Closed-loop optimization across iterations.
- Auto-Debug that repairs failing tool calls.

---

### 2.1 Closed-loop Optimization

Idea:

```
Round 1: generate 5 peptides  → mean MIC = 12 µM
    ↓  persist to evaluation_history
Round 2: auto-inject "target MIC < 5 µM" constraint
    ↓  Qwen adjusts the design strategy
         → mean MIC = 6 µM (improved)
```

Backend history (simplified, `backend/app.py`):

```python
evaluation_history = []

def add_evaluation_to_history(results: list):
    feedback = {
        "round": len(evaluation_history) + 1,
        "avg_mic": round(avg_mic, 2),
        "avg_hemolysis": round(avg_hemo, 3),
        "avg_cpp": round(avg_cpp, 3),
        "timestamp": pd.Timestamp.now().isoformat(),
    }
    evaluation_history.append(feedback)
```

System prompt injection (`agent/context_engine.py`):

```python
def build_system_prompt(language: str = "en", feedback: dict | None = None):
    if feedback:
        feedback_section = f"""
**CLOSED-LOOP OPTIMIZATION CONTEXT**
Previous Round: MIC = {feedback['avg_mic']} µM
Target: MIC < 5 µM
Strategy: increase net charge, add hydrophobic residues
"""
        return base_prompt + feedback_section
    return base_prompt
```

Outcome: 30–50 % MIC reduction without manual intervention.

---

### 2.2 Auto-Debug

Flow:

```
Tool call fails → capture exception
    ↓
ErrorAnalyzer pattern-match (~0.1 s)
    ↓
can fix?  → yes → retry
    ↓ no
LLMDebugger calls Qwen (~2–3 s)
    ↓
patch params → retry → success / bail out
```

Three layers (`agent/auto_debugger.py`):

1. **ErrorAnalyzer** — regex rules covering the seven most common failures (type mismatch, missing arg, invalid value, …).
2. **LLMDebugger** — Qwen-backed analysis with error history as context; extracts and validates a JSON patch.
3. **AutoDebugger** — orchestrator combining both engines with a 3-attempt retry budget.

Integration with the agent:

```python
class AMPAgentV3:
    def _execute_tool_with_retry(self, tool_func, tool_name, params, max_retries=3):
        for attempt in range(1, max_retries + 1):
            try:
                return tool_func(**params)
            except Exception as e:
                fixed_params, method = self.auto_debugger.debug_and_fix(
                    str(e), tool_name, params, attempt
                )
                if fixed_params:
                    params = fixed_params
```

---

### 2.3 Graph RAG Knowledge Base

Evolution:

```
v1: pure vector retrieval (ChromaDB)
    ↓
v2: PostgreSQL + pgvector + triples
    ↓
v3: Graph RAG — structured query + semantic search
```

Schema highlights (`backend/database.py`):

```sql
CREATE TABLE ontology_entity (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,           -- Target, Mechanism, Principle, ...
    name TEXT NOT NULL,
    description TEXT,
    source TEXT,                  -- literature, experiment, ai_generated
    embedding VECTOR(768),        -- pgvector semantic index
    extra_json JSONB,
    created_at TIMESTAMP
);

CREATE TABLE ontology_relation (
    id SERIAL PRIMARY KEY,
    subject_id TEXT REFERENCES ontology_entity(id),
    predicate TEXT NOT NULL,      -- has_mechanism, based_on_principle, ...
    object_id TEXT REFERENCES ontology_entity(id),
    weight REAL DEFAULT 1.0,
    metadata JSONB
);

ALTER TABLE sequences ADD COLUMN verified INTEGER DEFAULT 0;
ALTER TABLE sequences ADD COLUMN experimental_mic REAL;
ALTER TABLE sequences ADD COLUMN exported_to_ontology INTEGER DEFAULT 0;

CREATE TABLE tool_failure_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_name TEXT NOT NULL,
    error_history TEXT,
    auto_fixed INTEGER DEFAULT 0,
    session_id TEXT
);
```

Query engine (`backend/graph_rag.py`):

```python
def query_mechanisms_for_target(target: str, limit: int = 5):
    """
    Lookup effective mechanisms for a given target.

    1. Embed the query.
    2. Vector-search similar Target entities.
    3. Traverse `has_mechanism` edges.
    4. Sort by edge weight, return Top-K.
    """
    query_embedding = embedding_model.encode(target)
    cursor.execute(
        """
        SELECT id, name, description,
               1 - (embedding <=> %s::vector) AS similarity
        FROM ontology_entity
        WHERE type = 'Target'
        ORDER BY embedding <=> %s::vector
        LIMIT 3
        """,
        (query_embedding.tolist(), query_embedding.tolist()),
    )
    mechanisms = []
    for target_entity in targets:
        cursor.execute(
            """
            SELECT m.name, m.description, r.weight
            FROM ontology_relation r
            JOIN ontology_entity m ON r.object_id = m.id
            WHERE r.subject_id = %s AND r.predicate = 'has_mechanism'
            ORDER BY r.weight DESC
            """,
            (target_entity["id"],),
        )
        mechanisms.extend(cursor.fetchall())
    return {"success": True, "mechanisms": mechanisms[:limit]}
```

Agent tools (`agent/tools.py`, `agent/amp_agent_v3.py`):

```python
def tool_query_mechanisms_for_target(target: str, limit: int = 5):
    """[RECOMMENDED] Query effective mechanisms for a given target (Graph RAG)."""
    from graph_rag import query_mechanisms_for_target
    return query_mechanisms_for_target(target, limit)

def tool_query_principles_for_mechanism(mechanism: str, limit: int = 5):
    """[RECOMMENDED] Query design principles grounded on a given mechanism (Graph RAG)."""
    from graph_rag import query_principles_for_mechanism
    return query_principles_for_mechanism(mechanism, limit)

tool_map = {
    # ...existing tools
    "query_mechanisms_for_target": tool_query_mechanisms_for_target,
    "query_principles_for_mechanism": tool_query_principles_for_mechanism,
}
```

Human-in-the-loop feedback (`frontend/src/components/SequencePanel.jsx`):

```jsx
<Button icon={<CheckCircleOutlined />} onClick={markAsVerified}>
  Mark Verified ({selectedRows.length})
</Button>
<Button icon={<ExportOutlined />} onClick={exportToOntology}>
  Export to KB
</Button>

<Table rowSelection={{ selectedRowKeys: selectedRows }} />
```

Data flow:

```
Wet-lab validation → Mark Verified → sequences.verified = 1
    ↓
Export to KB → export_sequences_to_ontology()
    ↓
ontology_entity (type='DesignCase', source='user_experiment')
    ↓
Agent retrieves verified cases in later sessions
```

Highlights:

- Structured triples enable multi-hop reasoning.
- pgvector indexes provide semantic search.
- Experimental results flow back into the knowledge base.
- Auto-Debug logs power continual improvement.
- Every fact carries provenance (source, timestamp, confidence).
- Backwards compatible with the legacy JSON knowledge base.
- One-command bring-up via `docker compose up -d amp-postgres`.

### 3. Knowledge retrieval

```
User query
    ↓
Sentence-Transformers (all-mpnet-base-v2)
    ↓ 768-d vector
ChromaDB similarity search
    ↓ Top-K neighbours
Context returned to the agent
```

Sources:

- Curated literature on antimicrobial peptides.
- Publicly available MIC / CPP / hemolysis datasets.
- Motif pattern libraries.

Offline deployment:

- Model cache under `/root/.cache/huggingface/`.
- Vector store at `knowledge_builder/integrated_knowledge_base/vector_store/`.
- No outbound network access required at runtime.

### 4. Microservices

Network (`docker-compose.yml`):

```yaml
networks:
  amp-net:
    driver: bridge
```

GPU allocation:

| GPU   | Services                        | Notes                         |
| ----- | ------------------------------- | ----------------------------- |
| GPU 0 | Generators, MIC, Macrel         | Generation + activity         |
| GPU 1 | Structure (ESMFold)             | Dedicated to structure        |
| GPU 2 | Hemolysis, CPP                  | Toxicity + permeability       |

Service discovery via Docker DNS:

```python
SERVICES = {
    "GENERATOR": "http://generator:8001",
    "MIC":       "http://amp-mic:8000",
    # ...
}
```

---

## AI Model Details

### Generator comparison

| Model         | Type                   | Strengths                  | Typical use                  |
| ------------- | ---------------------- | -------------------------- | ---------------------------- |
| AMP-Designer  | Prompt-based LM        | Fast and stable            | General-purpose AMP design   |
| Diff-AMP      | Diffusion              | Explorative                | Novel structural motifs      |
| HydrAMP       | Reinforcement learning | Optimization-oriented      | Property improvement         |

### Predictor performance (reference)

| Model         | Task                  | Metric        | Notes                       |
| ------------- | --------------------- | ------------- | --------------------------- |
| MIC Ensemble  | Activity              | AUC ≥ 0.85    | BiLSTM + CNN + MBM ensemble |
| Macrel        | AMP probability       | AUC ≈ 0.91    | Lightweight Random Forest   |
| HemoPi2       | Hemolysis             | AUC ≈ 0.88    | Deep-learning model         |
| CPPpred       | Cell-penetration      | ACC ≈ 0.82    | Ensemble model              |
| ESMFold       | Structure             | pLDDT > 70    | Protein language model      |

---

## Security & Configuration

### Environment variables

```bash
# .env
DASHSCOPE_API_KEY=your_dashscope_api_key
FLASK_ENV=production
```

Never commit the real `.env` — use `.env.example` as a template.

### Pinned dependencies (selected)

```txt
openai==1.3.0                   # DashScope compatibility
httpx==0.24.1                   # required by openai 1.3.0
sentence-transformers>=5.0.0
numpy>=1.24.3,<2.0              # chromadb compatibility
huggingface-hub>=0.20.0         # offline model loading
```

### Offline deployment checklist

- HuggingFace cache is mounted into the backend container.
- ChromaDB vector store is persisted locally.
- Docker images are pre-built; no online pulls at runtime.
- The agent can operate fully disconnected once the LLM call is routed locally (or DashScope is reachable).

---

## Performance Notes

### Batch execution

```python
# Avoid GPU OOM by auto-batching
MAX_BATCH_SIZE = 4
num_batches = math.ceil(num_samples / MAX_BATCH_SIZE)
```

### On-demand services

```python
def start_tool(self, tool_name):
    if tool_name in self.service_map:
        container = self.service_map[tool_name]
        if not self.is_running(container):
            self.docker_client.containers.get(container).start()
```

### Streaming responses

```python
def generate():
    for chunk in agent.chat(user_message):
        yield f"data: {json.dumps(chunk)}\n\n"
```

---

## Deployment Guide

### Quick start

```bash
# 1. Bring up all services
docker compose up -d

# 2. Start the frontend dev server
cd frontend && npm run dev

# 3. Open the UI
# Frontend: http://<host>:3000
# Backend:  http://localhost:5000
```

### Production deployment

```bash
# 1. Build the production frontend
cd frontend && npm run build

# 2. Serve with Nginx
docker compose up -d nginx

# 3. Open
# http://<host>:80
```

### GPU requirements

- Minimum: 3 GPUs with ≥ 12 GB VRAM each.
- Recommended: 3 × RTX 4080 Super (16 GB VRAM).
- CUDA 11.8+, driver 520+.

---

## Known Issues

1. **numpy version conflict** — ChromaDB 0.4.18 is not compatible with NumPy 2.0. Pin to `numpy>=1.24.3,<2.0`.
2. **httpx proxy parameter** — OpenAI SDK 1.3.0 is incompatible with newer `httpx`. Pin to `httpx==0.24.1`.
3. **Flask debug duplicate output** — `debug=True` spawns a second process; disable in production.
4. **Vite external access** — by default the dev server only listens on `localhost`; set `server.host = '0.0.0.0'`.

---

## Roadmap

Near term:

- Add more generator backbones.
- Improve knowledge-base retrieval quality.
- Polish frontend visualization components.
- Ship sequence history management.

Long term:

- Integrate a Process Reward Model (PRM).
- Extend to broader protein design.
- Add molecular-docking simulation.
- Build an end-to-end drug-design pipeline.

---

## References

Core documentation:

- [Flask](https://flask.palletsprojects.com/)
- [React](https://react.dev/)
- [Ant Design](https://ant.design/)
- [DashScope API](https://help.aliyun.com/zh/dashscope/)
- [sentence-transformers](https://www.sbert.net/)
- [ChromaDB](https://docs.trychroma.com/)

Model references:

- **AMP-Designer** — prompt-based language model.
- **Diff-AMP** — diffusion model for peptide generation.
- **HydrAMP** — reinforcement-learning approach.
- **ESMFold** — [Meta AI ESM](https://github.com/facebookresearch/esm).

---

## Structure Discrimination Pipeline

### Motivation

Evolution:

```
v1: generation + Macrel filter
    ↓
v2: generation + ESMFold structure prediction
    ↓
v3: generation + ESMFold + PGAT-ABPp structure discrimination
```

Benefits:

- Structure-aware filtering that goes beyond sequence features.
- High-confidence decisions via graph-attention analysis.
- End-to-end flow: AMP-Designer → ESMFold → PGAT → MIC / Hemo / CPP.
- Pluggable interface for future discrimination models.

### Pipeline

```
User prompt ("design 5 peptides against E. coli")
    ↓
AMP-Designer generates sequences (default generator)
    ↓
ESMFold predicts 3D structures (PDB)
    ↓
PGAT-ABPp structural classification (binary softmax)
    ↓ filter by pgat_threshold
MIC / Hemolysis / CPP evaluation
    ↓
Multi-objective ranking and visualization
```

Key components:

1. **ESMFold service** (`services/07-structure/`) — protein language model; input: sequence; output: PDB; runs on GPU 1.
2. **PGAT-ABPp service** (`services/11-pgat-abpp/`) — Graph Attention Network; input: PDB path; output: `[p_nonAMP, p_AMP]` softmax.
3. **Agent integration** (`agent/tools.py`, `agent/amp_agent_v3.py`):

   ```python
   def tool_structure_discrimination_pipeline(target, num_samples,
                                              pgat_threshold=0.5,
                                              generator="default"):
       """
       Entry point for the structure-discrimination stack.

       Stage 1: generate sequences (AMP-Designer)
       Stage 2: predict structures (ESMFold)
       Stage 3: classify structures (PGAT-ABPp)
       Stage 4: evaluate activity (MIC / Hemo / CPP)
       Stage 5: multi-objective ranking
       """
   ```

4. **Generator protection** (`agent/amp_agent_v3.py`):

   ```python
   # Force the structure pipeline to use AMP-Designer by default
   if generator_param != "default" and not (user_asks_hydramp or user_asks_diffamp):
       logger.info("Forcing generator to 'default' for the structure pipeline")
       generator_param = "default"
       args["generator"] = "default"
   ```

### A note on PGAT softmax

- PGAT outputs a **binary softmax** `[p_nonAMP, p_AMP]`.
- Values tend to saturate near 0 or 1 — this is a **classification confidence**, not a smooth probability.
- Good as a **structural gatekeeper** (pass / fail).
- Not suitable as a fine-grained ranking signal on its own.

Why do accepted samples all score close to 1.0? The classifier assigns sharp values away from the decision boundary; after thresholding, only high-confidence samples survive. Pair PGAT with continuous metrics (MIC, hemolysis, CPP) to break ties.

### Frontend integration

`frontend/src/components/StructureDemoGuide.jsx`:

- Sidebar entry: **Structure Demo Guide**.
- Route: `/structure-demo`.
- Contents: Scenario 0–6 walkthroughs (English).
- Rendering: React + Ant Design + `react-markdown` + `remark-gfm`.

Scenarios covered:

- Scenario 1 — multi-generator design + evaluation + visualization.
- Scenario 2 — closed-loop optimization (second round).
- Scenario 3 — Graph RAG mechanism lookup + design principles.
- Scenario 4 — wet-lab feedback flowing back into the knowledge base.
- Scenario 5 — Auto-Debug self-repair.
- Scenario 6 — multi-generator comparison with 3D structures.

### Known limitations

- Pipeline is fully runnable end-to-end.
- Occasional index-out-of-range issues on the PGAT side due to PDB-to-graph mismatches.
- PGAT scores saturate — useful for filtering but not ranking on their own.

Mitigations include PDB normalization, edge-index validation, and self-loop cleanup in the PGAT service.

### Related documents

| Document                               | Purpose                      | Location             |
| -------------------------------------- | ---------------------------- | -------------------- |
| `STRUCTURE_PIPELINE_QUICKSTART.md`     | Fast test commands           | `docs/`              |
| `STRUCTURE_DISCRIMINATION_PIPELINE.md` | Detailed pipeline reference  | `docs/`              |

---

## Release History

### v3.0.3 — Structure discrimination stack

- ESMFold + PGAT-ABPp integrated end-to-end.
- Generator protection ensures the structure pipeline uses AMP-Designer.
- Demo guide (Scenarios 0–6) added to the frontend.
- Bug fix: JSX template-literal backtick escaping.

### v3.0.2 — Graph RAG knowledge base

- PostgreSQL + pgvector knowledge graph.
- Triple-based (subject–predicate–object) structured queries.
- Human-in-the-loop verification → export to knowledge base.
- Auto-Debug failure logs feed continual improvement.

### v3.0.1 — Intelligent enhancements

- Closed-loop optimization (30–50 % MIC reduction across rounds).
- Auto-Debug (fast 0.1 s / intelligent 2–3 s recovery).

### v3.0 — Flask + React rearchitecture

- Migrated to Flask (backend) + React (frontend).
- Integrated the knowledge retrieval system.
- SSE streaming responses.
- Dynamic multi-generator switching.

### v2.0 — Streamlit monolith

- Streamlit single-page app.
- Baseline agent capabilities.
- Initial multi-model integration.

---

**License**: MIT  
**Maintainer**: Chinfo Lab

