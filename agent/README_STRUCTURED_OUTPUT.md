# AMP Agent: Structured Output and Biological Expert Upgrade

## Overview

The core goal of this upgrade is to **turn the LLM into a real AMP biologist
rather than a plain tool-call dispatcher**.

### Shipped capabilities

1. **Knowledge base expansion** (7,387 entries)
   - 575 literature passages (mechanism, design strategy, clinical trials)
   - 482 MIC experimental records (activity tiers: high / medium / low)
   - 4,404 CPP records (cell-penetrating properties)
   - 1,926 hemolysis records (safety profile)

2. **Expert-oriented system prompt**
   - Strengthens the biologist role
   - Deepens the AMP design principles (amphipathicity, net charge,
     hydrophobicity, helical structure)
   - Enforces a "knowledge base first" rule
   - Adds detailed few-shot examples

3. **Structured output system**
   - JSON-schema-constrained responses
   - Tool-call chain tracking
   - Biological reasoning validation
   - Quality metric scoring

4. **Tool-call logging**
   - Records every `search_knowledge` call
   - Tracks parameters, results, latency, relevance
   - Exports aggregated reports

---

## Core design principle

### **You are a biologist first, and an AI tool user second.**

```
Priority order:
1. search_knowledge  -> learn design principles
2. plan              -> decide which tools to run, based on evidence
3. execute tools     -> generate / evaluate / predict
4. interpret results -> reason with peptide chemistry
5. validate          -> cross-check against the literature
```

---

## Structured output example

### Input
```text
User: "Design 3 antimicrobial peptides targeting E. coli with low toxicity."
```

### Output (structured)
```json
{
  "session_id": "session_20251213_203642",
  "user_query": "Design 3 antimicrobial peptides targeting E. coli with low toxicity.",

  "reasoning_chain": [
    {
      "reasoning_type": "knowledge_query",
      "thought": "E. coli is Gram-negative, so the outer LPS barrier matters. Let me first look up design principles for G- bacteria.",
      "citations": [
        {
          "source": "literature",
          "query": "Gram-negative AMP design net charge",
          "relevance_score": 0.82,
          "content_snippet": "AMPs targeting G- usually require a net charge of +4 to +7 ..."
        }
      ],
      "principles": ["membrane", "net_charge", "hydrophobicity"],
      "confidence": 0.9
    },
    {
      "reasoning_type": "tool_planning",
      "thought": "Based on the KB, target parameters: net charge +5, hydrophobicity 50-60%, alpha-helical. Now generate sequences.",
      "principles": ["helix", "hydrophobicity"],
      "confidence": 0.85
    }
  ],

  "tool_calls": [
    {
      "tool_name": "search_knowledge",
      "parameters": {
        "query": "Gram-negative AMP design net charge hydrophobicity",
        "knowledge_type": "literature",
        "top_k": 5
      },
      "success": true,
      "latency_ms": 127.5
    },
    {
      "tool_name": "generate_sequences",
      "parameters": {
        "target": "Gram-negative",
        "count": 10
      },
      "success": true,
      "latency_ms": 3245.8
    }
  ],

  "quality_metrics": {
    "total_knowledge_queries": 1,
    "knowledge_coverage_score": 0.60,
    "biological_rigor_score": 0.75
  }
}
```

### Quality-validation output
```
Biological-rigor check

Knowledge-base queries : 1
Knowledge coverage     : 0.60 / 1.0
Biological rigor       : 0.75 / 1.0

Warnings:
- Knowledge coverage is below target (0.60). Consider citing more literature.

Structured response saved to: <project_root>/agent/logs/structured_session_*.json
```

---

## How to use

### 1. Validate the structured output (no LLM required)
```bash
cd <project_root>/agent
python3 test_structured_agent.py --test 3
```

### 2. Validate the "knowledge base first" rule (requires Qwen running)
```bash
# Make sure the Qwen service is running on http://localhost:8000
python3 test_structured_agent.py --test 1
```

### 3. End-to-end design flow
```bash
python3 test_structured_agent.py --test 2
```

### 4. Use inside the Streamlit UI
```bash
streamlit run amp_ui_v3.py
```
The agent automatically emits structured output; the quality check is
rendered after every response.

---

## Key files

| File                         | Purpose                | Notes                                 |
|------------------------------|------------------------|---------------------------------------|
| `amp_agent_v3.py`            | Agent main class       | Structured output + validation wired  |
| `structured_output.py`       | Structured-output core | Parse, validate, score                |
| `tool_call_logger.py`        | Tool-call logger       | Records every tool invocation         |
| `knowledge_retriever.py`     | Knowledge retriever    | 7,387 entries, vectorized             |
| `test_structured_agent.py`   | Test harness           | 3 validation scenarios                |

