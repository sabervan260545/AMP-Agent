# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
AMP Agent Skills - High-level Task Orchestration Layer
======================================================

Skills are high-level capabilities that encapsulate complex workflows, enabling
the agent to handle multi-step requirements flexibly.

Architecture layers:
    - Tool Layer: atomic operations (generate, evaluate, predict, etc.)
    - Skill Layer: workflow orchestration (multi-tool composition + decision logic)
    - Agent Layer: intent recognition + Skill routing

Design principles:
    1. Each Skill is an independent, reusable complete capability
    2. Skills encapsulate best practices and domain expert experience
    3. Support conditional branching, loops, exception handling
    4. Maintain backward compatibility with existing Tool system

Author: AMP Platform Team
Version: 1.0.0
License: MIT
"""

import logging
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class SkillPriority(Enum):
    """Skill priority enum"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class SkillResult:
    """Skill execution result"""
    success: bool
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'message': self.message,
            'data': self.data,
            'metadata': self.metadata
        }


@dataclass
class SkillDefinition:
    """Skill definition"""
    name: str
    description: str
    category: str  # 'design', 'evaluation', 'analysis', 'optimization'
    priority: SkillPriority = SkillPriority.MEDIUM
    required_params: List[str] = field(default_factory=list)
    optional_params: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'description': self.description,
            'category': self.category,
            'priority': self.priority.value,
            'required_params': self.required_params,
            'optional_params': self.optional_params,
            'tags': self.tags
        }


class SkillRegistry:
    """Skill registry center"""
    
    def __init__(self):
        self._skills: Dict[str, Callable] = {}
        self._definitions: Dict[str, SkillDefinition] = {}
    
    def register(self, 
                 name: str, 
                 func: Callable,
                 definition: SkillDefinition):
        """Register a Skill"""
        self._skills[name] = func
        self._definitions[name] = definition
        logger.info(f"✅ Registered skill: {name}")
    
    def get_skill(self, name: str) -> Optional[Callable]:
        """Get Skill function"""
        return self._skills.get(name)
    
    def get_definition(self, name: str) -> Optional[SkillDefinition]:
        """Get Skill definition"""
        return self._definitions.get(name)
    
    def list_skills(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all available Skills"""
        skills = []
        for name, definition in self._definitions.items():
            if category is None or definition.category == category:
                skills.append(definition.to_dict())
        return sorted(skills, key=lambda x: x['priority'], reverse=True)
    
    def has_skill(self, name: str) -> bool:
        """Check if a Skill exists"""
        return name in self._skills


# Global Skill registry
_global_skill_registry = SkillRegistry()


def get_skill_registry() -> SkillRegistry:
    """Get the global Skill registry"""
    return _global_skill_registry


def skill_decorator(func: Callable) -> Callable:
    """Skill decorator"""
    func._is_skill = True
    return func