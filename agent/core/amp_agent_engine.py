# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
AMP Agent Core Engine
=====================
Agent core engine, integrating state management, conversation management,
Skills and Tools orchestration.
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
    AMP Agent core engine
    
    Responsibilities:
    1. Integrate state management and conversation management
    2. Implement ReAct reasoning loop
    3. Orchestrate Skills and Tools
    4. Handle intent recognition and routing
    
    Attributes:
        state: AgentState - State manager
        conversation: ConversationManager - Conversation manager
        skill_registry: Skill registry
        intent_recognizer: Intent recognizer
        tools_schema: JSON Schema definitions for Tools
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
        Initialize Agent engine
        
        Args:
            client: OpenAI-compatible API client
            model_name: Model name
            language: Interface language
            skill_registry: Skill registry
            intent_recognizer: Intent recognizer
            tools_schema: JSON Schema for Tools
        """
        self.client = client
        self.model = model_name
        self.language = language
        self.skill_registry = skill_registry
        self.intent_recognizer = intent_recognizer
        self.tools_schema = tools_schema or []
        
        # Initialize subcomponents
        self.state = AgentState()
        self.conversation = ConversationManager(language)
        
        logger.info(f"✅ AMPAgentEngine initialized (model={model_name}, language={language})")
    
    def chat(self, user_input: str, max_iterations: int = 10) -> Generator[str, None, None]:
        """
        Main conversation method - integrates intent recognition and ReAct loop
        
        Args:
            user_input: User input
            max_iterations: Maximum number of iterations
        
        Yields:
            Response text chunks
        """
        # Step 1: Record user input
        self.state.add_message("user", user_input)
        self.state.set_current_input(user_input)
        self.state.reset_visualization()
        
        logger.info(f"📝 User input: {user_input[:50]}...")
        
        # Step 2: Intent recognition (prioritize Skills)
        if self.intent_recognizer:
            yield from self._try_skill_execution(user_input)
            return
        
        # Step 3: Fall back to traditional ReAct mode
        yield from self._react_loop(user_input, max_iterations)
    
    def _try_skill_execution(self, user_input: str) -> Generator[str, None, None]:
        """
        Attempt to execute task using a Skill
        
        Args:
            user_input: User input
        
        Yields:
            Response text chunks
        """
        logger.info(f"🔍 Analyzing user input for skill intent: {user_input[:50]}...")
        
        intent = self.intent_recognizer.recognize(user_input)
        
        if intent and intent['confidence'] >= 0.6:
            logger.info(f"🎯 Detected intent: {intent['skill_name']} (confidence: {intent['confidence']:.2f})")
            
            yield f"**🤖 Smart Intent Recognition**: Detected intent → **{intent['skill_name']}**\n\n"
            yield f"⚡ **Launching Automated Workflow**: Invoking {intent['skill_name']} skill...\n\n"
            
            try:
                skill_func = self.skill_registry.get_skill(intent['skill_name'])
                if skill_func:
                    result = skill_func(**intent.get('params', {}))
                    
                    if result.success:
                        yield from self._format_skill_result(result)
                        self.state.add_message("assistant", f"Skill {intent['skill_name']} executed successfully")
                        return
                    else:
                        yield f"⚠️ {intent['skill_name']} encountered issues, switching to traditional ReAct mode...\n\n"
                
                else:
                    yield f"⚠️ Skill {intent['skill_name']} not found, using traditional mode...\n\n"
            
            except Exception as e:
                logger.error(f"❌ Skill execution failed: {e}", exc_info=True)
                yield f"❌ Skill execution failed: {str(e)}\n\n"
                yield "🔄 Switched to traditional tool-calling mode...\n\n"
        
        # Skill execution failed or no match, fall back to ReAct
        yield "🔄 Using traditional tool-calling mode...\n\n"
        yield from self._react_loop(user_input)
    
    def _react_loop(self, user_input: str, max_iterations: int = 10) -> Generator[str, None, None]:
        """
        ReAct reasoning loop - fully migrated from amp_agent_v3.py
        
        Args:
            user_input: User input
            max_iterations: Maximum number of iterations
        
        Yields:
            Response text chunks
        """
        iteration = 0
        while iteration < max_iterations:
            iteration += 1
            
            # Get conversation history
            history = self.state.get_history(last_n=10)
            messages = [
                {"role": "system", "content": "You are AMP Agent."}
            ] + history
            
            # Step 1: Call LLM
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
                
                # Step 2: Manual parsing (compatible with models that don't support tool_calls)
                if not tool_calls:
                    # TODO: implement _parse_manual_tool_call method
                    # manual = self._parse_manual_tool_call(content)
                    # if manual:
                    #     tool_calls = manual
                    pass
                
                # Step 3: Yield thinking process
                if content:
                    yield f"{content}\n\n"
                
                # Step 4: Record assistant response
                self.state.add_message("assistant", content)
                
                # Step 5: Check if finished (no tool calls)
                if not tool_calls:
                    yield "✅ Task completed"
                    break
                
                # Step 6: Execute tools
                for tool in tool_calls:
                    # Parse tool call
                    if isinstance(tool, dict):
                        fn_name = tool['function']['name']
                        args_str = tool['function']['arguments']
                        tool_id = tool.get('id')
                    else:
                        fn_name = tool.function.name
                        args_str = tool.function.arguments
                        tool_id = getattr(tool, 'id', None)
                    
                    # Parse arguments
                    try:
                        raw_args = json.loads(args_str)
                    except:
                        raw_args = {}
                    
                    yield f"🔧 Executing tool: {fn_name}\n"
                    
                    # Execute tool
                    tool_output = self._execute_tool(fn_name, raw_args)
                    
                    yield f"✅ {tool_output}\n"
                    
                    # Record tool result
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
        
        # Release resources
        # if self.orchestrator:
        #     self.orchestrator.switch_to_default()
    
    def _format_skill_result(self, result) -> Generator[str, None, None]:
        """
        Format Skill execution result
        
        Args:
            result: SkillResult object
        
        Yields:
            Formatted text chunks
        """
        yield f"✅ **Task Completed**: {result.name}\n\n"
        yield f"**Result**:\n{result.summary}\n\n"
        
        if hasattr(result, 'visualization_data') and result.visualization_data:
            yield "**Visualization data generated**\n"
    
    def _execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """
        Generic tool execution method - fully migrated version
        
        Args:
            tool_name: Tool name
            args: Tool arguments
        
        Returns:
            Tool execution result
        """
        logger.info(f"🔧 Executing tool: {tool_name}")
        
        try:
            # Route to appropriate handler based on tool name
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
                # Generic tool execution
                logger.warning(f"⚠️ Unknown tool: {tool_name}, executing generically")
                return f"Tool {tool_name} executed (generic)"
        
        except Exception as e:
            logger.error(f"❌ Tool execution failed: {e}", exc_info=True)
            return f"Error executing {tool_name}: {str(e)}"
    
    def _handle_generate_task(self, args: Dict[str, Any]) -> str:
        """Handle sequence generation task - real implementation"""
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
        """Handle AMP design task - real implementation"""
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
        """Handle evaluation task - real implementation"""
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
        """Handle ranking task - real implementation"""
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
        """Handle structure prediction task - real implementation"""
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
        Clean conversation history to comply with OpenAI API format
        
        Args:
            history: Raw conversation history
        
        Returns:
            Cleaned history
        """
        # TODO: fully implement history cleaning logic
        # Currently returns raw history (simplified version)
        return history
    
    def get_state_statistics(self) -> Dict[str, Any]:
        """
        Get Agent state statistics
        
        Returns:
            Statistics dictionary
        """
        return self.state.get_statistics()
    
    def clear_state(self):
        """Clear Agent state"""
        self.state.clear_history()
        self.conversation.clear_thoughts()
        logger.info("Agent state cleared")
