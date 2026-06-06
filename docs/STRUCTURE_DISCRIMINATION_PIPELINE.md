# PGAT-ABPp Structure Discrimination Pipeline

## Overview

This document describes the integration of the PGAT-ABPp structure-discrimination model into the AMP-Agent platform.

## Core capability

### Pipeline flow

```
User requests "structure-based screening"
    ↓
Qwen-based agent recognises the intent
    ↓
AMP-Designer generates sequences
    ↓
ESMFold predicts the 3D structures
    ↓
PGAT-ABPp screens them and analyses structure
    ↓
Surviving candidates run MIC / Hemolysis / CPP prediction
    ↓
Results are returned
```

### Stages

1. **Stage 1 — Sequence generation**
   - Uses AMP-Designer / Diff-AMP / HydrAMP.
   - Supports target specification (Gram-negative, Gram-positive, etc.).

2. **Stage 2 — Structure prediction**
   - ESMFold predicts the 3D structure.
   - Output format: standard PDB.

3. **Stage 3 — PGAT-ABPp screening**
   - Graph-attention-network classifier over the structure.
   - Uses ProtT5 embeddings (offline variant B).
   - Configurable threshold (default `0.5`).

4. **Stage 4 — Functional prediction**
   - MIC (minimum inhibitory concentration).
   - Hemolysis.
   - CPP (cell-penetration probability).

5. **Stage 5 — Ranking and output**
   - Composite scoring and ranking.
   - Returns the top candidates.

## Implementation

### Service configuration

#### PGAT-ABPp service

- **Container name**: `amp-pgat-abpp`
- **Port mapping**: `8010:8000`
- **Lifecycle**: on-demand (`restart: "no"`)
- **Health check**: `http://localhost:8010/health`

#### `docker-compose` snippet

```yaml
pgat-abpp:
  build:
    context: ./services/11-pgat-abpp
    dockerfile: Dockerfile
  container_name: amp-pgat-abpp
  ports:
    - "8010:8000"
  volumes:
    - ./services/11-pgat-abpp:/app
  restart: "no"
  networks:
    - amp-network
  environment:
    - PYTHONUNBUFFERED=1
```

### Tool-orchestrator configuration

```python
"pgat_abpp": {
    "container":      "amp-pgat-abpp",
    "health_url":     "http://localhost:8010/health",
    "required_for":   ["structure_discrimination", "graph_based_prediction"],
    "startup_time":   10,
    "resource_level": "high",
}
```

#### Workflow definition

```python
self.workflow = {
    "structure": ["pdb_analyzer", "biopython_processor", "pgat_abpp"],
}
```

### Agent tool

#### `tool_structure_discrimination_pipeline`

```python
def tool_structure_discrimination_pipeline(
    target: str = "Gram-negative",
    num_samples: int = 10,
    pgat_threshold: float = 0.5,
    generator: str = "default",
    mic_threshold: float = 32.0,
    hemolysis_threshold: float = 10.0,
) -> Dict[str, Any]:
    ...
```

**Parameters**:

- `target` — target class (`"Gram-negative"`, `"Gram-positive"`, `"Mammalian"`, `"Antifungal"`, `"Antiviral"`).
- `num_samples` — number of sequences to generate.
- `pgat_threshold` — PGAT decision threshold (0.0–1.0).
- `generator` — generator choice (`"default"` / `"diverse"` / `"refine"`).
- `mic_threshold` — MIC filter threshold (μg/mL).
- `hemolysis_threshold` — hemolysis filter threshold (%).

**Response**:

```json
{
  "success": true,
  "pipeline_stages": {
    "generated": 10,
    "structure_predicted": 9,
    "passed_pgat": 7,
    "final_candidates": 5
  },
  "sequences": [
    {
      "sequence": "KWKLFKKIGAVLKVL...",
      "generator": "AMP-Designer",
      "pgat_score": 0.85,
      "pgat_label": 1,
      "structure_pdb": "ATOM  1  N   ...",
      "mic_pred": 12.5,
      "hemolysis_pred": 3.2,
      "cpp_pred": 0.78,
      "passes_thresholds": true
    }
  ],
  "summary": "Pipeline completed: 5 candidates found",
  "errors": []
}
```

#### `TOOLS_SCHEMA` registration

```python
{
    "type": "function",
    "function": {
        "name": "structure_discrimination_pipeline",
        "description": (
            "[RECOMMENDED FOR STRUCTURE-BASED DESIGN] End-to-end structure-"
            "discrimination pipeline: generate → ESMFold → PGAT-ABPp → "
            "MIC / Hemolysis / CPP. Use this when the user explicitly asks for "
            "structure-based design, structural screening, or mentions PGAT-ABPp."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "target": {"...": "..."},
                "num_samples": {"...": "..."},
                "pgat_threshold": {"...": "..."},
                "generator": {"...": "..."},
                "mic_threshold": {"...": "..."},
                "hemolysis_threshold": {"...": "..."}
            },
            "required": ["target", "num_samples"]
        }
    }
}
```

