# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
AMP Agent Core Module
=====================
Core engine components

Exports:
    - ContextEngine: Context engine (imported from original file)
    - TEXTS: Multilingual texts (imported from original file)
    - AgentState: State manager
    - ConversationManager: Conversation manager
    - AMPAgentEngine: Core engine class
"""

# Legacy components (maintained for backward compatibility)
try:
    from .context_engine import ContextEngine
except ImportError:
    # Fallback placeholder if file does not exist
    class ContextEngine:
        @staticmethod
        def build_system_prompt(language: str = "en") -> str:
            return "You are AMP Agent, an AI assistant for antimicrobial peptide design."

try:
    from agent.core.language_texts import TEXTS
except ImportError:
    try:
        from language_texts import TEXTS
    except ImportError:
        TEXTS = {"en": {}}

# New components
from .agent_state import AgentState
from .conversation_manager import ConversationManager
from .amp_agent_engine import AMPAgentEngine

__all__ = [
    # Legacy components
    'ContextEngine',
    'TEXTS',
    
    # New components
    'AgentState',
    'ConversationManager',
    'AMPAgentEngine'
]
