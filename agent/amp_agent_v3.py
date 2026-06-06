"""
AMP Agent v5.2 - Memory Injection Fixed Version
====================================
Fixes:
1. ✅ Fixed "context amnesia": Write generated sequence entities to conversation history to prevent Agent from repeating generation tasks
2. ✅ Maintain v5.1 structure prediction patience value (3 retries)
3. ✅ Maintain ContextEngine integration
"""

import json
import logging
import os
import pandas as pd
import time
import re
from typing import List, Dict, Any, Generator
import sys
sys.path.append('/data/amp-generator-platform/backend')
from database import DatabaseManager

from language_texts import TEXTS

# Import tools
from tools import (
    tool_generate_amp,
    tool_batch_evaluate,
    tool_rank_sequences,
    tool_predict_structure,
    tool_search_knowledge,
    tool_predict_mic_only,
    tool_predict_hemolysis_only,
    tool_predict_cpp_only,
    tool_structure_discrimination_pipeline,  # New: structure discrimination pipeline
    TOOLS_SCHEMA
)

# Import Auto-Debugger
try:
    from auto_debugger import AutoDebugger
except ImportError:
    logger.warning("⚠️ AutoDebugger not loaded, error recovery will be limited")
    AutoDebugger = None

# Force import ContextEngine
try:
    from context_engine import ContextEngine
except ImportError:
    class ContextEngine:
        @staticmethod
        def build_system_prompt(language="en"): return "You are AMP Agent."
        @staticmethod
        def _normalize_tool_params(name, params): return params

# Import ToolOrchestrator (prefer packaged version, fallback to legacy top-level)
try:
    from tools.tool_orchestrator import ToolOrchestrator
except ImportError:
    try:
        from tool_orchestrator import ToolOrchestrator  # Legacy fallback
    except ImportError:
        ToolOrchestrator = None
        logger.warning("⚠️ ToolOrchestrator not loaded, container orchestration unavailable")

# Import SkillIntentRecognizer
try:
    import sys as _sys, os as _os
    _skill_dir = _os.path.join(_os.path.dirname(__file__), 'skills')
    if _skill_dir not in _sys.path:
        _sys.path.insert(0, _skill_dir)
    from skill_intent_recognizer import SkillIntentRecognizer as _SkillIntentRecognizer
except ImportError as _e:
    _SkillIntentRecognizer = None
    logger.warning(f"⚠️ SkillIntentRecognizer not loaded: {_e}")

logger = logging.getLogger(__name__)

