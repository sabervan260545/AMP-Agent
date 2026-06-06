# Skill: rapid_design

## Trigger
User wants to **quickly generate AMP candidates** without specifying a particular generator, structure validation, or multi-model comparison. Keywords: "fast", "quick", "rapidly", "immediately", "now".

## SOP (Standard Operating Procedure)

### Step 1 — Extract parameters
From the user's message, extract:
- `target`: pathogen or cell type (one of `Gram-negative`, `Gram-positive`, `Mammalian`, `Antifungal`, `Antiviral`). Default: `Gram-negative`.
- `num_samples`: integer number of sequences requested. Default: 5.
- `strategy`: use `"default"` (AMP-Designer, fast) unless user says "novel/diverse" → `"diverse"`, or "optimize/refine" → `"refine"`.

### Step 2 — Call design_new_amps DIRECTLY
```
design_new_amps(
    target=<extracted_target>,
    num_samples=<extracted_num_samples>,
    strategy=<extracted_strategy>
)
```
⚠️ DO NOT call `search_knowledge` before this step. Knowledge retrieval is already embedded.

### Step 3 — Present results
After `design_new_amps` returns:
- Show a ranked table: Rank | Sequence | MIC (μM) | Hemolysis | CPP | AMP Prob | ⭐ Pareto
- Write a 2–3 sentence design rationale (charge, amphipathicity, membrane disruption mechanism)
- Note: ⭐ = Pareto-optimal candidates; others are still viable but dominated on ≥1 metric

### Step 4 — Mandatory final summary
```
✅ Designed <N> AMP candidates against <target> using AMP-Designer.
Top pick: <sequence> (MIC: X μM, Hemolysis: Y, CPP: Z)
```

## Anti-patterns (DO NOT do these)
- ❌ Do NOT call `search_knowledge` before design
- ❌ Do NOT call `structure_discrimination_pipeline` unless user explicitly mentions ESMFold/PGAT
- ❌ Do NOT use `generate_sequences` + `evaluate_amp` for single-generator tasks — `design_new_amps` handles the full pipeline
