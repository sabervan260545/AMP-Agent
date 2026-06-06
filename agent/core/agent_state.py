# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
AMP Agent State Management
==========================
Agent 状态管理类，负责管理对话历史、全局数据框、可视化状态等。
"""

import logging
from typing import List, Dict, Any, Optional
import pandas as pd

logger = logging.getLogger(__name__)


class AgentState:
    """
    Agent 状态管理器
    
    职责:
    1. 管理对话历史
    2. 管理全局序列数据框
    3. 管理可视化生成状态
    4. 管理当前用户输入
    
    Attributes:
        conversation_history: List[Dict] - 对话历史记录
        global_df: pd.DataFrame - 所有生成的序列数据
        visualization_generated: bool - 是否已生成可视化
        current_user_input: str - 当前用户输入
    """
    
    def __init__(self):
        """初始化 Agent 状态"""
        self.conversation_history: List[Dict[str, str]] = []
        self.global_df: Optional[pd.DataFrame] = None
        self.visualization_generated: bool = False
        self.current_user_input: str = ""
        
        logger.debug("AgentState initialized")
    
    def add_message(self, role: str, content: str):
        """
        添加对话消息
        
        Args:
            role: "user" 或 "assistant"
            content: 消息内容
        """
        self.conversation_history.append({
            "role": role,
            "content": content
        })
        logger.debug(f"Added {role} message: {content[:50]}...")
    
    def clear_history(self):
        """清空对话历史"""
        self.conversation_history = []
        logger.info("Conversation history cleared")
    
    def get_history(self, last_n: Optional[int] = None) -> List[Dict[str, str]]:
        """
        获取对话历史
        
        Args:
            last_n: 如果指定，只返回最近 N 条消息
        
        Returns:
            对话历史列表
        """
        if last_n is None:
            return self.conversation_history
        return self.conversation_history[-last_n:]
    
    def set_global_df(self, df: pd.DataFrame):
        """
        设置全局数据框
        
        Args:
            df: 包含序列信息的 DataFrame
        """
        self.global_df = df
        logger.debug(f"Global DF updated with {len(df)} sequences")
    
    def get_global_df(self) -> Optional[pd.DataFrame]:
        """获取全局数据框"""
        return self.global_df
    
    def mark_visualization_generated(self):
        """标记可视化已生成"""
        self.visualization_generated = True
        logger.debug("Visualization marked as generated")
    
    def reset_visualization(self):
        """重置可视化状态"""
        self.visualization_generated = False
        logger.debug("Visualization state reset")
    
    def is_visualization_generated(self) -> bool:
        """检查可视化是否已生成"""
        return self.visualization_generated
    
    def set_current_input(self, user_input: str):
        """
        设置当前用户输入
        
        Args:
            user_input: 用户输入文本
        """
        self.current_user_input = user_input
        logger.debug(f"Current input set: {user_input[:50]}...")
    
    def get_current_input(self) -> str:
        """获取当前用户输入"""
        return self.current_user_input
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取状态统计信息
        
        Returns:
            包含统计数据的字典
        """
        return {
            "conversation_turns": len(self.conversation_history),
            "total_sequences": len(self.global_df) if self.global_df is not None else 0,
            "visualization_generated": self.visualization_generated,
            "has_current_input": bool(self.current_user_input)
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """
        将状态转换为字典（用于序列化）
        
        Returns:
            状态字典
        """
        return {
            "conversation_history": self.conversation_history,
            "global_df": self.global_df.to_dict() if self.global_df is not None else None,
            "visualization_generated": self.visualization_generated,
            "current_user_input": self.current_user_input
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentState':
        """
        从字典加载状态
        
        Args:
            data: 状态字典
        
        Returns:
            AgentState 实例
        """
        state = cls()
        state.conversation_history = data.get('conversation_history', [])
        state.global_df = pd.DataFrame.from_dict(data['global_df']) if data.get('global_df') else None
        state.visualization_generated = data.get('visualization_generated', False)
        state.current_user_input = data.get('current_user_input', '')
        return state
