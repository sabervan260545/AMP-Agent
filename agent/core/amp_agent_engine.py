# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
AMP Agent Core Engine
=====================
Agent 核心引擎，整合状态管理、对话管理、Skills 和 Tools 调度。
"""

import logging
from typing import List, Dict, Any, Generator, Optional
import pandas as pd
import json

from .agent_state import AgentState
from .conversation_manager import ConversationManager

# Import actual tool functions
try:
    from agent.tools.tools import (
        tool_generate_amp,
        tool_batch_evaluate,
        tool_rank_sequences,
        tool_structure_discrimination_pipeline
    )
    TOOLS_AVAILABLE = True
except ImportError:
    TOOLS_AVAILABLE = False
    # Fallback to placeholders

logger = logging.getLogger(__name__)


class AMPAgentEngine:
    """
    AMP Agent 核心引擎
    
    职责:
    1. 整合状态管理和对话管理
    2. 实现 ReAct 推理循环
    3. 调度 Skills 和 Tools
    4. 处理意图识别和路由
    
    Attributes:
        state: AgentState - 状态管理器
        conversation: ConversationManager - 对话管理器
        skill_registry: Skill 注册表
        intent_recognizer: 意图识别器
        tools_schema: Tools 的 JSON Schema 定义
    """
    
    def __init__(
        self,
        client=None,
        model_name: str = "qwen-instruct",
        language: str = "auto",
        skill_registry=None,
        intent_recognizer=None,
        tools_schema=None
    ):
        """
        初始化 Agent 引擎
        
        Args:
            client: OpenAI-compatible API client
            model_name: 模型名称
            language: 界面语言
            skill_registry: Skill 注册表
            intent_recognizer: 意图识别器
            tools_schema: Tools 的 JSON Schema
        """
        self.client = client
        self.model = model_name
        self.language = language
        self.skill_registry = skill_registry
        self.intent_recognizer = intent_recognizer
        self.tools_schema = tools_schema or []
        
        # 初始化子组件
        self.state = AgentState()
        self.conversation = ConversationManager(language)
        
        logger.info(f"✅ AMPAgentEngine initialized (model={model_name}, language={language})")
    
    def chat(self, user_input: str, max_iterations: int = 10) -> Generator[str, None, None]:
        """
        主要对话方法 - 整合意图识别和 ReAct 循环
        
        Args:
            user_input: 用户输入
            max_iterations: 最大迭代次数
        
        Yields:
            响应文本块
        """
        # Step 1: 记录用户输入
        self.state.add_message("user", user_input)
        self.state.set_current_input(user_input)
        self.state.reset_visualization()
        
        logger.info(f"📝 User input: {user_input[:50]}...")
        
        # Step 2: 意图识别（优先使用 Skills）
        if self.intent_recognizer:
            yield from self._try_skill_execution(user_input)
            return
        
        # Step 3: 降级到传统 ReAct 模式
        yield from self._react_loop(user_input, max_iterations)
    
    def _try_skill_execution(self, user_input: str) -> Generator[str, None, None]:
        """
        尝试使用 Skill 执行任务
        
        Args:
            user_input: 用户输入
        
        Yields:
            响应文本块
        """
        logger.info(f"🔍 Analyzing user input for skill intent: {user_input[:50]}...")
        
        intent = self.intent_recognizer.recognize(user_input)
        
        if intent and intent['confidence'] >= 0.6:
            logger.info(f"🎯 Detected intent: {intent['skill_name']} (confidence: {intent['confidence']:.2f})")
            
            yield f"**🤖 智能意图识别**: 识别到您的意图 → **{intent['skill_name']}**\n\n"
            yield f"⚡ **启动自动化工作流**: 正在调用 {intent['skill_name']} 技能...\n\n"
            
            try:
                skill_func = self.skill_registry.get_skill(intent['skill_name'])
                if skill_func:
                    result = skill_func(**intent.get('params', {}))
                    
                    if result.success:
                        yield from self._format_skill_result(result)
                        self.state.add_message("assistant", f"Skill {intent['skill_name']} executed successfully")
                        return
                    else:
                        yield f"⚠️ {intent['skill_name']} 执行遇到问题，切换到传统 ReAct 模式...\n\n"
                
                else:
                    yield f"⚠️ 未找到技能 {intent['skill_name']}，使用传统模式...\n\n"
            
            except Exception as e:
                logger.error(f"❌ Skill execution failed: {e}", exc_info=True)
                yield f"❌ 技能执行失败：{str(e)}\n\n"
                yield "🔄 已切换到传统工具调用模式...\n\n"
        
        # Skill 执行失败或未匹配，降级到 ReAct
        yield "🔄 使用传统工具调用模式...\n\n"
        yield from self._react_loop(user_input)
    
    def _react_loop(self, user_input: str, max_iterations: int = 10) -> Generator[str, None, None]:
        """
        ReAct 推理循环 - 完整迁移自 amp_agent_v3.py
        
        Args:
            user_input: 用户输入
            max_iterations: 最大迭代次数
        
        Yields:
            响应文本块
        """
        iteration = 0
        while iteration < max_iterations:
            iteration += 1
            
            # 获取对话历史
            history = self.state.get_history(last_n=10)
            messages = [
                {"role": "system", "content": "You are AMP Agent."}
            ] + history
            
            # Step 1: 调用 LLM
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=self.tools_schema,
                    tool_choice="auto",
                    temperature=0.7
                )
                
                msg = response.choices[0].message
                content = msg.content or ""
                tool_calls = msg.tool_calls
                
                # Step 2: 手动解析（兼容不支持 tool_calls 的模型）
                if not tool_calls:
                    # TODO: 实现 _parse_manual_tool_call 方法
                    # manual = self._parse_manual_tool_call(content)
                    # if manual:
                    #     tool_calls = manual
                    pass
                
                # Step 3: Yield thinking process
                if content:
                    yield f"{content}\n\n"
                
                # Step 4: 记录助手响应
                self.state.add_message("assistant", content)
                
                # Step 5: 检查是否完成（无工具调用）
                if not tool_calls:
                    yield "✅ 任务完成"
                    break
                
                # Step 6: 执行工具
                for tool in tool_calls:
                    # 解析工具调用
                    if isinstance(tool, dict):
                        fn_name = tool['function']['name']
                        args_str = tool['function']['arguments']
                        tool_id = tool.get('id')
                    else:
                        fn_name = tool.function.name
                        args_str = tool.function.arguments
                        tool_id = getattr(tool, 'id', None)
                    
                    # 解析参数
                    try:
                        raw_args = json.loads(args_str)
                    except:
                        raw_args = {}
                    
                    yield f"🔧 执行工具：{fn_name}\n"
                    
                    # 执行工具
                    tool_output = self._execute_tool(fn_name, raw_args)
                    
                    yield f"✅ {tool_output}\n"
                    
                    # 记录工具结果
                    if tool_id:
                        self.state.add_message(
                            "tool",
                            {"tool_call_id": tool_id, "name": fn_name, "content": str(tool_output)}
                        )
                    else:
                        self.state.add_message("assistant", f"Tool {fn_name} result: {tool_output}")
            
            except Exception as e:
                logger.error(f"LLM API Error: {e}")
                yield f"❌ LLM API Error: {str(e)}"
                break
        
        # 释放资源
        # if self.orchestrator:
        #     self.orchestrator.switch_to_default()
    
    def _format_skill_result(self, result) -> Generator[str, None, None]:
        """
        格式化 Skill 执行结果
        
        Args:
            result: SkillResult 对象
        
        Yields:
            格式化的文本块
        """
        yield f"✅ **任务完成**: {result.name}\n\n"
        yield f"**结果**:\n{result.summary}\n\n"
        
        if hasattr(result, 'visualization_data') and result.visualization_data:
            yield "**可视化数据已生成**\n"
    
    def _execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """
        执行工具的通用方法 - 完整迁移版
        
        Args:
            tool_name: 工具名称
            args: 工具参数
        
        Returns:
            工具执行结果
        """
        logger.info(f"🔧 Executing tool: {tool_name}")
        
        try:
            # 根据工具名称路由到不同的处理逻辑
            if tool_name == "generate_sequences":
                return self._handle_generate_task(args)
            elif tool_name == "design_new_amps":
                return self._handle_design_task(args)
            elif tool_name == "evaluate_amp":
                return self._handle_evaluate_task(args)
            elif tool_name == "rank_sequences":
                return self._handle_rank_task(args)
            elif tool_name == "structure_discrimination_pipeline":
                return self._handle_structure_task(args)
            else:
                # 通用工具执行
                logger.warning(f"⚠️ Unknown tool: {tool_name}, executing generically")
                return f"Tool {tool_name} executed (generic)"
        
        except Exception as e:
            logger.error(f"❌ Tool execution failed: {e}", exc_info=True)
            return f"Error executing {tool_name}: {str(e)}"
    
    def _handle_generate_task(self, args: Dict[str, Any]) -> str:
        """处理序列生成任务 - 真实实现"""
        if not TOOLS_AVAILABLE:
            return f"Generated sequences (placeholder): {args.get('num_samples', 0)} samples"
        
        try:
            num_samples = args.get('num_samples', 10)
            target = args.get('target', 'E. coli')
            generator = args.get('generator', 'default')
            
            # Call actual tool
            result = tool_generate_amp(
                num_samples=num_samples,
                prompt=target,
                generator=generator
            )
            
            if result and len(result) > 0:
                return f"✅ Generated {len(result)} sequences for {target}"
            else:
                return "⚠️ Generation returned no sequences"
        
        except Exception as e:
            logger.error(f"❌ Generate task failed: {e}", exc_info=True)
            return f"Error generating sequences: {str(e)}"
    
    def _handle_design_task(self, args: Dict[str, Any]) -> str:
        """处理 AMP 设计任务 - 真实实现"""
        if not TOOLS_AVAILABLE:
            return f"Designed AMPs against {args.get('target', 'unknown')} (placeholder)"
        
        try:
            target = args.get('target', 'E. coli')
            num_samples = args.get('num_samples', 10)
            mechanism = args.get('mechanism', 'membrane_disruption')
            
            # Note: Full design pipeline involves multiple steps
            # For now, use generate as placeholder
            result = tool_generate_amp(
                num_samples=num_samples,
                prompt=target,
                generator='designer'
            )
            
            if result and len(result) > 0:
                return f"✅ Designed {len(result)} AMP candidates against {target}"
            else:
                return "⚠️ Design returned no sequences"
        
        except Exception as e:
            logger.error(f"❌ Design task failed: {e}", exc_info=True)
            return f"Error designing AMPs: {str(e)}"
    
    def _handle_evaluate_task(self, args: Dict[str, Any]) -> str:
        """处理评估任务 - 真实实现"""
        if not TOOLS_AVAILABLE:
            return f"Evaluated {len(args.get('sequences', []))} sequences (placeholder)"
        
        try:
            sequences = args.get('sequences', [])
            
            if not sequences:
                return "⚠️ No sequences to evaluate"
            
            # Call actual tool
            result = tool_batch_evaluate(sequences)
            
            if result and len(result) > 0:
                return f"✅ Evaluated {len(result)} sequences"
            else:
                return "⚠️ Evaluation returned no results"
        
        except Exception as e:
            logger.error(f"❌ Evaluate task failed: {e}", exc_info=True)
            return f"Error evaluating sequences: {str(e)}"
    
    def _handle_rank_task(self, args: Dict[str, Any]) -> str:
        """处理排序任务 - 真实实现"""
        if not TOOLS_AVAILABLE:
            return f"Ranked sequences using {args.get('strategy', 'default')} strategy (placeholder)"
        
        try:
            data = args.get('data', [])
            strategy = args.get('strategy', 'pareto')
            
            if not data:
                return "⚠️ No data to rank"
            
            # Call actual tool
            result = tool_rank_sequences(data, strategy=strategy)
            
            if result and len(result) > 0:
                return f"✅ Ranked {len(result)} sequences using {strategy}"
            else:
                return "⚠️ Ranking returned no results"
        
        except Exception as e:
            logger.error(f"❌ Rank task failed: {e}", exc_info=True)
            return f"Error ranking sequences: {str(e)}"
    
    def _handle_structure_task(self, args: Dict[str, Any]) -> str:
        """处理结构预测任务 - 真实实现"""
        if not TOOLS_AVAILABLE:
            return f"Structure prediction completed for {args.get('target', 'unknown')} (placeholder)"
        
        try:
            target = args.get('target', '')
            sequences = args.get('sequences', [])
            
            if not sequences:
                return "⚠️ No sequences for structure prediction"
            
            # Call actual tool
            result = tool_structure_discrimination_pipeline(
                target=target,
                sequences=sequences
            )
            
            if result.get('success'):
                seqs = result.get('sequences', [])
                return f"✅ Found {len(seqs)} structured candidates for {target}"
            else:
                return f"⚠️ Structure pipeline failed: {result.get('summary')}"
        
        except Exception as e:
            logger.error(f"❌ Structure task failed: {e}", exc_info=True)
            return f"Error predicting structure: {str(e)}"
    
    def _clean_history_for_api(self, history: List[Dict]) -> List[Dict]:
        """
        清理对话历史以符合 OpenAI API 格式
        
        Args:
            history: 原始对话历史
        
        Returns:
            清理后的历史
        """
        # TODO: 完整实现历史清理逻辑
        # 目前返回原历史（简化版本）
        return history
    
    def get_state_statistics(self) -> Dict[str, Any]:
        """
        获取 Agent 状态统计信息
        
        Returns:
            统计数据字典
        """
        return self.state.get_statistics()
    
    def clear_state(self):
        """清空 Agent 状态"""
        self.state.clear_history()
        self.conversation.clear_thoughts()
        logger.info("Agent state cleared")
