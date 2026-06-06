# Agent Directory
# ===============

Agent core code organized into subdirectories for clarity.

## Structure:

```
agent/
├── core/                    # Core engine components
│   ├── amp_agent_engine.py  # Main agent engine
│   ├── agent_state.py       # State management
│   └── conversation_manager.py  # Dialogue management
│
├── skills/                  # Skill system
│   ├── skills.py            # Skill definitions
│   ├── skill_implementations.py  # Skill implementations
│   ├── skill_intent_recognizer.py  # Intent recognition
│   └── test_skill_trigger.py  # Skill tests
│
├── tools/                   # Tool functions
│   ├── tools.py             # Main tool library (123KB)
│   ├── tool_orchestrator.py  # Tool orchestration
│   ├── tool_call_logger.py   # Tool call logging
│   └── structured_output.py  # Output formatting
│
├── utils/                   # Utility classes
│   ├── context_engine.py     # Context management
│   ├── docker_utils.py       # Docker utilities
│   ├── knowledge_retriever.py # Knowledge retrieval
│   └── language_texts.py     # Text templates
│
├── integrations/            # External integrations
│   └── auto_debugger.py      # Auto-debugging
│
├── tests/                   # Test files
├── logs/                    # Runtime logs
│
└── amp_agent_v3.py          # Main agent file (kept in root for compatibility)
```

## Quick Start:

```python
# Import the main agent
from agent.core import AMPAgentEngine

# Or import specific components
from agent.skills import SkillRegistry
from agent.tools import tool_generate_amp
```

## Last Updated: 2026-01-12