# ==================== Skill Content Loader ====================
def _load_skill_content(skill_name: str) -> str:
    """
    Progressive disclosure: load the full SKILL.md content for the triggered skill.
    Maps skill_name from SkillIntentRecognizer to the corresponding SKILL.md directory.
    """
    _skill_name_map = {
        'rapid_design': 'rapid_design',
        'multi_generator_benchmark': 'compare_generators',
        'structure_validated_design': 'structure_discrimination',
        'knowledge_guided_design': 'knowledge_guided_design',
    }
    folder = _skill_name_map.get(skill_name, skill_name)
    skill_file = os.path.join(os.path.dirname(__file__), 'skills', folder, 'SKILL.md')
    try:
        with open(skill_file, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logger.warning(f"⚠️ SKILL.md not found for skill '{skill_name}' at {skill_file}")
        return ""

# ==================== 1. 🧠 PRM (Process Reward Model) ====================

class ProcessRewardModel:
    def evaluate(self, step_name: str, input_args: Dict, output_data: Any) -> Dict:
        if step_name == "generate":
            expected = input_args.get("num_samples", 5)
            actual = len(output_data) if isinstance(output_data, list) else 0
            if actual == 0: return {"score": 0.0, "passed": False, "reason": "Empty generation result"}
            if actual < expected * 0.5: return {"score": 0.5, "passed": False, "reason": "Insufficient generation count"}
            return {"score": 1.0, "passed": True, "reason": "Pass"}
        elif step_name == "evaluate":
            if not output_data: return {"score": 0.0, "passed": False, "reason": "Empty evaluation result"}
            valid_amp = sum(1 for item in output_data if item.get("is_amp") is True)
            if valid_amp == 0: return {"score": 0.0, "passed": False, "reason": "No valid AMP found"}
            return {"score": 1.0, "passed": True, "reason": f"Found {valid_amp} valid sequences"}
        return {"score": 1.0, "passed": True, "reason": "Pass"}

# ==================== 2. Agent Main Class ====================

def extract_params_from_user_input(user_input: str) -> dict:
    """
    Extract key parameters from user input (regex preprocessing).

    Examples:
        "Design 10 peptides" -> {"num_samples": 10}
        "Generate 8 AMPs against Gram-negative" -> {"num_samples": 8, "target": "Gram-negative"}
        "Create 5 sequences for Gram-positive" -> {"num_samples": 5, "target": "Gram-positive"}
    """
    import re
    params = {}
    
    # 1. Extract numeric count (num_samples)
    # Matches: "10 peptides", "8 AMPs", "5 sequences", "3 candidates"
    num_match = re.search(r'(\d+)\s*(peptide|amp|sequence|candidate)', user_input, re.IGNORECASE)
    if num_match:
        params['num_samples'] = int(num_match.group(1))
        logger.info(f"🔍 Extracted num_samples={params['num_samples']} from user input")
    
    # 2. Extract target organism type
    target_patterns = {
        'Gram-negative': r'gram[\s-]?negative|g[\s-]?\-',
        'Gram-positive': r'gram[\s-]?positive|g[\s-]?\+',
        'Mammalian': r'mammalian|cancer|tumor',
        'Antifungal': r'antifungal|fungi|fungal',
        'Antiviral': r'antiviral|virus|viral'
    }
    
    for target, pattern in target_patterns.items():
        if re.search(pattern, user_input, re.IGNORECASE):
            params['target'] = target
            logger.info(f"🔍 Extracted target={target} from user input")
            break
    
    # 3. Extract generation strategy
    if re.search(r'novel|diverse|different|varied', user_input, re.IGNORECASE):
        params['strategy'] = 'diverse'
    elif re.search(r'refine|optimize|improve', user_input, re.IGNORECASE):
        params['strategy'] = 'refine'
    
    return params


# ═══════════════════════════════════════════════════════════════════════════════
# INPUT SPELL CORRECTION (Auto-Debug Pre-processing Layer)
# ═══════════════════════════════════════════════════════════════════════════════
# Common typos in scientific/technical keywords that may affect tool routing.
# Each typo maps to its correct form. Matching is case-insensitive.
COMMON_TYPOS = {
    # "structural" variants
    "strucural": "structural",
    "structrual": "structural",
    "structual": "structural",
    "strucutral": "structural",
    "sturctural": "structural",
    "structual": "structural",
    # "constraints" variants
    "constaints": "constraints",
    "constriants": "constraints",
    "constrains": "constraints",  # common omission of 't'
    "constratints": "constraints",
    "constrants": "constraints",
    "constriant": "constraint",
    "constaint": "constraint",
    # "structure" variants
    "strucure": "structure",
    "strucuture": "structure",
    "struture": "structure",
    "sturcture": "structure",
    "structre": "structure",
    # "prediction" variants
    "prediciton": "prediction",
    "predcition": "prediction",
    "predictoin": "prediction",
    # "generate" / "design" variants
    "genereate": "generate",
    "genreate": "generate",
    "desgin": "design",
    "dseign": "design",
    # "hemolysis" variants
    "hemolysys": "hemolysis",
    "hemolyss": "hemolysis",
    "haemolysis": "hemolysis",  # British spelling variant (acceptable)
    # "antimicrobial" variants
    "antimicrobal": "antimicrobial",
    "antimicrobail": "antimicrobial",
    "antimicorbial": "antimicrobial",
    # "peptide" variants
    "peptdie": "peptide",
    "peptid": "peptide",
    "peptied": "peptide",
    # "discrimination" variants
    "discriminaton": "discrimination",
    "discrimintaion": "discrimination",
    "discrimnation": "discrimination",
    # "pareto" variants
    "pereto": "pareto",
    "paretoo": "pareto",
    # "novel" variants
    "noval": "novel",
    "novle": "novel",
    "noevl": "novel",
}


def _correct_user_input(text: str) -> tuple:
    """
    Auto-Debug Pre-processing: correct common typos in user input.
    
    Returns:
        (corrected_text, list_of_corrections)
        where list_of_corrections is a list of (typo, correction) tuples.
    """
    if not text:
        return text, []
    
    corrections = []
    words = text.split()
    corrected_words = []
    
    for word in words:
        # Strip trailing punctuation for matching, preserve it after
        stripped = word.rstrip('.,!?;:')
        suffix = word[len(stripped):]
        
        lower_stripped = stripped.lower()
        if lower_stripped in COMMON_TYPOS:
            corrected = COMMON_TYPOS[lower_stripped]
            # Preserve original capitalization pattern
            if stripped.isupper():
                corrected = corrected.upper()
            elif stripped[0].isupper():
                corrected = corrected.capitalize()
            corrections.append((stripped, corrected))
            corrected_words.append(corrected + suffix)
        else:
            corrected_words.append(word)
    
    return ' '.join(corrected_words), corrections


class AMPAgentV3:
    def __init__(self, client, model_name="qwen-instruct", language="en", verbose=False):
        self.client = client
        self.model = model_name
        self.language = language
        self.texts = TEXTS.get(language, TEXTS["en"])  # ✅ Fallback to EN instead of ZH
        self.verbose = verbose
        self.prm = ProcessRewardModel()
        self.conversation_history = []
        self.log_callback = None
        self.global_df = None
        self.visualization_generated = False  # Prevent duplicate visualization generation
        self._last_compare_result = None  # Cache for the current comparison task data
        self._generated_sequences_cache = {}  # seq -> generator_name mapping to preserve generator tag across LLM calls
        self.system_prompt = ContextEngine.build_system_prompt(language)
        self.orchestrator = ToolOrchestrator() if ToolOrchestrator else None
        
        # Initialize Auto-Debugger
        self.auto_debugger = AutoDebugger(client, model_name) if AutoDebugger else None
        if self.auto_debugger:
            logger.info("✅ Auto-Debugger initialized (Pattern + LLM mode)")
        else:
            logger.warning("⚠️ Auto-Debugger unavailable")
        
        # Initialize database manager
        try:
            self.db = DatabaseManager()
            logger.info("✅ Database initialized")
            # Restore historical data on startup
            self._restore_from_database()
        except Exception as e:
            logger.error(f"❌ Failed to initialize database: {e}")
            self.db = None
        
        if self.orchestrator:
            # Start lightweight Designer by default as a persistent base service
            self.orchestrator.start_tool("amp_designer", silent=True)
                
        # Initialize SkillIntentRecognizer
        self.skill_recognizer = _SkillIntentRecognizer() if _SkillIntentRecognizer else None
        if self.skill_recognizer:
            logger.info("✅ SkillIntentRecognizer initialized")
        else:
            logger.warning("⚠️ SkillIntentRecognizer unavailable, all requests use ReAct mode")
    
    def _execute_tool_with_retry(self, tool_func, tool_name: str, params: dict, max_retries: int = 3):
        """
        🔧 Execute tool with Auto-Debug retry mechanism
            
        Args:
            tool_func: The tool function to execute
            tool_name: Name of the tool (for logging and debugging)
            params: Parameters to pass to the tool
            max_retries: Maximum number of retry attempts (default: 3)
            
        Returns:
            Tool execution result
            
        Raises:
            Exception: If all retries fail
        """
        error_history = []  # Track all failed attempts
            
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"🔧 [{tool_name}] Attempt {attempt}/{max_retries}")
                logger.info(f"   Params: {params}")
                    
                # Execute the tool
                result = tool_func(**params)
                    
                # Success! Clear error history
                if self.auto_debugger and attempt > 1:
                    logger.info(f"✅ [{tool_name}] Succeeded after {attempt} attempts")
                    self.auto_debugger.clear_history()
                    
                return result
                
            except Exception as e:
                error_msg = str(e)
                logger.warning(f"❌ [{tool_name}] Attempt {attempt} failed: {error_msg[:200]}")
                    
                # Record error into history
                error_info = {
                    "attempt": attempt,
                    "error": error_msg,
                    "error_type": type(e).__name__,
                    "params": params.copy(),
                    "timestamp": time.time()
                }
                error_history.append(error_info)
                    
                # Record error in history
                if self.auto_debugger:
                    self.auto_debugger.record_error(tool_name, params, error_msg, attempt)
                    
                # If this is the last attempt, log to database and raise
                if attempt >= max_retries:
                    logger.error(f"❌ [{tool_name}] All {max_retries} attempts failed")
                        
                    # Log to database for Auto-Debug analysis
                    try:
                        self.db_manager.log_tool_failure(
                            tool_name=tool_name,
                            params=params,
                            error_history=error_history,
                            session_id=getattr(self, 'session_id', None)
                        )
                    except Exception as log_err:
                        logger.error(f"⚠️  Failed to log tool failure: {log_err}")
                        
                    raise
                    
                # Try Auto-Debug
                if self.auto_debugger:
                    fixed_params, fix_method = self.auto_debugger.debug_and_fix(
                        error_msg, tool_name, params, attempt
                    )
                        
                    if fixed_params:
                        logger.info(f"🔧 Auto-Debug fixed params using {fix_method} method")
                        params = fixed_params  # Use fixed parameters for next attempt
                    else:
                        logger.warning(f"⚠️  Auto-Debug could not fix the error")
                        # Still retry with original params (maybe transient error)
                else:
                    logger.warning("⚠️  Auto-Debugger not available, retrying with original params")

    def chat(self, user_input: str, max_iterations: int = 10) -> Generator:
        # ── Auto-Debug Pre-processing: Spell Correction ──
        corrected_input, corrections = _correct_user_input(user_input)
        if corrections:
            typo_details = ', '.join(f'"{t}" → "{c}"' for t, c in corrections)
            logger.info(f"🔤 Auto-Debug [Input Correction]: {typo_details}")
            user_input = corrected_input  # Use corrected input for all downstream processing
            # Notify user in chat stream (yield before task starts)
            yield f"🔤 **Auto-correction applied**: {typo_details}\n"
        
        self.conversation_history.append({"role": "user", "content": user_input})
        self.visualization_generated = False  # Reset visualization flag per conversation
        self._last_compare_result = None  # Reset comparison data cache per conversation
        self._generated_sequences_cache = {}  # Reset sequence-generator cache per conversation
        self.current_user_input = user_input  # Store current user input for downstream tool handling

        # Regex preprocessing: extract key parameters
        extracted_params = extract_params_from_user_input(user_input)
        
        # Skill intent recognition (progressive disclosure: inject full SKILL.md SOP when triggered)
        skill_hint = ""
        _active_skill = None  # Track the currently active skill for downstream tool-call guards
        if self.skill_recognizer:
            skill_result = self.skill_recognizer.recognize(user_input)
            if skill_result and skill_result['confidence'] >= 0.7:
                sname = skill_result['skill_name']
                sparams = skill_result.get('params', {})
                _active_skill = sname
                logger.info(f"🎯 Skill intent detected: {sname} (confidence={skill_result['confidence']:.2f}, params={sparams})")
                # Progressive disclosure: load and inject full SKILL.md content
                skill_content = _load_skill_content(sname)
                if skill_content:
                    skill_hint = (
                        f"\n\n--- ACTIVATED SKILL: {sname} ---\n"
                        f"Confidence: {skill_result['confidence']:.2f} | Extracted params: {sparams}\n"
                        f"Follow the SOP below EXACTLY for this request:\n\n"
                        f"{skill_content}\n"
                        f"--- END SKILL: {sname} ---\n"
                    )
                else:
                    # Fallback: use a short hint when SKILL.md is missing
                    skill_hint = f"\n\n🎯 Skill '{sname}' triggered (confidence={skill_result['confidence']:.2f}). Params: {sparams}\n"
        
        # Inject extracted parameters into the system prompt when present
        if extracted_params:
            param_hint = "\n\n⚠️ EXTRACTED PARAMETERS FROM USER INPUT:\n"
            if 'num_samples' in extracted_params:
                param_hint += f"- num_samples: {extracted_params['num_samples']}\n"
            if 'target' in extracted_params:
                param_hint += f"- target: {extracted_params['target']}\n"
            if 'strategy' in extracted_params:
                param_hint += f"- strategy: {extracted_params['strategy']}\n"
            param_hint += "\nYou MUST use these exact values when calling tools.\n"
            
            # Append the hint to the system prompt temporarily
            augmented_system_prompt = self.system_prompt + param_hint + skill_hint
        else:
            augmented_system_prompt = self.system_prompt + skill_hint
        
        # Non-technical tasks: reply directly
        if not self._is_technical_task(user_input):
            try:
                messages = [{"role": "system", "content": augmented_system_prompt}] + self.conversation_history[-10:]
                resp = self.client.chat.completions.create(model=self.model, messages=messages)
                yield resp.choices[0].message.content
                return
            except: pass

        # ReAct loop: iterate tool calls until the task is complete
        iteration = 0
        _task_done = False  # Comparison-task completion flag used to break the outer loop
        while iteration < max_iterations:
            iteration += 1
            if _task_done:  # Comparison task finished, exit outer loop
                break
            
            # Build the current conversation context (with augmented system prompt).
            # To avoid the DashScope/Qwen error "messages with role 'tool' must be a response
            # to a preceding message with 'tool_calls'", the history is cleaned here so that
            # only tool messages whose matching tool_calls exist in the current window are kept.
            history = self.conversation_history[-10:]

            # Collect all valid tool_call_ids present in the current window
            valid_tool_call_ids = set()
            for m in history:
                if m.get("role") == "assistant" and m.get("tool_calls"):
                    try:
                        for tc in m["tool_calls"]:
                            # OpenAI/Qwen style: tool_call carries an id attribute or field
                            if isinstance(tc, dict):
                                tid = tc.get("id")
                            else:
                                tid = getattr(tc, "id", None)
                            if tid:
                                valid_tool_call_ids.add(tid)
                    except Exception:
                        continue
            
            # Collect tool_call_ids of all tool responses
            tool_responses = set()
            for m in history:
                if m.get("role") == "tool" and m.get("tool_call_id"):
                    tool_responses.add(m["tool_call_id"])
            
            # Drop tool messages without matching tool_calls to prevent orphan tool entries,
            # and drop assistant messages whose tool_calls have incomplete responses.
            filtered_history = []
            for m in history:
                if m.get("role") == "assistant" and m.get("tool_calls"):
                    # Check whether every tool_call_id has a matching response
                    try:
                        required_ids = set()
                        for tc in m["tool_calls"]:
                            if isinstance(tc, dict):
                                tid = tc.get("id")
                            else:
                                tid = getattr(tc, "id", None)
                            if tid:
                                required_ids.add(tid)
                                    
                        if required_ids.issubset(tool_responses):
                            filtered_history.append(m)
                        else:
                            missing = required_ids - tool_responses
                            logger.warning(f"Skipping assistant with incomplete tool responses. Missing: {missing}")
                    except Exception as e:
                        logger.warning(f"Error validating tool_calls: {e}")
                elif m.get("role") == "tool":
                    if m.get("tool_call_id") in valid_tool_call_ids:
                        filtered_history.append(m)
                    else:
                        logger.warning(f"Skipping orphan tool message without matching tool_calls: {m.get('name')}")
                else:
                    filtered_history.append(m)

            messages = [{"role": "system", "content": augmented_system_prompt}] + filtered_history
            
            # compare_generators Skill: dynamically inject generate_sequences + evaluate_amp tools
            _active_tools_schema = list(TOOLS_SCHEMA)
            if _active_skill == 'multi_generator_benchmark':
                _compare_tools = [
                    {
                        "type": "function",
                        "function": {
                            "name": "generate_sequences",
                            "description": "Generate AMP sequences from a specific generator. Used for multi-generator comparison. Call this 3 times (generator=default/diverse/refine), then merge results and call evaluate_amp once.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "num_samples": {"type": "integer", "description": "Number of sequences to generate per generator"},
                                    "target": {"type": "string", "enum": ["Gram-negative", "Gram-positive", "Mammalian", "Antifungal", "Antiviral"]},
                                    "generator": {"type": "string", "enum": ["default", "diverse", "refine"], "description": "default=AMP-Designer, diverse=Diff-AMP, refine=HydrAMP"}
                                },
                                "required": ["num_samples", "target", "generator"]
                            }
                        }
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "evaluate_amp",
                            "description": "Evaluate a list of AMP sequences for MIC, hemolysis, CPP and AMP probability. Call once with all merged sequences from all generators.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "sequences": {"type": "array", "items": {"type": "object"}, "description": "List of sequence dicts with 'sequence' and 'generator' fields"}
                                },
                                "required": ["sequences"]
                            }
                        }
                    }
                ]
                _active_tools_schema = _active_tools_schema + _compare_tools
                logger.info("✅ Injected generate_sequences + evaluate_amp into tools schema for compare_generators Skill")

            try:
                response = self.client.chat.completions.create(
                    model=self.model, 
                    messages=messages, 
                    tools=_active_tools_schema, 
                    tool_choice="auto",  # Let the model pick the most suitable tool
                    temperature=0.7
                )
                msg = response.choices[0].message
                content = msg.content or ""
                tool_calls = msg.tool_calls
                
                if not tool_calls:
                    manual = self._parse_manual_tool_call(content)
                    if manual: tool_calls = manual
                
                # CRITICAL: forcibly correct LLM tool-selection mistakes
                if tool_calls:
                    for i, tool in enumerate(tool_calls):
                        fn_name = tool['function']['name'] if isinstance(tool, dict) else tool.function.name
                        
                        # If the user did not explicitly request structure discrimination but LLM picked structure_discrimination_pipeline
                        if fn_name == "structure_discrimination_pipeline":
                            user_input_lower = user_input.lower() if user_input else ""
                            has_structure_keywords = any(kw in user_input_lower for kw in [
                                "structure-based", "esmfold", "pgat", "3d structure",
                                "structural constraint", "structural constraints",
                                "structural design", "structure prediction",
                                "structure discrimination", "structural guidance",
                                "structural", "structure-aware",
                            ])
                            
                            if not has_structure_keywords:
                                logger.warning(f"🔥 LLM mistakenly chose structure_discrimination_pipeline, forcing design_new_amps instead")
                                
                                # Force replace with design_new_amps
                                if isinstance(tool, dict):
                                    tool['function']['name'] = 'design_new_amps'
                                else:
                                    tool.function.name = 'design_new_amps'
                                
                                logger.info(f"\u2705 Corrected tool choice from structure_discrimination_pipeline to design_new_amps")
                
                        # REVERSE GUARD: user explicitly requested structure pipeline but LLM chose design_new_amps
                        elif fn_name == "design_new_amps":
                            user_input_lower = user_input.lower() if user_input else ""
                            has_structure_keywords = any(kw in user_input_lower for kw in [
                                "structure-based", "esmfold", "pgat", "3d structure",
                                "structural constraint", "structural constraints",
                                "structural design", "structure prediction",
                                "structure discrimination", "structural guidance",
                                "structural", "structure-aware",
                            ])
                            
                            if has_structure_keywords:
                                logger.warning(f"🔥 LLM chose design_new_amps but user requested structure pipeline, forcing structure_discrimination_pipeline")
                                
                                # Force replace with structure_discrimination_pipeline
                                if isinstance(tool, dict):
                                    tool['function']['name'] = 'structure_discrimination_pipeline'
                                else:
                                    tool.function.name = 'structure_discrimination_pipeline'
                                
                                logger.info(f"✅ Corrected tool choice from design_new_amps to structure_discrimination_pipeline")
                
                # 🚨 HIGHEST PRIORITY GUARD: seq+mutate intent → force analyze_sequence
                # Prevents LLM from calling design_new_amps/generate_sequences when user
                # wants to analyze and mutate an existing sequence.
                if tool_calls:
                    import re as _re_guard, json as _json_guard
                    _u_lower = (user_input or '').lower()
                    _has_seq  = bool(_re_guard.search(r'\b[ACDEFGHIKLMNPQRSTVWY]{8,}\b', user_input or ''))
                    _has_ref  = bool(_re_guard.search(r'#\s*\d+', user_input or ''))
                    _mut_sigs = [
                        'mutant', 'mutants', 'mutate', 'mutation', 'mutations',
                        'optimized mutant', 'optimized mutants', 'optimize mutant',
                        'improve its', 'improve the ranking', 'improve ranking',
                        'improve its overall', 'better ranking', '\u7a81\u53d8', '\u4f18\u5316\u7a81\u53d8'
                    ]
                    _wants_mut = any(s in _u_lower for s in _mut_sigs)
                    _all_fns   = [
                        (tc['function']['name'] if isinstance(tc, dict) else tc.function.name)
                        for tc in tool_calls
                    ]
                    _has_design = any(fn in ('design_new_amps', 'generate_sequences') for fn in _all_fns)
                    if (_has_seq or _has_ref) and _wants_mut and _has_design:
                        _sm = _re_guard.search(r'\b([ACDEFGHIKLMNPQRSTVWY]{8,})\b', user_input or '')
                        _tseq = _sm.group(1).upper() if _sm else ''
                        logger.warning(f"\U0001f6a8 TOP-GUARD: seq+mutate intent, overriding tool_calls \u2192 analyze_sequence({_tseq})")
                        class _FakeFunc:
                            name = 'analyze_sequence'
                            arguments = _json_guard.dumps({'sequence': _tseq})
                        class _FakeTC:
                            id = f'guard_{_tseq[:6]}'
                            function = _FakeFunc()
                        tool_calls = [_FakeTC()]
                        if self.conversation_history and self.conversation_history[-1].get('role') == 'assistant':
                            self.conversation_history[-1]['tool_calls'] = tool_calls
                
                # If tool_calls are present this is the LLM decision-phase monologue and is not exposed to the user
                if content and tool_calls:
                    logger.debug(f"[LLM inner reasoning (suppressed)]: {content[:200]}")
                
                # Append the Qwen response to history (only when tool_calls exist)
                if tool_calls:
                    # DEBUG: print tool_calls structure
                    logger.info(f"🔍 [Assistant Response] tool_calls count={len(tool_calls)}")
                    for idx, tc in enumerate(tool_calls):
                        if isinstance(tc, dict):
                            logger.info(f"  [{idx}] dict: id={tc.get('id')}, function={tc.get('function', {}).get('name')}")
                        else:
                            logger.info(f"  [{idx}] object: id={getattr(tc, 'id', None)}, function={getattr(tc.function, 'name', None)}")
                    
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": content,
                        "tool_calls": tool_calls
                    })

                # No tool call: decide whether this is a "planning monologue" or a "final answer"
                if not tool_calls:
                    import re as _re
                    # Planning-monologue signals:
                    # 1. Trailing tool_name(...) pseudocode call (strongest signal)
                    # 2. Very short content expressing intent without real answer
                    TOOL_NAMES = [
                        "search_knowledge", "query_mechanisms_for_target", "query_principles_for_mechanism",
                        "query_ontology", "design_new_amps", "generate_sequences", "evaluate_amp",
                        "rank_sequences", "analyze_sequence", "predict_structure", "mutate_sequence"
                    ]
                    # Detect trailing pseudocode pattern: tool_name(...)
                    has_pseudocode = any(
                        _re.search(rf'\b{tn}\s*\(', content) for tn in TOOL_NAMES
                    )
                    # Detect pure planning (very short + no substantial content)
                    is_very_short_planning = len(content.strip()) < 300 and any(
                        sig in content.lower() for sig in [
                            "i'll search", "let me search", "i will search",
                            "i'll query", "let me query", "i will query",
                            "let me retrieve", "i'll retrieve",
                            "let me run", "i'll run",
                        ]
                    )
                    looks_like_planning = has_pseudocode or is_very_short_planning
                    
                    if looks_like_planning and iteration < max_iterations - 2:
                        logger.info(f"[Planning monologue detected (pseudocode={has_pseudocode}, short={is_very_short_planning}), continuing loop]: {content[:120]}")
                        # Append planning monologue to history so LLM continues (do not yield to user)
                        self.conversation_history.append({
                            "role": "assistant",
                            "content": content
                        })
                        # Append a user-side nudge to push LLM into actually calling tools
                        self.conversation_history.append({
                            "role": "user",
                            "content": "Please proceed and call the tools now (do not describe your plan — just invoke the tools directly)."
                        })
                        continue  # Proceed to the next iteration without yielding the planning monologue
                    else:
                        # Genuine final answer: emit to user
                        if content:
                            yield f"{content}\n\n"
                        self.conversation_history.append({
                            "role": "assistant",
                            "content": content
                        })
                        yield self.texts["task_complete"]
                        break
        
                # Execute tool calls
                if tool_calls:
                    for tool in tool_calls:
                        if isinstance(tool, dict):
                            fn_name = tool['function']['name']
                            args_str = tool['function']['arguments']
                            # For standard tool_calls the id is provided by the model; manually parsed calls may lack id
                            tool_id = tool.get('id')
                        else:
                            fn_name = tool.function.name
                            args_str = tool.function.arguments
                            tool_id = getattr(tool, 'id', None)
                        
                        # DEBUG: log tool_id status
                        logger.info(f"🔍 [Tool Call] fn_name={fn_name}, tool_id={tool_id}, type={type(tool)}")
                        logger.info(f"🔍 [Tool Args] args_str type={type(args_str)}, len={len(str(args_str))}")
                                
                        try: 
                            raw_args = json.loads(args_str)
                            logger.info(f"🔍 [Tool Raw Args] raw_args={raw_args}")
                        except Exception as e:
                            logger.error(f"❌ Failed to parse args_str: {e}")
                            logger.error(f"   args_str content: {repr(args_str)[:500]}")
                            raw_args = {}
                                
                        args = ContextEngine._normalize_tool_params(fn_name, raw_args)
                        logger.info(f"🔍 [Tool Normalized Args] args={args}")
                        
                        # Force parameter override using regex-extracted values
                        if fn_name in ["design_new_amps", "generate_sequences"]:
                            if 'num_samples' in extracted_params:
                                old_val = args.get('num_samples')
                                args['num_samples'] = extracted_params['num_samples']
                                logger.warning(f"⚠️ FORCED OVERRIDE: {fn_name}.num_samples changed from {old_val} to {args['num_samples']}")
                            
                            if 'target' in extracted_params and 'target' not in args:
                                args['target'] = extracted_params['target']
                                logger.info(f"✅ Injected target={args['target']} from extraction")
                            
                            if 'strategy' in extracted_params and 'strategy' not in args:
                                args['strategy'] = extracted_params['strategy']
                                logger.info(f"✅ Injected strategy={args['strategy']} from extraction")
                        
                        # Force ontology mode: switch search_knowledge.knowledge_type when the user explicitly mentions "ontology"
                        if fn_name == "search_knowledge":
                            try:
                                if user_input and "ontology" in user_input.lower():
                                    kt_before = args.get("knowledge_type", "literature")
                                    if kt_before != "ontology":
                                        args["knowledge_type"] = "ontology"
                                        logger.info(f"✅ Forced knowledge_type from {kt_before} to 'ontology' based on user hint in input")
                            except Exception as e:
                                logger.warning(f"⚠️ Failed to enforce ontology knowledge_type: {e}")
        
                        tool_output = ""
                                
                        # === design_new_amps: run the full four-step pipeline and return immediately ===
                        if fn_name == "design_new_amps":
                            # Guard: if the user input contains an explicit sequence or #N reference, the intent is to operate on an existing sequence.
                            # Example: "Analyze #5 AGLFPPPLWW... and generate optimized mutants"
                            # Here "generate" triggers design_new_amps, but the actual path should be analyze + mutate.
                            _user_raw_lower = (user_input or '').lower()
                            import re as _re
                            _has_seq_in_input = bool(_re.search(r'\b[ACDEFGHIKLMNPQRSTVWY]{8,}\b', user_input or ''))
                            _has_rank_ref    = bool(_re.search(r'#\s*\d+', user_input or ''))
                            _wants_mutate_op = any(s in _user_raw_lower for s in [
                                'mutant', 'mutants', 'mutate', 'mutation', 'mutations',
                                'optimize mutant', 'optimized mutant', 'optimized mutants',
                                'improve its', 'improve the ranking', 'improve ranking',
                                'better ranking', 'improve its overall',
                                '突变', '优化突变'
                            ])
                            if (_has_seq_in_input or _has_rank_ref) and _wants_mutate_op:
                                logger.warning("⚠️ design_new_amps intercepted: user has a concrete sequence + mutate intent → redirect to analyze+mutate")
                                # Extract the sequence
                                _seq_match = _re.search(r'\b([ACDEFGHIKLMNPQRSTVWY]{8,})\b', user_input or '')
                                _redir_seq  = _seq_match.group(1).upper() if _seq_match else ""
                                tool_output = (
                                    f"⚠️ REDIRECT: You called design_new_amps but the user wants to analyze and mutate an existing sequence: {_redir_seq}.\n"
                                    f"Do NOT design new sequences. Instead:\n"
                                    f"1. Call analyze_sequence with sequence='{_redir_seq}'\n"
                                    f"2. Then call mutate_sequence with sequence='{_redir_seq}' and goal='balanced'\n"
                                    f"Do NOT call design_new_amps."
                                )
                                self.conversation_history.append({"role": "tool", "tool_call_id": tool_id or "redirect_guard", "name": fn_name, "content": tool_output})
                                continue

                            # If compare_generators Skill is active, intercept design_new_amps and redirect
                            if _active_skill == 'multi_generator_benchmark':
                                logger.warning("⚠️ compare_generators Skill active: intercepting design_new_amps and redirecting to the generate_sequences workflow")
                                tool_output = (
                                    "⚠️ SKILL GUARD: You called design_new_amps but the active skill is compare_generators.\n"
                                    "You MUST NOT use design_new_amps for multi-generator comparison.\n"
                                    "CORRECT approach: Call generate_sequences 3 times (generator=default/diverse/refine), "
                                    "merge all sequences, then call evaluate_amp once with all merged sequences.\n"
                                    "Please retry using the compare_generators SOP."
                                )
                                self.conversation_history.append({
                                    "role": "tool",
                                    "tool_call_id": tool_id or "skill_guard",
                                    "name": fn_name,
                                    "content": tool_output
                                })
                                continue  # Return to LLM so it can re-invoke correctly
                            results_capture = []  # Capture the generated sequences
                            for chunk in self._handle_design_pipeline(args, results_capture):
                                yield chunk

                            # Task is already completed inside _handle_design_pipeline (including summary); finish here.
                            # Stop heavy generators and restore AMP-Designer as the default always-on service.
                            if self.orchestrator:
                                self.orchestrator.switch_to_default()
                            # Force return to prevent the LLM from continuing the loop after seeing tool_output
                            return
        
                        elif fn_name == "analyze_sequence":
                            _did_autochain = False
                            for chunk in self._handle_analyze_pipeline(args):
                                if isinstance(chunk, str): tool_output = "Analysis Done"
                                yield chunk
                            # If analyze auto-chained a mutate, the full task is done.
                            # Set tool_output to signal completion and return to prevent
                            # the LLM from calling mutate_sequence again independently.
                            user_raw_check = (user_input or '').lower()
                            _did_autochain = any(s in user_raw_check for s in [
                                'mutate','mutation','optimize','optimise','improve',
                                'redesign','突变','优化','改进','改造','提升'
                            ])
                            if _did_autochain:
                                tool_output = (
                                    "✅ TASK COMPLETE: analyze_sequence and mutate_sequence have both been executed. "
                                    "The mutation comparison table has been shown. "
                                    "Do NOT call mutate_sequence again. The task is fully done."
                                )
                                self.conversation_history.append({
                                    "role": "tool",
                                    "tool_call_id": tool_id or "analyze_done",
                                    "name": fn_name,
                                    "content": tool_output
                                })
                                return  # ← prevent LLM from re-invoking mutate
                        elif fn_name == "mutate_sequence":
                            for chunk in self._handle_mutate_pipeline(args):
                                if isinstance(chunk, str): tool_output = "Mutation Done"
                                yield chunk
                            return
                        elif fn_name == "structure_discrimination_pipeline":
                            # Structure discrimination pipeline (new)
                            logger.info(f"🧬 Starting structure discrimination pipeline with args: {args}")

                            # CRITICAL: Fallback logic to prevent infinite loops
                            if not hasattr(self, '_pgat_failure_count'):
                                self._pgat_failure_count = 0
                            
                            # Launch the required services
                            if self.orchestrator:
                                # Launch the generator
                                generator_param = args.get("generator", "default")
                                # Structure discrimination pipeline defaults to AMP-Designer;
                                # switch only when the user explicitly mentions HydrAMP / Diff-AMP
                                try:
                                    user_input_lower = user_input.lower() if user_input else ""
                                    user_asks_hydramp = ("hydramp" in user_input_lower) or ("优化" in user_input_lower) or ("refine" in user_input_lower)
                                    user_asks_diffamp = ("diff-amp" in user_input_lower) or ("diffamp" in user_input_lower) or ("多样" in user_input_lower) or ("diverse" in user_input_lower)
                                except Exception:
                                    user_asks_hydramp = False
                                    user_asks_diffamp = False

                                if generator_param != "default" and not (user_asks_hydramp or user_asks_diffamp):
                                    logger.info(f"🔧 Forcing generator to 'default' (AMP-Designer) for structure pipeline; previous={generator_param}")
                                    generator_param = "default"
                                    args["generator"] = "default"

                                if "diverse" in generator_param.lower():
                                    self.orchestrator.start_tool("diff_amp")
                                elif "refine" in generator_param.lower():
                                    self.orchestrator.start_tool("hydramp")
                                else:
                                    self.orchestrator.start_tool("amp_designer")
                                
                                # Launch structure prediction and PGAT services
                                self.orchestrator.start_tool("structure")
                                self.orchestrator.start_tool("pgat_abpp")
                            
                            yield f"🚀 **Starting structure discrimination pipeline**...\n\n"
                            yield f"Target: {args.get('target', 'Gram-negative')}\n"
                            yield f"Samples: {args.get('num_samples', 10)}\n"
                            yield f"PGAT Threshold: {args.get('pgat_threshold', 0.5)}\n\n"
                            
                            # Execute the pipeline
                            result = self._execute_tool_with_retry(
                                tool_structure_discrimination_pipeline,
                                "structure_discrimination_pipeline",
                                args
                            )
                            
                            if result.get("success"):
                                # Render pipeline summary
                                stages = result.get("pipeline_stages", {})
                                # Pipeline summary (HTML card)
                                stages_html = (
                                    "<div style='background:#f0f7ff;border-left:4px solid #1677ff;padding:12px 16px;"
                                    "border-radius:6px;margin:8px 0;font-size:13px'>"
                                    "<b style='color:#1677ff'>&#x2705; Pipeline Completed</b><br/>"
                                    "<span style='color:#555'>"
                                    f"&#x1F9EC; Generated: <b>{stages.get('generated',0)}</b> &nbsp;|&nbsp; "
                                    f"&#x1F3DB; ESMFold: <b>{stages.get('structure_predicted',0)}</b> &nbsp;|&nbsp; "
                                    f"&#x1F4CD; PGAT pass: <b>{stages.get('passed_pgat',0)}</b> &nbsp;|&nbsp; "
                                    f"&#x1F3AF; Final: <b>{stages.get('final_candidates',0)}</b>"
                                    "</span></div>"
                                )
                                yield {"type": "html_table", "content": stages_html}

                                # Top 3 candidate sequences (HTML card)
                                sequences = result.get("sequences", [])
                                if sequences:
                                    rank_colors = ['#d4edda','#d1ecf1','#fff3cd']
                                    rank_border = ['#28a745','#17a2b8','#ffc107']
                                    cards_html = "<div style='margin:8px 0'><b style='font-size:14px'>&#x1F3AF; Top 3 Candidates</b></div>"
                                    for i, seq_data in enumerate(sequences[:3]):
                                        sf     = seq_data.get('struct_features') or {}
                                        mic_v  = seq_data.get('mic_pred')
                                        hemo_v = seq_data.get('hemolysis_pred') or seq_data.get('hemolysis_score')
                                        cpp_v  = seq_data.get('cpp_pred')
                                        comp_v = seq_data.get('composite_score')
                                        pgat_v = seq_data.get('pgat_score')
                                        helix  = sf.get('helix_fraction', 0)
                                        sheet  = sf.get('sheet_fraction', 0)
                                        coil   = sf.get('coil_fraction', 0)
                                        plddt  = sf.get('mean_plddt', 0)
                                        rg_v   = sf.get('rg', 0)
                                        has_sf = bool(sf)
                                        helix_bar = ""
                                        if has_sf:
                                            hp = int(helix * 100)
                                            sp = int(sheet * 100)
                                            cp = int(coil  * 100)
                                            helix_bar = (
                                                "<div style='margin:5px 0 2px'>"
                                                "<span style='font-size:11px;color:#666'>Secondary structure: </span>"
                                                "<div style='display:inline-flex;height:9px;border-radius:4px;overflow:hidden;"
                                                "width:150px;vertical-align:middle;margin:0 4px'>"
                                                f"<div style='width:{hp}%;background:#1677ff' title='alpha-helix {hp}%'></div>"
                                                f"<div style='width:{sp}%;background:#52c41a' title='beta-sheet {sp}%'></div>"
                                                f"<div style='width:{cp}%;background:#d9d9d9' title='coil {cp}%'></div>"
                                                "</div>"
                                                f"<span style='font-size:11px;color:#1677ff'>&alpha;-helix {hp}%</span>"
                                                f"<span style='font-size:11px;color:#52c41a;margin-left:6px'>&beta;-sheet {sp}%</span>"
                                                f"<span style='font-size:11px;color:#888;margin-left:6px'>coil {cp}%</span>"
                                                f" &nbsp; <span style='font-size:11px;color:#555'>pLDDT: <b>{plddt:.2f}</b> &nbsp; Rg: <b>{rg_v:.1f}&Aring;</b></span>"
                                                "</div>"
                                            )
                                        metrics_html = ""
                                        if mic_v  is not None: metrics_html += f"<span style='margin-right:12px'>&#x1F4CA; MIC: <b>{mic_v:.2f}</b> &micro;M</span>"
                                        if hemo_v is not None: metrics_html += f"<span style='margin-right:12px'>&#x1F9EA; Hemolysis: <b>{hemo_v:.3f}</b></span>"
                                        if cpp_v  is not None: metrics_html += f"<span style='margin-right:12px'>CPP: <b>{cpp_v:.3f}</b></span>"
                                        if pgat_v is not None: metrics_html += f"<span>PGAT: <b>{pgat_v:.4f}</b></span>"
                                        comp_badge = ""
                                        if comp_v is not None:
                                            comp_badge = (f"<span style='float:right;background:#1677ff;color:white;"
                                                         f"padding:2px 8px;border-radius:10px;font-size:12px'>"
                                                         f"Composite {comp_v:.4f}</span>")
                                        bc = rank_border[i] if i < 3 else '#ccc'
                                        bg = rank_colors[i]  if i < 3 else '#fafafa'
                                        cards_html += (
                                            f"<div style='border-left:4px solid {bc};background:{bg};padding:10px 14px;"
                                            f"border-radius:6px;margin:6px 0;font-size:13px'>"
                                            f"<div style='margin-bottom:4px'>"
                                            f"<b style='font-size:15px'>#{i+1}</b> "
                                            f"<code style='background:rgba(255,255,255,0.7);padding:2px 6px;"
                                            f"border-radius:3px;font-size:13px'>{seq_data['sequence']}</code>"
                                            f"{comp_badge}"
                                            f"</div>"
                                            f"<div style='color:#444;margin:3px 0'>{metrics_html}</div>"
                                            f"{helix_bar}"
                                            f"</div>"
                                        )
                                    yield {"type": "html_table", "content": cards_html}
                                    
                                    # Emit an HTML summary table with real values to prevent LLM hallucination
                                    try:
                                        rows = ""
                                        for i, s in enumerate(sequences):
                                            p = s.get('pgat_score')
                                            p_str = f"{p:.4f}" if p is not None else "N/A"
                                            mic_v = s.get('mic_pred')
                                            mic_str = f"{mic_v:.2f}" if mic_v is not None else "N/A"
                                            hemo_v = s.get('hemolysis_pred') or s.get('hemolysis_score')
                                            hemo_str = f"{hemo_v:.3f}" if hemo_v is not None else "N/A"
                                            cpp_v = s.get('cpp_pred')
                                            cpp_str = f"{cpp_v:.3f}" if cpp_v is not None else "N/A"
                                            sf = s.get('struct_features') or {}
                                            helix_pct = f"{sf.get('helix_fraction',0)*100:.0f}%" if sf else "N/A"
                                            plddt_str = f"{sf.get('mean_plddt',0):.2f}" if sf else "N/A"
                                            rg_str    = f"{sf.get('rg',0):.1f}" if sf else "N/A"
                                            comp_v = s.get('composite_score')
                                            comp_str = f"{comp_v:.4f}" if comp_v is not None else "N/A"
                                            rows += (
                                                f"<tr><td>{i+1}</td>"
                                                f"<td style='font-family:monospace;color:#e84393'>{s['sequence']}</td>"
                                                f"<td>{mic_str}</td><td>{hemo_str}</td>"
                                                f"<td>{cpp_str}</td>"
                                                f"<td>{helix_pct}</td>"
                                                f"<td>{plddt_str}</td>"
                                                f"<td>{rg_str}</td>"
                                                f"<td><b>{comp_str}</b></td>"
                                                f"<td>{s.get('generator','N/A')}</td></tr>"
                                            )
                                        html_table = (
                                            "<table border='1' style='border-collapse:collapse;width:100%;font-size:12px'>"
                                            "<thead><tr style='background:#1677ff;color:white'>"
                                            "<th>Rank</th><th>Sequence</th><th>MIC (μM)</th>"
                                            "<th>Hemolysis</th><th>CPP</th>"
                                            "<th>α-Helix</th><th>pLDDT</th><th>Rg (Å)</th>"
                                            "<th>Composite ↓</th><th>Generator</th>"
                                            "</tr></thead><tbody>" + rows + "</tbody></table>"
                                        )
                                        yield {"type": "html_table", "content": html_table}
                                    except Exception as tbl_err:
                                        logger.warning(f"⚠️ Failed to generate summary table: {tbl_err}")

                                    # Persist to global_df
                                    new_df = pd.DataFrame(sequences)
                                    if self.global_df is None or self.global_df.empty:
                                        self.global_df = new_df
                                    else:
                                        self.global_df = pd.concat([self.global_df, new_df], ignore_index=True)
                                        self.global_df = self.global_df.drop_duplicates(subset=['sequence'], keep='last')
                                    
                                    # Persist to database
                                    self._save_to_database(sequences, session_id="structure_pipeline")

                                    # Hardcoded summary footer (with real generator name)
                                    actual_generator = sequences[0].get('generator', args.get('generator', 'AMP-Designer')) if sequences else args.get('generator', 'AMP-Designer')
                                    generator_display = {"diverse": "Diff-AMP", "refine": "HydrAMP"}.get(actual_generator, "AMP-Designer")
                                    
                                    yield f"\n\n✅ **Ready for Wet-Lab Testing**: The {len(sequences)} candidates identified by this structure-based pipeline represent high-confidence AMP leads with validated structural features. Proceed to synthesis and biological assays to confirm in-silico predictions.\n"
                                    
                                    # RAG + LLM scientific summary (aligned with _handle_design_pipeline)
                                    try:
                                        target_str = args.get('target', 'Gram-negative')
                                        user_lang = getattr(self, 'language', 'en')
                                        
                                        kb_result = tool_search_knowledge(
                                            query=f"antimicrobial peptide mechanisms against {target_str}, structure-activity relationship, amphipathicity, membrane disruption",
                                            knowledge_type="literature"
                                        )
                                        kb_context = ""
                                        if isinstance(kb_result, dict):
                                            results_list = kb_result.get("results", [])
                                            if results_list:
                                                kb_context = "\n\n".join(
                                                    item.get("content", "") for item in results_list[:3] if isinstance(item, dict)
                                                )
                                            else:
                                                kb_context = kb_result.get("result", "") or kb_result.get("content", "")
                                        elif isinstance(kb_result, str):
                                            kb_context = kb_result
                                        
                                        if kb_context:
                                            # Build a compact candidate table
                                            def _fmt_cand(i, s):
                                                sf = s.get('struct_features') or {}
                                                helix_pct = f"{sf.get('helix_fraction',0)*100:.0f}%" if sf else 'N/A'
                                                plddt_v   = f"{sf.get('mean_plddt',0):.2f}" if sf else 'N/A'
                                                rg_v      = f"{sf.get('rg',0):.1f}Å" if sf else 'N/A'
                                                comp_v    = s.get('composite_score')
                                                comp_s    = f"{comp_v:.4f}" if comp_v is not None else 'N/A'
                                                return (
                                                    f"  - Rank {i+1}: {s['sequence']} "
                                                    f"| MIC: {s.get('mic_pred','N/A')} μM "
                                                    f"| Hemo: {s.get('hemolysis_pred') or s.get('hemolysis_score','N/A')} "
                                                    f"| CPP: {s.get('cpp_pred','N/A')} "
                                                    f"| α-Helix: {helix_pct} | pLDDT: {plddt_v} | Rg: {rg_v} "
                                                    f"| CompositeScore: {comp_s}"
                                                )
                                            cand_table = "\n".join(
                                                _fmt_cand(i, s) for i, s in enumerate(sequences)
                                            )
                                            
                                            lang_instr = "请用中文回答。" if user_lang == 'zh' else "Please respond in English."
                                            summary_prompt = f"""{lang_instr}

You are an AMP expert assistant. Below are results from a structure-based deep learning pipeline that designed {len(sequences)} antimicrobial peptide (AMP) candidates targeting **{target_str}** bacteria using **{generator_display}** generator.

**Pipeline Used**: ESMFold (3D structure prediction) → PGAT-ABPp (structure-based discrimination) → MIC/Hemolysis/CPP evaluation
**Generator**: {generator_display}
**All candidates passed PGAT-ABPp structure discrimination (score ≥ threshold)**

All candidates:
{cand_table}

**Literature context (from knowledge base):**
{kb_context[:2000]}

---

Write a **concise, well-structured scientific commentary** with these sections (use `###` headers and bullet points):

### 🧬 Design Rationale
*(2-3 bullets: explain key sequence features — charge distribution, length, hydrophobicity — of top candidates and how they drive activity against {target_str}. Reference literature context.)*

### 🏗️ Secondary & Tertiary Structure Analysis
*(2-3 bullets: analyze the α-helix fractions, pLDDT confidence, and Rg compactness from the candidate table. Highlight which candidates have the highest helix content and what this means for membrane disruption. Note KKKPVKRILRWIR-type sequences with 0% helix if present.)*

### ⚖️ Activity–Safety Trade-off
*(2 bullets: interpret MIC vs Hemolysis vs CPP trade-offs. State which candidate has the best (lowest) Composite Score and why it ranks first despite any weaknesses. IMPORTANT: CPP (Cell-Penetrating Peptide score) is LOWER = SAFER — a high CPP value indicates higher mammalian cell penetration risk and cytotoxicity, which is UNDESIRABLE. Never describe high CPP as an advantage.)*

### 🔬 Next Steps
*(2 bullets: specific wet-lab validation recommendations)*

**CRITICAL RULES**:
- Only mention **{generator_display}** as the generator. Do NOT mention other generators.
- Hemolysis values are decimal fractions (0–1), NOT percentages. Use decimal format only.
- α-Helix fractions are percentages (e.g. 91% means highly helical). Interpret their biological significance.
- Composite Score is lower = better. Rank #1 has the lowest composite score.
- CPP score: LOWER is SAFER (lower cell penetration = less cytotoxicity risk). A candidate with high CPP is penalized in the composite score.
- If Rank #1 has a high CPP, explicitly note it as a safety concern and explain it ranks first due to superior MIC activity.
- Keep each section tight — 2-3 bullets max. No verbose preambles.
"""
                                            yield "\n\n---\n### 📚 Analysis & Recommendations\n\n"
                                            summary_response = self.client.chat.completions.create(
                                                model=self.model,
                                                messages=[
                                                    {"role": "system", "content": f"You are an expert in antimicrobial peptide science. Always respond using the exact Markdown section structure specified in the prompt. Generator used is {generator_display}. Hemolysis values are decimal fractions (0-1), never percentages. Do NOT mention other generators."},
                                                    {"role": "user", "content": summary_prompt}
                                                ],
                                                stream=True,
                                                temperature=0.3,
                                                max_tokens=600
                                            )
                                            for chunk in summary_response:
                                                delta = chunk.choices[0].delta.content if chunk.choices[0].delta.content else ""
                                                if delta:
                                                    yield delta
                                            yield "\n"
                                    except Exception as e:
                                        logger.warning(f"⚠️ Structure pipeline summary generation failed: {e}")
                                    
                                    tool_output = f"Structure discrimination pipeline completed: {len(sequences)} candidates found. Summary generated above."
                                    # Force return to prevent LLM from producing free-form summary text
                                    return
                                else:
                                    yield f"⚠️ No candidates passed the pipeline filters.\n"
                                    tool_output = "Pipeline completed but no candidates met the criteria"
                            else:
                                # Show the error
                                errors = result.get("errors", [])
                                yield f"\n❌ **Pipeline Failed:**\n"
                                for err in errors:
                                    yield f"- {err}\n"
                                tool_output = f"Pipeline failed: {result.get('summary', 'Unknown error')}"
                                
                                # CRITICAL: record PGAT failure count
                                self._pgat_failure_count += 1
                                logger.warning(f"🔥 PGAT failure count: {self._pgat_failure_count}")
                                
                                # CRITICAL: when the failure threshold is reached, force fallback to the default pipeline and exit the ReAct loop
                                if self._pgat_failure_count >= 2:
                                    logger.info("🔥 PGAT failure threshold reached, forcing fallback to design_new_amps")
                                    
                                    # Reset the failure counter
                                    self._pgat_failure_count = 0

                                    # Force call design_new_amps (with the four-step pipeline and summary)
                                    results_capture = []
                                    for chunk in self._handle_design_pipeline(args, results_capture):
                                        yield chunk
                                    
                                    if results_capture:
                                        seq_list = ", ".join([item['sequence'] for item in results_capture])
                                        tool_output = f"Success (Fallback). Generated {len(results_capture)} sequences: {seq_list}"
                                        
                                        # Write the result into conversation history so the LLM knows the task is complete
                                        self.conversation_history.append({
                                            "role": "assistant",
                                            "content": f"✅ Task completed using standard pipeline (PGAT-ABPp unavailable). Generated {len(results_capture)} AMP candidates."
                                        })
                                    else:
                                        tool_output = "Task failed."
                                    
                                    # Return directly to stop the ReAct loop
                                    return
                        elif fn_name == "generate_sequences":
                            # Generate sequences only, no evaluation

                            # Critical fix: start the matching container based on the generator parameter
                            generator_param = args.get("generator", "default")
                            if self.orchestrator:
                                if "diverse" in generator_param.lower():
                                    self.orchestrator.start_tool("diff_amp")
                                elif "refine" in generator_param.lower():
                                    self.orchestrator.start_tool("hydramp")
                                else:
                                    self.orchestrator.start_tool("amp_designer")
                            
                            from tools import tool_generate_sequences_only
                            # 🔧 Use Auto-Debug retry mechanism
                            result = self._execute_tool_with_retry(
                                tool_generate_sequences_only,
                                "generate_sequences",
                                {
                                    "num_samples": args.get("num_samples", 3),
                                    "prompt": args.get("target", "Gram-negative"),
                                    "generator": generator_param
                                }
                            )
                            # Return the JSON-formatted sequence list
                            tool_output = json.dumps(result, ensure_ascii=False)
                            yield self.texts["generation_complete"].format(count=len(result))
                            # Cache seq -> generator mapping to prevent LLM from losing the generator field in evaluate_amp
                            for item in result:
                                if isinstance(item, dict) and item.get('sequence'):
                                    self._generated_sequences_cache[item['sequence']] = item.get('generator', 'Unknown')
                        elif fn_name == "evaluate_amp":
                            # Evaluate a sequence list
                            from tools import tool_batch_evaluate
                            sequences = args.get("sequences", [])

                            # Determine whether this is a comparison task (for downstream table generation)
                            current_input = getattr(self, 'current_user_input', '')
                            is_compare = current_input and ("对比" in current_input or "比较" in current_input or "compare" in current_input.lower())
                            
                            # Critical fix: restore generator field from cache (LLM may drop it or pass a plain string list)
                            repaired_sequences = []
                            for s in sequences:
                                if isinstance(s, str):
                                    # LLM passed a plain string, look up generator from cache
                                    repaired_sequences.append({
                                        "sequence": s,
                                        "generator": self._generated_sequences_cache.get(s, "Unknown")
                                    })
                                elif isinstance(s, dict):
                                    seq_str = s.get("sequence", "")
                                    gen = s.get("generator") or self._generated_sequences_cache.get(seq_str, "Unknown")
                                    repaired_sequences.append({**s, "generator": gen})
                                else:
                                    repaired_sequences.append(s)
                            sequences = repaired_sequences
                            
                            # DEBUG: log input data
                            logger.info(f"🔍 evaluate_amp input: {len(sequences)} sequences")
                            if len(sequences) > 0:
                                logger.info(f"   first: {sequences[0]}")
                            
                            # 🔧 Use Auto-Debug retry mechanism
                            result = self._execute_tool_with_retry(
                                tool_batch_evaluate,
                                "evaluate_amp",
                                {"sequences": sequences}
                            )
                            
                            # DEBUG: log output data
                            logger.info(f"🔍 evaluate_amp output: {len(result)} entries")
                            if len(result) > 0:
                                logger.info(f"   first result: {result[0]}")
                                if 'mic_value' in result[0]:
                                    logger.info(f"   ✅ MIC value: {result[0].get('mic_value')}")
                                else:
                                    logger.warning(f"   ❌ missing mic_value in result[0]!")
                            
                            # Critical fix: save to global_df for downstream use.
                            # If result is non-empty, append to global_df instead of overwriting.
                            if result:
                                new_df = pd.DataFrame(result)
                                if self.global_df is None or self.global_df.empty:
                                    self.global_df = new_df
                                else:
                                    # Append new data without overwriting
                                    self.global_df = pd.concat([self.global_df, new_df], ignore_index=True)
                                    # Deduplicate on the `sequence` field
                                    self.global_df = self.global_df.drop_duplicates(subset=['sequence'], keep='last')

                                # Auto-save to database
                                self._save_to_database(result, session_id="default")

                                # Save to feedback history for closed-loop optimization
                                try:
                                    # Invoke backend's add_evaluation_to_history.
                                    # Note: this needs to reach backend through some mechanism.
                                    # Simplest: return the result so backend can handle it.
                                    # Alternative: Agent calls app's function directly (if available).
                                    logger.info(f"🔁 Evaluation complete, {len(result)} sequences ready for feedback loop")
                                except Exception as e:
                                    logger.warning(f"⚠️ Failed to save feedback: {e}")
                            else:
                                logger.warning("⚠️ evaluate_amp returned empty, skipping save")

                            # Return the JSON-formatted evaluation result
                            tool_output = json.dumps(result, ensure_ascii=False)
                            # Only emit "evaluation complete" when there is real evaluation data, avoiding a misleading "0 sequences"
                            if len(result) > 0:
                                yield self.texts["evaluation_complete"].format(count=len(result))
                            else:
                                # For empty results, only log; do not repeat "0 sequences" on the frontend
                                logger.info("⚠️ evaluate_amp completed with 0 sequences; no user-facing summary emitted.")
                                                        
                            # Auto-trigger visualization after evaluation (if multiple generators exist)
                            # Fix: only trigger when the user explicitly asked to compare
                            current_input = getattr(self, 'current_user_input', '')
                            is_compare = bool(current_input and ("对比" in current_input or "比较" in current_input or "compare" in current_input.lower()))
                            if is_compare:
                                generators_used = set(item.get('generator', 'Unknown') for item in result)
                                logger.info(f"🎯 Detected {len(generators_used)} generators: {generators_used}")
                                # Save current comparison data for rank_sequences (avoid mixing with historical data)
                                if len(generators_used) >= 2:
                                    self._last_compare_result = result
                                    logger.info(f"📦 Saved current comparison data: {len(result)} entries")
                            
                                # Prevent duplicate generation
                                if len(generators_used) >= 2 and not self.visualization_generated:
                                    self.visualization_generated = True  # Set the flag
                                    logger.info("📊 Starting generator comparison visualization...")
                                    try:
                                        from tools import tool_visualize_generator_comparison
                                        yield "\n### 📊 Generator Comparison Visualization\n"
                                        viz_result = tool_visualize_generator_comparison(result)
                                        
                                        if viz_result.get('status') == 'success':
                                            charts = viz_result.get('charts', {})
                                            # Compatible with new (single dashboard) and legacy (5 sub-charts) layouts
                                            if 'dashboard' in charts:
                                                yield self.texts["viz_radar"]
                                                yield {"type": "plotly_html", "content": charts['dashboard']}
                                            else:
                                                yield self.texts["viz_radar"]
                                                yield {"type": "plotly_html", "content": charts['radar']}
                                                yield self.texts["viz_success_rate"]
                                                yield {"type": "plotly_html", "content": charts['success_rate']}
                                                yield self.texts["viz_mic_dist"]
                                                yield {"type": "plotly_html", "content": charts['mic_box']}
                                                yield self.texts["viz_mic_scatter"]
                                                yield {"type": "plotly_html", "content": charts['scatter']}
                                                yield self.texts["viz_heatmap"]
                                                yield {"type": "plotly_html", "content": charts['heatmap']}
                                            
                                            yield "\n" + self.texts["visualization_complete"].format(
                                                message=viz_result.get('message', 'Visualization completed')
                                            ) + "\n"
                                            logger.info("✅ Visualization charts generated")
                                        else:
                                            logger.warning(f"⚠️ Generator comparison visualization failed: {viz_result.get('error')}")
                                    except Exception as e:
                                        logger.error(f"⚠️ Generator comparison visualization failed: {e}")
                                        import traceback
                                        traceback.print_exc()
                            
                            # Comparison task evaluation complete: stop LLM from triggering unrelated tools
                            if is_compare:
                                tool_output = f"Evaluation completed for {len(result)} sequences from {len(generators_used)} generators. DO NOT call visualize_peptide_structure, analyze_sequence, or any other tool. Comparison tables and charts are already rendered. Proceed directly to rank_sequences."
                        
                        elif fn_name == "rank_sequences":
                            # Ranking + automatic visualization
                            from tools import tool_rank_sequences
                            
                            # For comparison tasks, prefer the currently generated sequences to avoid mixing full history
                            current_input = getattr(self, 'current_user_input', '')
                            is_compare = current_input and ("对比" in current_input or "比较" in current_input or "compare" in current_input.lower())
                            last_compare = getattr(self, '_last_compare_result', None)
                            
                            if is_compare and last_compare:
                                rank_source = last_compare
                                logger.info(f"🎯 Comparison task: using current comparison data ({len(rank_source)} entries) instead of full historical data")
                            elif self.global_df is None or self.global_df.empty:
                                yield self.texts["no_eval_data"]
                                tool_output = "Error: No evaluated data available"
                                continue
                            else:
                                rank_source = self.global_df.to_dict('records')
                            
                            strategy = args.get("strategy", "pareto")
                            # 🔧 Use Auto-Debug retry mechanism
                            result = self._execute_tool_with_retry(
                                tool_rank_sequences,
                                "rank_sequences",
                                {
                                    "evaluated_data": rank_source,
                                    "strategy": strategy,
                                    "keep_all_generators": bool(is_compare)  # In comparison mode, keep sequences from all generators
                                }
                            )
                            
                            # Emit ranking result
                            if is_compare:
                                tool_output = "[COMPARE_TASK_DONE]"
                                if not result:
                                    yield self.texts["task_complete"]
                                    _task_done = True
                                    break
                            else:
                                tool_output = json.dumps(result, ensure_ascii=False)

                            # Comparison task: directly emit a code-driven HTML table (independent of LLM, 100% formatting control)
                            if is_compare and result:
                                try:
                                    # Build grouped statistics table
                                    from collections import defaultdict
                                    group_stats = defaultdict(lambda: {"mic": [], "hemo": [], "cpp": [], "amp": [], "count": 0})
                                    for item in result:
                                        g = item.get("generator", "Unknown")
                                        mic = item.get("mic_value")
                                        hemo = item.get("hemolysis_score")
                                        cpp = item.get("cpp_score")
                                        amp = item.get("amp_score")
                                        if mic is not None: group_stats[g]["mic"].append(float(mic))
                                        if hemo is not None: group_stats[g]["hemo"].append(float(hemo))
                                        if cpp is not None: group_stats[g]["cpp"].append(float(cpp))
                                        if amp is not None: group_stats[g]["amp"].append(float(amp))
                                        group_stats[g]["count"] += 1

                                    def avg(lst): return round(sum(lst)/len(lst), 3) if lst else "N/A"

                                    # Statistics table HTML
                                    stat_rows = ""
                                    for g, s in group_stats.items():
                                        amp_ok = sum(1 for v in s["amp"] if v >= 0.5)
                                        rate = f"{amp_ok}/{s['count']} ({100*amp_ok//s['count']}%)" if s['count'] > 0 else "N/A"
                                        stat_rows += f"<tr><td><b>{g}</b></td><td>{avg(s['mic'])}</td><td>{avg(s['hemo'])}</td><td>{avg(s['cpp'])}</td><td>{rate}</td></tr>"

                                    stat_html = f"""<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;width:100%;margin:8px 0'>
<thead><tr style='background:#f0f4ff'><th>Generator</th><th>Avg MIC (μM)</th><th>Avg Hemolysis</th><th>Avg CPP</th><th>Valid AMP Rate</th></tr></thead>
<tbody>{stat_rows}</tbody></table>"""

                                    # Detailed sequence table HTML
                                    detail_rows = ""
                                    for i, item in enumerate(result):
                                        star = "⭐" if item.get("is_pareto_optimal") else ""
                                        mic = round(float(item["mic_value"]), 2) if item.get("mic_value") is not None else "N/A"
                                        hemo = round(float(item["hemolysis_score"]), 3) if item.get("hemolysis_score") is not None else "N/A"
                                        cpp = round(float(item["cpp_score"]), 3) if item.get("cpp_score") is not None else "N/A"
                                        amp = round(float(item["amp_score"]), 3) if item.get("amp_score") is not None else "N/A"
                                        detail_rows += f"<tr><td>{i+1}{star}</td><td>{item.get('generator','?')}</td><td><code>{item.get('sequence','')}</code></td><td>{mic}</td><td>{hemo}</td><td>{cpp}</td><td>{amp}</td></tr>"

                                    detail_html = f"""<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;width:100%;margin:8px 0'>
<thead><tr style='background:#f0f4ff'><th>Rank</th><th>Generator</th><th>Sequence</th><th>MIC (μM)</th><th>Hemolysis</th><th>CPP</th><th>AMP Prob</th></tr></thead>
<tbody>{detail_rows}</tbody></table>"""

                                    yield "\n### 📊 Generator Comparison Statistics\n"
                                    yield {"type": "html_table", "content": stat_html}
                                    yield "\n### 📋 Detailed Sequence Comparison\n"
                                    yield {"type": "html_table", "content": detail_html}
                                except Exception as e:
                                    logger.warning(f"⚠️ Comparison table generation failed: {e}")
                                
                                # Comparison visualization (avoid duplicate generation)
                                generators_used = set(item.get('generator', 'Unknown') for item in result)
                                if len(generators_used) >= 2 and not self.visualization_generated:
                                    self.visualization_generated = True
                                    logger.info("📊 Starting generator comparison visualization...")
                                    try:
                                        from tools import tool_visualize_generator_comparison
                                        yield "\n### 📊 Generator Comparison Visualization\n"
                                        viz_result = tool_visualize_generator_comparison(result)
                                        
                                        if viz_result.get('status') == 'success':
                                            charts = viz_result.get('charts', {})
                                            # Compatible with new (single dashboard) and legacy (5 sub-charts) layouts
                                            if 'dashboard' in charts:
                                                yield self.texts["viz_radar"]
                                                yield {"type": "plotly_html", "content": charts['dashboard']}
                                            else:
                                                yield self.texts["viz_radar"]
                                                yield {"type": "plotly_html", "content": charts['radar']}
                                                yield self.texts["viz_success_rate"]
                                                yield {"type": "plotly_html", "content": charts['success_rate']}
                                                yield self.texts["viz_mic_dist"]
                                                yield {"type": "plotly_html", "content": charts['mic_box']}
                                                yield self.texts["viz_mic_scatter"]
                                                yield {"type": "plotly_html", "content": charts['scatter']}
                                                yield self.texts["viz_heatmap"]
                                                yield {"type": "plotly_html", "content": charts['heatmap']}
                                            yield "\n" + self.texts["visualization_complete"].format(
                                                message=viz_result.get('message', 'Visualization completed')
                                            ) + "\n"
                                            logger.info("✅ Visualization charts generated")
                                        else:
                                            logger.warning(f"⚠️ Generator comparison visualization failed: {viz_result.get('error')}")
                                    except Exception as e:
                                        logger.error(f"⚠️ Generator comparison visualization failed: {e}")
                                        import traceback
                                        traceback.print_exc()
                                
                            # Comparison task fully complete: write tool response to history first, then request LLM for a textual summary, then break
                                if tool_id:
                                    self.conversation_history.append({
                                        "role": "tool",
                                        "tool_call_id": tool_id,
                                        "name": fn_name,
                                        "content": "[COMPARE_TASK_DONE] All tables and charts have been rendered."
                                    })
                                try:
                                    # Clean history: remove assistant messages with tool_calls that have no matching tool response
                                    def _clean_history_for_summary(messages):
                                        # Collect all responded tool_call_ids
                                        responded_ids = set()
                                        for m in messages:
                                            if m.get("role") == "tool" and m.get("tool_call_id"):
                                                responded_ids.add(m["tool_call_id"])
                                        cleaned = []
                                        for m in messages:
                                            if m.get("role") == "assistant" and m.get("tool_calls"):
                                                # Check whether every tool_call has a response
                                                all_responded = True
                                                for tc in m["tool_calls"]:
                                                    # Handle both dict and ChatCompletionMessageToolCall objects
                                                    tc_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
                                                    if tc_id is None or tc_id not in responded_ids:
                                                        all_responded = False
                                                        break
                                                if not all_responded:
                                                    continue  # Skip orphan assistant messages
                                            cleaned.append(m)
                                        return cleaned
                                    
                                    summary_messages = _clean_history_for_summary(self.conversation_history[-12:])
                                    summary_resp = self.client.chat.completions.create(
                                        model=self.model,
                                        messages=[
                                            *summary_messages,
                                            {
                                                "role": "user",
                                                "content": (
                                                    "Please write a concise expert summary in English (no tools):\n"
                                                    "1. Performance comparison of generators (MIC, hemolysis, CPP, AMP probability)\n"
                                                    "2. Which generator performs best and why\n"
                                                    "3. Key advantages of the top-ranked sequence\n"
                                                    "Do not repeat tables."
                                                )
                                            }
                                        ],
                                        stream=False,
                                        max_tokens=600,
                                    )
                                    summary_text = summary_resp.choices[0].message.content or ""
                                    if summary_text.strip():
                                        yield f"{summary_text}\n\n"
                                except Exception as e:
                                    logger.warning(f"Summary generation failed: {e}")
                                yield self.texts["task_complete"]
                                _task_done = True
                                break
                        else:
                            tool_result = None
                            for chunk in self._execute_tool_react(fn_name, args):
                                yield chunk
                                # Capture the returned result
                                if isinstance(chunk, str) and "✅ 结果:" in chunk:
                                    tool_output = chunk
                                    tool_result = chunk
                                    
                            # If no output yet but there is a return value, use it
                            if not tool_output:
                                tool_output = "Completed"
        
                        # Critical fix: ensure every tool_call with a valid tool_call_id has a response message
                        # Only append role="tool" when a valid tool_id (actually returned by the model) exists, to avoid context mismatch
                        if tool_id:
                            self.conversation_history.append({
                                "role": "tool",
                                "tool_call_id": tool_id,
                                "name": fn_name,
                                "content": str(tool_output) if tool_output else "Completed"
                            })
                            logger.info(f"✅ [Tool Response] Appended tool message for {fn_name} with id={tool_id}")
                        else:
                            # When there is no id, log a warning but do not abort the flow.
                            # This typically happens with manually parsed <tools>{...}</tools> pseudo-calls.
                            logger.warning(f"⚠️ [Tool Response] Skipping tool message for {fn_name} (no tool_id found). This may cause Qwen 400 error if it was a real tool_call.")
                            # To avoid a 400, forcibly append an assistant message as a workaround
                            self.conversation_history.append({
                                "role": "assistant",
                                "content": f"Tool {fn_name} executed: {str(tool_output)[:100] if tool_output else 'Completed'}"
                            })
                            
                    # Tool execution complete, continue to the next loop so Qwen decides the next step
                    continue
        
            except Exception as e:
                logger.error(f"Agent Error: {e}")
                yield f"❌ System error: {str(e)}"
                break
        
        # Task finished: automatically stop heavy containers and restore default state
        if self.orchestrator:
            self.orchestrator.switch_to_default()

    # ================= 3. Core Pipelines =================

    # Key change: accept a result_container argument
    def _handle_design_pipeline(self, args: Dict, result_container: List = None) -> Generator:
        target = args.get("target", "Gram-negative")
        user_wanted_count = args.get("num_samples", 3)
        generation_count = user_wanted_count * 2 
        strategy = args.get("strategy", "pareto")
        generator = args.get("generator", "default")  # Retrieve the requested generator

        # generator routing: decided solely by args["generator"], never overridden by strategy.
        # strategy controls the ranking policy (pareto/diverse/refine), independent of generator choice.
        # generator is the generator selector (default=AMP-Designer, diverse=Diff-AMP, refine=HydrAMP).
        # If the LLM does not explicitly pass generator, keep "default" → AMP-Designer.
        if generator not in ("default", "diverse", "refine"):
            generator = "default"  # Fallback: invalid values fall back to AMP-Designer
        
        texts = self.texts

        yield texts["plan_title"].format(total=4)
        yield texts["plan_step"].format(num=1, desc="Design AMP candidates against {target}".format(target=target))
        yield texts["plan_step"].format(num=2, desc="Evaluate AMP-likeness, MIC, hemolysis and CPP properties")
        yield texts["plan_step"].format(num=3, desc="Rank candidates using multi-objective strategy: {strategy}".format(strategy=strategy))
        yield texts["plan_step"].format(num=4, desc="Predict 3D structure for the top-ranked sequence (auto-executed; skipped gracefully if ESMFold is unavailable)")

        yield f"🧪 **Task received: Design {user_wanted_count} potent AMPs against `{target}`...**\n"

        # === Orchestrator hook: pick the container to launch based on generator ===
        if self.orchestrator:
            if generator == "diverse":
                # Diff-AMP: started internally by _select_generator via orchestrator.start_tool("diff_amp").
                # Log only here to avoid redundant launches.
                logger.info("🎯 Orchestrator: Diff-AMP will be started on demand")
            elif generator == "refine":
                logger.info("🎯 Orchestrator: HydrAMP will be started on demand")
            else:
                # Default AMP-Designer is persistent; ensure it is running.
                self.orchestrator.start_tool("amp_designer")
        
        generator_display = {"diverse": "Diff-AMP", "refine": "HydrAMP", "default": "AMP-Designer"}.get(generator, "AMP-Designer")
        t0 = time.time()
        yield f"⏳ [1/4] Starting generator ({generator_display})..."
        raw_seqs = tool_generate_amp(num_samples=generation_count, prompt=target, generator=generator)  # Pass the correct generator argument
        
        eval_res = self.prm.evaluate("generate", {"num_samples": generation_count}, raw_seqs)
        if not eval_res["passed"]:
            # Generation quality too low, retry once
            yield "\n🔄 Generation quality insufficient, retrying..."
            raw_seqs = tool_generate_amp(num_samples=generation_count, prompt=target, generator=generator)  # Pass the correct generator argument
        
        if not raw_seqs:
            yield "\n❌ Generation failed: no sequences were returned. Please check generator services.\n"
            return
        yield f" ✅ (Got {len(raw_seqs)} seqs, {time.time()-t0:.1f}s)\n"
        
        t0 = time.time()
        yield f"⏳ [2/4] Multi-dimensional evaluation (MIC/Hemo/CPP/Macrel)..."
        evaluated = tool_batch_evaluate(raw_seqs)
        yield f" ✅ ({time.time()-t0:.1f}s)\n"
        
        yield f"⏳ [3/4] Intelligent ranking..."
        ranked = tool_rank_sequences(evaluated, strategy)
        if not ranked and evaluated: ranked = evaluated
        yield f" ✅\n"
        
        final_selection = ranked[:user_wanted_count]

        # Sanitize NaN/Inf to avoid JSON serialization failures and frontend stalls
        import math
        def _clean_nan(obj):
            if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
                return None
            if isinstance(obj, dict):
                return {k: _clean_nan(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_clean_nan(v) for v in obj]
            return obj
        final_selection = [_clean_nan(s) for s in final_selection]

        self.global_df = pd.DataFrame(final_selection)
        
        # Automatically persist results to the database
        self._save_to_database(final_selection, session_id="default")

        # Memory injection: only write the sequence field (lightweight) to avoid large-JSON stalls
        if result_container is not None and isinstance(result_container, list):
            result_container.extend([{"sequence": s["sequence"]} for s in final_selection if "sequence" in s])

        top_seq = final_selection[0]["sequence"] if final_selection else None
        if top_seq:
            yield f"⏳ [4/4] Predicting 3D structure for top-ranked sequence (ESMFold)..."
            struct = self._robust_predict_structure(top_seq)
            if struct and struct.get("pdb_content"):
                yield {"type": "pdb_data", "content": struct.get("pdb_content"), "sequence": top_seq}
                yield f" ✅ Structure predicted successfully\n"
            else:
                yield f" ⚠️ Structure prediction unavailable (ESMFold service not responding or not installed locally). The top sequence is still valid — structure visualization is an optional enhancement.\n"

        texts = self.texts

        # Task title
        yield texts["report_title"]

        # Basic info
        yield texts["report_target"].format(target=target) + "\n"
        yield texts["report_count"].format(count=len(final_selection)) + "\n"

        if final_selection:
            best = final_selection[0]
            yield texts["report_best"].format(sequence=best["sequence"]) + "\n"

            # Performance metrics
            yield texts["report_metrics"]
            yield texts["metric_mic"].format(value=self._safe_format(best.get('mic_value'), ".3f")) + "\n"
            yield texts["metric_amp"].format(value=self._safe_round(best.get('amp_score'))) + "\n"
            yield texts["metric_hemo"].format(value=self._safe_round(best.get('hemolysis_score'))) + "\n"
            yield texts["metric_cpp"].format(value=self._safe_round(best.get('cpp_score'))) + "\n"

            # Structure info
            yield texts["report_structure"]

            try:
                import streamlit as st
                st.session_state.sequence_library = {}
                for item in final_selection:
                    seq_key = item.get("sequence")
                    if seq_key:
                        st.session_state.sequence_library[seq_key] = item
                print(f"✅ [Asset Sync] Synced {len(final_selection)} records")
            except ImportError:
                pass

            # Detailed table
            df_data = []
            for idx, item in enumerate(final_selection):
                # Mark Pareto-front entries in the table
                pareto_mark = "⭐" if item.get("is_pareto_optimal") else ""
                df_data.append({
                    "Rank": idx + 1,
                    "Generator": item.get("generator", "Unknown"),  # Add generator column
                    "Pareto": pareto_mark,
                    "Sequence": item["sequence"],
                    "AMP Prob": self._safe_round(item.get('amp_score')),
                    "MIC (uM)": self._safe_format(item.get('mic_value'), ".3f"),
                    "Hemo Prob": self._safe_round(item.get('hemolysis_score')),
                    "CPP Prob": self._safe_round(item.get('cpp_score'))
                })

            df_final = pd.DataFrame(df_data)
            if not df_final.empty:
                yield texts["report_table"]
                yield df_final  # Emit the DataFrame directly; the frontend will render it
                yield "\n\n"

            # Visualization: 3D Pareto-front scatter plot
            try:
                from tools import visualize_pareto_front
                html_plot = visualize_pareto_front(final_selection, strategy=strategy)
                yield {"type": "plotly_html", "content": html_plot}
            except Exception as e:
                logger.warning(f"⚠️ Pareto 3D visualization failed: {e}")
            
            # Pareto-front 2D scatter plot (better suited for publication figures)
            try:
                from tools import visualize_pareto_2d
                html_plot_2d = visualize_pareto_2d(final_selection, strategy=strategy, axis_x="mic", axis_y="hemolysis")
                yield {"type": "plotly_html", "content": html_plot_2d}
                
                # Provide an additional MIC-vs-CPP projection for multi-angle paper figures
                html_plot_2d_cpp = visualize_pareto_2d(final_selection, strategy=strategy, axis_x="mic", axis_y="cpp")
                yield {"type": "plotly_html", "content": html_plot_2d_cpp}
            except Exception as e:
                logger.warning(f"⚠️ Pareto 2D visualization failed: {e}")

            # Pareto-result narrative (bilingual)
            pareto_seqs = [s for s in final_selection if s.get("is_pareto_optimal")]
            non_pareto_seqs = [s for s in final_selection if not s.get("is_pareto_optimal")]
            yield "\n\n"
            lang = getattr(self, 'language', 'en')
            if lang == 'zh':
                yield f"**🎯 多目标优化结果解读：**\n\n"
                yield f"- **{len(pareto_seqs)} 条 Pareto 最优序列**（标注 ⭐）代表了 MIC 活性、溶血风险与 CPP 穿膜能力之间的最佳权衡——在不牺牲其他指标的前提下，任何单项指标均无法进一步提升。\n"
                if pareto_seqs:
                    best_pareto = pareto_seqs[0]
                    yield f"- **最优 Pareto 序列：** `{best_pareto['sequence']}` — MIC: {self._safe_format(best_pareto.get('mic_value'), '.3f')} μM，溶血风险: {self._safe_round(best_pareto.get('hemolysis_score'))}，CPP 能力: {self._safe_round(best_pareto.get('cpp_score'))}\n"
                if non_pareto_seqs:
                    yield f"- {len(non_pareto_seqs)} 条序列为**非支配序列**（至少存在一条 Pareto 序列在所有指标上均优于它）。\n"
                yield f"- **建议：** 优先对 ⭐ Pareto 最优序列进行实验验证，它们在预测效力与安全性之间具有最优平衡。\n\n"
            else:
                yield f"**🎯 Multi-Objective Optimization Summary:**\n\n"
                yield f"- **{len(pareto_seqs)} Pareto-optimal sequence(s)** (marked ⭐) represent the best trade-offs between MIC activity, hemolysis risk, and CPP capability — no single objective can be improved without sacrificing another.\n"
                if pareto_seqs:
                    best_pareto = pareto_seqs[0]
                    yield f"- **Top Pareto sequence:** `{best_pareto['sequence']}` — MIC: {self._safe_format(best_pareto.get('mic_value'), '.3f')} μM, Hemolysis: {self._safe_round(best_pareto.get('hemolysis_score'))}, CPP: {self._safe_round(best_pareto.get('cpp_score'))}\n"
                if non_pareto_seqs:
                    yield f"- {len(non_pareto_seqs)} sequence(s) are **dominated** (at least one Pareto sequence outperforms them on all objectives simultaneously).\n"
                yield f"- **Recommendation:** Prioritize the ⭐ Pareto-optimal sequences for experimental validation, as they offer the best balance of predicted potency and safety.\n\n"
            
            # Three-generator comparison visualization (triggered when multiple generators are present)
            # Fix: only trigger when the user explicitly asks for a comparison
            current_input = getattr(self, 'current_user_input', '')
            if current_input and ("对比" in current_input or "比较" in current_input or "compare" in current_input.lower()):
                generators_used = set(item.get('generator', 'Unknown') for item in final_selection)
                if len(generators_used) >= 2:
                    try:
                        from tools import tool_visualize_generator_comparison
                        yield "\n### 📊 Generator Comparison Visualization\n"
                        viz_result = tool_visualize_generator_comparison(final_selection)
                        
                        if viz_result.get('status') == 'success':
                            charts = viz_result.get('charts', {})
                            
                            # 1. Radar chart - comprehensive performance comparison
                            yield "\n#### 🎯 Comprehensive Performance Radar\n"
                            yield {"type": "plotly_html", "content": charts['radar']}
                            
                            # 2. Success-rate bar chart
                            yield "\n#### 🏆 Valid-AMP Generation Success Rate\n"
                            yield {"type": "plotly_html", "content": charts['success_rate']}
                            
                            # 3. MIC distribution box plot
                            yield "\n#### 💊 MIC Activity Distribution\n"
                            yield {"type": "plotly_html", "content": charts['mic_box']}
                            
                            # 4. Scatter plot - MIC vs AMP probability
                            yield "\n#### 📈 MIC vs AMP Probability Scatter\n"
                            yield {"type": "plotly_html", "content": charts['scatter']}
                            
                            # 5. Quality score heatmap
                            yield "\n#### 🌡️ Quality Score Heatmap\n"
                            yield {"type": "plotly_html", "content": charts['heatmap']}
                            
                            yield "\n✅ " + viz_result.get('message', 'Visualization completed') + "\n"
                        else:
                            logger.warning(f"⚠️ Generator comparison visualization failed: {viz_result.get('error')}")
                            
                    except Exception as e:
                        logger.warning(f"⚠️ Generator comparison visualization failed: {e}")

        # ====== Knowledge-base-driven comprehensive summary (full format) ======
        try:
            best_seq = final_selection[0]["sequence"] if final_selection else ""
            best_mic = self._safe_format(final_selection[0].get('mic_value'), ".2f") if final_selection else "N/A"
            best_hemo = self._safe_round(final_selection[0].get('hemolysis_score')) if final_selection else "N/A"
            best_cpp  = self._safe_round(final_selection[0].get('cpp_score')) if final_selection else "N/A"
            best_amp  = self._safe_round(final_selection[0].get('amp_score')) if final_selection else "N/A"
            pareto_count = len([s for s in final_selection if s.get("is_pareto_optimal")])
            user_lang = getattr(self, 'language', 'en')

            # Query the knowledge base for background on this target
            from tools import tool_search_knowledge
            kb_result = tool_search_knowledge(
                query=f"antimicrobial peptide mechanism activity design principles against {target}",
                knowledge_type="literature"
            )

            # Extract knowledge-base content
            kb_context = ""
            if isinstance(kb_result, dict):
                results_list = kb_result.get("results", [])
                if results_list:
                    kb_context = "\n\n".join(
                        item.get("content", "") for item in results_list[:3] if isinstance(item, dict)
                    )
                else:
                    kb_context = kb_result.get("result", "") or kb_result.get("content", "")
            elif isinstance(kb_result, str):
                kb_context = kb_result

            if kb_context:
                # Build a compact candidate-sequence table
                cand_table = "\n".join(
                    f"  - Rank {i+1}: {s['sequence']} | MIC: {self._safe_format(s.get('mic_value'), '.2f')} μM "
                    f"| Hemo: {self._safe_round(s.get('hemolysis_score'))} "
                    f"| CPP: {self._safe_round(s.get('cpp_score'))} "
                    f"| AMP: {self._safe_round(s.get('amp_score'))}"
                    f"{' ⭐Pareto' if s.get('is_pareto_optimal') else ''}"
                    for i, s in enumerate(final_selection)
                )
                
                # Retrieve the generator display name
                generator_used = final_selection[0].get('generator', 'AMP-Designer') if final_selection else 'AMP-Designer'

                lang_instr = "请用中文回答。" if user_lang == 'zh' else "Please respond in English."
                summary_prompt = f"""{lang_instr}

You are an AMP expert assistant. Below are results from a deep learning pipeline that designed {len(final_selection)} antimicrobial peptide (AMP) candidates targeting **{target}** bacteria using **{generator_used}**.

**Pipeline Results:**
- Candidates returned: {len(final_selection)} (screened from {len(final_selection)*2} generated)
- Pareto-optimal (⭐): {pareto_count} sequences
- Top candidate: `{best_seq}` — MIC {best_mic} μM | Hemolysis {best_hemo} | CPP {best_cpp} | AMP prob {best_amp}
- Generator used: **{generator_used}**

All candidates:
{cand_table}

**Literature context (from knowledge base):**
{kb_context[:2000]}

---

Write a **concise, well-structured assistant reply** (NOT a formal report) with the following sections using `###` headers and bullet points. Keep a natural, analytical tone — like an expert commenting on results:

### 🧬 Design Rationale
*(2-3 bullets: connect the top sequence features — charge, length, hydrophobicity, motifs — to the literature principles for {target}. State whether the predicted MIC aligns with benchmarks.)*

### ⚖️ Trade-offs & Pareto Analysis  
*(2-3 bullets: briefly interpret the Pareto front — what the ⭐ sequences represent, which offers best potency/safety balance, and what trade-off exists among the candidates.)*

### 🔬 Limitations & Next Steps
*(2-3 bullets: in-silico prediction caveats + specific wet-lab validation recommendations)*

Keep each section tight — no verbose preambles, no restating the task. Write as if continuing a conversation.
"""

                yield "\n\n---\n"
                yield texts.get("knowledge_summary_title", "### 📚 Analysis & Recommendations\n\n")

                # Stream the summary (token budget is large enough for the full format)
                summary_response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are an expert in antimicrobial peptide science. Always respond using the exact Markdown section structure specified in the prompt. Do not deviate from the requested format."},
                        {"role": "user", "content": summary_prompt}
                    ],
                    stream=True,
                    temperature=0.3,
                    max_tokens=800
                )
                for chunk in summary_response:
                    delta = chunk.choices[0].delta.content if chunk.choices[0].delta.content else ""
                    if delta:
                        yield delta

                yield "\n"
            else:
                logger.warning("⚠️ Knowledge-base query returned no results; skipping summary generation")

        except Exception as e:
            logger.warning(f"⚠️ Knowledge-base summary generation failed: {e}")

    # ================= 4. Robust Analysis Pipeline =================

    def _handle_analyze_pipeline(self, args: Dict) -> Generator:
        seqs = args.get("sequences", [])
        if not seqs and args.get("sequence"):
            seqs = [args.get("sequence")]
            
        texts = self.texts

        if not seqs:
            yield texts["generated_insufficient"].format(actual=0, target=1, time=0.0)
            return

        for seq in seqs:
            seq = seq.upper().strip()
            if len(seq) < 5:
                continue

            # 1. Physicochemical properties + basic evaluation
            # Prefer historical evaluation data from the DB / Sequence Assets to avoid redundant service calls.
            metrics_list = []
            if getattr(self, "db", None):
                try:
                    record = self.db.get_latest_sequence(seq)
                    if record and any(record.get(k) is not None for k in ["mic_value", "hemolysis_score", "cpp_score", "amp_score"]):
                        metrics_list = [record]
                        logger.info(f"✅ Reused historical metrics for sequence {seq} from database")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to reuse metrics from database for {seq}: {e}")

            if not metrics_list:
                # Fall back to a normal evaluation-tool call
                yield texts["step_evaluate"].format(current=2, end=2, total=3)
                metrics_list = tool_batch_evaluate([seq])

            if metrics_list:
                metrics = metrics_list[0]
                mic_str = self._safe_format(metrics.get('mic_value'))
                yield texts["generated"].format(count=1, time=0.0)
                yield f"MIC: {mic_str}\n"

                # 2. Structure prediction
                yield texts["step_structure"].format(current=3, total=3)
                t0 = time.time()
                struct = self._robust_predict_structure(seq)
                if struct and struct.get("pdb_content"):
                    pdb_content = struct.get("pdb_content")
                    yield {"type": "pdb_data", "content": pdb_content, "sequence": seq}
                    yield texts["structure_success"].format(time=time.time() - t0)

                    # Append: lightweight structure analysis on PDB coordinates (geometric approximation)
                    try:
                        from tools import tool_analyze_structure_basic
                        metrics3d = tool_analyze_structure_basic(pdb_content)
                    except Exception as e:
                        metrics3d = {"error": str(e)}
                        logger.warning(f"⚠️ tool_analyze_structure_basic failed: {e}")

                    if isinstance(metrics3d, dict) and not metrics3d.get("error"):
                        length = metrics3d.get("length")
                        helix_frac = metrics3d.get("helix_like_fraction")
                        rg = metrics3d.get("rg")
                        contact_density = metrics3d.get("contact_density")
                        kink_positions = metrics3d.get("kink_positions", [])

                        # Gracefully handle None / type issues
                        def _fmt(x):
                            return f"{x:.2f}" if isinstance(x, (int, float)) else str(x)

                        summary_line = (
                            f"Structure metrics (approx.): length={length}, "
                            f"helix_like_fraction≈{_fmt(helix_frac)}, "
                            f"Rg≈{_fmt(rg)} Å, "
                            f"contact_density≈{_fmt(contact_density)}, "
                            f"kink_positions={kink_positions}\n"
                        )
                        yield summary_line
                    else:
                        logger.info(f"\u2139\ufe0f Structure metrics not available: {metrics3d.get('error') if isinstance(metrics3d, dict) else metrics3d}")
                else:
                    yield texts["structure_failed"]

                # === LLM scientific interpretation ===
                try:
                    mic_str   = self._safe_format(metrics.get('mic_value'))
                    hemo_str  = self._safe_format(metrics.get('hemolysis_score'))
                    cpp_str   = self._safe_format(metrics.get('cpp_score'))
                    amp_str   = self._safe_format(metrics.get('amp_score'))
                    user_lang = getattr(self, '_last_user_lang', 'en')
                    lang_instr = "\u8bf7\u7528\u4e2d\u6587\u56de\u7b54\u3002" if user_lang == 'zh' else "Please respond in English."
                    analyze_prompt = f"""{lang_instr}

You are an AMP expert. Below is a single peptide sequence with its evaluation metrics:

Sequence : {seq}
AMP prob : {amp_str}
MIC      : {mic_str} \u03bcM
Hemolysis: {hemo_str}
CPP score: {cpp_str}
"""
                    if isinstance(metrics3d, dict) and not metrics3d.get('error'):
                        hf = metrics3d.get('helix_like_fraction')
                        rg_v = metrics3d.get('rg')
                        cd_v = metrics3d.get('contact_density')
                        kp   = metrics3d.get('kink_positions', [])
                        analyze_prompt += f"3D structure (approx):\n  helix_like_fraction : {hf:.2f}\n  Rg : {rg_v:.2f} \u00c5\n  contact_density : {cd_v:.2f}\n  kink_positions : {kp}\n"
                    analyze_prompt += """
---
Write a concise scientific commentary (4 short sections, use ### headers):

### \U0001f9ec Sequence Features
*(1-2 bullets: net charge, hydrophobicity pattern, amphipathicity potential)*

### \U0001f3d7\ufe0f Secondary Structure
*(1-2 bullets: helical content, compactness, any kinks and their implications)*

### \u2696\ufe0f Activity vs Safety
*(1-2 bullets: interpret MIC, hemolysis, CPP trade-off)*

### \U0001f52c Suggested Next Steps
*(1-2 bullets: specific improvements or experiments; if hemolysis>0.35 or MIC>16, suggest mutate_sequence tool)*

Rules: each section max 2 bullets, be specific, no verbose preambles.
"""
                    yield "\n\n---\n### \U0001f4da Scientific Analysis\n\n"
                    analysis_resp = self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": "You are an antimicrobial peptide expert. Be concise and scientific."},
                            {"role": "user", "content": analyze_prompt}
                        ],
                        stream=True,
                        temperature=0.3,
                        max_tokens=500,
                    )
                    for chunk in analysis_resp:
                        delta = chunk.choices[0].delta.content if chunk.choices[0].delta.content else ""
                        if delta:
                            yield delta
                    yield "\n"
                except Exception as e:
                    logger.warning(f"\u26a0\ufe0f analyze LLM summary failed: {e}")
            else:
                yield "\u274c Basic analysis failed\n"

            yield "---\n"

            # ================================================================
            # Auto-chaining: if the user input also contains a mutate/optimize intent,
            # automatically trigger mutation after analysis completes.
            # ================================================================
            user_raw = getattr(self, 'current_user_input', '') or ''
            MUTATE_SIGNALS = [
                'mutate', 'mutation', 'optimize', 'optimise', 'improve', 'redesign',
                '突变', '优化', '改进', '改造', '提升', '重设计',
            ]
            wants_mutate = any(sig in user_raw.lower() for sig in MUTATE_SIGNALS)

            if wants_mutate and metrics_list:
                # ================================================================
                # Goal inference: honor explicit user intent first, then fall back to metric-based heuristics.
                # ================================================================
                goal = None

                # 1st priority: user explicitly stated the goal
                u = user_raw.lower()
                if any(s in u for s in ['hemolysis', 'toxicity', '溶血', '毒性', 'lytic', '安全性', 'safer', 'less toxic']):
                    goal = 'lower_hemolysis'
                elif any(s in u for s in ['mic', 'potency', 'activity', '活性', '效力', 'antibacterial', '抗菌', 'kill', '杀菌', 'minimum inhibitory']):
                    goal = 'lower_mic'
                elif any(s in u for s in ['balance', 'balanced', '平衡', '综合', '全面']):
                    goal = 'balanced'

                # 2nd priority: infer the weakest metric automatically
                if goal is None and metrics:
                    mic_v  = metrics.get('mic_value') or 99.0
                    hemo_v = metrics.get('hemolysis_score') or 0.0
                    cpp_v  = metrics.get('cpp_score') or 0.0

                    # Normalize to [0,1]; higher means worse
                    mic_bad  = min(mic_v / 64.0, 1.0)          # MIC > 64 is treated as the worst
                    hemo_bad = min(hemo_v, 1.0)                 # Hemolysis is already in 0~1
                    # Higher CPP is better, so flipping: low CPP counts as a weakness (not included in mutation goal)

                    # Anything above threshold is considered a weakness
                    MIC_THRESHOLD  = 0.25   # ~16 µM
                    HEMO_THRESHOLD = 0.35   # 35% hemolysis

                    mic_problem  = mic_bad  > MIC_THRESHOLD
                    hemo_problem = hemo_bad > HEMO_THRESHOLD

                    if mic_problem and hemo_problem:
                        # Pick whichever is more severe
                        goal = 'lower_hemolysis' if hemo_bad > mic_bad else 'lower_mic'
                    elif hemo_problem:
                        goal = 'lower_hemolysis'
                    elif mic_problem:
                        goal = 'lower_mic'
                    else:
                        goal = 'balanced'  # All metrics acceptable; perform overall optimization

                goal = goal or 'balanced'  # Final fallback

                # Report the inferred rationale to the user
                goal_reason = {
                    'lower_mic'      : '🎯 Goal: lower MIC (enhance antibacterial potency)',
                    'lower_hemolysis': '🛡️ Goal: lower hemolysis (improve safety)',
                    'balanced'       : '⚖️ Goal: balanced (activity + safety)',
                }.get(goal, goal)

                yield f"\n\n---\n### 🧬 Auto-chained Mutation Optimization\n\n{goal_reason}\n\n"
                mutate_args = {
                    'sequence': seq,
                    'goal': goal,
                    'target': args.get('target', 'Gram-negative'),
                    'num_variants': 3,
                }
                self._in_analyze_chain = True   # prevent mutate→analyze loop
                for chunk in self._handle_mutate_pipeline(mutate_args):
                    yield chunk
                self._in_analyze_chain = False

    def _handle_mutate_pipeline(self, args: Dict) -> Generator:
        """Handler for mutate_sequence tool calls.
        Generates rule-based mutant variants, re-evaluates them, and yields
        an LLM commentary comparing original vs best mutant.
        If the user also requested analysis ("analyze and mutate"), run analyze first.
        """
        from tools import tool_mutate_sequence

        seq    = args.get("sequence", "").upper().strip()
        target = args.get("target", "Gram-negative")
        goal   = args.get("goal", "balanced")
        n_var  = int(args.get("num_variants", 3))

        if not seq:
            yield "\u274c mutate_sequence: no sequence provided.\n"
            return

        # ── Auto-prepend analyze if user mentioned "analyze" but LLM skipped it ──
        # Use _in_mutate_from_analyze flag to prevent circular call (analyze→mutate→analyze)
        user_raw = getattr(self, 'current_user_input', '') or ''
        ANALYZE_SIGNALS = ['analyze', 'analysis', 'analyse', '分析']
        already_from_analyze = getattr(self, '_in_analyze_chain', False)
        if not already_from_analyze and any(sig in user_raw.lower() for sig in ANALYZE_SIGNALS):
            self._in_analyze_chain = True
            yield "\n### 🔬 Sequence Analysis\n"
            for chunk in self._handle_analyze_pipeline({"sequence": seq}):
                yield chunk
            yield "\n---\n"
            self._in_analyze_chain = False
            return  # analyze pipeline already auto-chains mutate at the end

        yield f"\U0001f9ec **Mutation Optimization** for `{seq}`  "
        yield f"Goal: **{goal}** | Target: **{target}** | Variants: **{n_var}**\n\n"

        try:
            result = tool_mutate_sequence(sequence=seq, target=target, goal=goal, num_variants=n_var)
        except Exception as e:
            yield f"\u274c tool_mutate_sequence failed: {e}\n"
            return

        if not result.get("success"):
            yield f"\u274c {result.get('error', 'Unknown error')}\n"
            return

        original = result["original"]
        variants = result["variants"]
        best     = result["best_variant"]
        improv   = result["improvement"]

        # ---- Render comparison HTML table ----
        def _row(label, r, highlight=False):
            def _fv(*keys):
                for k in keys:
                    v = r.get(k)
                    if v is not None: return v
                return 'N/A'
            mic_v  = _fv('mic_value', 'mic_pred')
            hemo_v = _fv('hemolysis_score', 'hemolysis_pred')
            cpp_v  = _fv('cpp_score', 'cpp_pred')
            comp_v = r.get('composite_score', 'N/A')
            mut    = r.get('mutation_description', '')
            bg = "background:#d4edda" if highlight else ""
            mic_s  = f"{mic_v:.2f}" if isinstance(mic_v, float) else str(mic_v)
            hemo_s = f"{hemo_v:.3f}" if isinstance(hemo_v, float) else str(hemo_v)
            cpp_s  = f"{cpp_v:.3f}" if isinstance(cpp_v, float) else str(cpp_v)
            comp_s = f"{comp_v:.4f}" if isinstance(comp_v, float) else str(comp_v)
            return (
                f"<tr style='{bg}'>"
                f"<td style='padding:4px 8px;font-family:monospace'>{r.get('sequence','')}</td>"
                f"<td style='padding:4px 8px;color:#666;font-size:11px'>{mut}</td>"
                f"<td style='padding:4px 8px;text-align:center'>{mic_s}</td>"
                f"<td style='padding:4px 8px;text-align:center'>{hemo_s}</td>"
                f"<td style='padding:4px 8px;text-align:center'>{cpp_s}</td>"
                f"<td style='padding:4px 8px;text-align:center;font-weight:bold'>{comp_s}</td>"
                f"</tr>"
            )

        table_html = (
            "<div style='margin:8px 0'>"
            "<b style='font-size:13px'>\U0001f4ca Mutation Comparison</b>"
            "<table style='border-collapse:collapse;font-size:12px;margin-top:6px;width:100%'>"
            "<thead><tr style='background:#f0f0f0'>"
            "<th style='padding:4px 8px;text-align:left'>Sequence</th>"
            "<th style='padding:4px 8px;text-align:left'>Mutation</th>"
            "<th style='padding:4px 8px'>MIC (\u03bcM)</th>"
            "<th style='padding:4px 8px'>Hemolysis</th>"
            "<th style='padding:4px 8px'>CPP</th>"
            "<th style='padding:4px 8px'>Composite\u2193</th>"
            "</tr></thead><tbody>"
        )
        table_html += _row("Original", original, highlight=False)
        for v in variants:
            is_best = v.get("sequence") == best.get("sequence")
            table_html += _row("Variant", v, highlight=is_best)
        table_html += "</tbody></table>"

        # Improvement summary bar
        # delta_comp = orig - best: positive = improvement (best has lower composite = better)
        delta_comp = improv.get('composite_score_delta', 0)
        delta_mic  = improv.get('mic_delta', 0)
        delta_hemo = improv.get('hemolysis_delta', 0)
        improved = delta_comp > 0
        color = "#28a745" if improved else "#dc3545"
        comp_label = f"improved by {abs(delta_comp):.4f}" if improved else f"worse by {abs(delta_comp):.4f}"
        mic_label  = f"MIC {'-' if delta_mic > 0 else '+'}{abs(delta_mic):.2f} μM ({'better' if delta_mic > 0 else 'worse'})"
        hemo_label = f"Hemo {'-' if delta_hemo > 0 else '+'}{abs(delta_hemo):.4f} ({'better' if delta_hemo > 0 else 'worse'})"
        table_html += (
            f"<div style='margin-top:6px;font-size:12px;color:{color}'>"
            f"Best variant vs original: composite {comp_label} | {mic_label} | {hemo_label}"
            f"</div></div>"
        )
        yield {"type": "html_table", "content": table_html}

        # ---- LLM commentary with RAG context ----
        try:
            user_lang  = getattr(self, '_last_user_lang', 'en')
            lang_instr = "\u8bf7\u7528\u4e2d\u6587\u56de\u7b54\u3002" if user_lang == 'zh' else "Please respond in English."

            def _fmt_seq(r):
                if not isinstance(r, dict): return f"  (invalid record: {r!r})\n"
                def _fv(*keys):
                    for k in keys:
                        v = r.get(k)
                        if v is not None: return v
                    return 'N/A'
                mic_v  = _fv('mic_value', 'mic_pred')
                hemo_v = _fv('hemolysis_score', 'hemolysis_pred')
                cpp_v  = _fv('cpp_score', 'cpp_pred')
                comp_v = r.get('composite_score', 'N/A')
                return (
                    f"  Seq: {r.get('sequence','')}\n"
                    f"  Mutation: {r.get('mutation_description','')}\n"
                    f"  MIC={mic_v}, Hemolysis={hemo_v}, CPP={cpp_v}, Composite={comp_v}\n"
                )

            # Build RAG knowledge context section
            rag_ctx = result.get('rag_context', {})
            db_ctx  = result.get('db_context', {})
            rag_section = ""
            if rag_ctx:
                vec_hits = rag_ctx.get('vector_hits', [])
                graph_mechs = rag_ctx.get('graph_mechs', [])
                graph_princ = rag_ctx.get('graph_principles', [])
                rag_summary = rag_ctx.get('summary', '')
                if vec_hits or graph_mechs or graph_princ or rag_summary:
                    parts = []
                    if rag_summary:
                        parts.append(f"RAG summary: {rag_summary[:300]}")
                    if graph_mechs:
                        parts.append(f"Relevant mechanisms: {', '.join(str(m) for m in graph_mechs[:3])}")
                    if graph_princ:
                        parts.append(f"Key principles: {', '.join(str(p) for p in graph_princ[:3])}")
                    if vec_hits:
                        lit_snippets = [
                            (h.get('content', '')[:100] if isinstance(h, dict) else str(h)[:100])
                            for h in vec_hits[:2]
                        ]
                        parts.append("Literature evidence:\n" + "\n".join(f"  - {s}" for s in lit_snippets))
                    rag_section = "\n\nKnowledge base context retrieved via Hybrid RAG:\n" + "\n".join(parts)

            db_section = ""
            if db_ctx.get('exact_match'):
                em = db_ctx['exact_match']
                db_section = (f"\n\nDatabase record for original sequence: "
                              f"MIC={em.get('mic_value','N/A')}, Hemolysis={em.get('hemolysis_score','N/A')}, "
                              f"CPP={em.get('cpp_score','N/A')}")
            elif db_ctx.get('similar_seqs'):
                db_section = f"\n\nDatabase: {len(db_ctx['similar_seqs'])} similar sequences found for reference."

            vars_text = "".join(_fmt_seq(v) for v in variants)
            mutate_prompt = f"""{lang_instr}

You are an AMP expert with access to literature knowledge and database context.
A RAG-enhanced mutation optimization was performed on the following peptide:

Original sequence: {seq}
{_fmt_seq(original)}

Generated variants (sorted by composite score, lower=better):
{vars_text}
Best variant: {best.get('sequence','')}
Improvement: composite_score_delta={delta_comp:+.4f}, MIC_delta={delta_mic:+.2f} \u03bcM, Hemolysis_delta={delta_hemo:+.4f}
{rag_section}{db_section}

---
Write a concise mutation analysis (3 sections, ### headers):

### \U0001f9ec Mutation Rationale
*(1-2 bullets: explain why the substitution(s) in the best variant should improve activity or safety, citing RAG knowledge if available)*

### \U0001f4c8 Performance Improvement
*(1-2 bullets: quantify the changes in MIC, hemolysis, CPP; highlight if the improvement is meaningful)*

### \U0001f52c Recommendation
*(1 bullet: recommend whether to proceed with the best variant or suggest a further round of optimization)*

Rules: be specific and quantitative, cite RAG evidence when relevant, max 2 bullets per section, no preambles.
"""
            yield "\n\n---\n### \U0001f9eb Mutation Analysis\n\n"
            mutate_resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an antimicrobial peptide design expert with access to literature and database knowledge. Be concise and quantitative."},
                    {"role": "user", "content": mutate_prompt}
                ],
                stream=True,
                temperature=0.3,
                max_tokens=600,
            )
            for chunk in mutate_resp:
                delta = chunk.choices[0].delta.content if chunk.choices[0].delta.content else ""
                if delta:
                    yield delta
            yield "\n"
        except Exception as e:
            logger.warning(f"\u26a0\ufe0f mutate LLM commentary failed: {e}")

    def _robust_predict_structure(self, seq):
        max_retries = 3
        for i in range(max_retries):
            wait_time = 2 if i == 0 else (i * 5)
            if i > 0: print(f"🔄 Structure-prediction retry {i}/{max_retries}...")
            time.sleep(wait_time)
            try:
                struct = tool_predict_structure(seq)
                if struct and struct.get("pdb_content"): return struct
            except Exception as e: print(f"❌ Attempt {i+1} exception: {e}")
        return None
    
    def _execute_tool_react(self, tool_name: str, params: Dict) -> Generator:
        # === Orchestrator hook: automatically wake up the tool container ===
        if self.orchestrator:
            self.orchestrator.start_tool(tool_name)
        # =====================================
        self._log("INFO", f"Generic invocation: {tool_name}")
    
        # Knowledge-type tools run silently and are not exposed in the user-facing stream
        SILENT_TOOLS = {"search_knowledge", "query_ontology", "query_mechanisms_for_target", "query_principles_for_mechanism"}
        is_silent = tool_name in SILENT_TOOLS

        if not is_silent:
            yield f"🔧 **Executing**: `{tool_name}`...\n"
        if tool_name == "rank_sequences" and self.global_df is not None:
            params["evaluated_data"] = self.global_df.to_dict('records')
        try:
            from tools import (
                tool_generate_sequences_only,
                tool_batch_evaluate, 
                tool_predict_structure, 
                tool_search_knowledge, 
                tool_rank_sequences,
                tool_visualize_peptide_structure,
                tool_query_mechanisms_for_target,
                tool_query_principles_for_mechanism,
                tool_query_ontology,
                tool_structure_discrimination_pipeline  # New
            )
            tool_map = {
                "generate_sequences": tool_generate_sequences_only,
                "evaluate_amp": tool_batch_evaluate,
                "predict_structure": tool_predict_structure,
                "search_knowledge": tool_search_knowledge,
                "rank_sequences": tool_rank_sequences,
                "visualize_peptide_structure": tool_visualize_peptide_structure,
                "query_mechanisms_for_target": tool_query_mechanisms_for_target,
                "query_principles_for_mechanism": tool_query_principles_for_mechanism,
                "query_ontology": tool_query_ontology,
                "structure_discrimination_pipeline": tool_structure_discrimination_pipeline  # New
            }
            if tool_name in tool_map:
                # Debug logging
                logger.info(f"Calling {tool_name} with params: {params}")
                
                # Validate required params for visualize_peptide_structure
                if tool_name == "visualize_peptide_structure":
                    if 'sequence' not in params or not params.get('sequence'):
                        error_msg = "Error: 'sequence' parameter is required and cannot be empty"
                        logger.error(error_msg + f". Received params: {params}")
                        yield f"❌ {error_msg}\n"
                        return error_msg
                
                res = tool_map[tool_name](**params)
                
                # Special handling for visualization tools
                if tool_name == "visualize_peptide_structure" and isinstance(res, dict):
                    # New layout: if the tool returned a `combined` field, render the merged canvas directly
                    if 'combined' in res:
                        yield "\n### 🧬 Peptide Structure Visualizations\n"
                        combined = res['combined']
                        import plotly.graph_objects as go
                        if isinstance(combined, go.Figure):
                            combined = combined.to_html(
                                include_plotlyjs='cdn',
                                config={'displayModeBar': False}
                            )
                        yield {"type": "plotly_html", "content": combined}
                        yield "\n✅ " + res.get('message', 'Generated Helical Wheel + Hydrophobicity Profile in a single canvas') + "\n"
                        return str(res.get('message', 'Visualization completed'))
                    
                    # Legacy compatibility: if only `wheel`/`hydro` fields are present
                    elif 'wheel' in res:
                        yield "\n### 🧬 Peptide Structure Visualizations\n"
                        
                        # 1. Helical Wheel
                        yield "\n#### 🧬 Helical Wheel Projection\n"
                        yield {"type": "plotly_html", "content": res['wheel']}
                        
                        # 2. Hydrophobicity Profile (only if available)
                        if 'hydro' in res:
                            yield "\n#### 🌊 Hydrophobicity Profile\n"
                            yield {"type": "plotly_html", "content": res['hydro']}
                        
                        # 3. (Optional) Radar chart has been deprecated in tool_visualize_peptide_structure
                        # If future versions reintroduce it, we display it only when the key exists
                        if 'radar' in res:
                            yield "\n#### 📊 Comprehensive Performance Radar\n"
                            yield {"type": "plotly_html", "content": res['radar']}
                        
                        yield "\n✅ " + res.get('message', 'Visualization completed') + "\n"
                        return str(res.get('message', 'Visualization completed'))
                    else:
                        yield f"✅ Result: {str(res)[:100]}...\n"
                        return str(res)
                else:
                    if not is_silent:
                        yield f"✅ Result: {str(res)[:100]}...\n"
                    return str(res)
            else: 
                yield f"❌ Unknown tool\n"
                return "Error: Unknown tool"
        except Exception as e: 
            yield f"❌ Error: {e}\n"
            return f"Error: {e}"

    def _df_to_markdown(self, df):
        if df.empty: return ""
        headers = df.columns.tolist()
        header_row = "| " + " | ".join(str(h) for h in headers) + " |"
        separator = "| " + " | ".join(["---"] * len(headers)) + " |"
        rows = []
        for _, row in df.iterrows():
            rows.append("| " + " | ".join(str(val) for val in row) + " |")
        return "\n".join([header_row, separator] + rows)
    
    # ==================== Database-Related Methods ====================
    
    def _restore_from_database(self):
        """Restore historical data from the database into global_df."""
        if not self.db:
            return
        
        try:
            # Load the most recent 500 sequences
            df = self.db.load_sequences(limit=500)
            if not df.empty:
                self.global_df = df
                logger.info(f"✅ Restored {len(df)} sequences from database")
            else:
                logger.info("ℹ️ No historical sequences found")
        except Exception as e:
            logger.error(f"❌ Failed to restore from database: {e}")
    
    def _save_to_database(self, sequences: List[Dict], session_id: str = "default"):
        """Persist sequences to the database."""
        if not self.db or not sequences:
            return
        
        try:
            count = self.db.save_sequences(sequences, session_id=session_id)
            logger.info(f"✅ Saved {count} sequences to database")
        except Exception as e:
            logger.error(f"❌ Failed to save to database: {e}")

    def _parse_manual_tool_call(self, content):
        match = re.search(r"<(tools|xml)>\s*({[\s\S]*?})\s*</\1>", content, re.IGNORECASE)
        if match:
            try: return [{"function": {"name": json.loads(match.group(2))["name"], "arguments": json.dumps(json.loads(match.group(2)).get("arguments", {}))}}]
            except: pass
        return None

    def _is_technical_task(self, text):
        TECHNICAL_KEYWORDS = [
            # Design / generation
            "设计", "design", "生成", "generate", "create", "amp", "mic",
            "结构", "structure", "分析", "analyze", "analyse",
            # Knowledge retrieval / mechanism (these must go through RAG tools, not simple replies)
            "mechanism", "mechanisms", "机制", "原理", "principle",
            "what", "how", "why", "explain", "which", "compare",
            "most effective", "effective", "efficacy", "activity",
            "gram-negative", "gram-positive", "bacteria", "pathogen",
            "hemolysis", "toxicity", "selectivity", "antimicrobial",
            "peptide", "sequence", "target",
        ]
        return any(k in text.lower() for k in TECHNICAL_KEYWORDS) and len(text) > 3

    def _safe_round(self, v): return round(v, 3) if isinstance(v, float) else v
    def _safe_format(self, v, f=".3f"): return f"{v:{f}}" if isinstance(v, float) else v
    
    def _log(self, level, msg):
        print(f"[{level}] {msg}", flush=True)
        if self.log_callback: self.log_callback({"level": level, "message": msg})