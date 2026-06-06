# Structure Discrimination Pipeline — Quickstart

## What is it?

The structure-discrimination pipeline is an end-to-end workflow for screening antimicrobial peptides with 3D-structure information. It integrates:

- **Sequence generation** — AMP-Designer / Diff-AMP / HydrAMP.
- **Structure prediction** — ESMFold.
- **Structure classification** — PGAT-ABPp (graph-attention network).
- **Functional prediction** — MIC / Hemolysis / CPP.

## 30-second quickstart

### 1. In Chat Lab (recommended)

Type any of the following into the chat box:

```
Design 10 AMPs against E. coli using the structure-discrimination pipeline
```

```
Use PGAT-ABPp to screen peptides against S. aureus, generating 15 candidates
```

```
Run the structure-discrimination stack and design 5 antifungal peptides
```

### 2. Via HTTP API

```bash
curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Design 5 AMPs using the structure-discrimination pipeline",
    "session_id": "test"
  }'
```

### 3. Run the test script

```bash
cd <project_root>
python test_structure_pipeline.py
```

## Examples

### Example 1 — Basic usage

**Prompt**:

```
Use the structure-discrimination pipeline to design 10 AMPs against Gram-negative bacteria
```

**Output**:

```
🚀 Starting structure discrimination pipeline...
Target: Gram-negative
Samples: 10
PGAT Threshold: 0.5

[Stage 1/5] Generating sequences...
✅ Generated 10 sequences

[Stage 2/5] Predicting structures with ESMFold...
✅ Predicted 10 structures

[Stage 3/5] Running PGAT-ABPp discrimination...
✅ 8 sequences passed PGAT screening (threshold=0.5)

[Stage 4/5] Predicting MIC / Hemolysis / CPP for passed candidates...
✅ Evaluation completed

[Stage 5/5] Ranking and generating summary...

### ✅ Pipeline Completed

**Pipeline Stages:**
- Generated: 10 sequences
- Structure predicted: 10
- Passed PGAT-ABPp: 8
- Final candidates: 8

**Top 3 Candidates:**

**1. KWKLFKKIGAVLKVL**
   - Generator: AMP-Designer
   - PGAT Score: 0.850
   - MIC: 12.5 μg/mL
   - Hemolysis: 3.2%
   - CPP: 0.78

**2. GIGKFLHSAKKFGKA**
   - Generator: AMP-Designer
   - PGAT Score: 0.823
   - MIC: 15.8 μg/mL
   - Hemolysis: 4.1%
   - CPP: 0.72

**3. FKRPLKRVKGLVKAF**
   - Generator: AMP-Designer
   - PGAT Score: 0.801
   - MIC: 18.3 μg/mL
   - Hemolysis: 5.6%
   - CPP: 0.69
```

### Example 2 — Tuning the PGAT threshold

**Prompt**:

```
Use PGAT-ABPp to screen AMPs with a stricter threshold of 0.7
```

The agent sets `pgat_threshold=0.7` and keeps only high-scoring candidates.

### Example 3 — Switching generators

**Prompt**:

```
Use Diff-AMP to generate diverse sequences, then run the structure-discrimination pipeline
```

The agent dispatches the call with `generator="diverse"`.

### Example 4 — Compound constraints

**Prompt**:

```
Design AMPs against S. aureus:
- 20 candidates
- PGAT threshold 0.6
- MIC < 25 μg/mL
- Hemolysis < 5%
```

The agent parses all constraints and forwards them to the pipeline.

## Advanced parameters

| Parameter             | Default       | Purpose                                    |
| --------------------- | ------------- | ------------------------------------------ |
| `target`              | Gram-negative | Target microbe or membrane class.          |
| `num_samples`         | 10            | Number of generated sequences.             |
| `pgat_threshold`      | 0.5           | PGAT decision threshold (0–1).             |
| `generator`           | default       | `default` / `diverse` / `refine`.          |
| `mic_threshold`       | 32.0          | MIC filter threshold (μg/mL).              |
| `hemolysis_threshold` | 10.0          | Hemolysis filter threshold (%).            |