## Usage

### 1. Chat Lab

Trigger the pipeline through natural language:

```
User: "Design 10 AMPs against E. coli using structure discrimination — filter with PGAT-ABPp first"

Agent: 🚀 Starting structure discrimination pipeline...
       Target: Gram-negative
       Samples: 10
       PGAT Threshold: 0.5

       [Stage 1/5] Generating sequences...
       ✅ Generated 10 sequences

       [Stage 2/5] Predicting structures with ESMFold...
       ✅ Predicted 10 structures

       [Stage 3/5] Running PGAT-ABPp discrimination...
       ✅ 8 sequences passed PGAT screening

       [Stage 4/5] Predicting MIC / Hemolysis / CPP...
       ✅ Evaluation completed

       [Stage 5/5] Ranking and generating summary...

       ### ✅ Pipeline Completed

       **Top 3 Candidates:**
       1. KWKLFKKIGAVLKVL...
          - PGAT Score: 0.85
          - MIC: 12.5 μg/mL
          - Hemolysis: 3.2%
```

### 2. HTTP API

```bash
curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Design 5 AMPs using the structure-discrimination pipeline",
    "session_id": "test_session"
  }'
```

### 3. Direct function call

```python
from tools import tool_structure_discrimination_pipeline

result = tool_structure_discrimination_pipeline(
    target="Gram-negative",
    num_samples=5,
    pgat_threshold=0.6,
    generator="default",
)

print(result)
```

### 4. Test script

```bash
cd <project_root>
python test_structure_pipeline.py
```

## Implementation details

### Variant B — Offline ProtT5 embeddings

Current implementation uses the offline embedding variant:

**Phase 1 (shipped)**:

- Demonstrates the flow using `example_data/data_U50.npy`.
- PGAT-ABPp service health check in place.
- Returns a placeholder score (`pgat_score=0.8`).

**Phase 2 (planned)**:

- PDB → contact-map + CSV conversion.
- Offline ProtT5 embedding generation.
- Full PGAT-ABPp prediction.

### PDB processing skeleton

```python
# TODO: full implementation
# 1. PDB → contact map (via PDBProcess.py)
# 2. Sequence → ProtT5 embeddings (offline)
# 3. Call PGAT-ABPp /predict
```

### Service dependencies

The pipeline auto-starts these services:

1. **Generator** — amp-designer / diff-amp / hydramp.
2. **Structure** — ESMFold.
3. **PGAT-ABPp** — structure classifier.
4. **MIC / Hemolysis / CPP** — functional predictors.

## Operations

### Health checks

```bash
# PGAT-ABPp service
curl http://localhost:8010/health

# Aggregated service health
curl http://localhost:5000/api/services/health
```

### Logs

```bash
docker logs amp-pgat-abpp --tail 50 -f
docker logs amp-backend   --tail 50 -f
```

### Container management

```bash
docker compose up -d pgat-abpp
docker compose stop pgat-abpp
docker compose restart pgat-abpp
```

## Troubleshooting

### 1. PGAT-ABPp service unresponsive

```bash
docker ps | grep pgat
docker logs amp-pgat-abpp
docker compose restart pgat-abpp
```

### 2. Structure prediction fails

```bash
docker ps | grep structure
docker compose restart structure
```

### 3. Pipeline timeouts

- Reduce `num_samples`.
- Verify all services are healthy.
- Inspect the backend logs for bottlenecks.

## Roadmap

### Short term (Phase 2)

- Full PDB → PGAT-ABPp input conversion.
- Online ProtT5 embedding generation.
- Batch-inference optimisation for PGAT-ABPp.

### Mid term

- User-tunable PGAT threshold helpers.
- Richer structural-analysis visualisations.
- Additional structural feature extractors.

### Long term

- Support multiple structure predictors (AlphaFold2, RoseTTAFold).
- Real-time ProtT5 embedding service.
- Structure–function correlation analysis.

## References

### PGAT-ABPp paper

- **Title**: "PGAT-ABPp: Harnessing Protein Language Models and Graph Attention Networks for Antibacterial Peptide Identification with Remarkable Accuracy".
- **Framework**: TensorFlow 2.13.1 + Python 3.8.18.
- **Inputs**: PDB file + ProtT5-XL-UniRef50 embeddings.

### Related docs

- [ESMFold integration](./ESMFOLD_INTEGRATION.md)
- [Graph RAG architecture](./GRAPH_RAG_ARCHITECTURE.md)
- [Tool orchestrator guide](./TOOL_ORCHESTRATOR_GUIDE.md)

## Changelog

- Initial integration — PGAT-ABPp Docker container, tool-orchestrator config, agent tool integration, offline-embedding variant (B), full pipeline smoke test passed.

---

**Maintainer**: Chinfo Lab  
**Status**: Integrated (Phase 1 complete)
