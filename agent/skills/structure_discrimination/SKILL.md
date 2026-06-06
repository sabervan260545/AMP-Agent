# Skill: structure_discrimination

## Trigger
User EXPLICITLY mentions structure-based validation. ALL of the following keywords must be present (or strongly implied together): "structure-based" AND "ESMFold" / "PGAT" / "3D structure" / "structure discrimination".

⚠️ DO NOT trigger this skill if user simply says "Design X AMPs" without structure keywords.

## SOP (Standard Operating Procedure)

### Pre-check — Verify Docker services
`structure_discrimination_pipeline` requires Docker service `amp-pgat-abpp` on port 8010.
- If service is unavailable → immediately fall back to `design_new_amps` (see Step 3b).

### Step 1 — Call structure_discrimination_pipeline
```
structure_discrimination_pipeline(
    target=<extracted_target>,
    num_samples=<extracted_num_samples>
)
```
This pipeline internally runs: Generate → ESMFold 3D structure prediction → PGAT-ABPp discrimination → MIC/Hemolysis/CPP evaluation.

### Step 2 — Present structure-validated results
After successful return:
- Show table: Rank | Sequence | MIC (μM) | Hemolysis | CPP | PGAT Score | 3D Confidence
- Mention which sequences passed structure discrimination (PGAT score threshold)
- Explain why structure validation adds value: "PGAT-ABPp confirms that these sequences maintain stable 3D conformations consistent with AMP activity"

### Step 3a — Mandatory final summary (success)
```
✅ Structure-validated design complete.
Generated <N> sequences → ESMFold predicted 3D structures → PGAT-ABPp filtered.
Final candidates: <M> sequences passed structure discrimination.
```

### Step 3b — Fallback (service unavailable)
If `structure_discrimination_pipeline` fails after ≤2 retries:
```
sequences = generate_sequences(num_samples=5, target="Gram-negative", generator="default")
evaluated = evaluate_amp(sequences=sequences)
ranked = rank_sequences(evaluated_data=evaluated, strategy="pareto")
```
Explain to user: "PGAT-ABPp structure discrimination service is currently unavailable. Using standard generation + evaluation pipeline instead."
⚠️ After fallback completes, DO NOT call `structure_discrimination_pipeline` again — task is complete.

## Anti-patterns (DO NOT do these)
- ❌ Do NOT use this skill for regular design requests without structure keywords
- ❌ Do NOT retry structure_discrimination_pipeline more than 2 times
- ❌ Do NOT call structure_discrimination_pipeline again after fallback completes
