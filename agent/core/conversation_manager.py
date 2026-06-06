# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
AMP Agent Conversation Manager
===============================
Conversation manager, responsible for formatting messages, managing thinking state,
generating responses, etc.
"""

import logging
from typing import List, Dict, Any, Optional, Generator

logger = logging.getLogger(__name__)


class ConversationManager:
    """
    Conversation manager
    
    Responsibilities:
    1. Format user and assistant messages
    2. Manage thinking process records
    3. Generate structured responses
    4. Handle multi-turn conversation context
    """
    
    def __init__(self, language: str = "zh"):
        """
        Initialize conversation manager
        
        Args:
            language: Interface language ("en", "zh", "auto")
        """
        self.language = language
        self.thinking_history: List[str] = []
        
        logger.debug(f"ConversationManager initialized (language={language})")
    
    def format_user_message(self, user_input: str) -> Dict[str, str]:
        """
        Format user message
        
        Args:
            user_input: User input text
        
        Returns:
            Formatted message dictionary
        """
        return {
            "role": "user",
            "content": user_input
        }
    
    def format_assistant_message(self, content: str) -> Dict[str, str]:
        """
        Format assistant message
        
        Args:
            content: Assistant response content
        
        Returns:
            Formatted message dictionary
        """
        return {
            "role": "assistant",
            "content": content
        }
    
    def add_thought(self, thought: str):
        """
        Record a thinking process entry
        
        Args:
            thought: Thinking content
        """
        self.thinking_history.append(thought)
        logger.debug(f"Thought added: {thought[:50]}...")
    
    def clear_thoughts(self):
        """Clear thinking history"""
        self.thinking_history = []
        logger.debug("Thinking history cleared")
    
    def get_thoughts(self) -> List[str]:
        """Get all thinking records"""
        return self.thinking_history
    
    def format_react_response(
        self,
        thought: str,
        action: Optional[str] = None,
        action_input: Optional[Dict] = None,
        observation: Optional[Any] = None
    ) -> str:
        """
        Format a ReAct-style response
        
        Args:
            thought: Thinking content
            action: Tool name (if any)
            action_input: Tool arguments (if any)
            observation: Tool execution result (if any)
        
        Returns:
            Formatted response string
        """
        response_parts = [f"Thought: {thought}"]
        
        if action and action_input is not None:
            response_parts.append(f"Action: {action}")
            response_parts.append(f"Action Input: {action_input}")
        
        if observation is not None:
            response_parts.append(f"Observation: {observation}")
        
        return "\n".join(response_parts)
    
    def extract_final_answer(self, response: str) -> Optional[str]:
        """
        Extract final answer from response
        
        Args:
            response: Complete response string
        
        Returns:
            Final answer, or None if not found
        """
        # Look for "Final Answer:" marker
        if "Final Answer:" in response:
            return response.split("Final Answer:")[-1].strip()
        return None
    
    def has_final_answer(self, response: str) -> bool:
        """
        Check whether response contains a final answer
        
        Args:
            response: Response string
        
        Returns:
            True if final answer is present
        """
        return self.extract_final_answer(response) is not None
    
    def stream_response(self, chunks: List[str]) -> Generator[str, None, None]:
        """
        Stream response chunks
        
        Args:
            chunks: List of text chunks
        
        Yields:
            Text chunks one by one
        """
        for chunk in chunks:
            yield chunk
    
    def format_tool_result(self, tool_name: str, result: Any) -> str:
        """
        Format tool execution result
        
        Args:
            tool_name: Tool name
            result: Execution result
        
        Returns:
            Formatted result string
        """
        return f"**{tool_name} result**:\n{result}"
    
    def format_error_message(self, error: str, suggestion: Optional[str] = None) -> str:
        """
        Format error message
        
        Args:
            error: Error description
            suggestion: Suggested solution
        
        Returns:
            Formatted error message
        """
        msg = f"❌ **Error**: {error}"
        if suggestion:
            msg += f"\n\n💡 **Suggestion**: {suggestion}"
        return msg
    
    def format_success_message(self, message: str, details: Optional[str] = None) -> str:
        """
        Format success message
        
        Args:
            message: Success message
            details: Additional details
        
        Returns:
            Formatted success message
        """
        msg = f"✅ **Success**: {message}"
        if details:
            msg += f"\n\n{details}"
        return msg
    
    def build_context_summary(
        self,
        user_input: str,
        recent_history: List[Dict[str, str]],
        max_history: int = 5
    ) -> str:
        """
        Build context summary
        
        Args:
            user_input: Current user input
            recent_history: Recent conversation history
            max_history: Maximum number of history messages to include
        
        Returns:
            Context summary string
        """
        context_lines = [f"User: {user_input}"]
        
        # Include recent history (reverse order)
        for msg in reversed(recent_history[-max_history:]):
            role = "User" if msg['role'] == 'user' else "Assistant"
            content = msg['content'][:100] + "..." if len(msg['content']) > 100 else msg['content']
            context_lines.append(f"{role}: {content}")
        
        return "\n".join(context_lines)
