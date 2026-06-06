# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
AMP Agent State Management
==========================
Agent state management class, responsible for managing conversation history,
global dataframe, visualization state, etc.
"""

import logging
from typing import List, Dict, Any, Optional
import pandas as pd

logger = logging.getLogger(__name__)


class AgentState:
    """
    Agent state manager
    
    Responsibilities:
    1. Manage conversation history
    2. Manage global sequence dataframe
    3. Manage visualization generation state
    4. Manage current user input
    
    Attributes:
        conversation_history: List[Dict] - Conversation history records
        global_df: pd.DataFrame - All generated sequence data
        visualization_generated: bool - Whether visualization has been generated
        current_user_input: str - Current user input
    """
    
    def __init__(self):
        """Initialize Agent state"""
        self.conversation_history: List[Dict[str, str]] = []
        self.global_df: Optional[pd.DataFrame] = None
        self.visualization_generated: bool = False
        self.current_user_input: str = ""
        
        logger.debug("AgentState initialized")
    
    def add_message(self, role: str, content: str):
        """
        Add a conversation message
        
        Args:
            role: "user" or "assistant"
            content: Message content
        """
        self.conversation_history.append({
            "role": role,
            "content": content
        })
        logger.debug(f"Added {role} message: {content[:50]}...")
    
    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []
        logger.info("Conversation history cleared")
    
    def get_history(self, last_n: Optional[int] = None) -> List[Dict[str, str]]:
        """
        Get conversation history
        
        Args:
            last_n: If specified, return only the last N messages
        
        Returns:
            List of conversation history
        """
        if last_n is None:
            return self.conversation_history
        return self.conversation_history[-last_n:]
    
    def set_global_df(self, df: pd.DataFrame):
        """
        Set global dataframe
        
        Args:
            df: DataFrame containing sequence information
        """
        self.global_df = df
        logger.debug(f"Global DF updated with {len(df)} sequences")
    
    def get_global_df(self) -> Optional[pd.DataFrame]:
        """Get global dataframe"""
        return self.global_df
    
    def mark_visualization_generated(self):
        """Mark visualization as generated"""
        self.visualization_generated = True
        logger.debug("Visualization marked as generated")
    
    def reset_visualization(self):
        """Reset visualization state"""
        self.visualization_generated = False
        logger.debug("Visualization state reset")
    
    def is_visualization_generated(self) -> bool:
        """Check whether visualization has been generated"""
        return self.visualization_generated
    
    def set_current_input(self, user_input: str):
        """
        Set current user input
        
        Args:
            user_input: User input text
        """
        self.current_user_input = user_input
        logger.debug(f"Current input set: {user_input[:50]}...")
    
    def get_current_input(self) -> str:
        """Get current user input"""
        return self.current_user_input
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get state statistics
        
        Returns:
            Dictionary containing statistical data
        """
        return {
            "conversation_turns": len(self.conversation_history),
            "total_sequences": len(self.global_df) if self.global_df is not None else 0,
            "visualization_generated": self.visualization_generated,
            "has_current_input": bool(self.current_user_input)
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert state to dictionary (for serialization)
        
        Returns:
            State dictionary
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
        Load state from dictionary
        
        Args:
            data: State dictionary
        
        Returns:
            AgentState instance
        """
        state = cls()
        state.conversation_history = data.get('conversation_history', [])
        state.global_df = pd.DataFrame.from_dict(data['global_df']) if data.get('global_df') else None
        state.visualization_generated = data.get('visualization_generated', False)
        state.current_user_input = data.get('current_user_input', '')
        return state
