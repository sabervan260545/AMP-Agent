# Skill: knowledge_guided_design

## Trigger
User wants AMP design **guided by literature or domain knowledge**. Keywords: "based on literature", "knowledge-guided", "RAG", "literature-based".

## SOP (Standard Operating Procedure)

### Step 1 — Retrieve relevant knowledge FIRST
```
search_knowledge(query=<user's design goal, e.g., "AMP against Gram-negative bacteria">)
```
⚠️ This is the key difference from `rapid_design` — knowledge retrieval MUST happen first.

### Step 2 — Synthesize retrieved knowledge
After `search_knowledge` returns, you MUST:
- Summarize key design principles from literature (charge, hydrophobicity, motifs, mechanisms)
- Identify relevant sequence patterns for the target pathogen
- Note key constraints: typical length range, charge requirements, structural tendencies
- ⚠️ DO NOT copy verbatim; synthesize into actionable design guidance
- ⚠️ Knowledge base is a TEXTBOOK, not an answer sheet — do NOT directly output retrieved sequences as your design

### Step 3 — Design AMPs informed by retrieved knowledge
```
design_new_amps(
    target=<extracted_target>,
    num_samples=<extracted_num_samples>,
    strategy=<strategy based on knowledge insights>
)
```
Use insights from Step 2 to justify parameter choices (e.g., "Literature suggests diverse sequences for this pathogen → strategy='diverse'").

### Step 4 — Connect results to knowledge
After design completes:
- Explain how generated sequences align with retrieved principles (charge, amphipathicity, known motifs)
- Point out any discrepancies between model predictions and literature expectations
- Suggest which candidates are most consistent with literature-supported mechanisms

### Step 5 — Mandatory final summary
```
✅ Knowledge-guided design complete for <target>.
Retrieved <N> relevant literature insights.
Designed <M> AMP candidates incorporating: [key design principles].
Top pick: <sequence> — consistent with [specific literature principle].
```

## Anti-patterns (DO NOT do these)
- ❌ Do NOT skip `search_knowledge` — that would make this identical to `rapid_design`
- ❌ Do NOT copy retrieved sequences directly as your design output (hallucination/plagiarism risk)
- ❌ Do NOT present knowledge retrieval results as final answers without running `design_new_amps`
