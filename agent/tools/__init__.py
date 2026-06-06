# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
AMP Agent Tools Module
======================
工具函数集合
"""

# 保持向后兼容 - 原有导入仍然有效
from .tools import *

# 导出 search_knowledge（从同目录下的 search_knowledge.py）
try:
    from .search_knowledge import search_knowledge
except ImportError:
    search_knowledge = None

__all__ = [
    'tool_generate_amp',
    'tool_batch_evaluate',
    'tool_rank_sequences',
    'tool_mutate_sequence',
    'TOOL_REGISTRY',
    'TOOLS_SCHEMA',
    'search_knowledge',
]
