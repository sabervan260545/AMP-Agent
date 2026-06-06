# AMP-Agent Skills System Guide

## Layout

```
agent/
├── skills.py                      # Skill base framework (core)
├── skill_implementations.py       # Core skill implementations
├── skill_agent_example.py         # Integration example
├── amp_agent_v3.py                # Existing agent (backward compatible)
└── tools.py                       # Atomic tools (unchanged)
```

---

## Architectural Layers

### Layer 1 — Tool layer

- **Responsibility**: atomic capabilities.
- **Characteristics**: single purpose, low level, direct service calls, stateless or trivially stateful.
- **Examples**:

  ```python
  tool_generate_amp()       # generate sequences
  tool_batch_evaluate()     # batch evaluation
  tool_rank_sequences()     # ranking
  tool_predict_structure()  # structure prediction
  ```

### Layer 2 — Skill layer ⭐ (new)

- **Responsibility**: orchestrate complex workflows.
- **Characteristics**: compose multiple tools, encapsulate best practices, support branching / loops / error recovery, provide a clear contract.
- **Examples**:

  ```python
  rapid_design()                # generate → evaluate → rank
  structure_validated_design()  # generate → evaluate → fold → classify
  knowledge_guided_design()     # RAG → inject → generate
  ```

### Layer 3 — Agent layer

- **Responsibility**: intent recognition + skill routing.
- **Characteristics**: understands natural language, picks the right skill, forwards parameters, returns results.
- **Examples**:

  ```python
  # User: "Please rapidly design 10 peptides against E. coli."
  agent.execute_skill("rapid_design", target="E. coli", num_candidates=10)
  ```

---

## Core Skills

### 1. Rapid Design

- **Skill name**: `rapid_design`
- **Workflow**:

  ```
  1. Generate sequences with the selected generator.
  2. Batch evaluate (MIC + Hemolysis + CPP + Macrel).
  3. Pareto rank and return Top-K.
  ```

- **When to use**: quickly obtain candidate sequences; no need for structural verification; time-sensitive tasks.
- **Example**:

  ```python
  from skills import get_skill_registry

  registry = get_skill_registry()
  rapid_design = registry.get_skill("rapid_design")

  result = rapid_design(
      target="E. coli",
      num_candidates=10,
      generator="default",
  )

  print(result.to_dict())
  # {
  #   "success": True,
  #   "message": "Successfully designed 10 AMP candidates",
  #   "data": {
  #     "candidates": [...],
  #     "generator_used": "default",
  #   },
  # }
  ```

---

### 2. Structure-Validated Design

- **Skill name**: `structure_validated_design`
- **Workflow**:

  ```
  1. Over-sample candidates (×3 oversampling).
  2. Initial evaluation (MIC + Hemolysis + CPP).
  3. ESMFold structure prediction.
  4. PGAT-ABPp classification (filter by fold_score).
  5. Return validated sequences.
  ```

- **When to use**: high-risk targets, designs that must fold reliably, final-shortlist filtering.
- **Example**:

  ```python
  structure_design = registry.get_skill("structure_validated_design")

  result = structure_design(
      target="S. aureus",
      num_candidates=5,
      min_fold_score=0.6,
  )

  # result.data["candidates"] contains validated sequences,
  # each with `fold_score` and `structure_pdb` fields.
  ```

---

### 3. Knowledge-Guided Design

- **Skill name**: `knowledge_guided_design`
- **Workflow**:

  ```
  1. Retrieve knowledge from the RAG store using target / keywords.
  2. Extract design principles and mechanisms.
  3. Inject them into the generator prompt.
  4. Generate and evaluate sequences.
  ```

- **When to use**: target-specific mechanism-aware design, domain-knowledge augmentation, exploring novel mechanisms.
- **Example**:

  ```python
  knowledge_design = registry.get_skill("knowledge_guided_design")

  result = knowledge_design(
      target="P. aeruginosa",
      query_keywords="membrane disruption mechanism",
      use_rag=True,
  )

  # result.data["design_principles_used"] contains retrieved principles.
  # result.data["mechanisms_used"] contains extracted mechanisms.
  ```

---

## Adding a Custom Skill

### Step 1 — Define the skill

In `skill_implementations.py`:

```python
from skills import skill_decorator, SkillResult, SkillDefinition, SkillPriority

@skill_decorator
def my_custom_skill(param1: str, param2: int = 10) -> SkillResult:
    """
    My custom skill.

    Workflow:
    1. ...
    2. ...
    3. ...
    """
    try:
        # Step 1: ...
        # Step 2: ...
        # Step 3: ...
        return SkillResult(
            success=True,
            message="Custom skill completed",
            data={"key_result": "value"},
            metadata={
                "execution_time": time.time() - start_time,
                "skill_name": "my_custom_skill",
            },
        )
    except Exception as e:
        return SkillResult(
            success=False,
            message=f"Custom skill failed: {str(e)}",
            data={},
        )
```

### Step 2 — Register it

Extend `register_core_skills()`:

```python
def register_core_skills():
    registry = get_skill_registry()

    registry.register(
        name="my_custom_skill",
        func=my_custom_skill,
        definition=SkillDefinition(
            name="my_custom_skill",
            description="Description of my custom skill",
            category="design",          # or "evaluation", "analysis", "optimization"
            priority=SkillPriority.MEDIUM,
            required_params=["param1"],
            optional_params={"param2": 10},
            tags=["custom", "special"],
        ),
    )
```