---

## Quality metrics

### 1. Knowledge coverage score
```python
# Formula
score = min(num_citations / 5.0, 1.0)

# Scale
# 0.8 - 1.0 : excellent (well cited)
# 0.5 - 0.8 : good      (some literature support)
# 0.0 - 0.5 : weak      (insufficient evidence)
```

### 2. Biological rigor score
```python
# Formula
score = (principle_coverage + knowledge_support) / 2

# Scale
# 0.7 - 1.0 : excellent (principle-compliant)
# 0.4 - 0.7 : acceptable
# 0.0 - 0.4 : fails (weak scientific reasoning)
```

### 3. Validation rules

**Mandatory**:
- Every design task must query the knowledge base first.
- Every sequence generation must be preceded by a `search_knowledge` call.
- Theoretical questions must cite literature.

**Warnings**:
- `total_knowledge_queries == 0`        -> knowledge base not consulted
- `knowledge_coverage_score < 0.3`      -> coverage too low
- `biological_rigor_score < 0.4`        -> insufficient rigor

---

## 14B vs 32B capability evaluation

### Dimensions

| Dimension               | 14B (baseline) | 32B (expected) | Method                                    |
|-------------------------|----------------|----------------|-------------------------------------------|
| KB-usage rate           | TBD            | higher         | count `search_knowledge` invocations      |
| Reasoning depth         | TBD            | deeper         | analyze `reasoning_chain` length & quality|
| Terminology accuracy    | TBD            | higher         | match `biological_principles`             |
| Design novelty          | TBD            | higher         | diversity & activity of generated peptides|
| Auto-debug self-repair  | TBD            | stronger       | auto-debug success rate                   |

### Comparison harness (planned)
```python
# TODO: benchmark_14b_vs_32b.py
# - Run the same tasks on both 14B and 32B.
# - Compare the quality metrics.
# - Emit a comparison report.
```

---

## Few-shot examples (already embedded in the prompt)

### Example 1: theoretical question (knowledge base first)
```
User: "What are the key principles for designing stable antimicrobial peptides?"

Thought: This is a theory question. I must first search the KB and answer
         with literature support.

Action : search_knowledge
Input  : {"query": "AMP design principles stability optimization modifications", "top_k": 5}

[Receives literature hits with relevance ~0.78]

Thought: The literature highlights hydrophobicity balance, helical structure,
         and C-terminal modifications.

Answer : Based on the knowledge base (5 papers), the key design principles
         include ...
```

### Example 2: design task (knowledge first, tools second)
```
User: "Design 3 highly stable antimicrobial peptides targeting E. coli."

Thought: The user wants highly stable AMPs. Let me look up stability-enhancing
         strategies first.

Action : search_knowledge
Input  : {"query": "improve AMP stability protease resistance modification", "top_k": 3}

[Learns about D-amino-acid substitution, cyclization, N-methylation]

Thought: The KB recommends cyclization and non-natural amino acids. Now
         generate the sequences.

Action : generate_sequences
Input  : {"target": "Gram-negative", "count": 10}
```

---

## Roadmap

1. **Knowledge graph construction** (Task 4)
   - Entity recognition: AMP names, bacterial species, modifications
   - Relation extraction: sequence-activity, structure-function
   - Graph queries: complex multi-hop reasoning

2. **LLM capability comparison** (Task 5)
   - 14B baseline tests
   - Wire up 32B API
   - Emit a performance comparison report

3. **UI enhancements**
   - Render the structured reasoning chain
   - Visualize knowledge coverage
   - Export the quality report

---

## Usage tips

### Best practices
1. For every design task, let the model query the KB first.
2. Watch the quality metrics - aim for `biological_rigor_score > 0.6`.
3. Persist the structured JSON for later analysis and reproducibility.

### Caveats
1. If you see the "KB not consulted" warning, the prompt needs more pressure.
2. Coverage < 0.3 usually means the LLM is hallucinating - re-run.
3. If 14B cannot reach the expected quality, fall back to the 32B API.

---

## Log locations

- **Tool-call log**: `<project_root>/agent/logs/session_*.jsonl`
- **Structured response**: `<project_root>/agent/logs/structured_*.json`
- **Aggregate report**: call `ToolCallLogger().generate_report()`

---

**Upgrade goal**: Turn the LLM from an AI tool-call dispatcher into an
AMP biologist.
**Key levers**: Mandatory KB-first + structured-output validation +
biological-rigor scoring.
