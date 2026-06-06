# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
AMP Agent Conversation Manager
==============================
对话管理器，负责格式化消息、管理思考状态、生成响应等。
"""

import logging
from typing import List, Dict, Any, Optional, Generator

logger = logging.getLogger(__name__)


class ConversationManager:
    """
    对话管理器
    
    职责:
    1. 格式化用户和助手消息
    2. 管理思考过程记录
    3. 生成结构化响应
    4. 处理多轮对话上下文
    """
    
    def __init__(self, language: str = "zh"):
        """
        初始化对话管理器
        
        Args:
            language: 界面语言 ("en", "zh", "auto")
        """
        self.language = language
        self.thinking_history: List[str] = []
        
        logger.debug(f"ConversationManager initialized (language={language})")
    
    def format_user_message(self, user_input: str) -> Dict[str, str]:
        """
        格式化用户消息
        
        Args:
            user_input: 用户输入文本
        
        Returns:
            格式化的消息字典
        """
        return {
            "role": "user",
            "content": user_input
        }
    
    def format_assistant_message(self, content: str) -> Dict[str, str]:
        """
        格式化助手消息
        
        Args:
            content: 助手回复内容
        
        Returns:
            格式化的消息字典
        """
        return {
            "role": "assistant",
            "content": content
        }
    
    def add_thought(self, thought: str):
        """
        添加思考过程记录
        
        Args:
            thought: 思考内容
        """
        self.thinking_history.append(thought)
        logger.debug(f"Thought added: {thought[:50]}...")
    
    def clear_thoughts(self):
        """清空思考历史"""
        self.thinking_history = []
        logger.debug("Thinking history cleared")
    
    def get_thoughts(self) -> List[str]:
        """获取所有思考记录"""
        return self.thinking_history
    
    def format_react_response(
        self,
        thought: str,
        action: Optional[str] = None,
        action_input: Optional[Dict] = None,
        observation: Optional[Any] = None
    ) -> str:
        """
        格式化 ReAct 模式的响应
        
        Args:
            thought: 思考内容
            action: 工具名称（如果有）
            action_input: 工具参数（如果有）
            observation: 工具执行结果（如果有）
        
        Returns:
            格式化的响应字符串
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
        从响应中提取最终答案
        
        Args:
            response: 完整的响应字符串
        
        Returns:
            最终答案，如果没有则返回 None
        """
        # 查找 "Final Answer:" 标记
        if "Final Answer:" in response:
            return response.split("Final Answer:")[-1].strip()
        return None
    
    def has_final_answer(self, response: str) -> bool:
        """
        检查响应是否包含最终答案
        
        Args:
            response: 响应字符串
        
        Returns:
            True 如果包含最终答案
        """
        return self.extract_final_answer(response) is not None
    
    def stream_response(self, chunks: List[str]) -> Generator[str, None, None]:
        """
        流式生成响应
        
        Args:
            chunks: 文本块列表
        
        Yields:
            逐个产生文本块
        """
        for chunk in chunks:
            yield chunk
    
    def format_tool_result(self, tool_name: str, result: Any) -> str:
        """
        格式化工具执行结果
        
        Args:
            tool_name: 工具名称
            result: 执行结果
        
        Returns:
            格式化的结果字符串
        """
        return f"**{tool_name} 执行结果**:\n{result}"
    
    def format_error_message(self, error: str, suggestion: Optional[str] = None) -> str:
        """
        格式化错误消息
        
        Args:
            error: 错误描述
            suggestion: 建议的解决方案
        
        Returns:
            格式化的错误消息
        """
        msg = f"❌ **错误**: {error}"
        if suggestion:
            msg += f"\n\n💡 **建议**: {suggestion}"
        return msg
    
    def format_success_message(self, message: str, details: Optional[str] = None) -> str:
        """
        格式化成功消息
        
        Args:
            message: 成功消息
            details: 详细信息
        
        Returns:
            格式化的成功消息
        """
        msg = f"✅ **成功**: {message}"
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
        构建上下文摘要
        
        Args:
            user_input: 当前用户输入
            recent_history: 最近的对话历史
            max_history: 最多包含的历史消息数
        
        Returns:
            上下文摘要字符串
        """
        context_lines = [f"用户：{user_input}"]
        
        # 添加最近的历史（倒序）
        for msg in reversed(recent_history[-max_history:]):
            role = "用户" if msg['role'] == 'user' else "助手"
            content = msg['content'][:100] + "..." if len(msg['content']) > 100 else msg['content']
            context_lines.append(f"{role}: {content}")
        
        return "\n".join(context_lines)