---

## Skills vs Tools

| Dimension          | Tool                     | Skill                          |
| ------------------ | ------------------------ | ------------------------------ |
| Granularity        | Atomic operation         | Composite workflow             |
| Responsibility     | Execute one task         | Orchestrate multiple steps     |
| Complexity         | Low                      | High                           |
| Reusability        | Cross-project generic    | Domain-specific                |
| Decision logic     | None / simple            | Branching, looping             |
| State              | Stateless                | Stateful                       |
| Error handling     | Raise                    | Internal recovery / fallback   |
| Audience           | Developer                | End user                       |

---

## Usage Patterns

### Pattern 1 — Use the skill registry directly

```python
from skills import get_skill_registry

registry = get_skill_registry()
skill = registry.get_skill("rapid_design")
result = skill(target="E. coli", num_candidates=10)
```

### Pattern 2 — Wrap with a skill agent

```python
from skill_agent_example import SkillEnabledAgent

skill_agent = SkillEnabledAgent(base_agent=agent)
result = skill_agent.rapid_design_amp(
    target="E. coli",
    num_candidates=10,
)
```

### Pattern 3 — Auto-routing inside the ReAct loop (future)

The agent recognises the user's intent and picks the right skill automatically:

```python
# User: "Please rapidly design peptides against E. coli."
# Agent selects the `rapid_design` skill automatically.
```

---

## Listing Available Skills

```python
from skills import get_skill_registry

registry = get_skill_registry()

all_skills = registry.list_skills()
design_skills = registry.list_skills(category="design")

for skill in design_skills:
    print(f"- {skill['name']}: {skill['description']}")
```

---

## Best Practices

### When to build a skill

Build one when you need to:

- Compose multiple tools.
- Encode a repeatable workflow.
- Express conditional decisions.
- Capture domain-expert knowledge.

Don't build one when:

- A single tool call suffices.
- The workflow is fixed and trivial.
- The task is a one-off.

### Design principles

- **Self-contained** — a skill is a complete capability on its own.
- **Reusable** — encodes best practices, usable in several contexts.
- **Explainable** — the inputs and outputs are specified.
- **Robust** — handles exceptions internally and offers graceful fallbacks.

### Naming

- Use `snake_case`.
- The name should describe the business intent, not the implementation.
- Examples: `rapid_design`, `structure_validated_design`.

---

## Migration Path

### Phase 1 — Backward compatibility (current)

- All existing tools keep working.
- The agent still defaults to tools.
- Skills act as an optional extension.

### Phase 2 — Gradual integration (future)

- The agent prefers skills when available.
- Complex tasks automatically go through skills.
- Simple tasks continue to call tools directly.

### Phase 3 — Skill-first (long term)

- The agent is built primarily on skills.
- Tools become low-level primitives.
- Skills are discoverable and dynamically loadable.

---

## Example Scenarios

### Scenario 1 — Rapid design

User: *"Design 10 peptides against E. coli, I'm in a hurry."*

Tool-based approach:

```python
seqs = tool_generate_amp(target="E. coli", num_samples=10)
evaluated = tool_batch_evaluate(seqs)
ranked = tool_rank_sequences(evaluated, strategy="pareto")
```

Skill-based approach:

```python
result = rapid_design(target="E. coli", num_candidates=10)
# Done in one call.
```

---

### Scenario 2 — High-risk target requiring correct folding

User: *"Design a cell-penetrating peptide targeting cancer cells — it must fold correctly."*

Tool-based approach:

```python
seqs = tool_generate_amp(...)
evaluated = tool_batch_evaluate(seqs)
structures = [tool_predict_structure(s) for s in evaluated]
filtered = [s for s in structures if s["fold_score"] > 0.6]
ranked = tool_rank_sequences(filtered, ...)
```

Skill-based approach:

```python
result = structure_validated_design(
    target="cancer cells",
    num_candidates=5,
    min_fold_score=0.6,
)
```

---

### Scenario 3 — Mechanism-aware design

User: *"Design a novel antibacterial peptide against P. aeruginosa, ideally one that disrupts biofilms."*

Tool-based approach:

```python
rag_docs = tool_search_knowledge("P. aeruginosa biofilm disruption")
context = format_knowledge(rag_docs)
seqs = tool_generate_amp(target="P. aeruginosa", context=context)
evaluated = tool_batch_evaluate(seqs)
...
```

Skill-based approach:

```python
result = knowledge_guided_design(
    target="P. aeruginosa",
    query_keywords="biofilm disruption mechanism",
)
```

---

## Summary

### Value delivered

1. Raises the abstraction level from "tool invocation" to "task completion".
2. Encodes expert practices into reusable skills.
3. Speeds up development by composing existing skills.
4. Keeps the system flexible — skills can be combined to tackle novel requirements.

### Next steps

- Core skills shipped: Rapid Design, Structure-Validated Design, Knowledge-Guided Design.
- Skill registry is in place.
- Example code is provided.
- Integrate with the production agent.
- Extend with more skills as real use cases emerge.

---

## Contact

For questions or suggestions, contact the AMP-Agent Platform team.
