# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
Auto-Debug System for AMP Agent
================================
Combines pattern-based error fixing (fast) with LLM-based analysis (intelligent)

Author: AMP Agent Team
Date: 2026-01-08
"""

import re
import json
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class ErrorAnalyzer:
    """
    Pattern-based error analyzer (Fast path)
    Handles common errors without LLM calls
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
    def analyze(cls, error_msg: str, tool_name: str, params: dict) -> Optional[Dict[str, Any]]:
        """
        Analyze error and return fixed parameters if possible
        
        Returns:
            dict: Fixed parameters, or None if cannot auto-fix
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
    def _apply_fix(cls, fix_type: str, params: dict, match: re.Match, tool_name: str) -> Optional[dict]:
        """Apply specific fix based on error type"""
        fixed_params = params.copy()
        
        if fix_type == "convert_to_int":
            # Convert string parameters to int
            for key, value in fixed_params.items():
                if isinstance(value, str) and value.isdigit():
                    fixed_params[key] = int(value)
                    logger.info(f"  Converted {key}: '{value}' -> {int(value)}")
        
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
    LLM-based error analyzer (Intelligent path)
    Uses Qwen to analyze complex errors
    """
    
    def __init__(self, client, model_name: str = "qwen3.6-plus"):
        self.client = client
        self.model_name = model_name
    
    def analyze(self, error_msg: str, tool_name: str, params: dict, 
                error_history: list = None) -> Optional[Dict[str, Any]]:
        """
        Use LLM to analyze error and generate fix
        
        Args:
            error_msg: Error message string
            tool_name: Name of the failed tool
            params: Original parameters that caused the error
            error_history: List of previous error attempts
        
        Returns:
            dict: Fixed parameters, or None if LLM cannot fix
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
    
    def _extract_json(self, text: str) -> Optional[dict]:
        """Extract JSON from LLM response (handles markdown code blocks)"""
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
    Main Auto-Debug orchestrator
    Combines ErrorAnalyzer (fast) with LLMDebugger (intelligent)
    """
    
    def __init__(self, client, model_name: str = "qwen3.6-plus", max_retries: int = 3):
        self.error_analyzer = ErrorAnalyzer()
        self.llm_debugger = LLMDebugger(client, model_name)
        self.max_retries = max_retries
        self.error_history = []
    
    def debug_and_fix(self, error_msg: str, tool_name: str, params: dict, 
                      attempt: int = 1) -> Tuple[Optional[dict], str]:
        """
        Main debug entry point
        
        Returns:
            (fixed_params, fix_method): Fixed parameters and the method used
                fix_method: "pattern" | "llm" | "failed"
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
    
    def record_error(self, tool_name: str, params: dict, error_msg: str, attempt: int):
        """Record error for history context"""
        self.error_history.append({
            "tool": tool_name,
            "params": params,
            "error": error_msg,
            "attempt": attempt
        })
        
        # Keep only last 10 errors
        if len(self.error_history) > 10:
            self.error_history = self.error_history[-10:]
    
    def clear_history(self):
        """Clear error history (e.g., after successful execution)"""
        self.error_history = []
