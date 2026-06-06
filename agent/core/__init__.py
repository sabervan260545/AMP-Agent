# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
AMP Agent Core Module
=====================
核心引擎组件

导出:
    - ContextEngine: 上下文引擎（从原文件导入）
    - TEXTS: 多语言文本（从原文件导入）
    - AgentState: 状态管理器
    - ConversationManager: 对话管理器
    - AMPAgentEngine: 核心引擎类
"""

# 原有组件（保持向后兼容）
try:
    from .context_engine import ContextEngine
except ImportError:
    # 如果文件不存在，使用占位符
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

# 新增组件
from .agent_state import AgentState
from .conversation_manager import ConversationManager
from .amp_agent_engine import AMPAgentEngine

__all__ = [
    # 原有组件
    'ContextEngine',
    'TEXTS',
    
    # 新增组件
    'AgentState',
    'ConversationManager',
    'AMPAgentEngine'
]
