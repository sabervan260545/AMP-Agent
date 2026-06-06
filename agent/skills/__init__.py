# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
AMP Agent Skills System
=======================
Unified Skills import interface

Skills are high-level capabilities that encapsulate complex workflows, enabling
the agent to handle multi-step requirements flexibly.

Architecture layers:
    - Tool Layer: atomic operations (generate, evaluate, predict, etc.)
    - Skill Layer: workflow orchestration (multi-tool composition + decision logic)
    - Agent Layer: intent recognition + Skill routing

Usage example:
    ```python
    from agent.skills import rapid_design
    
    # Rapid AMP design
    result = rapid_design(
        target="E. coli",
        num_candidates=10
    )
    
    print(result.summary)
    ```
"""

from .base import (
    SkillResult,
    SkillDefinition,
    SkillPriority,
    SkillRegistry,
    get_skill_registry,
    skill_decorator
)


# Lazy-import implementation modules to avoid circular dependencies
def __getattr__(name):
    if name == 'rapid_design':
        from .skill_implementations import rapid_design
        return rapid_design
    elif name == 'structure_validated_design':
        from .skill_implementations import structure_validated_design
        return structure_validated_design
    elif name == 'knowledge_guided_design':
        from .skill_implementations import knowledge_guided_design
        return knowledge_guided_design
    elif name == 'SkillIntentRecognizer':
        from .intent_recognizer import SkillIntentRecognizer
        return SkillIntentRecognizer
    elif name == 'SkillIntegratedAgent':
        from .skill_integrated_agent import SkillIntegratedAgent
        return SkillIntegratedAgent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Base classes
    'SkillResult',
    'SkillDefinition',
    'SkillPriority',
    'SkillRegistry',
    
    # Registry
    'get_skill_registry',
    'skill_decorator',
    
    # Core Skills
    'rapid_design',
    'structure_validated_design',
    'knowledge_guided_design',
    
    # Intent recognition
    'SkillIntentRecognizer',
    
    # Integrated agent
    'SkillIntegratedAgent',
]


# Package version info
__version__ = '1.0.0'
__author__ = 'AMP Platform Team'


def register_all_skills():
    """
    Register all available Skills
    
    Returns:
        Number of registered Skills
    """
    from .skill_implementations import register_core_skills
    return register_core_skills()


def get_available_skills():
    """
    Get list of all available Skills
    
    Returns:
        List of Skill names
    """
    # Ensure registration is executed (prevent registry instance mismatch from parallel imports)
    from .skill_implementations import register_core_skills
    register_core_skills()
    registry = get_skill_registry()
    return [s['name'] for s in registry.list_skills()]


def describe_skill(name: str) -> str:
    """
    Get detailed description of a specific Skill
    
    Args:
        name: Skill name
    
    Returns:
        Skill description string
    """
    registry = get_skill_registry()
    
    definition = registry.get_definition(name)
    if definition is None:
        return f"❌ Skill '{name}' not found"
    
    description = f"**{name}**\n\n"
    description += f"{definition.description}\n\n"
    description += f"**Priority**: {definition.priority.value}\n"
    description += f"**Category**: {definition.category}\n"
    description += f"**Required Params**: {', '.join(definition.required_params) if definition.required_params else 'None'}\n"
    description += f"**Tags**: {', '.join(definition.tags) if definition.tags else 'None'}\n"
    
    return description