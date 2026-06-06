# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
Auto-Debug System for AMP Agent
=================================

Two-tier error recovery system combining pattern-based heuristics (fast path)
with LLM-powered analysis (intelligent path) for automatic error correction.

Architecture:
- **ErrorAnalyzer**: Pattern-based matching for common errors (no LLM needed)
- **LLMDebugger**: Qwen-powered analysis for complex errors
- **AutoDebugger**: Orchestrator managing retry logic and fallback strategy

Key Features:
- 8 pre-defined error patterns with automatic fixes
- Fuzzy matching for enum parameter values
- LLM-based fix generation with error history context
- Automatic retry with exponential backoff
- JSON extraction from LLM responses

Author: AMP Platform Team
Version: Production 1.0
License: MIT
"""

import re
import json
import logging
from typing import Dict, Any, Optional, Tuple, List

logger = logging.getLogger(__name__)


class ErrorAnalyzer:
    """
    Pattern-based error analyzer for fast error recovery (Fast Path).
    
    Provides zero-latency error fixing by matching common error patterns
    against a predefined rule set. No LLM calls required, making it ideal
    for high-frequency errors like type mismatches.
    
    Capabilities:
    - Type conversion (str ↔ int, str ↔ float)
    - Missing parameter injection with defaults
    - Enum parameter fuzzy matching
    - Value range clamping
    - Sign correction (negative → positive)
    
    Attributes:
        ERROR_PATTERNS (dict): Pattern definitions with regex and fix types
        DEFAULT_VALUES (dict): Default values for common parameters
        VALID_OPTIONS (dict): Valid enum values for each parameter
    
    Examples:
        >>> analyzer = ErrorAnalyzer()
        >>> params = {'num_samples': '10'}  # String instead of int
        >>> fixed = analyzer.analyze("expected int, got str", "generate_amp", params)
        >>> fixed['num_samples']
        10
    
    Notes:
        - Stateless class (all methods are class methods)
        - Returns None if no pattern matches (triggers LLM path)
        - Logs all fix operations for debugging
    """
    
    # Common error patterns and their automatic fixes
    ERROR_PATTERNS = {
        "type_mismatch_int": {
            "pattern": r"expected.*?int.*?got.*?str|num_samples.*?must be int",
            "fix_type": "convert_to_int",
            "description": "Convert string to integer"
        },
        "type_mismatch_str": {
            "pattern": r"expected.*?str.*?got.*?int|target.*?must be str",
            "fix_type": "convert_to_str",
            "description": "Convert to string"
        },
        "missing_required_param": {
            "pattern": r"missing.*?required.*?'(\w+)'|(\w+).*?is required",
            "fix_type": "add_default_param",
            "description": "Add missing parameter with default value"
        },
        "invalid_target_value": {
            "pattern": r"invalid target|target must be one of",
            "fix_type": "fix_target_value",
            "description": "Fix target parameter to valid option"
        },
        "invalid_strategy_value": {
            "pattern": r"invalid strategy|strategy must be one of",
            "fix_type": "fix_strategy_value",
            "description": "Fix strategy parameter to valid option"
        },
        "negative_value": {
            "pattern": r"must be positive|cannot be negative",
            "fix_type": "make_positive",
            "description": "Convert negative value to positive"
        },
        "out_of_range": {
            "pattern": r"out of range|too large|too small",
            "fix_type": "clamp_value",
            "description": "Clamp value to valid range"
        },
        "math_operand_mismatch": {
            "pattern": r"unsupported operand type\(s\) for .*: 'str' and 'int'",
            "fix_type": "convert_digit_strings",
            "description": "Convert digit strings to integers for math operations"
        }
    }
    
    # Default values for common parameters
    DEFAULT_VALUES = {
        "num_samples": 5,
        "target": "Gram-negative",
        "strategy": "default",
        "ranking": "pareto"
    }
    
    # Valid options for enum parameters
    VALID_OPTIONS = {
        "target": ["Gram-negative", "Gram-positive", "Mammalian", "Antifungal", "Antiviral"],
        "strategy": ["default", "fast", "diverse", "novel", "refine", "optimize"],
        "ranking": ["pareto", "mic_only", "balanced"]
    }
    
    @classmethod
    def analyze(cls, error_msg: str, tool_name: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Analyze error message and attempt pattern-based fix.
        
        Iterates through predefined error patterns, attempting to match
        the error message and apply corresponding fixes.
        
        Args:
            error_msg: Complete error message string
            tool_name: Name of the tool that failed
            params: Original parameters that caused the error
        
        Returns:
            Fixed parameter dict if pattern matched and fix succeeded,
            None if no pattern matched (triggers LLM fallback)
        
        Examples:
            >>> params = {'num_samples': '5', 'target': 'E.coli'}
            >>> fixed = ErrorAnalyzer.analyze("num_samples must be int", "generate_amp", params)
            >>> fixed['num_samples']
            5  # Converted to int
        
        Notes:
            - Logs all pattern matching and fix attempts
            - Returns None to trigger LLM analysis if no pattern matches
            - Safe: Returns None on any exception during fix
        """
        logger.info(f"🔍 ErrorAnalyzer analyzing: {error_msg[:100]}...")
        
        for error_type, config in cls.ERROR_PATTERNS.items():
            match = re.search(config["pattern"], error_msg, re.IGNORECASE)
            if match:
                logger.info(f"✅ Detected error type: {error_type} - {config['description']}")
                
                # Apply the appropriate fix
                fix_type = config["fix_type"]
                try:
                    fixed_params = cls._apply_fix(fix_type, params, match, tool_name)
                    if fixed_params:
                        logger.info(f"🔧 Auto-fixed params: {fixed_params}")
                        return fixed_params
                except Exception as e:
                    logger.warning(f"⚠️ Fix attempt failed: {e}")
        
        logger.info("❌ No pattern matched, need LLM analysis")
        return None
    
    @classmethod
    def _apply_fix(cls, fix_type: str, params: Dict[str, Any], match: re.Match, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Apply specific fix strategy based on error type.
        
        Implements concrete fix logic for each error pattern type identified
        by the analyze() method.
        
        Args:
            fix_type: Fix strategy identifier (e.g., 'convert_to_int')
            params: Original parameters to fix
            match: Regex match object containing captured groups
            tool_name: Name of the tool (for context-aware fixes)
        
        Returns:
            Fixed parameter dict, or None if fix not applicable
        
        Supported Fix Types:
            - convert_to_int: String → Integer conversion
            - convert_digit_strings: Heuristic digit string detection and conversion
            - convert_to_str: Non-string → String conversion
            - add_default_param: Inject missing parameters with defaults
            - fix_target_value: Fuzzy match and correct enum values
            - fix_strategy_value: Fuzzy match strategy enum
            - make_positive: Negative → Positive conversion
            - clamp_value: Range clamping (e.g., 1-50 for num_samples)
        
        Examples:
            >>> match = re.search(r"num_samples", "num_samples must be int")
            >>> fixed = ErrorAnalyzer._apply_fix("convert_to_int", {"num_samples": "10"}, match, "generate_amp")
            >>> fixed['num_samples']
            10
        
        Notes:
            - Returns None if no changes made (fix not applicable)
            - Logs each individual fix operation
            - Safe: Returns copy of params, never modifies original
        """
        logger.info(f"🔧 Auto-Debug attempting fix: {fix_type} for tool {tool_name}")

        fixed_params = params.copy()
        
        if fix_type == "convert_to_int":
            # Convert string parameters to int
            for key, value in fixed_params.items():
                if isinstance(value, str) and value.isdigit():
                    fixed_params[key] = int(value)
                    logger.info(f"  Converted {key}: '{value}' -> {int(value)}")
        
        elif fix_type == "convert_digit_strings":
            # Heuristic fix for math operation errors
            # Strategy: Convert all digit-like string parameters to int
            fixed = False
            for key, value in fixed_params.items():
                # Check if string and contains only digits
                if isinstance(value, str) and value.isdigit():
                    fixed_params[key] = int(value)
                    logger.info(f" 🔧 Heuristic fix for math error: {key}='{value}' -> {int(value)}")
                    fixed = True
            
            # If no parameters could be converted, fix strategy not applicable, return None
            if not fixed:
                return None

        elif fix_type == "convert_to_str":
            # Convert non-string parameters to str
            for key, value in fixed_params.items():
                if not isinstance(value, str) and key in ["target", "strategy", "ranking"]:
                    fixed_params[key] = str(value)
                    logger.info(f"  Converted {key}: {value} -> '{value}'")
        
        elif fix_type == "add_default_param":
            # Add missing parameter
            param_name = match.group(1) or match.group(2)
            if param_name in cls.DEFAULT_VALUES:
                fixed_params[param_name] = cls.DEFAULT_VALUES[param_name]
                logger.info(f"  Added {param_name}={cls.DEFAULT_VALUES[param_name]}")
        
        elif fix_type == "fix_target_value":
            # Fix invalid target value
            if "target" in fixed_params:
                current = fixed_params["target"]
                # Try fuzzy matching
                for valid_option in cls.VALID_OPTIONS["target"]:
                    if current.lower() in valid_option.lower() or valid_option.lower() in current.lower():
                        fixed_params["target"] = valid_option
                        logger.info(f"  Fixed target: '{current}' -> '{valid_option}'")
                        break
                else:
                    # Use default
                    fixed_params["target"] = cls.DEFAULT_VALUES["target"]
                    logger.info(f"  Reset target to default: '{cls.DEFAULT_VALUES['target']}'")
        
        elif fix_type == "fix_strategy_value":
            # Fix invalid strategy value
            if "strategy" in fixed_params:
                current = fixed_params["strategy"]
                for valid_option in cls.VALID_OPTIONS["strategy"]:
                    if current.lower() in valid_option.lower():
                        fixed_params["strategy"] = valid_option
                        logger.info(f"  Fixed strategy: '{current}' -> '{valid_option}'")
                        break
                else:
                    fixed_params["strategy"] = cls.DEFAULT_VALUES["strategy"]
                    logger.info(f"  Reset strategy to default: '{cls.DEFAULT_VALUES['strategy']}'")
        
        elif fix_type == "make_positive":
            # Convert negative values to positive
            for key, value in fixed_params.items():
                if isinstance(value, (int, float)) and value < 0:
                    fixed_params[key] = abs(value)
                    logger.info(f"  Made {key} positive: {value} -> {abs(value)}")
        
        elif fix_type == "clamp_value":
            # Clamp out-of-range values
            if "num_samples" in fixed_params:
                value = fixed_params["num_samples"]
                if isinstance(value, int):
                    clamped = max(1, min(value, 50))  # Range: 1-50
                    if clamped != value:
                        fixed_params["num_samples"] = clamped
                        logger.info(f"  Clamped num_samples: {value} -> {clamped}")
        
        return fixed_params if fixed_params != params else None


class LLMDebugger:
    """
    LLM-powered error analyzer for complex errors (Intelligent Path).
    
    Uses Qwen language model to analyze errors that cannot be fixed by
    pattern-based heuristics. Provides intelligent parameter correction
    based on error context and history.
    
    Capabilities:
    - Natural language error understanding
    - Context-aware parameter correction
    - Error history integration for avoiding repeated failures
    - JSON extraction from diverse LLM response formats
    
    Attributes:
        client: OpenAI-compatible API client
        model_name: Model identifier (default: "qwen3.6-plus")
    
    Examples:
        >>> from openai import OpenAI
        >>> client = OpenAI(api_key="...")
        >>> debugger = LLMDebugger(client)
        >>> params = {'target': 'invalid_target'}
        >>> fixed = debugger.analyze("Invalid target value", "generate_amp", params)
        >>> fixed['target']
        'Gram-negative'  # LLM corrected it
    
    Notes:
        - Fallback for complex errors that pattern matching cannot handle
        - Temperature set to 0.1 for deterministic fixes
        - Supports error history to avoid repeated mistakes
    """
    
    def __init__(self, client, model_name: str = "qwen3.6-plus"):
        self.client = client
        self.model_name = model_name
    
    def analyze(self, error_msg: str, tool_name: str, params: Dict[str, Any], 
                error_history: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
        """
        Use LLM to analyze error and generate corrected parameters.
        
        Sends error context to Qwen model with structured prompt requesting
        JSON-only response. Includes error history to avoid repeated mistakes.
        
        Args:
            error_msg: Complete error message string
            tool_name: Name of the tool that failed
            params: Original parameters that caused the error
            error_history: List of previous error attempts (last 3 used)
        
        Returns:
            Fixed parameter dict if LLM successfully generated valid JSON,
            None if LLM failed or returned invalid JSON
        
        Examples:
            >>> debugger = LLMDebugger(client)
            >>> params = {'num_samples': 'five'}  # Invalid type
            >>> history = [{'params': {'num_samples': 5}, 'error': 'Another error'}]
            >>> fixed = debugger.analyze("num_samples must be int", "generate_amp", params, history)
            >>> fixed['num_samples']
            5
        
        Notes:
            - Uses low temperature (0.1) for deterministic fixes
            - Only last 3 error attempts are included in context
            - Handles markdown code blocks and raw JSON responses
            - Logs LLM response for debugging
        """
        logger.info(f"🤖 LLMDebugger analyzing with Qwen...")
        
        # Build context from error history
        history_context = ""
        if error_history:
            history_context = "\n\n**Previous failed attempts:**\n"
            for i, err in enumerate(error_history[-3:], 1):  # Last 3 attempts
                history_context += f"{i}. Params: {err['params']} → Error: {err['error'][:100]}\n"
        
        debug_prompt = f"""🛠️ **AUTO-DEBUG REQUEST**

You are an expert Python debugger. A tool call failed and needs to be fixed.

**Failed Tool**: `{tool_name}`

**Original Parameters**:
```json
{json.dumps(params, indent=2)}
```

**Error Message**:
```
{error_msg}
```
{history_context}

**Your Task**:
1. Analyze the error and identify the root cause
2. Provide ONLY the corrected parameters as a valid JSON object
3. Do NOT include any explanation, code, or markdown formatting
4. Return ONLY raw JSON

**Example Output** (for reference, return JSON only):
{{
  "num_samples": 5,
  "target": "Gram-negative",
  "strategy": "default"
}}

**Corrected Parameters**:"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a JSON-only debugging assistant. Return ONLY valid JSON, no explanations."},
                    {"role": "user", "content": debug_prompt}
                ],
                temperature=0.1  # Low temperature for deterministic fixes
            )
            
            response_text = response.choices[0].message.content.strip()
            logger.info(f"🤖 LLM response: {response_text[:200]}...")
            
            # Try to extract JSON from response
            fixed_params = self._extract_json(response_text)
            
            if fixed_params:
                logger.info(f"✅ LLM fixed params: {fixed_params}")
                return fixed_params
            else:
                logger.warning("❌ LLM response is not valid JSON")
                return None
                
        except Exception as e:
            logger.error(f"❌ LLM analysis failed: {e}")
            return None
    
    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Extract JSON from LLM response with robust parsing.
        
        Attempts multiple extraction strategies to handle various LLM
        response formats (raw JSON, markdown code blocks, embedded JSON).
        
        Args:
            text: Raw LLM response text
        
        Returns:
            Parsed JSON dict, or None if no valid JSON found
        
        Extraction Strategies:
            1. Direct JSON parsing (raw JSON response)
            2. Markdown code block extraction (```json ... ```)
            3. Regex-based JSON object search (find first {...} block)
        
        Examples:
            >>> debugger = LLMDebugger(client)
            >>> # Raw JSON
            >>> debugger._extract_json('{"num_samples": 5}')
            {'num_samples': 5}
            >>> 
            >>> # Markdown code block
            >>> debugger._extract_json('```json\n{"num_samples": 5}\n```')
            {'num_samples': 5}
        
        Notes:
            - Falls back to regex if markdown extraction fails
            - Returns None on any parsing error (safe fallback)
            - Handles nested JSON objects
        """
        # Try direct parsing first
        try:
            return json.loads(text)
        except:
            pass
        
        # Try extracting from markdown code block
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except:
                pass
        
        # Try finding any JSON object
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except:
                pass
        
        return None


class AutoDebugger:
    """
    Main auto-debug orchestrator integrating fast and intelligent paths.
    
    Manages the complete error recovery workflow with fallback strategy:
    1. **Fast Path**: Pattern-based fix (ErrorAnalyzer)
    2. **Intelligent Path**: LLM-based fix (LLMDebugger)
    3. **Failure**: Return None to trigger manual intervention
    
    Features:
    - Automatic retry with configurable max attempts
    - Error history tracking for context-aware LLM analysis
    - API call optimization (LLM only used for first 2 attempts)
    - Automatic history cleanup after successful execution
    
    Attributes:
        error_analyzer: ErrorAnalyzer instance for pattern-based fixes
        llm_debugger: LLMDebugger instance for intelligent fixes
        max_retries: Maximum retry attempts (default: 3)
        error_history: List of recent error attempts (max 10)
    
    Examples:
        >>> from openai import OpenAI
        >>> client = OpenAI(api_key="...")
        >>> debugger = AutoDebugger(client, max_retries=3)
        >>> params = {'num_samples': '10'}  # String instead of int
        >>> fixed, method = debugger.debug_and_fix("expected int", "generate_amp", params)
        >>> fixed['num_samples']
        10
        >>> method
        'pattern'  # Fixed by fast path
    
    Notes:
        - Always try pattern-based fix first (zero latency)
        - LLM only called if pattern matching fails
        - Error history limited to last 10 entries
    """
    
    def __init__(self, client, model_name: str = "qwen3.6-plus", max_retries: int = 3):
        self.error_analyzer = ErrorAnalyzer()
        self.llm_debugger = LLMDebugger(client, model_name)
        self.max_retries = max_retries
        self.error_history = []
    
    def debug_and_fix(self, error_msg: str, tool_name: str, params: Dict[str, Any], 
                      attempt: int = 1) -> Tuple[Optional[Dict[str, Any]], str]:
        """
        Main debug entry point with automatic fallback strategy.
        
        Attempts to fix tool call errors using a two-tier approach:
        1. Fast path: Pattern-based fix (ErrorAnalyzer)
        2. Intelligent path: LLM-based fix (LLMDebugger, first 2 attempts only)
        
        Args:
            error_msg: Complete error message string
            tool_name: Name of the tool that failed
            params: Original parameters that caused the error
            attempt: Current attempt number (1-based)
        
        Returns:
            Tuple of (fixed_params, fix_method):
                - fixed_params: Corrected parameter dict, or None if all methods failed
                - fix_method: One of:
                    - "pattern": Fixed by ErrorAnalyzer
                    - "llm": Fixed by LLMDebugger
                    - "failed": All methods exhausted
        
        Examples:
            >>> debugger = AutoDebugger(client)
            >>> params = {'num_samples': '10'}
            >>> fixed, method = debugger.debug_and_fix("expected int", "generate_amp", params)
            >>> fixed['num_samples']
            10
            >>> method
            'pattern'
            
            >>> # Complex error requiring LLM
            >>> params = {'target': 'some_weird_value'}
            >>> fixed, method = debugger.debug_and_fix("Invalid target", "generate_amp", params)
            >>> method
            'llm'
        
        Notes:
            - LLM only called for first 2 attempts to save API costs
            - Logs all fix attempts for debugging
            - Returns (None, 'failed') if both methods fail
        """
        logger.info(f"🛠️ Auto-Debug attempt {attempt}/{self.max_retries}")
        
        # Step 1: Try pattern-based fix (fast)
        fixed_params = self.error_analyzer.analyze(error_msg, tool_name, params)
        if fixed_params:
            return fixed_params, "pattern"
        
        # Step 2: Try LLM-based fix (intelligent)
        if attempt <= 2:  # Only use LLM for first 2 attempts to save API calls
            fixed_params = self.llm_debugger.analyze(
                error_msg, tool_name, params, self.error_history
            )
            if fixed_params:
                return fixed_params, "llm"
        
        # Step 3: Failed to fix
        logger.warning(f"❌ Auto-Debug failed after attempt {attempt}")
        return None, "failed"
    
    def record_error(self, tool_name: str, params: Dict[str, Any], error_msg: str, attempt: int) -> None:
        """
        Record error attempt for history context in LLM analysis.
        
        Maintains a rolling history of the last 10 error attempts, which
        is used by LLMDebugger to avoid repeating the same mistakes.
        
        Args:
            tool_name: Name of the tool that failed
            params: Parameters that caused the error
            error_msg: Complete error message string
            attempt: Attempt number (1-based)
        
        Examples:
            >>> debugger = AutoDebugger(client)
            >>> debugger.record_error("generate_amp", {"num_samples": "10"}, "expected int", 1)
            >>> len(debugger.error_history)
            1
        
        Notes:
            - History automatically limited to last 10 entries
            - Called automatically by amp_agent_v3 after each failed attempt
            - Used by LLMDebugger.analyze() for context
        """
        self.error_history.append({
            "tool": tool_name,
            "params": params,
            "error": error_msg,
            "attempt": attempt
        })
        
        # Keep only last 10 errors
        if len(self.error_history) > 10:
            self.error_history = self.error_history[-10:]
    
    def clear_history(self) -> None:
        """
        Clear error history after successful execution.
        
        Should be called after a tool call succeeds to prevent old errors
        from affecting future LLM analysis.
        
        Examples:
            >>> debugger = AutoDebugger(client)
            >>> debugger.record_error("generate_amp", {}, "some error", 1)
            >>> len(debugger.error_history)
            1
            >>> debugger.clear_history()
            >>> len(debugger.error_history)
            0
        
        Notes:
            - Called automatically by amp_agent_v3 after successful tool execution
            - Prevents error history pollution across different tasks
        """
        self.error_history = []
