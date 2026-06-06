# Skill: compare_generators

## Trigger
User explicitly wants to **compare multiple generators** (AMP-Designer, Diff-AMP, HydrAMP). Keywords: "compare", "benchmark", "AMP-Designer vs Diff-AMP", "which generator is better", "performance difference".

## SOP (Standard Operating Procedure)

⚠️ CRITICAL: During comparison, DO NOT call `search_knowledge` or other unrelated tools. Focus ONLY on: generate → evaluate → analyze.
⚠️ CRITICAL: Do NOT use `design_new_amps` for comparison — it runs a single-model pipeline and loses cross-model comparison.

### Step 1 — Generate from each model separately (DO NOT evaluate yet)
```
seqs_designer = generate_sequences(num_samples=3, target="Gram-negative", generator="default")
seqs_diffamp  = generate_sequences(num_samples=3, target="Gram-negative", generator="diverse")
seqs_hydramp  = generate_sequences(num_samples=3, target="Gram-negative", generator="refine")
```
Use the target extracted from user's message. Default num_samples per generator: 3.

### Step 2 — Merge all sequences
```
all_sequences = seqs_designer + seqs_diffamp + seqs_hydramp  # Total 9 sequences
```

### Step 3 — Evaluate all sequences together (single call)
```
evaluated = evaluate_amp(sequences=all_sequences)
```

### Step 4 — Comparative analysis with GROUPED statistics
⚠️ DO NOT just show a ranked list — that is NOT a comparison.

YOU MUST group results by `generator` field and calculate:
- Average MIC per generator: `sum(mic_values) / count`
- Average hemolysis per generator
- Average CPP per generator
- Success rate per generator (amp_score ≥ 0.5)

Then identify winners:
- Which generator has lowest average MIC (highest potency)?
- Which generator has lowest average hemolysis (best safety)?
- Which generator has best overall balance?

⚠️ DO NOT generate 3 separate Pareto plots.

### Step 5 — Present results in TWO parts

**Part 1: Summary statistics table (3 rows, one per generator)**
```
=== Generator Comparison Statistics ===

| Generator    | Avg MIC (μM) | Avg Hemolysis | Avg CPP | Valid AMP Rate  |
|--------------|-------------|---------------|---------|-----------------|
| AMP-Designer | 12.3        | 0.22          | 0.18    | 66.7% (2/3)     |
| Diff-AMP     | 15.7        | 0.18          | 0.15    | 33.3% (1/3)     |
| HydrAMP      | 9.8         | 0.28          | 0.22    | 100% (3/3)      |

Overall conclusions:
- 🏆 Best potency: HydrAMP (Avg MIC 9.8 μM)
- 🛑 Best safety: Diff-AMP (Avg hemolysis 0.18)
- ⚖️ Best balance: AMP-Designer
```

**Part 2: Full sequence details table with Generator column**
```
| Rank | Generator    | Sequence      | MIC (μM) | Hemo | CPP  | AMP Prob |
|------|-------------|---------------|---------|------|------|----------|
| 1    | HydrAMP     | KWKLFKK...    | 7.2     | 0.28 | 0.22 | 0.95     |
| 2    | AMP-Designer| GIGKFL...     | 12.3    | 0.22 | 0.18 | 0.78     |
```

Write a clear comparative summary with recommendations based on application scenario.

## Anti-patterns (DO NOT do these)
- ❌ Do NOT call `design_new_amps` for comparison tasks
- ❌ Do NOT present only a ranked list without grouped statistics
- ❌ Do NOT generate 3 separate Pareto plots
- ❌ Do NOT call `search_knowledge` during comparison