### Tuning tips

**Sample size (`num_samples`)**
- Smoke test: 3–5.
- Normal use: 10–20.
- Large-scale screening: 50+.

**PGAT threshold (`pgat_threshold`)**
- Loose screening: 0.3–0.5 (keep more candidates).
- Standard screening: 0.5–0.7 (recommended).
- Strict screening: 0.7–0.9 (keep only high-confidence).

**Generator choice (`generator`)**
- `default` — AMP-Designer, fast and balanced.
- `diverse` — Diff-AMP, explores novel sequences.
- `refine` — HydrAMP, refines existing sequences.

## Comparison with the classic pipeline

### Classic `design_new_amps`

```
Generate → MIC / Hemo / CPP evaluation → Rank
```

- Pros: fast and simple.
- Cons: no structural information, relies on sequence features alone.

### Structure-discrimination pipeline

```
Generate → ESMFold → PGAT filter → Functional evaluation → Rank
```

- Pros: structure-aware decisions, more accurate filtering.
- Cons: higher compute cost.

### When to use the structure-discrimination pipeline

Use it when:

- You need high-precision screening.
- Structure–function relationships matter.
- You are exploring novel antimicrobial mechanisms.
- The request explicitly calls for a "structure-based" workflow.

Avoid it when:

- You are doing a quick prototype / smoke test.
- You need large-scale generation (> 100 sequences).
- You are running on resource-constrained hardware.

## Output fields

### Pipeline statistics

- `generated` — sequences emitted in stage 1.
- `structure_predicted` — structures successfully predicted in stage 2.
- `passed_pgat` — sequences that passed PGAT filtering in stage 3.
- `final_candidates` — final shortlist.

### Per-sequence fields

- `sequence` — peptide sequence.
- `generator` — which generator produced it.
- `pgat_score` — PGAT score (0–1).
- `pgat_label` — binary label (0 / 1).
- `structure_pdb` — predicted 3D structure (PDB text).
- `mic_pred` — predicted MIC (μg/mL).
- `hemolysis_pred` — predicted hemolysis (%).
- `cpp_pred` — predicted cell-penetration probability (0–1).
- `passes_thresholds` — whether all filters passed.

## Troubleshooting

### 1. "PGAT service unavailable"

```bash
docker compose up -d pgat-abpp
docker logs amp-pgat-abpp
```

### 2. "Structure prediction failed"

```bash
docker compose up -d structure
docker logs amp-structure
```

### 3. Pipeline timeout

- Reduce `num_samples` to 3–5.
- Check service status: `docker ps`.
- Inspect logs: `docker logs amp-backend`.

### 4. No candidates pass screening

- Lower `pgat_threshold` (e.g. 0.3).
- Increase `num_samples`.
- Relax `mic_threshold` / `hemolysis_threshold`.

## Best practices

### First-time use

```
Generate 3 test sequences using the structure-discrimination pipeline
```

Small batch first — validates the plumbing.

### Production design

```
Design 15 AMPs against E. coli using the structure-discrimination pipeline, PGAT threshold 0.6
```

Balanced speed and quality.

### High-precision screening

```
Screen AMPs with the structure-discrimination pipeline:
- 30 candidates
- PGAT threshold 0.75
- MIC < 20
- Hemolysis < 3%
```

Strict filtering to surface only high-quality candidates.

### Knowledge-base augmented

```
First look up antimicrobial mechanisms for E. coli, then design 10 peptides using the structure-discrimination pipeline
```

Combine ontology knowledge with structural screening for smarter design.

## Related resources

- [Full technical reference](./STRUCTURE_DISCRIMINATION_PIPELINE.md)
- [ESMFold integration notes](./ESMFOLD_INTEGRATION.md)
- [Tool orchestrator guide](./TOOL_ORCHESTRATOR_GUIDE.md)

## Getting help

1. Check the logs: `docker logs amp-backend`.
2. Verify service status: `docker ps`.
3. Read the full technical reference.
4. Contact the platform maintainer.

---

**Version**: v1.0  
**Status**: Production-ready
