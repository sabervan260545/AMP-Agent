# Skill: mutation_optimization

## Trigger
User asks to **mutate**, **optimize**, **improve**, **redesign**, **enhance**, or **refine** a **specific existing AMP sequence**.

Keywords (any combination triggers this skill):
- mutate, optimize, improve, redesign, enhance, refine + sequence

⚠️ DO NOT trigger this skill for general "Design new AMPs" requests — use `design_new_amps` instead.
⚠️ DO trigger this skill even when user says "analyze AND mutate" — run analyze first, then mutate.

---

## SOP (Standard Operating Procedure)

### Pre-flight — Extract sequence from context
- If user provides the sequence inline (e.g. "mutate VVGILIKIVNGVWKKILGRL"), use it directly.
- If user says "optimize #5" or "mutate the worst one", look up the sequence from the most recent
  ranked table in conversation history.
- If sequence cannot be determined, ask the user to provide it explicitly.

### Step 1 — Call `mutate_sequence` (RAG-enhanced)
```
mutate_sequence(
    sequence  = <extracted_sequence>,
    target    = <target_organism>,     # default "Gram-negative"
    goal      = <goal>,                # "lower_mic" | "lower_hemolysis" | "balanced" (default)
    num_variants = 3,                  # default 3
    rag_enhanced = true                # always true — enables Hybrid RAG context
)
```

**What happens internally:**
1. **Vector RAG** queries literature knowledge base for mutation rules matching the sequence profile
   (charge, hemolytic residues, helicity) and optimization goal.
2. **Graph RAG** retrieves ranked antimicrobial mechanisms against the target organism and
   evidence-based design principles (e.g. cationic_enhancement, amphipathic_helix).
3. **Database query** checks historical evaluations of identical or length-similar sequences
   to inform mutation positions via DB-mirror rule.
4. **RAG-informed rule library** generates diverse variants across rule types:
   - `cationic_N_term`: Add K/R at N-terminus → lower MIC via membrane disruption
   - `helix_mid`: Ala-substitution in mid-helix → improve amphipathic propensity
   - `hemolysis_reduce`: Replace W/F/Y with A/S → lower hemolysis (literature: Trp removal)
   - `db_mirror`: Mirror K/R positions from top DB performers with same length
5. **Batch evaluation**: MIC / Hemolysis / CPP / AMP probability for all variants.
6. **Ranking**: composite_score = 0.50×MIC_norm + 0.30×Hemo_norm + 0.20×(1−CPP_norm).

### Step 2 — Present results
After successful return, the handler automatically renders:
- **HTML comparison table**: original + all variants, green highlight on best variant
- **Δ metrics summary**: composite_score Δ, MIC Δ (μM), Hemolysis Δ, CPP Δ
- **LLM Mutation Analysis** (3 sections):
  - 🔬 Mutation Rationale (grounded in RAG knowledge)
  - 📈 Performance Improvement (quantified)
  - ✅ Recommendation (proceed / further optimize)

### Step 3 — Optional follow-up
If the user asks to "run another round" or "try lower_hemolysis goal":
- Call `mutate_sequence` again with the **best_variant sequence** as input and the new goal.
- This enables iterative optimization chains.

---

## Goal selection guide

| User intent | goal parameter |
|-------------|---------------|
| "MIC is too high / not potent enough" | `lower_mic` |
| "Too toxic / hemolysis too high" | `lower_hemolysis` |
| "Make it better overall" / default | `balanced` |
| "Improve safety without losing activity" | `lower_hemolysis` then verify MIC |

---

## Anti-patterns (DO NOT do these)
- ❌ Do NOT call `design_new_amps` when user wants to mutate an existing sequence
- ❌ Do NOT set `rag_enhanced=false` unless explicitly requested
- ❌ Do NOT apply mutate_sequence to sequences shorter than 5 amino acids
- ❌ Do NOT stop after generating variants — always show the comparison table + LLM analysis
- ❌ Do NOT run mutate_sequence more than 3 times in one turn without user confirmation

---

## Success criteria
✅ Comparison table rendered (original vs ≥3 variants)
✅ Best variant composite_score lower than original (improvement > 0)
✅ LLM mutation analysis completed with RAG citations
✅ User can identify the best mutant and understand why it is better
