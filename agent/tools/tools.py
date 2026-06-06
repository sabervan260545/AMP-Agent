# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
AMP Platform Tools - Production Ready
======================================

Comprehensive toolkit for antimicrobial peptide (AMP) design, evaluation,
and analysis. This module provides:

- Multi-generator orchestration (AMP-Designer, Diff-AMP, HydrAMP)
- Batch evaluation with MIC, hemolysis, CPP, and Macrel predictions
- Pareto-optimal ranking for multi-objective optimization
- Structure prediction and discrimination pipelines
- Knowledge base and ontology query interfaces
- Visualization tools for comparative analysis

Author: AMP Platform Team
Version: Production 1.0
License: MIT
"""

import math
import json
import requests
import pandas as pd
import logging
import time
import sys
import os
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path
import plotly.graph_objects as go
import plotly.express as px
import plotly.io as pio
import numpy as np
from collections import Counter

logger = logging.getLogger(__name__)

# ==================== Module Imports with Fallbacks ====================

# Import DatabaseManager for ontology queries
try:
    sys.path.append('/data/amp-generator-platform/backend')
    from database import DatabaseManager  # type: ignore
    _ontology_db_manager = DatabaseManager()
    logger.info("✅ Ontology DatabaseManager initialized in tools")
except Exception as e:
    _ontology_db_manager = None
    logger.warning(f"⚠️ Ontology DatabaseManager not available in tools: {e}")

# Import knowledge search tool - use importlib to load directly from file, avoiding package path issues
search_knowledge = None
_sk_candidates = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'search_knowledge.py'),  # 同目录
    '/app/agent/tools/search_knowledge.py',
    '/data/amp-generator-platform/agent/tools/search_knowledge.py',
]
for _sk_path in _sk_candidates:
    if os.path.isfile(_sk_path):
        try:
            import importlib.util as _ilu
            _spec = _ilu.spec_from_file_location("search_knowledge_mod", _sk_path)
            _mod = _ilu.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
            search_knowledge = _mod.search_knowledge
            logger.info(f"✅ search_knowledge tool loaded: {_sk_path}")
            break
        except Exception as _e:
            logger.warning(f"⚠️ search_knowledge load failed ({_sk_path}): {_e}")
if search_knowledge is None:
    logger.warning("⚠️ search_knowledge tool not loaded: all paths failed")

# Import ToolOrchestrator for dynamic container management
try:
    from .tool_orchestrator import ToolOrchestrator
    _global_orchestrator = ToolOrchestrator()
    logger.info("✅ ToolOrchestrator initialized for dynamic generator switching")
except Exception:
    # Legacy fallback to top-level module
    try:
        from tool_orchestrator import ToolOrchestrator
        _global_orchestrator = ToolOrchestrator()
        logger.info("✅ ToolOrchestrator initialized (legacy top-level path)")
    except Exception as e:
        _global_orchestrator = None
        logger.warning(f"⚠️ ToolOrchestrator not available: {e}")

# ==================== Configuration Constants ====================

# Service endpoints for microservices architecture
SERVICES = {
    "GENERATOR": "http://generator:8001",      # AMP-Designer (default generator)
    "DIFF_AMP": "http://amp-diff-amp:8000",    # Diff-AMP (novel/diverse sequences)
    "HYDRAMP": "http://amp-hydramp:8000",      # HydrAMP (optimized sequences)
    "MIC": "http://amp-mic:8000",              # MIC prediction service
    "HEMOLYSIS": "http://amp-hemolysis:8000",  # Hemolysis prediction service
    "CPP": "http://amp-cpp:8000",              # CPP prediction service
    "STRUCTURE": "http://amp-structure:8000",  # ESMFold structure prediction
    "MACREL": "http://amp-macrel:8000",        # Macrel AMP classification
    "PGAT_ABPP": "http://amp-pgat-abpp:8000"   # PGAT-ABPp structure discrimination
}

# Generation configuration
MAX_BATCH_SIZE = 4  # Maximum sequences per batch to prevent OOM
DEFAULT_NUM_SAMPLES = 5
GENERATOR_RETRY_ATTEMPTS = 3
GENERATOR_TIMEOUT = 120  # seconds
BATCH_COOLDOWN = 1.5  # seconds between batches

# Evaluation configuration
EVALUATION_TIMEOUT = 600  # seconds
EVALUATION_COOLDOWN = 0.5  # seconds between requests
MACREL_AMP_THRESHOLD = 0.5  # AMP classification threshold

# Target organism mapping (supports Chinese and English)
TARGET_MAP = {
    "阴性": "Gram-negative",
    "negative": "Gram-negative",
    "gram-negative": "Gram-negative",
    "革兰氏阴性": "Gram-negative",
    "阳性": "Gram-positive",
    "positive": "Gram-positive",
    "gram-positive": "Gram-positive",
    "革兰氏阳性": "Gram-positive",
    "真菌": "Antifungal",
    "fungal": "Antifungal",
    "antifungal": "Antifungal",
    "病毒": "Antiviral",
    "viral": "Antiviral",
    "antiviral": "Antiviral",
    "癌": "Mammalian",
    "mammalian": "Mammalian",
    "哺乳动物": "Mammalian"
}

# ==================== Helper Functions ====================

def _normalize_target(prompt: str) -> str:
    """
    Normalize target organism name to standard format.
    
    Supports both Chinese and English input, converting to canonical
    English names used by generation services.
    
    Args:
        prompt: Target organism string (e.g., "阴性", "Gram-negative")
        
    Returns:
        Normalized target name
        
    Examples:
        >>> _normalize_target("阴性")
        'Gram-negative'
        >>> _normalize_target("gram-negative bacteria")
        'Gram-negative'
    """
    prompt_lower = prompt.lower()
    for key, value in TARGET_MAP.items():
        if key in prompt_lower:
            return value
    return prompt


def _validate_num_samples(num_samples: Any, default: int = DEFAULT_NUM_SAMPLES) -> int:
    """
    Validate and convert num_samples parameter to integer.
    
    Provides auto-debug capability by attempting type conversion
    and falling back to default value if conversion fails.
    
    Args:
        num_samples: Input value (int, str, or other)
        default: Default value if conversion fails
        
    Returns:
        Valid integer value
        
    Examples:
        >>> _validate_num_samples("5")
        5
        >>> _validate_num_samples("invalid")
        5  # falls back to default
    """
    if isinstance(num_samples, str):
        try:
            original_value = num_samples
            num_samples = int(num_samples)
            logger.info(f"🔧 Auto-converted num_samples: '{original_value}' -> {num_samples}")
            return num_samples
        except ValueError:
            logger.warning(f"⚠️ Invalid num_samples '{num_samples}', using default {default}")
            return default
    elif not isinstance(num_samples, int):
        logger.warning(f"⚠️ Invalid num_samples type {type(num_samples)}, using default {default}")
        return default
    return num_samples


def _select_generator(generator: str) -> Tuple[str, str, bool]:
    """
    Select appropriate generator service based on strategy.
    
    Args:
        generator: Generation strategy ('default'/'diverse'/'refine')
        
    Returns:
        Tuple of (generator_url, generator_name, use_hydramp_format)
        
    Examples:
        >>> _select_generator("diverse")
        ('http://amp-diff-amp:8000', 'Diff-AMP', False)
    """
    generator_lower = generator.lower()
    
    if "diverse" in generator_lower or "novel" in generator_lower:
        if _global_orchestrator:
            _global_orchestrator.start_tool("diff_amp")
        logger.info("🎯 Using Diff-AMP generator")
        return SERVICES["DIFF_AMP"], "Diff-AMP", False
    
    elif "refine" in generator_lower or "optimize" in generator_lower:
        if _global_orchestrator:
            _global_orchestrator.start_tool("hydramp")
        logger.info("🎯 Using HydrAMP generator")
        return SERVICES["HYDRAMP"], "HydrAMP", True
    
    else:
        if _global_orchestrator:
            _global_orchestrator.start_tool("amp_designer")
        logger.info("🎯 Using AMP-Designer generator (default)")
        return SERVICES["GENERATOR"], "AMP-Designer", False


def _call_generator_api(
    generator_url: str,
    target: str,
    n: int,
    use_hydramp_format: bool,
    timeout: int = GENERATOR_TIMEOUT
) -> List[str]:
    """
    Call generator API with appropriate payload format.
    
    Handles different API formats for different generators:
    - AMP-Designer/Diff-AMP: {"n": int, "target": str}
    - HydrAMP: {"num_samples": int, "mode": "amp"}
    
    Args:
        generator_url: Service endpoint URL
        target: Target organism
        n: Number of sequences to generate
        use_hydramp_format: Whether to use HydrAMP payload format
        timeout: Request timeout in seconds
        
    Returns:
        List of generated sequences
        
    Raises:
        requests.RequestException: If API call fails
    """
    if use_hydramp_format:
        payload = {"num_samples": n, "mode": "amp"}
    else:
        payload = {"n": n, "target": target}
    
    response = requests.post(
        f"{generator_url}/generate",
        json=payload,
        timeout=timeout
    )
    response.raise_for_status()
    
    data = response.json()
    
    if use_hydramp_format:
        return [item["sequence"] for item in data.get("data", []) if "sequence" in item]
    else:
        return data.get("sequences", [])


# ==================== Generator Tools ====================

def tool_generate_amp(
    num_samples: int = DEFAULT_NUM_SAMPLES,
    prompt: str = "Gram-negative",
    generator: str = "default"
) -> List[Dict[str, str]]:
    """
    Generate AMP sequences with automatic batching and retry.
    
    This is the primary sequence generation tool, supporting multiple
    generator backends with automatic resource management and error recovery.
    
    Features:
    - Automatic batching to prevent OOM errors
    - Type-safe parameter validation
    - Multi-generator support (AMP-Designer, Diff-AMP, HydrAMP)
    - Automatic retry on failure
    - Container orchestration integration
    
    Args:
        num_samples: Number of sequences to generate
        prompt: Target pathogen (supports Chinese and English)
        generator: Generation strategy:
            - 'default': AMP-Designer (fast, general-purpose)
            - 'diverse'/'novel': Diff-AMP (GAN-based, diverse)
            - 'refine'/'optimize': HydrAMP (VAE-based, optimized)
    
    Returns:
        List of dicts with keys:
            - sequence (str): Generated amino acid sequence
            - generator (str): Name of generator used
    
    Examples:
        >>> result = tool_generate_amp(num_samples=5, prompt="Gram-negative")
        >>> len(result)
        5
        >>> result[0]
        {'sequence': 'KKLFKKILKYL', 'generator': 'AMP-Designer'}
    
    Notes:
        - Uses oversampling and batching for production use
        - For multi-generator comparison, use tool_generate_sequences_only
        - Automatically manages Docker containers via ToolOrchestrator
    """
    # Validate and normalize parameters
    num_samples = _validate_num_samples(num_samples)
    target = _normalize_target(prompt)
    generator_url, generator_name, use_hydramp = _select_generator(generator)
    
    # Batch generation with retry
    all_sequences = []
    num_batches = math.ceil(num_samples / MAX_BATCH_SIZE)
    
    logger.info(f"Task: Generate {num_samples} sequences in {num_batches} batches")
    
    for batch_idx in range(num_batches):
        current_n = min(MAX_BATCH_SIZE, num_samples - len(all_sequences))
        if current_n <= 0:
            break
        
        logger.info(f"  ⚡ Batch {batch_idx + 1}/{num_batches} (n={current_n})...")
        
        # Retry logic for single batch
        batch_success = False
        for attempt in range(GENERATOR_RETRY_ATTEMPTS):
            try:
                seqs = _call_generator_api(
                    generator_url, target, current_n, use_hydramp
                )
                
                if seqs:
                    for seq in seqs:
                        all_sequences.append({
                            "sequence": seq,
                            "generator": generator_name
                        })
                    batch_success = True
                    break
            except Exception as e:
                logger.error(f"Batch {batch_idx + 1} attempt {attempt + 1} failed: {e}")
                time.sleep(1)
        
        if not batch_success:
            logger.warning(f"⚠️ Batch {batch_idx + 1} generation failed after {GENERATOR_RETRY_ATTEMPTS} attempts")
        
        # Cooldown between batches to release GPU memory
        if batch_idx < num_batches - 1:
            time.sleep(BATCH_COOLDOWN)
    
    logger.info(f"✅ Generation complete: {len(all_sequences)}/{num_samples} sequences")
    return all_sequences


def tool_generate_sequences_only(
    num_samples: int = 3,
    prompt: str = "Gram-negative",
    generator: str = "default"
) -> List[Dict[str, str]]:
    """
    Generate sequences without evaluation for multi-generator comparison.
    
    This tool is specifically designed for benchmarking tasks where fair
    comparison between generators is required. Unlike tool_generate_amp,
    it does NOT use oversampling and generates exactly the requested count.
    
    Key Differences from tool_generate_amp:
    - No oversampling (generates exactly num_samples, not 2x)
    - No automatic evaluation
    - Preserves generator attribution for comparison
    - Designed for fair benchmarking workflows
    
    Args:
        num_samples: Exact number of sequences to generate (no oversampling)
        prompt: Target pathogen (supports Chinese and English)
        generator: Generation strategy ('default'/'diverse'/'refine')
    
    Returns:
        List of dicts with keys:
            - sequence (str): Generated amino acid sequence
            - generator (str): Name of generator used
    
    Examples:
        >>> # Compare three generators with exact counts
        >>> amp_designer = tool_generate_sequences_only(5, "Gram-negative", "default")
        >>> diff_amp = tool_generate_sequences_only(5, "Gram-negative", "diverse")
        >>> hydramp = tool_generate_sequences_only(5, "Gram-negative", "refine")
        >>> len(amp_designer), len(diff_amp), len(hydramp)
        (5, 5, 5)  # Exact counts for fair comparison
    
    Notes:
        - Use this for "compare generators" or "benchmark" tasks
        - For production design tasks, use tool_generate_amp instead
        - Results should be merged and evaluated together for fairness
    """
    # Validate and normalize parameters (reuse helper functions)
    num_samples = _validate_num_samples(num_samples, default=3)
    target = _normalize_target(prompt)
    generator_url, generator_name, use_hydramp = _select_generator(generator)
    
    # Batch generation WITHOUT oversampling
    all_sequences = []
    num_batches = math.ceil(num_samples / MAX_BATCH_SIZE)
    
    logger.info(f"Comparison mode: Generate exactly {num_samples} sequences in {num_batches} batches")
    
    for batch_idx in range(num_batches):
        current_n = min(MAX_BATCH_SIZE, num_samples - len(all_sequences))
        if current_n <= 0:
            break
        
        logger.info(f"  ⚡ Batch {batch_idx + 1}/{num_batches} (n={current_n})...")
        
        batch_success = False
        for attempt in range(GENERATOR_RETRY_ATTEMPTS):
            try:
                seqs = _call_generator_api(
                    generator_url, target, current_n, use_hydramp
                )
                
                if seqs:
                    for seq in seqs:
                        all_sequences.append({
                            "sequence": seq,
                            "generator": generator_name
                        })
                    batch_success = True
                    break
            except Exception as e:
                logger.error(f"Batch {batch_idx + 1} attempt {attempt + 1} failed: {e}")
                time.sleep(1)
        
        if not batch_success:
            logger.warning(f"⚠️ Batch {batch_idx + 1} generation failed")
    
    # Ensure exact count (trim if over-generated)
    result = all_sequences[:num_samples]
    logger.info(f"✅ Comparison mode complete: {len(result)}/{num_samples} sequences")
    return result

# ==================== Evaluation Tools ====================

def tool_batch_evaluate(
    sequences: List[Dict[str, str]]
) -> List[Dict[str, Any]]:
    """
    Batch evaluation of AMP sequences with comprehensive metrics.
    
    Evaluates sequences across multiple dimensions:
    - Macrel: AMP classification probability
    - MIC: Minimum Inhibitory Concentration (antibacterial activity)
    - Hemolysis: Cytotoxicity to mammalian red blood cells
    - CPP: Cell-Penetrating Peptide probability (mammalian cell penetration)
    
    Features:
    - Serial evaluation with cooldown to prevent service overload
    - Automatic fallback for failed predictions
    - Generator attribution preservation for comparison tasks
    - Backward compatibility with List[str] input format
    
    Args:
        sequences: List of sequence dicts with keys:
            - sequence (str): Amino acid sequence
            - generator (str, optional): Generator name for attribution
            
            Also supports legacy List[str] format for backward compatibility.
    
    Returns:
        List of evaluation dicts with keys:
            - sequence (str): Original sequence
            - generator (str): Generator name (or "Unknown")
            - amp_score (float): AMP probability (0-1)
            - is_amp (bool): Whether sequence is classified as AMP
            - mic_value (float): MIC in μM (lower is better)
            - mic_log (float): Log-transformed MIC
            - mic_unit (str): Unit ("μM")
            - hemolysis_score (float): Hemolysis probability (0-1, lower is better)
            - is_toxic (bool): Whether sequence is hemolytic
            - cpp_score (float): CPP probability (0-1, lower is better for AMPs)
            - is_cpp (bool): Whether sequence is classified as CPP
    
    Examples:
        >>> seqs = [{'sequence': 'KKLFKKILKYL', 'generator': 'AMP-Designer'}]
        >>> results = tool_batch_evaluate(seqs)
        >>> results[0]['amp_score']
        0.95
        >>> results[0]['mic_value']
        8.5  # μM
    
    Notes:
        - Cooldown periods prevent API rate limiting
        - Failed predictions result in None values
        - For structure pipeline without Macrel, use tool_batch_evaluate_no_macrel
    """
    results = []
    
    for item in sequences:
        # Backward compatibility: support both List[Dict] and List[str]
        if isinstance(item, dict):
            seq = item.get("sequence")
            generator_name = item.get("generator", "Unknown")
        else:
            seq = item
            generator_name = "Unknown"
        
        row = {
            "sequence": seq,
            "generator": generator_name,
            "mic_value": None,
            "mic_log": None,
            "hemolysis_score": None,
            "is_toxic": None,
            "cpp_score": None,
            "is_cpp": None,
            "is_amp": None,
            "amp_score": None
        }
        
        # 1. Macrel: AMP classification
        try:
            r = requests.post(
                f"{SERVICES['MACREL']}/predict_macrel_only",
                json={"sequence": seq},
                timeout=60
            )
            if r.status_code == 200:
                data = r.json()
                row["amp_score"] = (
                    data.get("score")
                    or data.get("macrel_score")
                    or data.get("composite_score")
                )
                amp_score = row["amp_score"]
                row["is_amp"] = (
                    float(amp_score) >= MACREL_AMP_THRESHOLD
                    if amp_score is not None
                    else False
                )
        except Exception as e:
            logger.warning(f"Macrel prediction failed: {str(e)} - {seq}")
            # Fallback: simple heuristic based on amino acid composition
            pos_charge = sum(seq.count(aa) for aa in 'KR')
            hydrophobic = sum(seq.count(aa) for aa in 'LAIV')
            ratio = (pos_charge + hydrophobic) / len(seq) if len(seq) > 0 else 0
            row["amp_score"] = 0.8 if ratio > 0.4 else 0.2
            row["is_amp"] = ratio > 0.4
        
        # 2. MIC: Antibacterial activity
        time.sleep(EVALUATION_COOLDOWN)
        try:
            r = requests.post(
                f"{SERVICES['MIC']}/predict",
                json={"sequence": seq},
                timeout=EVALUATION_TIMEOUT
            )
            if r.status_code == 200:
                data = r.json()
                logger.info(f"🔬 MIC response: {seq[:12]}... -> {data}")
                
                if "mic_value" in data and data["mic_value"] is not None:
                    row["mic_value"] = data["mic_value"]
                    row["mic_unit"] = data.get("mic_unit", "μM")
                    row["mic_log"] = data.get("mic_log")
                    logger.info(f"✅ MIC: {row['mic_value']} {row['mic_unit']} (log: {row['mic_log']})")
        except Exception as e:
            logger.warning(f"⚠️ MIC prediction failed: {seq[:20]}... - {e}")
        
        # 3. Hemolysis: Cytotoxicity
        time.sleep(1.0)
        try:
            r = requests.post(
                f"{SERVICES['HEMOLYSIS']}/predict",
                json={"sequence": seq},
                timeout=EVALUATION_TIMEOUT
            )
            if r.status_code == 200:
                try:
                    data = r.json()
                    
                    # Try multiple field names for compatibility
                    score = (
                        data.get("hemolysis_score")
                        or data.get("score")
                        or data.get("prob")
                    )
                    # Convert percentage to decimal (e.g., 31.5 -> 0.315)
                    if score is not None and score > 1:
                        score = score / 100.0
                    row["hemolysis_score"] = score
                    
                    if data.get("is_toxic") is not None:
                        row["is_toxic"] = data.get("is_toxic")
                    elif row["hemolysis_score"] is not None:
                        row["is_toxic"] = float(row["hemolysis_score"]) > 0.5
                
                except json.JSONDecodeError as e:
                    logger.error(f"Hemolysis API JSON decode error for {seq}: {e}. Raw: {r.text[:100]}...")
            
            elif r.status_code == 500:
                logger.error(f"Hemolysis API error 500 for {seq}. Raw: {r.text[:100]}...")
        
        except Exception as e:
            logger.error(f"Hemolysis API connection error for {seq}: {e}")
        
        # 4. CPP: Cell-penetrating peptide
        time.sleep(1.0)
        try:
            r = requests.post(
                f"{SERVICES['CPP']}/predict",
                json={"sequence": seq},
                timeout=EVALUATION_TIMEOUT
            )
            if r.status_code == 200:
                data = r.json()
                row["cpp_score"] = data.get("score")
                
                if data.get("label"):
                    row["is_cpp"] = (data.get("label") == "CPP")
                elif row["cpp_score"] is not None:
                    row["is_cpp"] = float(row["cpp_score"]) > 0.5
        except:
            pass
        
        results.append(row)
    
    return results


def tool_batch_evaluate_no_macrel(sequences: List[str]) -> List[Dict[str, Any]]:
    """
    Batch evaluation without Macrel (for structure discrimination pipeline).
    
    This simplified evaluator is used in the structure discrimination pipeline
    where AMP classification has already been performed by PGAT-ABPp. Only
    MIC, hemolysis, and CPP predictions are needed.
    
    Args:
        sequences: List of amino acid sequences
    
    Returns:
        List of dicts with keys:
            - sequence (str): Original sequence
            - mic (float): MIC value in μM
            - hemolysis (float): Hemolysis probability
            - cpp (float): CPP probability
    
    Examples:
        >>> seqs = ["KKLFKKILKYL", "GLFDIVKKVVGALG"]
        >>> results = tool_batch_evaluate_no_macrel(seqs)
        >>> results[0]['mic']
        12.5
    
    Notes:
        - Used exclusively by structure_discrimination_pipeline
        - Faster than tool_batch_evaluate as it skips Macrel
        - All failed predictions result in None values
    """
    results = []
    
    for seq in sequences:
        row = {
            "sequence": seq,
            "mic": None,
            "hemolysis": None,
            "cpp": None
        }
        
        # MIC prediction
        time.sleep(EVALUATION_COOLDOWN)
        try:
            r = requests.post(
                f"{SERVICES['MIC']}/predict",
                json={"sequence": seq},
                timeout=EVALUATION_TIMEOUT
            )
            if r.status_code == 200:
                data = r.json()
                if "mic_value" in data and data["mic_value"] is not None:
                    row["mic"] = data["mic_value"]
        except Exception as e:
            logger.warning(f"MIC prediction failed: {str(e)} - {seq[:20]}...")
        
        # Hemolysis prediction
        time.sleep(EVALUATION_COOLDOWN)
        try:
            r = requests.post(
                f"{SERVICES['HEMOLYSIS']}/predict",
                json={"sequence": seq},
                timeout=EVALUATION_TIMEOUT
            )
            if r.status_code == 200:
                data = r.json()
                # 兼容 'hemolysis_score' 和旧版 'score' 两种键名
                hemo_val = data.get("hemolysis_score") or data.get("score")
                if hemo_val is not None:
                    # Convert percentage to decimal if needed (e.g., 31.5 -> 0.315)
                    if hemo_val > 1:
                        hemo_val = hemo_val / 100.0
                    row["hemolysis"] = hemo_val
        except Exception as e:
            logger.warning(f"Hemolysis prediction failed: {str(e)} - {seq[:20]}...")
        
        # CPP prediction
        time.sleep(EVALUATION_COOLDOWN)
        try:
            r = requests.post(
                f"{SERVICES['CPP']}/predict",
                json={"sequence": seq},
                timeout=EVALUATION_TIMEOUT
            )
            if r.status_code == 200:
                data = r.json()
                if "score" in data:
                    row["cpp"] = data["score"]
        except Exception as e:
            logger.warning(f"CPP prediction failed: {str(e)} - {seq[:20]}...")
        
        results.append(row)
    
    return results


# ==================== Single-Task Prediction Tools ====================

def tool_predict_mic_only(sequences: List[str]) -> List[Dict[str, Any]]:
    """
    Predict MIC (Minimum Inhibitory Concentration) only.
    
    Lightweight prediction tool that calls only the MIC service,
    useful when other metrics are not needed.
    
    Args:
        sequences: List of amino acid sequences
    
    Returns:
        List of dicts with keys:
            - sequence (str): Original sequence
            - mic_value (float): MIC in μM (or None if failed)
            - mic_unit (str): Unit ("μM")
            - error (str, optional): Error message if prediction failed
    
    Examples:
        >>> seqs = ["KKLFKKILKYL"]
        >>> results = tool_predict_mic_only(seqs)
        >>> results[0]['mic_value']
        8.5
    """
    results = []
    for seq in sequences:
        row = {"sequence": seq, "mic_value": None, "mic_unit": None}
        try:
            r = requests.post(
                f"{SERVICES['MIC']}/predict",
                json={"sequence": seq},
                timeout=EVALUATION_TIMEOUT
            )
            if r.status_code == 200:
                data = r.json()
                log_mic = data.get("score") or data.get("mic_value")
                if log_mic is not None and log_mic >= 0:
                    # Convert from log(μM) to μM
                    import numpy as np
                    mic_um = np.power(10, log_mic)
                    row["mic_value"] = round(mic_um, 4)
                    row["mic_unit"] = "μM"
                elif log_mic is not None:  # -1 indicates prediction failure
                    row["mic_value"] = None
        except Exception as e:
            row["error"] = str(e)
        results.append(row)
    return results


def tool_predict_hemolysis_only(sequences: List[str]) -> List[Dict[str, Any]]:
    """
    Predict hemolysis (cytotoxicity) only.
    
    Args:
        sequences: List of amino acid sequences
    
    Returns:
        List of dicts with keys:
            - sequence (str): Original sequence
            - hemolysis_score (float): Hemolysis probability (0-1)
            - is_toxic (bool): Whether sequence is hemolytic (> 0.5)
            - error (str, optional): Error message if prediction failed
    """
    results = []
    for seq in sequences:
        row = {"sequence": seq, "hemolysis_score": None, "is_toxic": None}
        try:
            r = requests.post(
                f"{SERVICES['HEMOLYSIS']}/predict",
                json={"sequence": seq},
                timeout=EVALUATION_TIMEOUT
            )
            if r.status_code == 200:
                data = r.json()
                score = (
                    data.get("hemolysis_score")
                    or data.get("score")
                    or data.get("prob")
                )
                row["hemolysis_score"] = score
                if score is not None:
                    row["is_toxic"] = float(score) > 0.5
        except Exception as e:
            row["error"] = str(e)
        results.append(row)
    return results


def tool_predict_cpp_only(sequences: List[str]) -> List[Dict[str, Any]]:
    """
    Predict CPP (Cell-Penetrating Peptide) probability only.
    
    Args:
        sequences: List of amino acid sequences
    
    Returns:
        List of dicts with keys:
            - sequence (str): Original sequence
            - cpp_score (float): CPP probability (0-1)
            - is_cpp (bool): Whether sequence is CPP (> 0.5)
            - error (str, optional): Error message if prediction failed
    
    Notes:
        - Lower CPP scores are desirable for AMPs (< 0.3 ideal)
        - High CPP indicates mammalian cell penetration risk
    """
    results = []
    for seq in sequences:
        row = {"sequence": seq, "cpp_score": None, "is_cpp": None}
        try:
            r = requests.post(
                f"{SERVICES['CPP']}/predict",
                json={"sequence": seq},
                timeout=EVALUATION_TIMEOUT
            )
            if r.status_code == 200:
                data = r.json()
                row["cpp_score"] = data.get("score")
                if data.get("label"):
                    row["is_cpp"] = (data.get("label") == "CPP")
                elif row["cpp_score"] is not None:
                    row["is_cpp"] = float(row["cpp_score"]) > 0.5
        except Exception as e:
            row["error"] = str(e)
        results.append(row)
    return results

# ==================== Ranking Tools ====================

def _prepare_ranking_dataframe(evaluated_data: List[Dict], keep_all_generators: bool = False) -> pd.DataFrame:
    """
    Prepare DataFrame for multi-objective ranking.
    
    Preprocessing steps:
    1. Filter by Macrel AMP score (≥ 0.5 threshold)
    2. Convert metrics to numeric types
    3. Fill missing values with conservative defaults
    4. Create normalized sorting columns
    
    Args:
        evaluated_data: List of evaluation results from tool_batch_evaluate
        keep_all_generators: If True (compare mode), ensures every generator
            keeps at least its best sequence even if amp_score < 0.5.
    
    Returns:
        Filtered and prepared DataFrame with sorting columns:
            - mic_sort: MIC values (lower is better, missing = 100.0)
            - hemo_sort: Hemolysis scores (lower is better, missing = 1.0)
            - cpp_sort: CPP scores (lower is better, missing = 1.0)
    
    Notes:
        - Sequences with amp_score < 0.5 are filtered out (unless keep_all_generators=True)
        - If no sequences pass AMP filter, returns all candidates with warning
        - Missing metrics get conservative (worst-case) defaults
    """
    df = pd.DataFrame(evaluated_data)
    if df.empty:
        return df
    
    # Filter by AMP classification threshold
    df["amp_score_num"] = pd.to_numeric(df.get("amp_score"), errors="coerce").fillna(0)
    df_filtered = df[df["amp_score_num"] >= MACREL_AMP_THRESHOLD].copy()
    
    if keep_all_generators and "generator" in df.columns:
        # Compare mode: ensure every generator keeps at least its best sequence
        all_generators = set(df["generator"].unique())
        kept_generators = set(df_filtered["generator"].unique()) if not df_filtered.empty else set()
        missing_generators = all_generators - kept_generators
        if missing_generators:
            logger.warning(f"⚠️ Generators with all sequences below AMP threshold, keeping best sequence each: {missing_generators}")
            for gen in missing_generators:
                gen_rows = df[df["generator"] == gen].copy()
                if not gen_rows.empty:
                    best_row = gen_rows.sort_values("amp_score_num", ascending=False).head(1)
                    df_filtered = pd.concat([df_filtered, best_row], ignore_index=True)
    elif len(df_filtered) == 0:
        logger.warning(
            f"⚠️ No sequences passed Macrel AMP filter (≥ {MACREL_AMP_THRESHOLD}), "
            "returning all candidates"
        )
        df_filtered = df.copy()
    
    # Create sorting columns with conservative defaults
    df_filtered["mic_sort"] = pd.to_numeric(
        df_filtered.get("mic_value"),
        errors="coerce"
    ).fillna(100.0)  # Missing MIC = assume high (worst case)
    
    df_filtered["hemo_sort"] = pd.to_numeric(
        df_filtered.get("hemolysis_score"),
        errors="coerce"
    ).fillna(1.0)  # Missing hemolysis = assume toxic (worst case)
    
    df_filtered["cpp_sort"] = pd.to_numeric(
        df_filtered.get("cpp_score"),
        errors="coerce"
    ).fillna(1.0)  # Missing CPP = assume high penetration (worst case)
    
    return df_filtered.reset_index(drop=True)


def _dominates(a: Dict, b: Dict, keys: List[str]) -> bool:
    """
    Check if vector a Pareto-dominates vector b.
    
    For minimization objectives, a dominates b if:
    - a is better or equal in all dimensions
    - a is strictly better in at least one dimension
    
    Args:
        a: First candidate dict
        b: Second candidate dict
        keys: List of metric keys to compare
    
    Returns:
        True if a dominates b, False otherwise
    
    Examples:
        >>> a = {'mic_sort': 5, 'hemo_sort': 0.2}
        >>> b = {'mic_sort': 10, 'hemo_sort': 0.3}
        >>> _dominates(a, b, ['mic_sort', 'hemo_sort'])
        True  # a is better in both dimensions
    """
    better_or_equal_all = True
    strictly_better = False
    
    for k in keys:
        va = a.get(k, 0)
        vb = b.get(k, 0)
        if va > vb:  # Worse in at least one dimension
            better_or_equal_all = False
            break
        if va < vb:  # Strictly better in this dimension
            strictly_better = True
    
    return better_or_equal_all and strictly_better


def _apply_pareto_ranking(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply Pareto front ranking on MIC / Hemolysis / CPP (all minimized).
    
    Pareto optimality identifies sequences that cannot be improved in one
    objective without worsening another. This is the recommended ranking
    strategy for multi-objective AMP optimization.
    
    Algorithm:
    1. Compute non-dominated set (Pareto frontier)
    2. Sort frontier by MIC → Hemolysis → CPP
    3. Sort dominated set with same ordering
    4. Concatenate so Pareto front appears at top
    
    Args:
        df: DataFrame with columns mic_sort, hemo_sort, cpp_sort
    
    Returns:
        Ranked DataFrame with _is_pareto_front flag column
    
    Notes:
        - All three objectives are minimized (lower is better)
        - Sequences on Pareto front are marked with _is_pareto_front = True
    """
    if df.empty:
        return df

    keys = ["mic_sort", "hemo_sort", "cpp_sort"]
    records = df[keys].to_dict(orient="records")
    n = len(records)
    dominated = [False] * n

    for i in range(n):
        if dominated[i]:
            continue
        for j in range(n):
            if i == j:
                continue
            if _dominates(records[j], records[i], keys):
                dominated[i] = True
                break

    df["_is_pareto_front"] = [not d for d in dominated]
    front = df[df["_is_pareto_front"]].sort_values(keys, ascending=[True, True, True])
    rest = df[~df["_is_pareto_front"]].sort_values(keys, ascending=[True, True, True])
    ranked = pd.concat([front, rest], ignore_index=True)
    return ranked
    

def _apply_mic_only_ranking(df: pd.DataFrame) -> pd.DataFrame:
    """
    Single-objective ranking: prioritize MIC, then Hemolysis, then CPP.
    
    This strategy focuses purely on antibacterial activity (MIC) as the
    primary objective, using hemolysis and CPP only as tiebreakers.
    
    Args:
        df: DataFrame with columns mic_sort, hemo_sort, cpp_sort
    
    Returns:
        Sorted DataFrame (ascending order for all metrics)
    
    Notes:
        - Best for rapid screening where activity is paramount
        - Safety metrics (hemolysis, CPP) are secondary considerations
    """
    if df.empty:
        return df
    return df.sort_values(["mic_sort", "hemo_sort", "cpp_sort"], ascending=[True, True, True])


def _apply_balanced_ranking(df: pd.DataFrame) -> pd.DataFrame:
    """
    Weighted multi-objective ranking with explicit normalization.
    
    This strategy computes a weighted composite score combining all three
    objectives with predefined weights:
    - MIC: 60% (antibacterial activity)
    - Hemolysis: 25% (mammalian cell safety)
    - CPP: 15% (cell penetration penalty)
    
    Args:
        df: DataFrame with columns mic_sort, hemo_sort, cpp_sort
    
    Returns:
        Sorted DataFrame by composite score (descending, higher is better)
    
    Notes:
        - All metrics are normalized to [0, 1] range before weighting
        - Lower raw values → higher normalized scores (minimization)
        - Weights reflect relative importance in therapeutic context
    """
    if df.empty:
        return df

    metrics = ["mic_sort", "hemo_sort", "cpp_sort"]
    norm_cols = {}
    for m in metrics:
        col = pd.to_numeric(df[m], errors="coerce").fillna(0.0)
        vmin = float(col.min())
        vmax = float(col.max())
        if vmax > vmin:
            # lower raw value → higher normalized score
            norm = 1.0 - (col - vmin) / (vmax - vmin)
        else:
            norm = pd.Series([0.5] * len(df), index=df.index)
        norm_cols[m] = norm

    # Maintain original weight configuration: MIC 60%, Hemolysis 25%, CPP 15%
    df["_score_balanced"] = (
        0.6 * norm_cols["mic_sort"]
        + 0.25 * norm_cols["hemo_sort"]
        + 0.15 * norm_cols["cpp_sort"]
    )
    return df.sort_values("_score_balanced", ascending=False)


def tool_rank_sequences(evaluated_data: List[Dict], strategy: str = "pareto", keep_all_generators: bool = False) -> List[Dict]:
    """
    Multi-objective ranking tool for AMP candidate prioritization.
    
    Supports three ranking strategies:
    1. **pareto** (default, recommended): Multi-objective Pareto optimality
    2. **mic_only**: Single-objective focus on antibacterial activity
    3. **balanced**: Weighted composite score (MIC 60%, Hemo 25%, CPP 15%)
    
    The Pareto strategy identifies non-dominated sequences that represent
    optimal trade-offs between activity, safety, and selectivity.
    
    Args:
        evaluated_data: List of dicts from tool_batch_evaluate with keys:
            - sequence (str): Amino acid sequence
            - mic_value (float): MIC in μM
            - hemolysis_score (float): Hemolysis probability
            - cpp_score (float): CPP probability
            - amp_score (float): Macrel AMP classification
        strategy: Ranking method ('pareto', 'mic_only', 'balanced')
        keep_all_generators: If True (compare mode), ensures every generator
            keeps at least its best sequence even if amp_score < 0.5.
    
    Returns:
        Ranked list of dicts with added keys:
            - is_pareto_optimal (bool): True if on Pareto frontier (pareto mode only)
            - All original evaluation metrics preserved
    
    Examples:
        >>> data = tool_batch_evaluate([{"sequence": "KKLFKKILKYL"}])
        >>> ranked = tool_rank_sequences(data, strategy="pareto")
        >>> ranked[0]['is_pareto_optimal']
        True
    
    Notes:
        - Sequences with amp_score < 0.5 are filtered out (unless keep_all_generators=True)
        - Missing metrics get conservative defaults (worst-case)
        - All objectives are minimized (lower is better)
        - Pareto front sequences appear first in results
    """
    if not evaluated_data:
        return []

    df_filtered = _prepare_ranking_dataframe(evaluated_data, keep_all_generators=keep_all_generators)
    if df_filtered.empty:
        return []

    strategy = (strategy or "pareto").lower()

    if strategy == "mic_only":
        ranked = _apply_mic_only_ranking(df_filtered)
    elif strategy == "balanced":
        ranked = _apply_balanced_ranking(df_filtered)
    else:
        # Default: Pareto ranking (recommended for papers and visualization)
        ranked = _apply_pareto_ranking(df_filtered)

    cols_to_drop = ["mic_sort", "hemo_sort", "cpp_sort", "amp_score_num"]
    if "_score_balanced" in ranked.columns:
        cols_to_drop.append("_score_balanced")
    
    # Fix: Remove potential duplicate is_pareto_optimal column to avoid conflicts
    logger.info(f"🔍 Before cleanup, columns: {ranked.columns.tolist()}")
    if "is_pareto_optimal" in ranked.columns:
        logger.warning("⚠️ Found existing is_pareto_optimal, will drop it")
        cols_to_drop.append("is_pareto_optimal")
    
    # Drop temporary columns
    ranked = ranked.drop(columns=[c for c in cols_to_drop if c in ranked.columns])
    logger.info(f"🔍 After dropping, columns: {ranked.columns.tolist()}")
    
    # Rename _is_pareto_front to is_pareto_optimal
    if "_is_pareto_front" in ranked.columns:
        ranked.rename(columns={"_is_pareto_front": "is_pareto_optimal"}, inplace=True)
        logger.info(f"🔍 After rename, columns: {ranked.columns.tolist()}")
    
    # DEBUG: Check for duplicate column names
    if len(ranked.columns) != len(set(ranked.columns)):
        logger.error(f"❌ DataFrame has duplicate columns: {ranked.columns.tolist()}")
        # Remove duplicate columns
        ranked = ranked.loc[:, ~ranked.columns.duplicated()]
    
    return ranked.to_dict(orient="records")

def visualize_pareto_front(evaluated_data: List[Dict], strategy: str = "pareto") -> str:
    """
    Generate interactive 3D Pareto frontier visualization.
    
    Creates a 3D scatter plot showing the trade-off space between:
    - MIC (μM, antibacterial activity)
    - Hemolysis (mammalian cytotoxicity)
    - CPP (cell penetration)
    
    Args:
        evaluated_data: List of evaluation results from tool_batch_evaluate
        strategy: Ranking strategy ('pareto', 'mic_only', 'balanced')
    
    Returns:
        Plotly HTML string for embedding in Streamlit or web interfaces
    
    Visual encoding:
        - Red diamonds: Pareto-optimal sequences (non-dominated)
        - Blue circles: Dominated sequences
        - Hover shows sequence and all metrics
    
    Examples:
        >>> data = tool_batch_evaluate([{"sequence": "KKLFKKILKYL"}])
        >>> html = visualize_pareto_front(data)
        >>> assert "plotly" in html.lower()
    
    Notes:
        - Requires Plotly library
        - All axes use "lower is better" orientation
        - Interactive rotation and zoom enabled
    """
    if not evaluated_data:
        return "<p>⚠️ No data to visualize</p>"

    try:
        import plotly.graph_objects as go
    except ImportError:
        return "<p>⚠️ Plotly not installed. Please run: pip install plotly</p>"

    # 1. Compute ranking results (preserve is_pareto_optimal column)
    ranked = tool_rank_sequences(evaluated_data, strategy=strategy)
    if not ranked:
        return "<p>⚠️ Empty ranking result</p>"

    df = pd.DataFrame(ranked)
    mic = df.get("mic_value", pd.Series([0] * len(df)))
    hemo = df.get("hemolysis_score", pd.Series([0] * len(df)))
    cpp = df.get("cpp_score", pd.Series([0] * len(df)))
    seqs = df.get("sequence", pd.Series([""] * len(df)))

    # 2. Separate Pareto frontier from dominated points
    is_pareto = df.get("is_pareto_optimal", pd.Series([False] * len(df)))
    front_mask = is_pareto == True
    rest_mask = ~front_mask

    # 3. Plot two groups of scatter points
    fig = go.Figure()

    # Non-Pareto (dominated) points - blue circles
    if rest_mask.sum() > 0:
        fig.add_trace(go.Scatter3d(
            x=mic[rest_mask],
            y=hemo[rest_mask],
            z=cpp[rest_mask],
            mode="markers",
            marker=dict(size=6, color="rgba(52, 152, 219, 0.6)", opacity=0.8,
                       line=dict(width=1, color="rgb(52, 152, 219)")),
            text=seqs[rest_mask],
            hovertemplate="<b>%{text}</b><br>MIC: %{x:.2f} μM<br>Hemo: %{y:.3f}<br>CPP: %{z:.3f}<extra></extra>",
            name="Dominated"
        ))

    # Pareto frontier - red diamonds
    if front_mask.sum() > 0:
        fig.add_trace(go.Scatter3d(
            x=mic[front_mask],
            y=hemo[front_mask],
            z=cpp[front_mask],
            mode="markers",
            marker=dict(size=10, color="crimson", symbol="diamond", opacity=1.0,
                       line=dict(width=2, color="darkred")),
            text=seqs[front_mask],
            hovertemplate="<b>⭐ Pareto Optimal</b><br>%{text}<br>MIC: %{x:.2f} μM<br>Hemo: %{y:.3f}<br>CPP: %{z:.3f}<extra></extra>",
            name="Pareto Front"
        ))

    fig.update_layout(
        title=None,  # Hide internal title, use frontend title instead
        scene=dict(
            xaxis=dict(
                title="MIC (μM, lower is better)",
                titlefont=dict(size=11, color='#2d3436'),
                gridcolor='rgba(100,100,100,0.5)',  # Strengthen grid lines
                showgrid=True,
                showbackground=True,
                backgroundcolor='rgba(245,245,245,0.9)'
            ),
            yaxis=dict(
                title="Hemolysis Score (lower is better)",
                titlefont=dict(size=11, color='#2d3436'),
                gridcolor='rgba(100,100,100,0.5)',  # Strengthen grid lines
                showgrid=True,
                showbackground=True,
                backgroundcolor='rgba(245,245,245,0.9)'
            ),
            zaxis=dict(
                title="CPP Score (lower is better)",
                titlefont=dict(size=11, color='#2d3436'),
                gridcolor='rgba(100,100,100,0.5)',  # Strengthen grid lines
                showgrid=True,
                showbackground=True,
                backgroundcolor='rgba(245,245,245,0.9)'
            ),
            bgcolor='white'
        ),
        width=500,
        height=450,
        margin=dict(t=20, b=30, l=30, r=30),  # reduce top margin
        paper_bgcolor='white',
        legend=dict(
            x=0.02,
            y=0.98,
            xanchor="left",
            yanchor="top",
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="#dfe6e9",
            borderwidth=1,
            font=dict(size=10)
        ),
        font=dict(family='Arial')
    )

    return fig.to_html(include_plotlyjs="inline", full_html=False)


def visualize_pareto_2d(evaluated_data: List[Dict], strategy: str = "pareto", 
                        axis_x: str = "mic", axis_y: str = "hemolysis") -> str:
    """Generate 2D Pareto frontier scatter plot for publication-quality figures.
    
    Args:
        evaluated_data: List of evaluated sequences with metrics
        strategy: Ranking strategy ('pareto', 'mic_only', 'balanced')
        axis_x: X-axis metric ('mic', 'hemolysis', 'cpp')
        axis_y: Y-axis metric ('mic', 'hemolysis', 'cpp')
    
    Returns:
        Plotly HTML string for Streamlit embedding
    
    Notes:
        - 2D plots are clearer for papers than 3D plots
        - Pareto frontier highlighted with red diamonds
        - Non-frontier points shown as blue circles
    """
    if not evaluated_data:
        return "<p>⚠️ No data to visualize</p>"
    
    try:
        import plotly.graph_objects as go
    except ImportError:
        return "<p>⚠️ Plotly not installed. Run: pip install plotly</p>"
    
    # 1. Compute ranking with Pareto labels
    ranked = tool_rank_sequences(evaluated_data, strategy=strategy)
    if not ranked:
        return "<p>⚠️ Empty ranking result</p>"
    
    df = pd.DataFrame(ranked)
    
    # 2. Map axis names to dataframe columns
    metric_map = {
        "mic": ("mic_value", "MIC (μM)", "lower is better"),
        "hemolysis": ("hemolysis_score", "Hemolysis Score", "lower is better"),
        "cpp": ("cpp_score", "CPP Score", "lower is better")
    }
    
    x_col, x_label, x_note = metric_map.get(axis_x, metric_map["mic"])
    y_col, y_label, y_note = metric_map.get(axis_y, metric_map["hemolysis"])
    
    x_data = df.get(x_col, pd.Series([0] * len(df)))
    y_data = df.get(y_col, pd.Series([0] * len(df)))
    seqs = df.get("sequence", pd.Series([""]*len(df)))
    
    # 3. Separate Pareto frontier and dominated points
    is_pareto = df.get("is_pareto_optimal", pd.Series([False] * len(df)))
    front_mask = is_pareto == True
    rest_mask = ~front_mask
    
    # 4. Create 2D scatter plot
    fig = go.Figure()
    
    # Non-Pareto (dominated) points - blue circles
    if rest_mask.sum() > 0:
        fig.add_trace(go.Scatter(
            x=x_data[rest_mask],
            y=y_data[rest_mask],
            mode="markers",
            marker=dict(size=10, color="rgba(52, 152, 219, 0.6)", opacity=0.8, symbol="circle",
                       line=dict(width=1, color="rgb(52, 152, 219)")),
            text=seqs[rest_mask],
            hovertemplate="<b>%{text}</b><br>" + f"{x_label}: %{{x:.2f}}<br>{y_label}: %{{y:.3f}}<extra></extra>",
            name="Dominated",
            showlegend=True
        ))
    
    # Pareto frontier - red diamonds
    if front_mask.sum() > 0:
        fig.add_trace(go.Scatter(
            x=x_data[front_mask],
            y=y_data[front_mask],
            mode="markers",
            marker=dict(size=14, color="crimson", symbol="diamond", opacity=1.0, 
                       line=dict(width=2, color="darkred")),
            text=seqs[front_mask],
            hovertemplate="<b>⭐ Pareto Optimal</b><br>%{text}<br>" + f"{x_label}: %{{x:.2f}}<br>{y_label}: %{{y:.3f}}<extra></extra>",
            name="Pareto Front",
            showlegend=True
        ))
    
    # 5. Layout configuration for publication quality
    fig.update_layout(
        title=None,  # Hide internal title, use frontend title instead
        xaxis=dict(
            title=f"{x_label} (lower is better)",
            showgrid=True,
            gridcolor="rgba(200,200,200,0.3)",
            zeroline=False,
            titlefont=dict(size=12, color='#2d3436'),
            tickfont=dict(size=10)
        ),
        yaxis=dict(
            title=f"{y_label} (lower is better)",
            showgrid=True,
            gridcolor="rgba(200,200,200,0.3)",
            zeroline=False,
            titlefont=dict(size=12, color='#2d3436'),
            tickfont=dict(size=10)
        ),
        width=500,
        height=450,
        plot_bgcolor="white",
        paper_bgcolor='white',
        margin=dict(t=20, b=50, l=60, r=30),  # reduce top margin
        legend=dict(
            x=0.02,
            y=0.98,
            xanchor="left",
            yanchor="top",
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="#dfe6e9",
            borderwidth=1,
            font=dict(size=10)
        ),
        hovermode="closest",
        font=dict(family='Arial'),
        autosize=False  # Disable automatic resizing
    )
    
    return fig.to_html(include_plotlyjs="inline", full_html=False)


def tool_predict_structure(sequence: str = None, **kwargs) -> Dict:
    """
    Predict 3D structure
    
    Args:
        sequence: Peptide sequence string, or pass via kwargs
    """
    # Support two calling conventions: sequence="xxx" or **{"sequence": "xxx"}
    if sequence is None:
        sequence = kwargs.get("sequence", kwargs.get("seq", ""))
    
    if not sequence:
        return {"error": "lack of sequence parameter"}
    
    try:
        r = requests.post(f"{SERVICES['STRUCTURE']}/predict_structure", json={"sequence": sequence}, timeout=600)
        if r.status_code == 200: 
            result = r.json()
            result['sequence'] = sequence 
            return result
        else:
            return {"error": f"HTTP {r.status_code}: {r.text[:200]}"}
    except Exception as e:
        return {"error": f"Structure prediction failed: {str(e)}"}

# ==================== Knowledge Base and Ontology Tools ====================

def tool_search_knowledge(query: str = "", knowledge_type: str = "literature", top_k: int = 5, **kwargs) -> Dict[str, Any]:
    """
    Search AMP knowledge base with hybrid retrieval modes.
    
    Supports two retrieval strategies:
    1. **Vector-based RAG**: Semantic search across literature corpus
    2. **Structured Ontology**: Direct access to aggregated domain concepts
    
    The ontology mode provides pre-aggregated statistics on:
    - Design principles (e.g., "cationic charge", "hydrophobicity")
    - Action mechanisms (e.g., "membrane disruption", "pore formation")
    - Target organisms (e.g., "E. coli", "S. aureus")
    - Mechanism-target co-occurrence matrix
    
    Args:
        query: Natural language query string
        knowledge_type: Search mode ('literature', 'mic', 'cpp', 'hemolysis', 'ontology')
        top_k: Number of results to return (vector mode only)
        **kwargs: Extra parameters (mode="ontology" as alias for knowledge_type)
    
    Returns:
        Dict with keys:
            - success (bool): Operation status
            - results (list): Search results with content, source, relevance_score
            - total_found (int): Number of results
            - query (str): Echo of input query
            - knowledge_type (str): Echo of search mode
    
    Examples:
        >>> # Vector search
        >>> result = tool_search_knowledge("cationic AMPs", "literature", top_k=3)
        >>> len(result['results'])
        3
        
        >>> # Ontology overview
        >>> ontology = tool_search_knowledge("", mode="ontology")
        >>> ontology['results'][0]['content']['design_principles']
        [{'name': 'cationic charge', 'count': 45, 'sources': [...]}]
    
    Notes:
        - Ontology mode reads from integrated_knowledge_base/literature_knowledge.json
        - Vector mode requires search_knowledge service to be loaded
        - Design principles/mechanisms sorted by document frequency
    """
    # Accept mode="ontology" as a user-friendly alias for knowledge_type
    mode = kwargs.get("mode")
    if isinstance(mode, str) and mode.lower() == "ontology" and knowledge_type == "literature":
        knowledge_type = "ontology"

    # Special structured ontology mode: read integrated knowledge JSON directly (no vector DB required)
    if knowledge_type == "ontology":
        kb_base = Path("/data/amp-generator-platform/knowledge_builder/integrated_knowledge_base")
        kb_file = kb_base / "01_literature_knowledge" / "literature_knowledge.json"
        if not kb_file.exists():
            logger.warning(f"Ontology knowledge file not found: {kb_file}")
            return {
                "success": False,
                "error": f"Ontology knowledge file not found at {kb_file}",
                "results": [],
                "query": query,
                "knowledge_type": "ontology"
            }
        try:
            with kb_file.open("r", encoding="utf-8") as f:
                records = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load ontology knowledge: {e}")
            return {
                "success": False,
                "error": f"Failed to load ontology knowledge: {e}",
                "results": [],
                "query": query,
                "knowledge_type": "ontology"
            }

        # Aggregate core domain concepts across all literature entries
        design_principles: Dict[str, Dict[str, Any]] = {}
        action_mechanisms: Dict[str, Dict[str, Any]] = {}
        target_organisms: Dict[str, Dict[str, Any]] = {}
        experimental_values: List[float] = []
        mech_target_counts: Dict[Tuple[str, str], int] = {}

        for item in records:
            meta = item.get("metadata", {})
            src = meta.get("source", "unknown")
            core = item.get("knowledge_core", {})

            for dp in core.get("design_principles", []):
                entry = design_principles.setdefault(dp, {"count": 0, "sources": set()})
                entry["count"] += 1
                entry["sources"].add(src)

            for mech in core.get("action_mechanisms", []):
                entry = action_mechanisms.setdefault(mech, {"count": 0, "sources": set()})
                entry["count"] += 1
                entry["sources"].add(src)
                # record co-occurrence with each target organism in this document
                for tgt in core.get("target_organisms", []):
                    pair = (mech, tgt)
                    mech_target_counts[pair] = mech_target_counts.get(pair, 0) + 1

            for tgt in core.get("target_organisms", []):
                entry = target_organisms.setdefault(tgt, {"count": 0, "sources": set()})
                entry["count"] += 1
                entry["sources"].add(src)

            # Optional: collect experimental MIC values (normalized to μM when available)
            evidence = item.get("evidence_bank", {})
            for ev in evidence.get("experimental_values", []):
                try:
                    val = ev.get("normalized_value_uM") or ev.get("original_value")
                    if isinstance(val, (int, float)):
                        # we will aggregate these later into summary statistics
                        experimental_values.append(float(val))
                except Exception:
                    continue

        def _normalize(mapping: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
            items: List[Dict[str, Any]] = []
            for name, info in mapping.items():
                items.append({
                    "name": name,
                    "count": info.get("count", 0),
                    "sources": sorted(list(info.get("sources", [])))
                })
            # sort by count desc so that the most common concepts come first
            items.sort(key=lambda x: x["count"], reverse=True)
            return items

        # Aggregate simple statistics for experimental MIC values if available
        experimental_stats: Dict[str, Any] = {}
        if experimental_values:
            try:
                vals = sorted(experimental_values)
                n = len(vals)
                experimental_stats = {
                    "count": n,
                    "min_uM": min(vals),
                    "max_uM": max(vals),
                    "mean_uM": sum(vals) / n if n > 0 else None,
                }
            except Exception as e:
                logger.warning(f"⚠️ Failed to aggregate experimental MIC stats: {e}")

        mechanism_target_matrix: List[Dict[str, Any]] = []
        if mech_target_counts:
            for (mech, tgt), c in mech_target_counts.items():
                mechanism_target_matrix.append({
                    "mechanism": mech,
                    "target": tgt,
                    "count": c,
                })
            mechanism_target_matrix.sort(key=lambda x: x["count"], reverse=True)

        overview = {
            "design_principles": _normalize(design_principles),
            "action_mechanisms": _normalize(action_mechanisms),
            "target_organisms": _normalize(target_organisms),
            "experimental_values_stats": experimental_stats,
            "mechanism_target_matrix": mechanism_target_matrix,
        }

        return {
            "success": True,
            "results": [
                {
                    "content": overview,
                    "source": "integrated_ontology",
                    "relevance_score": 1.0,
                    "type": "ontology_overview"
                }
            ],
            "total_found": 1,
            "query": query,
            "knowledge_type": "ontology"
        }

    # Legacy vector-based search mode
    if search_knowledge is None:
        return {
            "success": False,
            "error": "search_knowledge not loaded",
            "results": [],
            "query": query,
            "knowledge_type": knowledge_type
        }
    
    try:
        result = search_knowledge(query=query, knowledge_type=knowledge_type, top_k=top_k)
        # Ensure query/knowledge_type are always present for downstream Agent reasoning
        if isinstance(result, dict):
            result.setdefault("query", query)
            result.setdefault("knowledge_type", knowledge_type)
        return result
    except Exception as e:
        logger.error(f"search_knowledge function call failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "results": [],
            "query": query,
            "knowledge_type": knowledge_type
        }


def tool_analyze_sequence(sequence: str) -> Dict[str, Any]:
    """Analyze a single peptide sequence for physicochemical properties and predictions.
    
    Args:
        sequence: Peptide amino acid sequence (e.g., 'KLLKLLK')
    
    Returns:
        Dict containing:
        - sequence: Original sequence
        - length: Sequence length
        - basic_properties: {charge, hydrophobicity, etc.}
        - predictions: {is_amp, amp_score, mic_value, hemolysis_score, cpp_score}
        - interpretation: Human-readable analysis
    """
    if not sequence or not isinstance(sequence, str):
        return {
            "success": False,
            "error": "Invalid sequence: must be a non-empty string"
        }
    
    # Clean sequence
    seq = sequence.strip().upper()
    
    # Basic properties calculation
    length = len(seq)
    
    # Charge calculation (K, R: +1; D, E: -1)
    positive = sum(seq.count(aa) for aa in 'KR')
    negative = sum(seq.count(aa) for aa in 'DE')
    net_charge = positive - negative
    
    # Hydrophobicity (simple Kyte-Doolittle scale approximation)
    hydrophobic_aas = 'AILMFVW'
    hydrophobic_count = sum(seq.count(aa) for aa in hydrophobic_aas)
    hydrophobicity_ratio = hydrophobic_count / length if length > 0 else 0
    
    # Amphipathicity indicator (mixed charge and hydrophobic)
    amphipathic_score = (positive + hydrophobic_count) / length if length > 0 else 0
    
    basic_properties = {
        "length": length,
        "net_charge": net_charge,
        "positive_residues": positive,
        "negative_residues": negative,
        "hydrophobic_residues": hydrophobic_count,
        "hydrophobicity_ratio": round(hydrophobicity_ratio, 3),
        "amphipathic_score": round(amphipathic_score, 3)
    }
    
    # Call prediction services
    predictions = {
        "is_amp": None,
        "amp_score": None,
        "mic_value": None,
        "mic_unit": "μM",
        "hemolysis_score": None,
        "is_toxic": None,
        "cpp_score": None,
        "is_cpp": None
    }
    
    try:
        # Use batch evaluate to get all predictions
        eval_result = tool_batch_evaluate([{"sequence": seq, "generator": "User Input"}])
        if eval_result and len(eval_result) > 0:
            pred = eval_result[0]
            predictions["is_amp"] = pred.get("is_amp")
            predictions["amp_score"] = pred.get("amp_score")
            predictions["mic_value"] = pred.get("mic_value")
            predictions["mic_unit"] = pred.get("mic_unit", "μM")
            predictions["hemolysis_score"] = pred.get("hemolysis_score")
            predictions["is_toxic"] = pred.get("is_toxic")
            predictions["cpp_score"] = pred.get("cpp_score")
            predictions["is_cpp"] = pred.get("is_cpp")
    except Exception as e:
        logger.warning(f"⚠️ Prediction services failed: {e}")
    
    # Generate interpretation
    interpretation = []
    
    # AMP classification
    if predictions["is_amp"]:
        interpretation.append(f"✅ Classified as AMP (score: {predictions['amp_score']:.3f})")
    else:
        interpretation.append(f"❌ Not classified as AMP (score: {predictions['amp_score']:.3f})")
    
    # MIC
    if predictions["mic_value"] is not None:
        mic_val = predictions["mic_value"]
        if mic_val < 5:
            interpretation.append(f"🎯 Excellent potency: MIC = {mic_val:.2f} μM (< 5 μM)")
        elif mic_val < 10:
            interpretation.append(f"✅ Good potency: MIC = {mic_val:.2f} μM (5-10 μM)")
        else:
            interpretation.append(f"⚠️ Moderate potency: MIC = {mic_val:.2f} μM (> 10 μM)")
    
    # Hemolysis
    if predictions["hemolysis_score"] is not None:
        hemo = predictions["hemolysis_score"]
        if predictions["is_toxic"]:
            interpretation.append(f"⚠️ High hemolysis risk: {hemo:.3f} (> 0.5)")
        else:
            interpretation.append(f"✅ Low hemolysis: {hemo:.3f} (< 0.5)")
    
    # CPP
    if predictions["cpp_score"] is not None:
        cpp = predictions["cpp_score"]
        if predictions["is_cpp"]:
            interpretation.append(f"⚠️ High cell penetration: CPP = {cpp:.3f} (may cause cytotoxicity)")
        else:
            interpretation.append(f"✅ Low cell penetration: CPP = {cpp:.3f}")
    
    # Structural features
    if net_charge > 3:
        interpretation.append(f"🔋 Highly cationic (+{net_charge}): favors bacterial membrane binding")
    elif net_charge < 0:
        interpretation.append(f"⚠️ Anionic charge ({net_charge}): unusual for AMPs")
    
    if hydrophobicity_ratio > 0.5:
        interpretation.append(f"💧 High hydrophobicity ({hydrophobicity_ratio:.2f}): may enhance membrane insertion")
    
    return {
        "success": True,
        "sequence": seq,
        "basic_properties": basic_properties,
        "predictions": predictions,
        "interpretation": interpretation
    }


def tool_query_ontology(facet: str = "overview") -> Dict[str, Any]:
    """
    Query structured AMP ontology with facet-based navigation.
    
    Provides access to aggregated domain knowledge extracted from literature:
    - Design principles (e.g., "cationic charge", "hydrophobicity")
    - Action mechanisms (e.g., "membrane disruption", "pore formation")
    - Target organisms (e.g., "E. coli", "S. aureus")
    - Experimental MIC statistics
    - Mechanism-target co-occurrence matrix
    
    Args:
        facet: Data facet to return. Options:
            - 'overview': Full ontology (all facets)
            - 'design_principles': Design principles only
            - 'action_mechanisms': Mechanisms of action only
            - 'target_organisms': Target organisms only
            - 'experimental_values_stats': MIC statistics
            - 'mechanism_target_matrix': Mechanism-target co-occurrence
    
    Returns:
        Dict with keys:
            - success (bool): Operation status
            - facet (str): Echo of requested facet
            - data (list | dict): Facet-specific data structure
    
    Examples:
        >>> # Get all design principles
        >>> result = tool_query_ontology("design_principles")
        >>> result['data'][0]
        {'name': 'cationic charge', 'count': 45, 'sources': [...]}
        
        >>> # Get MIC statistics
        >>> stats = tool_query_ontology("experimental_values_stats")
        >>> stats['data']['mean_uM']
        8.5
    
    Notes:
        - Prioritizes database (Graph RAG) if available
        - Falls back to JSON-based aggregation
        - All counts represent document frequencies
    """
    # Prioritize database query for ontology overview (Graph RAG friendly)
    if _ontology_db_manager is not None:
        try:
            overview = _ontology_db_manager.get_ontology_overview()
            if facet == "overview":
                data = overview
            elif facet in ["design_principles", "action_mechanisms", "target_organisms", "mechanism_target_matrix"]:
                data = overview.get(facet, [])
            elif facet == "experimental_values_stats":
                data = overview.get("experimental_values_stats", {})
            else:
                data = overview

            return {
                "success": True,
                "facet": facet,
                "data": data,
            }
        except Exception as e:
            logger.warning(f"⚠️ Failed to query ontology from database, falling back to JSON overview: {e}")

    # Fallback: Directly call ontology mode of search_knowledge (JSON aggregation)
    base = tool_search_knowledge(query="", knowledge_type="ontology", top_k=1)
    if not base.get("success"):
        return base
    results = base.get("results") or []
    if not results:
        return {
            "success": False,
            "error": "No ontology overview available",
            "facet": facet,
        }

    content = results[0].get("content") or {}

    if facet == "overview":
        data = content
    elif facet in ["design_principles", "action_mechanisms", "target_organisms", "mechanism_target_matrix"]:
        data = content.get(facet, [])
    elif facet == "experimental_values_stats":
        data = content.get("experimental_values_stats", {})
    else:
        data = content

    return {
        "success": True,
        "facet": facet,
        "data": data,
    }


def tool_query_mechanisms_for_target(target: str, limit: int = 5) -> Dict[str, Any]:
    """
    Query effective action mechanisms for specific target organism (Graph RAG).
    
    This function searches the literature-derived ontology for mechanisms that
    are documented to be effective against the specified pathogen. Results are
    ranked by document frequency (higher = more evidence).
    
    Args:
        target: Target organism name (e.g., "E.coli", "S.aureus", "Gram-negative")
        limit: Maximum number of results to return (default: 5)
    
    Returns:
        Dict with keys:
            - success (bool): Operation status
            - target (str): Echo of input target
            - mechanisms (list): List of mechanism dicts with:
                - mechanism (str): Mechanism name
                - doc_count (int): Number of supporting documents
                - evidence_docs (list): List of evidence document IDs
            - source (str, optional): "ontology_fallback" if Graph RAG unavailable
    
    Examples:
        >>> result = tool_query_mechanisms_for_target("E.coli")
        >>> result['mechanisms'][0]
        {'mechanism': 'membrane_disruption', 'doc_count': 12, 'evidence_docs': [...]}
    
    Notes:
        - Prioritizes Graph RAG backend if available
        - Falls back to mechanism_target_matrix from ontology
        - Results sorted by document frequency (descending)
    """
    try:
        # Attempt to query from Graph RAG backend
        from graph_rag import query_mechanisms_for_target
        result = query_mechanisms_for_target(target, limit)
        
        if result.get("success"):
            return result
        else:
            # If Graph RAG unavailable, fallback to ontology overview
            logger.warning(f"⚠️  Graph RAG query failed, falling back to ontology overview")
            overview = tool_query_ontology(facet="mechanism_target_matrix")
            if overview.get("success"):
                matrix = overview.get("data", [])
                # Filter mechanisms matching target
                filtered = [m for m in matrix if target.lower() in m.get("target", "").lower()]
                # Sort by count descending
                filtered.sort(key=lambda x: x.get("count", 0), reverse=True)
                # Convert format
                mechanisms = []
                for item in filtered[:limit]:
                    mechanisms.append({
                        "mechanism": item.get("mechanism"),
                        "doc_count": item.get("count"),
                        "evidence_docs": []  
                    })
                return {
                    "success": True,
                    "target": target,
                    "mechanisms": mechanisms,
                    "source": "ontology_fallback"
                }
            
            return {"success": False, "error": "Failed to query mechanisms"}
            
    except Exception as e:
        logger.error(f"❌ Failed to query mechanisms for target {target}: {e}")
        return {"success": False, "error": str(e)}


def tool_query_principles_for_mechanism(mechanism: str, limit: int = 5) -> Dict[str, Any]:
    """
    Query design principles co-occurring with specific mechanism (Graph RAG).
    
    This function searches the literature-derived ontology for design principles
    that are documented in the same context as the specified mechanism, revealing
    common design strategies for that mechanism.
    
    Args:
        mechanism: Mechanism name (e.g., "membrane_disruption", "pore_formation")
        limit: Maximum number of results to return (default: 5)
    
    Returns:
        Dict with keys:
            - success (bool): Operation status
            - mechanism (str): Echo of input mechanism
            - design_principles (list): List of principle dicts with:
                - principle (str): Principle name
                - doc_count (int): Number of supporting documents
                - evidence_docs (list): List of evidence document IDs
    
    Examples:
        >>> result = tool_query_principles_for_mechanism("membrane_disruption")
        >>> result['design_principles'][0]
        {'principle': 'cationic_enhancement', 'doc_count': 8, 'evidence_docs': [...]}
    
    Notes:
        - Requires Graph RAG backend (no fallback available)
        - Results sorted by document frequency (descending)
        - Returns error if Graph RAG unavailable
    """
    try:
        # Attempt to query from Graph RAG backend
        from graph_rag import query_principles_for_mechanism
        result = query_principles_for_mechanism(mechanism, limit)
        
        if result.get("success"):
            return result
        else:
            # If Graph RAG unavailable, return error
            logger.warning(f"⚠️  Graph RAG query failed for mechanism {mechanism}")
            return {"success": False, "error": "Graph RAG backend not available"}
            
    except Exception as e:
        logger.error(f"❌ Failed to query principles for mechanism {mechanism}: {e}")
        return {"success": False, "error": str(e)}


# ==================== Visualization Tools ====================

def tool_visualize_generator_comparison(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate multi-generator comparison dashboard (2x2 subplot layout).
    
    Creates a comprehensive 4-panel visualization for benchmarking multiple
    AMP generators across different evaluation dimensions:
    
    Panel 1 (Radar): Overall performance metrics (potency, safety, AMP score)
    Panel 2 (Box): MIC distribution comparison
    Panel 3 (Bar): Amino acid composition analysis
    Panel 4 (Scatter): Sequence property relationships
    
    Args:
        results: List of evaluation results with keys:
            - sequence (str): Amino acid sequence
            - generator (str): Generator identifier ('default', 'diverse', 'refine')
            - mic_value (float): MIC in μM
            - hemolysis_score (float): Hemolysis probability
            - cpp_score (float): CPP probability
            - amp_score (float): AMP classification score
    
    Returns:
        Dict with keys:
            - status (str): 'success' or 'error'
            - html (str): Plotly HTML for embedding (if success)
            - error (str): Error message (if failed)
    
    Examples:
        >>> data = [{"sequence": "KKLFKKILKYL", "generator": "default", ...}]
        >>> viz = tool_visualize_generator_comparison(data)
        >>> assert viz['status'] == 'success'
    
    Notes:
        - Generator labels mapped: default→AMP-Designer, diverse→Diff-AMP, refine→HydrAMP
        - Light theme optimized for publication
        - Requires plotly library
    """
    import pandas as pd
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import plotly.express as px
    import plotly.io as pio
    from collections import Counter

    # 1. Data validation
    if not results:
        return {"status": "error", "error": "No data available"}

    df = pd.DataFrame(results)
    if 'generator' not in df.columns: df['generator'] = 'Unknown'

    # Generator name mapping (convert code names to display names)
    name_map = {
        "default": "AMP-Designer",
        "refine": "HydrAMP",
        "diverse": "Diff-AMP",
        "mic_model": "Discriminator"
    }
    df['generator_display'] = df['generator'].map(lambda x: name_map.get(str(x), str(x)))
    
    # Force numeric conversion
    numeric_cols = ['mic_value', 'hemolysis_score', 'cpp_score', 'amp_score', 'net_charge', 'hydrophobic_moment']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Define light color theme
    colors = ['#2E86C1', '#E74C3C', '#27AE60', '#8E44AD']
    generators_list = df['generator_display'].unique()

    # =================================================
    # Create 2x2 subplot layout
    # =================================================
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            "Model Performance Overview",
            "MIC Distribution",
            "Amino Acid Composition",
            "Sequence Properties"
        ),
        specs=[
            [{"type": "scatterpolar"}, {"type": "box"}],
            [{"type": "bar"}, {"type": "scatter"}]
        ],
        vertical_spacing=0.16, 
        horizontal_spacing=0.12,
        row_heights=[0.5, 0.5],
        column_widths=[0.5, 0.5]
    )

    # =================================================
    # Panel 1: Comprehensive Radar Chart - Top Left
    # =================================================
    metrics_summary = []
    for gen in generators_list:
        sub = df[df['generator_display'] == gen]
        mic = sub['mic_value'].dropna()
        mic_score = max(0, min(1, (64 - mic.mean()) / 64)) if not mic.empty else 0.1
        hemo = sub['hemolysis_score'].dropna()
        safe_score = max(0, min(1, 1.0 - hemo.mean())) if not hemo.empty else 0.5
        amp = sub['amp_score'].dropna()
        amp_score = amp.mean() if not amp.empty else 0.1
            
        metrics_summary.append({
            "Generator": gen, 
            "Potency": mic_score, "Safety": safe_score, "AMP Probability": amp_score, "Stability": 0.85
        })
        
    # Adjust label order (Potency at top with 45-degree rotation)
    categories = ['Potency', 'Safety', 'AMP Probability', 'Stability']  # Restore original order
    for idx, item in enumerate(metrics_summary):
        vals = [item[c] for c in categories]
        vals += [vals[0]]
        fig.add_trace(
            go.Scatterpolar(
                r=vals, theta=categories + [categories[0]], 
                fill='toself', name=item['Generator'],
                line=dict(color=colors[idx % len(colors)], width=2),
                opacity=0.6,
                showlegend=True
            ),
            row=1, col=1
        )

    # =================================================
    # Panel 2: MIC Distribution (Box Plot) - Top Right
    # =================================================
    if 'mic_value' in df.columns:
        for idx, gen in enumerate(generators_list):
            sub_data = df[df['generator_display'] == gen]['mic_value'].dropna()
            fig.add_trace(
                go.Box(
                    y=sub_data,
                    name=gen,
                    marker_color=colors[idx % len(colors)],
                    boxpoints='all',
                    showlegend=False
                ),
                row=1, col=2
            )

    # =================================================
    # Panel 3: Amino Acid Composition (Bar Chart) - Bottom Left
    # =================================================
    aa_counts = []
    for gen in generators_list:
        seqs = "".join(df[df['generator_display'] == gen]['sequence'].tolist())
        counts = Counter(seqs)
        total = sum(counts.values()) if counts else 1
        for aa, count in counts.items():
            aa_counts.append({"Generator": gen, "AA": aa, "Freq": count/total})
            
    if aa_counts:
        df_aa = pd.DataFrame(aa_counts).sort_values("AA")
        for idx, gen in enumerate(generators_list):
            sub_aa = df_aa[df_aa['Generator'] == gen]
            fig.add_trace(
                go.Bar(
                    x=sub_aa['AA'],
                    y=sub_aa['Freq'],
                    name=gen,
                    marker_color=colors[idx % len(colors)],
                    showlegend=False
                ),
                row=2, col=1
            )

    # =================================================
    # Panel 4: Sequence Properties (Scatter) - Bottom Right
    # =================================================
    if 'length' not in df.columns: df['length'] = df['sequence'].apply(len)
    def calc_charge(s): return s.count('K') + s.count('R') - s.count('D') - s.count('E')
    if 'net_charge' not in df.columns: df['net_charge'] = df['sequence'].apply(calc_charge)

    for idx, gen in enumerate(generators_list):
        sub_scatter = df[df['generator_display'] == gen]
        fig.add_trace(
            go.Scatter(
                x=sub_scatter['length'],
                y=sub_scatter['net_charge'],
                mode='markers',
                name=gen,
                marker=dict(
                    size=sub_scatter['amp_score'] * 20,
                    color=colors[idx % len(colors)],
                    opacity=0.7
                ),
                text=sub_scatter['sequence'],
                hovertemplate='<b>%{text}</b><br>Length: %{x}<br>Charge: %{y}<extra></extra>',
                showlegend=False
            ),
            row=2, col=2
        )

    # =================================================
    # Global Layout Configuration
    # =================================================
    fig.update_layout(
        height=1000,  # Reduced height (removed main title)
        width=1400,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.12,
            xanchor="center",
            x=0.5,
            font=dict(size=12, color='#333')
        ),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='white',
        font=dict(color='#333333', family="Arial, sans-serif", size=11),
        # Removed main title (using frontend title instead)
        # title=dict(...),  # deleted
        margin=dict(l=60, r=60, t=40, b=100)  # Further reduced top margin
    )
    
    # Adjust subplot title font size
    for ann in fig.layout.annotations:
        ann.font.size = 13  # Reduce title font size

    # Adjust subplot axes
    fig.update_xaxes(title_text="Generator", row=1, col=2, tickangle=0)
    fig.update_yaxes(title_text="MIC (μM)", range=[-5, 25], row=1, col=2)
    fig.update_xaxes(title_text="Amino Acid", row=2, col=1, tickangle=0)
    fig.update_yaxes(title_text="Frequency", row=2, col=1)
    fig.update_xaxes(title_text="Length", row=2, col=2)
    fig.update_yaxes(title_text="Net Charge", row=2, col=2)

    # Radar chart specific settings
    fig.update_polars(
        radialaxis=dict(
            visible=True, 
            range=[0, 1], 
            gridcolor='#ddd', 
            linecolor='#ccc'
        ),
        angularaxis=dict(
            gridcolor='#ddd', 
            linecolor='#ccc', 
            tickfont=dict(size=8, color='#333'),
            rotation=45  # Rotate 45 degrees, placing first label at top-right
        )
    )

    # Use CDN for Plotly, enable responsive rendering
    dashboard_html = pio.to_html(
        fig, 
        full_html=False, 
        include_plotlyjs='cdn', 
        config={
            'displayModeBar': True,  # Show toolbar with download button
            'responsive': True,
            'modeBarButtonsToAdd': ['downloadSvg'],  # Add SVG download option
            'toImageButtonOptions': {
                'format': 'png',
                'filename': 'multi_generator_comparison_dashboard',
                'height': 1000,
                'width': 1400,
                'scale': 2  # 2x resolution for better quality
            }
        }
    )

    return {
        "status": "success",
        "message": "Visualization generated",
        "charts": {"dashboard": dashboard_html},  # Return single merged chart
        "summary": metrics_summary
    }
    
def tool_visualize_peptide_structure(sequence: str = None, mic: float = None, hemo: float = None, cpp: float = None, macrel: float = None) -> Dict:
    """
    Generate visualizations for a single peptide sequence
    
    Args:
        sequence: Peptide sequence (e.g., 'KWKLFKKIGAVLKVL') - REQUIRED
        mic: Optional MIC value (μM) - not used in current visualizations
        hemo: Optional hemolysis score (0-1) - not used in current visualizations
        cpp: Optional CPP score (0-1) - not used in current visualizations
        macrel: Optional Macrel AMP probability (0-1) - not used in current visualizations
    
    Returns:
        Dictionary containing chart HTMLs: {'wheel': html, 'hydro': html}
        Note: Radar chart removed due to incompatible units (MIC in μM, scores in 0-1, charge in +/-)
    """
    try:
        from peptide_visualizer import PeptideVisualizer
        
        # Validate sequence parameter
        if sequence is None or not sequence:
            return {"error": "Missing required parameter: 'sequence'. Please provide a peptide sequence (e.g., 'KWKLFKKIGAVLKVL')"}
        
        if len(sequence) < 5:
            return {"error": f"Invalid sequence: '{sequence}' is too short. Must be at least 5 amino acids."}
        
        # Generate all plots
        charts = PeptideVisualizer.generate_all_plots(
            sequence=sequence.upper(),
            mic=mic,
            hemo=hemo,
            cpp=cpp,
            macrel=macrel
        )
        
        # Convert to HTML (skip entries that are already strings or not Figure objects)
        import plotly.graph_objects as go
        result = {}
        for chart_name, fig in charts.items():
            if isinstance(fig, go.Figure):
                result[chart_name] = fig.to_html(
                    include_plotlyjs='cdn',
                    config={'displayModeBar': False}
                )
            elif isinstance(fig, str):
                result[chart_name] = fig  # already HTML
        
        logger.info(f"✅ Generated 2 visualizations for sequence: {sequence[:10]}...")
        return {
            **result,
            "message": f"Generated 2 visualizations: Helical Wheel, Hydrophobicity Profile"
        }
        
    except Exception as e:
        logger.error(f"Peptide visualization failed: {e}")
        return {"error": f"Visualization generation failed: {str(e)}"}


def tool_analyze_structure_basic(pdb_content: str) -> Dict[str, Any]:
    """Lightweight geometric analysis of a single-peptide PDB structure.

    This function parses CA atom coordinates from a PDB string and computes
    approximate structural metrics without external MD packages.

    Returns a dictionary with:
        - length: number of residues with CA atoms
        - residue_ids: sorted residue indices
        - rg: radius of gyration (Å)
        - contact_density: number of medium/long-range CA-CA contacts per residue
        - kink_positions: residue indices where backbone bend angle is large
        - helix_like_fraction: 1 - (kink_count / length), rough helix-like estimate
    """
    import math

    if not pdb_content:
        return {"error": "Empty PDB content"}

    ca_coords = {}
    for line in pdb_content.splitlines():
        if not line.startswith("ATOM"):
            continue
        atom_name = line[12:16].strip()
        if atom_name != "CA":
            continue
        try:
            resseq = int(line[22:26].strip())
            x = float(line[30:38])
            y = float(line[38:46])
            z = float(line[46:54])
        except ValueError:
            continue
        ca_coords[resseq] = (x, y, z)

    residue_ids = sorted(ca_coords.keys())
    n = len(residue_ids)
    if n < 3:
        return {"error": f"Not enough CA atoms for analysis (found {n})"}

    points = [ca_coords[i] for i in residue_ids]

    # Radius of gyration
    cx = sum(p[0] for p in points) / n
    cy = sum(p[1] for p in points) / n
    cz = sum(p[2] for p in points) / n
    rg_sq = sum((p[0]-cx)**2 + (p[1]-cy)**2 + (p[2]-cz)**2 for p in points) / n
    rg = math.sqrt(max(rg_sq, 0.0))

    # Medium/long-range contacts based on CA-CA distance (< 8 Å, |i-j| > 2)
    contact_count = 0
    for i_idx in range(n):
        x1, y1, z1 = points[i_idx]
        for j_idx in range(i_idx + 1, n):
            # skip short-range neighbours
            if abs(residue_ids[j_idx] - residue_ids[i_idx]) <= 2:
                continue
            x2, y2, z2 = points[j_idx]
            dx = x1 - x2
            dy = y1 - y2
            dz = z1 - z2
            dist_sq = dx*dx + dy*dy + dz*dz
            if dist_sq <= 64.0:  # 8 Å cutoff
                contact_count += 1
    contact_density = contact_count / float(n)

    # Backbone bend-based "kink" detection
    kink_positions: List[int] = []
    for idx in range(1, n - 1):
        x0, y0, z0 = points[idx - 1]
        x1, y1, z1 = points[idx]
        x2, y2, z2 = points[idx + 1]
        v1 = (x1 - x0, y1 - y0, z1 - z0)
        v2 = (x2 - x1, y2 - y1, z2 - z1)
        len1 = math.sqrt(v1[0]**2 + v1[1]**2 + v1[2]**2)
        len2 = math.sqrt(v2[0]**2 + v2[1]**2 + v2[2]**2)
        if len1 < 1e-6 or len2 < 1e-6:
            continue
        dot = v1[0]*v2[0] + v1[1]*v2[1] + v1[2]*v2[2]
        cosang = dot / (len1 * len2)
        # numerical safety
        cosang = max(-1.0, min(1.0, cosang))
        angle_deg = math.degrees(math.acos(cosang))
        # Mark positions with large bends (threshold 40°, adjustable)
        if angle_deg > 40.0:
            kink_positions.append(residue_ids[idx])

    helix_like_fraction = max(0.0, 1.0 - len(kink_positions) / float(n))

    return {
        "length": n,
        "residue_ids": residue_ids,
        "rg": rg,
        "contact_density": contact_density,
        "kink_positions": kink_positions,
        "helix_like_fraction": helix_like_fraction,
    }

# ==================== Structure Prediction and Discrimination ====================


def _compute_structure_features(pdb_content: str) -> dict:
    """Extract multi-dimensional structural features from ESMFold PDB string.
    Uses Bio.PDB.PPBuilder + Ramachandran partitioning, no mkdssp needed."""
    import math
    result = {
        "helix_fraction": 0.0, "sheet_fraction": 0.0, "coil_fraction": 1.0,
        "mean_plddt": 0.0, "rg": 0.0, "contact_density": 0.0,
    }
    if not pdb_content:
        return result
    try:
        from Bio.PDB import PDBParser, PPBuilder
        import io
        parser = PDBParser(QUIET=True)
        struct = parser.get_structure("seq", io.StringIO(pdb_content))
        bfacs, ca_coords_list = [], []
        for model in struct:
            for chain in model:
                for residue in chain:
                    if "CA" in residue:
                        ca = residue["CA"]
                        bfacs.append(ca.get_bfactor())
                        ca_coords_list.append(ca.get_vector())
        if bfacs:
            # ESMFold B-factor stores pLDDT in 0~1 range directly
            result["mean_plddt"] = round(sum(bfacs) / len(bfacs), 4)
        ppb = PPBuilder()
        total, n_helix, n_sheet = 0, 0, 0
        for pp in ppb.build_peptides(struct):
            for phi, psi in pp.get_phi_psi_list():
                total += 1
                if phi is None or psi is None:
                    continue
                phi_d, psi_d = math.degrees(phi), math.degrees(psi)
                if -160 < phi_d < -40 and -60 < psi_d < 60:
                    n_helix += 1
                elif phi_d < -100 and (psi_d > 90 or psi_d < -150):
                    n_sheet += 1
        if total > 0:
            result["helix_fraction"] = round(n_helix / total, 4)
            result["sheet_fraction"] = round(n_sheet / total, 4)
            result["coil_fraction"] = round(max(0.0, 1.0 - n_helix/total - n_sheet/total), 4)
        n = len(ca_coords_list)
        if n >= 3:
            vecs = [v.get_array() for v in ca_coords_list]
            import numpy as _np2
            center = _np2.mean(vecs, axis=0)
            rg_sq = sum(float(((v - center) ** 2).sum()) for v in vecs) / n
            result["rg"] = round(float(math.sqrt(max(rg_sq, 0.0))), 4)
            contacts = sum(
                1 for i in range(n) for j in range(i+1, n)
                if abs(i-j) > 2 and float(((vecs[i]-vecs[j])**2).sum()) <= 64.0
            )
            result["contact_density"] = round(contacts / float(n), 4)
    except Exception as e:
        logger.warning(f"_compute_structure_features failed: {e}")
    return result


_DEFAULT_SCORE_WEIGHTS = {
    # Activity & Safety (50%): MIC 30% + Hemolysis 15% + CPP 5%
    "mic": 0.30, "hemolysis": 0.15, "cpp": 0.05,
    # Structure (50%): Helix 20% + pLDDT 20% + Compactness 10%
    "helix": 0.20, "plddt": 0.20, "compactness": 0.10,
}


def _balanced_multidim_rank(candidates: list, weights: dict) -> list:
    """Multi-dimensional composite scoring: min-max normalized weighted sum, lower = better."""
    if not candidates:
        return candidates
    total_w = sum(weights.values()) or 1.0
    w = {k: v / total_w for k, v in weights.items()}

    def _get_val(item, key):
        # Use 'is None' check to avoid treating 0.0 as falsy (e.g. cpp_pred=0.0 would be skipped by 'or')
        def _first_not_none(*keys_list):
            for k in keys_list:
                v = item.get(k)
                if v is not None:
                    return v
            return None
        if key == "mic":        return _first_not_none("mic_pred", "mic_value")
        if key == "hemolysis":
            v = _first_not_none("hemolysis_pred", "hemolysis_score")
            if v is not None and v > 1.5: v = v / 100.0
            return v
        if key == "cpp":        return _first_not_none("cpp_pred", "cpp_score")
        if key == "helix":      return (item.get("struct_features") or {}).get("helix_fraction")
        if key == "plddt":      return (item.get("struct_features") or {}).get("mean_plddt")
        if key == "compactness": return (item.get("struct_features") or {}).get("contact_density")
        return None

    dim_keys = list(w.keys())
    dim_vals = {k: [_get_val(item, k) for item in candidates] for k in dim_keys}
    HIGHER_BETTER = {"helix", "plddt", "compactness"}  # cpp is lower-is-better (less cell penetration = safer)
    # MIC uses log-scale normalization to avoid extreme outliers distorting the composite score
    LOG_SCALE = {"mic"}

    import math as _math

    def _normalize(vals, log_scale=False):
        valid = [v for v in vals if v is not None and v > 0]
        if not valid: return [0.5] * len(vals)
        if log_scale:
            log_vals = [_math.log(v) if v and v > 0 else None for v in vals]
            valid_log = [v for v in log_vals if v is not None]
            mn, mx = min(valid_log), max(valid_log)
            mean_v = sum(valid_log) / len(valid_log)
            return [(((v if v is not None else mean_v) - mn) / (mx - mn)) if mx != mn else 0.5 for v in log_vals]
        mn, mx = min(valid), max(valid)
        mean_v = sum(valid) / len(valid)
        return [(((v if v is not None else mean_v) - mn) / (mx - mn)) if mx != mn else 0.5 for v in vals]

    norm_vals = {}
    for k in dim_keys:
        nv = _normalize(dim_vals[k], log_scale=(k in LOG_SCALE))
        norm_vals[k] = [1.0 - x for x in nv] if k in HIGHER_BETTER else nv

    n = len(candidates)
    scores = [sum(w[k] * norm_vals[k][i] for k in dim_keys) for i in range(n)]
    for i, item in enumerate(candidates):
        item["composite_score"] = round(scores[i], 6)
        item["score_breakdown"] = {k: round(norm_vals[k][i], 4) for k in dim_keys}

    return sorted(candidates, key=lambda x: x["composite_score"])

def tool_structure_discrimination_pipeline(
    target: str = "Gram-negative",
    num_samples: int = 10,
    pgat_threshold: float = 0.5,
    generator: str = "default",
    mic_threshold: float = 32.0,
    hemolysis_threshold: float = 10.0
) -> Dict[str, Any]:
    """
    Complete structure-based AMP design and screening pipeline.
    
    This is the RECOMMENDED workflow for structure-aware AMP discovery.
    Unlike sequence-only methods, this pipeline validates 3D foldability
    and uses structure-based discrimination (PGAT-ABPp) for higher-confidence
    predictions.
    
    Pipeline Stages:
    1. **Generation**: Create candidate sequences with specified generator
    2. **Structure Prediction**: ESMFold 3D structure modeling
    3. **Structure Discrimination**: PGAT-ABPp binary classification (AMP vs non-AMP)
    4. **Activity Prediction**: MIC, hemolysis, CPP prediction for passed candidates
    5. **Filtering**: Apply user-defined thresholds
    
    Args:
        target: Target pathogen ("Gram-negative", "Gram-positive", "E.coli", etc.)
        num_samples: Number of sequences to generate (default: 10)
        pgat_threshold: PGAT-ABPp score threshold (default: 0.5)
        generator: Generator strategy ('default', 'diverse', 'refine')
        mic_threshold: Maximum acceptable MIC in μg/mL (default: 32.0)
        hemolysis_threshold: Maximum acceptable hemolysis % (default: 10.0)
    
    Returns:
        Dict with keys:
            - success (bool): Overall pipeline status
            - pipeline_stages (dict): Stage-wise counts:
                - generated (int): Initial sequences
                - structure_predicted (int): Successful ESMFold runs
                - passed_pgat (int): Passed PGAT discrimination
                - final_candidates (int): Met all thresholds
            - sequences (list): List of candidate dicts with:
                - sequence (str): Amino acid sequence
                - generator (str): Generator identifier
                - pgat_score (float): PGAT discrimination score
                - pgat_label (int): Binary label (1=AMP, 0=non-AMP)
                - structure_pdb (str): PDB file content
                - mic_pred (float): Predicted MIC
                - hemolysis_pred (float): Predicted hemolysis
                - cpp_pred (float): Predicted CPP
                - passes_thresholds (bool): Met all criteria
            - summary (str): Human-readable pipeline summary
            - errors (list): List of error messages
    
    Examples:
        >>> result = tool_structure_discrimination_pipeline(
        ...     target="E.coli",
        ...     num_samples=5,
        ...     pgat_threshold=0.7
        ... )
        >>> result['pipeline_stages']
        {'generated': 5, 'structure_predicted': 5, 'passed_pgat': 3, 'final_candidates': 2}
    
    Notes:
        - PGAT-ABPp requires Docker service: amp-pgat-abpp
        - ESMFold predictions written to /data/pgat_runs/<run_id>/
        - This pipeline is slower but more accurate than sequence-only methods
        - Use for final validation or when foldability is critical
    
    Warning:
        DO NOT use this pipeline for multi-generator comparison tasks.
        For benchmarking, use separate generation + evaluation to ensure fairness.
    """
    logger.info(f"🚀 Starting structure discrimination pipeline: target={target}, n={num_samples}, pgat_threshold={pgat_threshold}")
    
    result = {
        "success": False,
        "pipeline_stages": {
            "generated": 0,
            "structure_predicted": 0,
            "passed_pgat": 0,
            "final_candidates": 0
        },
        "sequences": [],
        "summary": "",
        "errors": []
    }
    
    try:
        # ============ Stage 1: Generate sequences ============
        logger.info("[Stage 1/5] Generating sequences...")
        generated_seqs = tool_generate_amp(
            num_samples=num_samples,
            prompt=target,
            generator=generator
        )
        
        if not generated_seqs:
            result["errors"].append("Generation failed: no sequences produced")
            return result
        
        result["pipeline_stages"]["generated"] = len(generated_seqs)
        logger.info(f"✅ Generated {len(generated_seqs)} sequences")
        
        # ============ Stage 2: Predict structures with ESMFold ============
        logger.info("[Stage 2/5] Predicting structures with ESMFold...")
        sequences_with_structure = []
        
        for idx, seq_item in enumerate(generated_seqs):
            seq = seq_item.get("sequence", "")
            if not seq:
                continue
            
            logger.info(f"  Predicting structure {idx+1}/{len(generated_seqs)}: {seq[:20]}...")
            try:
                structure_result = tool_predict_structure(sequence=seq)
                
                if structure_result.get("pdb_content"):
                    sequences_with_structure.append({
                        "sequence": seq,
                        "generator": seq_item.get("generator", generator),
                        "pdb_content": structure_result["pdb_content"],
                        "structure_info": structure_result.get("info", {})
                    })
                    logger.info(f"    ✅ Structure predicted")
                else:
                    logger.warning(f"    ⚠️ Structure prediction failed: {structure_result.get('error', 'unknown')}")
                    result["errors"].append(f"Structure prediction failed for {seq[:20]}...")
            except Exception as e:
                logger.error(f"    ❌ Structure prediction error: {e}")
                result["errors"].append(f"Structure error for {seq[:20]}...: {str(e)}")
        
        result["pipeline_stages"]["structure_predicted"] = len(sequences_with_structure)
        logger.info(f"✅ Predicted {len(sequences_with_structure)} structures")
        
        if not sequences_with_structure:
            result["summary"] = "Pipeline stopped: no structures could be predicted"
            return result
        
        # ============ Stage 3: PGAT-ABPp screening (structure discrimination) ============
        logger.info("[Stage 3/5] Running PGAT-ABPp discrimination...")
        
        # Start PGAT-ABPp service
        if _global_orchestrator:
            _global_orchestrator.start_tool("pgat_abpp")
            time.sleep(2)  # 等待服务启动
        
        # Write PDB files to shared volume for pgat-abpp container
        # backend container: ./data -> /app/data; PGAT container: ./data -> /data (same host dir)
        run_id = int(time.time() * 1000)
        shared_root_local = "/app/data/pgat_runs"  # backend container write path
        shared_root_pgat  = "/data/pgat_runs"       # PGAT container read path
        run_dir_local = os.path.join(shared_root_local, f"run_{run_id}")
        run_dir = os.path.join(shared_root_pgat, f"run_{run_id}")  # path sent to PGAT
        try:
            os.makedirs(run_dir_local, exist_ok=True)
        except Exception as e:
            logger.error(f"  ❌ Failed to create PGAT run directory {run_dir_local}: {e}")
            result["errors"].append(f"Failed to create PGAT run directory: {e}")
            # Fallback to placeholder PGAT scores
            for item in sequences_with_structure:
                item["pgat_score"] = 0.0
                item["pgat_label"] = 0
                item["pgat_note"] = "PGAT run directory creation failed"
        else:
            # Write PDB files (to backend container mount path)
            for idx, item in enumerate(sequences_with_structure):
                pdb_content = item.get("pdb_content", "")
                if not pdb_content:
                    continue
                filename = f"seq_{idx+1:03d}.pdb"
                pdb_path = os.path.join(run_dir_local, filename)
                try:
                    with open(pdb_path, "w") as f:
                        f.write(pdb_content)
                    item["pgat_pdb_file"] = pdb_path
                except Exception as e:
                    logger.error(f"  ❌ Failed to write PDB file for sequence {idx+1}: {e}")
                    result["errors"].append(f"Failed to write PDB file for sequence {idx+1}: {e}")
            
            # Call pgat-abpp /predict_from_pdb endpoint for structure discrimination
            try:
                health_check = requests.get(f"{SERVICES['PGAT_ABPP']}/health", timeout=30)
                if health_check.status_code == 200:
                    logger.info("  ✅ PGAT-ABPp service is healthy")
                    logger.info(f"  [Phase 2] Using PGAT-ABPp on PDB dir: {run_dir}")
                    pgat_result = requests.post(
                        f"{SERVICES['PGAT_ABPP']}/predict_from_pdb",
                        json={"pdb_dir": run_dir, "data_dir": run_dir},
                        timeout=600
                    )
                    if pgat_result.status_code == 200:
                        pgat_data = pgat_result.json()
                        logger.info(f"  ✅ PGAT-ABPp returned {pgat_data.get('num_samples', 0)} results")
                        scores = pgat_data.get("scores", [])
                        labels = pgat_data.get("labels", [])
                        filenames = pgat_data.get("filenames", []) or []
                        
                        # Build filename -> (score, label) mapping
                        score_map = {}
                        for fname, s, lbl in zip(filenames, scores, labels):
                            score_map[fname] = {"score": float(s), "label": int(lbl)}
                        
                        passed_count = 0
                        for idx, item in enumerate(sequences_with_structure):
                            filename = f"seq_{idx+1:03d}.pdb"
                            meta = score_map.get(filename)
                            if meta is not None:
                                item["pgat_score"] = meta["score"]
                                item["pgat_label"] = meta["label"]
                                item["pgat_note"] = "Phase 2: PGAT-ABPp score from structure"
                                if item["pgat_score"] >= pgat_threshold:
                                    passed_count += 1
                            else:
                                # No corresponding result, mark as failed
                                item["pgat_score"] = 0.0
                                item["pgat_label"] = 0
                                item["pgat_note"] = "PGAT result missing for this sequence"
                        result["pipeline_stages"]["passed_pgat"] = passed_count
                    else:
                        logger.warning(f"  ⚠️ PGAT prediction failed: {pgat_result.text[:200]}")
                        result["errors"].append(f"PGAT prediction failed: {pgat_result.status_code}")
                        for item in sequences_with_structure:
                            item["pgat_score"] = 0.0
                            item["pgat_label"] = 0
                            item["pgat_note"] = "PGAT service returned non-200 status"
                else:
                    logger.warning("  ⚠️ PGAT-ABPp service not healthy, skipping discrimination")
                    result["errors"].append("PGAT service health check failed")
                    for item in sequences_with_structure:
                        item["pgat_score"] = 0.0
                        item["pgat_label"] = 0
                        item["pgat_note"] = "Service unavailable"
            except Exception as e:
                logger.error(f"  ❌ PGAT-ABPp error: {e}")
                result["errors"].append(f"PGAT error: {str(e)}")
                for item in sequences_with_structure:
                    item["pgat_score"] = 0.0
                    item["pgat_label"] = 0
                    item["pgat_note"] = f"Error: {str(e)}"
        
        # Filter sequences that passed PGAT
        passed_sequences = [
            item for item in sequences_with_structure
            if item.get("pgat_score", 0) >= pgat_threshold
        ]
        
        logger.info(f"✅ {len(passed_sequences)} sequences passed PGAT screening (threshold={pgat_threshold})")
        
        if not passed_sequences:
            result["summary"] = f"Pipeline stopped: no sequences passed PGAT threshold ({pgat_threshold})"
            result["sequences"] = sequences_with_structure  
            return result
        
        # ============ Stage 4: Batch evaluation (MIC/Hemo/CPP) - without Macrel ============
        logger.info("[Stage 4/5] Predicting MIC/Hemolysis/CPP for passed candidates...")
        logger.info("  ℹ️  AMP discrimination already completed by PGAT-ABPp, skipping Macrel")
        
        sequences_only = [item["sequence"] for item in passed_sequences]
        
        # Call evaluation function without Macrel
        eval_results = tool_batch_evaluate_no_macrel(sequences_only)
        
        # Merge evaluation results
        for i, item in enumerate(passed_sequences):
            if i < len(eval_results):
                eval_data = eval_results[i]
                item["mic_pred"] = eval_data.get("mic", None)
                item["hemolysis_pred"] = eval_data.get("hemolysis", None)
                item["cpp_pred"] = eval_data.get("cpp", None)
                item["is_amp"] = item.get("pgat_label", 1)  
                
                # Determine if passes thresholds
                passes = True
                if item["mic_pred"] and item["mic_pred"] > mic_threshold:
                    passes = False
                if item["hemolysis_pred"] and item["hemolysis_pred"] > hemolysis_threshold:
                    passes = False
                
                item["passes_thresholds"] = passes
            else:
                item["mic_pred"] = None
                item["hemolysis_pred"] = None
                item["cpp_pred"] = None
                item["passes_thresholds"] = False
        
        logger.info("✅ Evaluation completed")
        
        # ============ Stage 4.5: Extract structure features ============
        logger.info("[Stage 4.5] Extracting structure features from PDB...")
        for item in passed_sequences:
            pdb = item.get("pdb_content", "")
            if pdb:
                item["struct_features"] = _compute_structure_features(pdb)
            else:
                item["struct_features"] = {}
        logger.info("✅ Structure features extracted")

        # ============ Stage 5: Multi-dimensional ranking ============
        logger.info("[Stage 5/5] Multi-dimensional ranking...")
        _weights = _DEFAULT_SCORE_WEIGHTS.copy()
        final_candidates = _balanced_multidim_rank(passed_sequences, _weights)
        
        # To map structure discrimination metrics to generic fields for easy database storage and frontend reuse
        for item in final_candidates:
            if "mic_pred" in item:
                item["mic_value"] = item.get("mic_pred")
            if "hemolysis_pred" in item:
                item["hemolysis_score"] = item.get("hemolysis_pred")
            if "cpp_pred" in item:
                item["cpp_score"] = item.get("cpp_pred")
            # Use PGAT-ABPp score as AMP probability (amp_score), replacing Macrel
            if "pgat_score" in item:
                item["amp_score"] = item.get("pgat_score")
        
        result["pipeline_stages"]["final_candidates"] = len(final_candidates)
        result["sequences"] = final_candidates
        result["success"] = True
        
        # Generate summary
        passed_thresholds = sum(1 for x in final_candidates if x.get("passes_thresholds", False))
        result["summary"] = (
            f"Structure discrimination pipeline completed:\n"
            f"  - Generated: {result['pipeline_stages']['generated']} sequences\n"
            f"  - Structure predicted: {result['pipeline_stages']['structure_predicted']}\n"
            f"  - Passed PGAT-ABPp: {result['pipeline_stages']['passed_pgat']}\n"
            f"  - Final candidates: {result['pipeline_stages']['final_candidates']}\n"
            f"  - Meeting thresholds (MIC<{mic_threshold}, Hemo<{hemolysis_threshold}%): {passed_thresholds}\n\n"
            f"Top candidate: {final_candidates[0]['sequence'] if final_candidates else 'N/A'}"
        )
        
        logger.info(f"✅ Pipeline completed: {passed_thresholds}/{len(final_candidates)} meet thresholds")
        
    except Exception as e:
        logger.error(f"❌ Pipeline error: {e}")
        result["errors"].append(f"Pipeline error: {str(e)}")
        result["summary"] = f"Pipeline failed: {str(e)}"
    
    return result

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "design_new_amps",
            "description": "Design novel antimicrobial peptide (AMP) sequences using deep learning models. This tool automatically generates peptides AND evaluates them (MIC/Hemolysis/CPP), then returns the top-ranked candidates. You do NOT need to call evaluate_amp after this.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string", 
                        "enum": ["Gram-negative", "Gram-positive", "Mammalian", "Antifungal", "Antiviral"],
                        "description": "Target pathogen type"
                    },
                    "num_samples": {
                        "type": "integer",
                        "description": "Number of peptides to return (e.g., if user asks for 10 peptides, set this to 10). IMPORTANT: Always extract this number from user's request."
                    },
                    "strategy": {
                        "type": "string", 
                        "enum": ["default", "conservative", "diverse"],
                        "description": "Generation strategy: default (balanced), conservative (safe), diverse (novel)"
                    },
                    "generator": {
                        "type": "string",
                        "enum": ["default", "refine", "diverse"],
                        "description": "Generator model selection: 'default' (AMP-Designer, fast and balanced), 'refine' (HydrAMP, for fine-tuning or when the user explicitly asks to use HydrAMP/refine), 'diverse' (Diff-AMP, for exploring novel sequences). Do not automatically prefer 'refine' just because the user mentions optimization; choose based on the overall task."
                    }
                },
                "required": ["target", "num_samples"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "structure_discrimination_pipeline",
            "description": "[RECOMMENDED FOR STRUCTURE-BASED DESIGN] Complete structure discrimination pipeline: Generate sequences → ESMFold structure prediction → PGAT-ABPp discrimination → MIC/Hemolysis/CPP prediction. Use this when the user explicitly requests structure-based design, structure screening, or mentions PGAT-ABPp. This tool combines generation, structure prediction, and evaluation in one pipeline.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "enum": ["Gram-negative", "Gram-positive", "Mammalian", "Antifungal", "Antiviral"],
                        "description": "Target pathogen type"
                    },
                    "num_samples": {
                        "type": "integer",
                        "description": "Number of sequences to generate initially (will be filtered by PGAT-ABPp)"
                    },
                    "pgat_threshold": {
                        "type": "number",
                        "description": "PGAT-ABPp discrimination threshold (0.0-1.0, default: 0.5). Higher values = stricter screening"
                    },
                    "generator": {
                        "type": "string",
                        "enum": ["default", "diverse", "refine"],
                        "description": "Generator selection: 'default' (AMP-Designer), 'diverse' (Diff-AMP), 'refine' (HydrAMP)"
                    },
                    "mic_threshold": {
                        "type": "number",
                        "description": "MIC threshold for final filtering (μg/mL, default: 32.0)"
                    },
                    "hemolysis_threshold": {
                        "type": "number",
                        "description": "Hemolysis threshold for final filtering (%, default: 10.0)"
                    }
                },
                "required": ["target", "num_samples"]
            }
        }
    },    
    {
        "type": "function",
        "function": {
            "name": "analyze_sequence",
            "description": "Analyze a peptide sequence for physicochemical properties and structural features.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sequence": {"type": "string"}
                },
                "required": ["sequence"]
            }
        }
    },    
    # generate_sequences、evaluate_amp、rank_sequences 已移出 TOOLS_SCHEMA。
    # 这三个工具仅供 _handle_design_pipeline 内部调用，不暴露给 LLM，
    # 防止 LLM 分步绕过四步流程导致无限循环。
    {
        "type": "function",
        "function": {
            "name": "query_ontology",
            "description": "Query structured AMP ontology (design principles, mechanisms, targets, MIC statistics, and mechanism-target co-occurrence). Use this when you need a compact, structured view of the domain ontology instead of free-text literature.",
            "parameters": {
                "type": "object",
                "properties": {
                    "facet": {
                        "type": "string",
                        "enum": [
                            "overview",
                            "design_principles",
                            "action_mechanisms",
                            "target_organisms",
                            "experimental_values_stats",
                            "mechanism_target_matrix"
                        ],
                        "default": "overview",
                        "description": "Which facet of the ontology to return. 'overview' returns the full aggregated ontology overview."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "Search the AMP professional knowledge base containing 575 curated literature excerpts covering mechanisms of action, design strategies, QSAR models, clinical trials, and production technologies. Use cases: answer theoretical questions, provide design recommendations, cite literature data, explain technical concepts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language query, e.g., 'What is the mechanism of action of AMPs?', 'How to improve AMP stability?'"
                    },
                    "knowledge_type": {
                        "type": "string",
                        "enum": ["literature", "mic", "cpp", "hemolysis", "ontology"],
                        "default": "literature",
                        "description": "Knowledge type. Use 'ontology' for structured AMP domain concepts (design principles, mechanisms, targets). Default 'literature' (literature knowledge, recommended)"
                    },
                    "top_k": {
                        "type": "integer",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 10,
                        "description": "Number of results to return, default 5"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "visualize_peptide_structure",
            "description": "Generate detailed visualizations for a single peptide sequence including helical wheel projection (amphipathicity), radar chart (comprehensive performance), and hydrophobicity profile. Use this when user asks to visualize structure, analyze amphipathicity, or generate helical wheel/radar charts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sequence": {
                        "type": "string",
                        "description": "Peptide sequence (e.g., 'KWKLFKKIGAVLKVL')"
                    },
                    "mic": {
                        "type": "number",
                        "description": "Optional MIC value in μM"
                    },
                    "hemo": {
                        "type": "number",
                        "description": "Optional hemolysis score (0-1)"
                    },
                    "cpp": {
                        "type": "number",
                        "description": "Optional CPP score (0-1)"
                    },
                    "macrel": {
                        "type": "number",
                        "description": "Optional Macrel AMP probability (0-1)"
                    }
                },
                "required": ["sequence"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_mechanisms_for_target",
            "description": "[RECOMMENDED FOR MECHANISM QUERIES] Query structured antimicrobial mechanisms against a target organism from the Graph RAG knowledge base. Returns ranked mechanisms with document counts and evidence sources. Use this FIRST when user asks about mechanisms for specific organisms (e.g., 'mechanisms for E.coli', 'how to target S.aureus'). This provides quantitative mechanism rankings faster than general search.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Target organism name, e.g., 'E.coli', 'S.aureus', 'Gram-negative', 'Gram-positive'"
                    },
                    "limit": {
                        "type": "integer",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 10,
                        "description": "Maximum number of mechanisms to return (default 5)"
                    }
                },
                "required": ["target"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_principles_for_mechanism",
            "description": "[RECOMMENDED FOR DESIGN PRINCIPLE QUERIES] Query design principles co-occurring with a specific antimicrobial mechanism from the Graph RAG knowledge base. Returns ranked principles with document counts and literature evidence. Use this FIRST when user asks about design strategies for specific mechanisms (e.g., 'design principles for membrane disruption', 'how to design pore-forming peptides'). Faster and more structured than general search.",
            "parameters": {
                "type": "object",
                "properties": {
                    "mechanism": {
                        "type": "string",
                        "description": "Mechanism name, e.g., 'membrane_disruption', 'pore_formation', 'immune_modulation'"
                    },
                    "limit": {
                        "type": "integer",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 10,
                        "description": "Maximum number of principles to return (default 5)"
                    }
                },
                "required": ["mechanism"]
            }
        }
    }
]

def tool_design_new_amps(target: str = "Gram-negative", num_samples: int = 5, strategy: str = "default", generator: str = "default", prompt: str = None) -> List[Dict[str, Any]]:
    """
    Design novel antimicrobial peptide (AMP) sequences using deep learning models.
    This tool automatically generates peptides AND evaluates them (MIC/Hemolysis/CPP), 
    then returns the top-ranked candidates. You do NOT need to call evaluate_amp after this.
    
    Args:
        target: Target pathogen type (Gram-negative, Gram-positive, Mammalian, Antifungal, Antiviral)
        num_samples: Number of peptides to return (e.g., if user asks for 10 peptides, set this to 10)
        strategy: Generation strategy (default, conservative, diverse)
        generator: Generator model selection (default=AMP-Designer, refine=HydrAMP, diverse=Diff-AMP)
    
    Returns:
        List of dictionaries containing sequence and evaluation data
    """
    try:
        # 🔥 [AUTO-DEBUG GUARD] Force type conversion before any arithmetic
        if isinstance(num_samples, str):
            try:
                num_samples = int(num_samples)
                logger.info(f"🔧 Auto-converted num_samples: '{num_samples}' -> {num_samples}")
            except ValueError:
                logger.warning(f"⚠️ Invalid num_samples '{num_samples}', using default 5")
                num_samples = 5
        elif not isinstance(num_samples, int):
            logger.warning(f"⚠️ Invalid num_samples type {type(num_samples)}, using default 5")
            num_samples = 5
        
        # Allow prompt aliasing if target is not explicitly provided
        if (not target or str(target).strip() == "") and prompt:
            target = prompt
        
        # Map strategy to generator if needed
        if generator == "default" and strategy == "diverse":
            generator = "diverse"
        elif generator == "default" and strategy == "refine":
            generator = "refine"
        
        # Generate sequences
        # Debug log: Check type before multiplication
        logger.info(f"🔍 DEBUG: Before multiplication - num_samples={num_samples}, type={type(num_samples)}")
        generation_count = num_samples * 2
        logger.info(f"🔍 DEBUG: After multiplication - generation_count={generation_count}, type={type(generation_count)}")
        raw_sequences = tool_generate_amp(num_samples=generation_count, prompt=target, generator=generator)
        
        # Evaluate the generated sequences
        evaluated_sequences = tool_batch_evaluate(raw_sequences)
        
        # Rank the sequences
        ranked_sequences = tool_rank_sequences(evaluated_sequences, strategy=strategy)
        
        # Return the top N sequences based on num_samples
        final_sequences = ranked_sequences[:num_samples]
        
        logger.info(f"✅ Designed {len(final_sequences)} AMPs against {target} using {generator} generator")
        
        return final_sequences
    
    except Exception as e:
        logger.error(f"design_new_amps failed: {e}")
        return [{"error": f"design_new_amps failed: {str(e)}"}]


# ============================================================
# Hybrid RAG-enhanced Mutation helpers
# ============================================================

def _query_mutation_knowledge_rag(sequence: str, goal: str, target: str) -> Dict[str, Any]:
    """Query Hybrid RAG (Vector RAG + Graph RAG) for mutation-relevant knowledge."""
    vector_hits: List[str] = []
    graph_mechs: List[str] = []
    graph_principles: List[str] = []

    try:
        aa_set = set(sequence)
        charge_aas = aa_set & {"K", "R", "H"}
        hemo_aas   = aa_set & {"W", "F", "Y"}
        goal_desc = {
            "lower_mic"       : "improve antimicrobial potency reduce MIC cationic charge membrane disruption",
            "lower_hemolysis" : "reduce hemolysis toxicity aromatic residue substitution safety",
            "balanced"        : "optimize AMP activity safety balance cationic amphipathic helix",
        }.get(goal, "AMP mutation optimization")
        vec_query = (
            f"AMP mutation optimization {goal_desc} "
            f"sequence features charge {'+' if charge_aas else 'neutral'} "
            f"{'tryptophan phenylalanine hemolytic' if hemo_aas else ''} "
            f"target {target}"
        )
        lit_result = tool_search_knowledge(query=vec_query, knowledge_type="literature", top_k=4)
        if lit_result.get("success"):
            for r in lit_result.get("results", []):
                c = r.get("content", "").strip()
                if c:
                    vector_hits.append(c[:300])
        if hemo_aas:
            hemo_result = tool_search_knowledge(
                query="reduce hemolysis AMP Trp Phe substitution alanine safety",
                knowledge_type="hemolysis", top_k=2
            )
            if hemo_result.get("success"):
                for r in hemo_result.get("results", []):
                    c = r.get("content", "").strip()
                    if c:
                        vector_hits.append(c[:200])
    except Exception as e:
        logger.warning(f"_query_mutation_knowledge_rag: Vector RAG failed: {e}")

    try:
        mech_result = tool_query_mechanisms_for_target(target=target, limit=3)
        if mech_result.get("success"):
            for m in mech_result.get("mechanisms", []):
                graph_mechs.append(m.get("mechanism", ""))
        primary_mech = graph_mechs[0] if graph_mechs else "membrane_disruption"
        prin_result = tool_query_principles_for_mechanism(mechanism=primary_mech, limit=4)
        if prin_result.get("success"):
            for p in prin_result.get("design_principles", []):
                graph_principles.append(p.get("principle", ""))
    except Exception as e:
        logger.warning(f"_query_mutation_knowledge_rag: Graph RAG failed: {e}")

    summary_parts = []
    if graph_mechs:
        summary_parts.append(f"Key mechanisms against {target}: {', '.join(graph_mechs[:3])}.")
    if graph_principles:
        summary_parts.append(f"Evidence-based design principles: {', '.join(graph_principles[:4])}.")
    if vector_hits:
        summary_parts.append("Literature insights:")
        for h in vector_hits[:3]:
            summary_parts.append(f"  - {h}")

    return {
        "vector_hits"      : vector_hits,
        "graph_mechs"      : graph_mechs,
        "graph_principles" : graph_principles,
        "summary"          : "\n".join(summary_parts),
    }


def _query_db_mutation_history(
    sequence: str,
    db_path: str = "/data/amp-generator-platform/backend/amp_platform.db"
) -> Dict[str, Any]:
    """Query SQLite/Postgres database for historical evaluation data of similar sequences."""
    import sqlite3
    import os

    result: Dict[str, Any] = {"exact_match": None, "similar_seqs": [], "stats": {}}
    if not os.path.exists(db_path):
        return result

    try:
        seq_len = len(sequence)
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                "SELECT sequence, mic_value, hemolysis_score, cpp_score, amp_score, composite_score "
                "FROM sequences WHERE sequence = ? ORDER BY created_at DESC LIMIT 1",
                (sequence,)
            )
            row = cur.fetchone()
            if row:
                result["exact_match"] = dict(row)
            cur.execute(
                "SELECT sequence, mic_value, hemolysis_score, cpp_score, amp_score "
                "FROM sequences "
                "WHERE length(sequence) BETWEEN ? AND ? "
                "  AND mic_value IS NOT NULL AND mic_value < 16 "
                "  AND hemolysis_score IS NOT NULL AND hemolysis_score < 0.35 "
                "ORDER BY mic_value ASC LIMIT 5",
                (seq_len - 3, seq_len + 3)
            )
            rows = cur.fetchall()
            result["similar_seqs"] = [dict(r) for r in rows]
            cur.execute(
                "SELECT COUNT(*) as n, AVG(mic_value) as avg_mic, "
                "AVG(hemolysis_score) as avg_hemo, AVG(cpp_score) as avg_cpp "
                "FROM sequences WHERE mic_value IS NOT NULL"
            )
            agg = cur.fetchone()
            if agg and agg["n"] > 0:
                result["stats"] = {
                    "n"       : agg["n"],
                    "avg_mic" : round(agg["avg_mic"] or 0, 2),
                    "avg_hemo": round(agg["avg_hemo"] or 0, 3),
                    "avg_cpp" : round(agg["avg_cpp"] or 0, 3),
                }
    except Exception as e:
        logger.warning(f"_query_db_mutation_history: DB query failed: {e}")

    return result


def tool_mutate_sequence(
    sequence: str,
    target: str = "Gram-negative",
    goal: str = "balanced",
    num_variants: int = 3,
    rag_enhanced: bool = True,
) -> Dict[str, Any]:
    """RAG-enhanced AMP mutation optimization.

    Pipeline:
      1. Query Hybrid RAG (Vector RAG literature + Graph RAG mechanisms/principles)
         to retrieve evidence-based mutation rules.
      2. Query the database for historical performance of identical/similar sequences.
      3. Apply rule library informed by RAG evidence to generate num_variants mutants.
      4. Batch re-evaluate all variants (MIC / Hemolysis / CPP).
      5. Rank by composite_score (lower = better), return full comparison dict.

    Args:
        sequence     : Input AMP sequence (amino acids, uppercase).
        target       : Target organism (e.g. 'Gram-negative', 'E.coli', 'S.aureus').
        goal         : 'lower_mic' | 'lower_hemolysis' | 'balanced'
        num_variants : Number of mutant sequences to generate (1-5, default 3).
        rag_enhanced : Whether to use Hybrid RAG context (default True).
    """
    import random

    seq = sequence.upper().strip()
    n   = len(seq)

    if n < 5:
        return {"error": "Sequence too short (min 5 aa)", "original_sequence": seq}

    rag_ctx: Dict[str, Any] = {}
    db_ctx:  Dict[str, Any] = {}

    if rag_enhanced:
        try:
            rag_ctx = _query_mutation_knowledge_rag(seq, goal, target)
            logger.info(f"[mutate] RAG: {len(rag_ctx.get('vector_hits',[]))} lit hits, "
                        f"mechs={rag_ctx.get('graph_mechs',[])}, "
                        f"principles={rag_ctx.get('graph_principles',[])}")
        except Exception as e:
            logger.warning(f"[mutate] RAG query failed (non-fatal): {e}")
            rag_ctx = {"vector_hits": [], "graph_mechs": [], "graph_principles": [], "summary": ""}
        try:
            db_ctx = _query_db_mutation_history(seq)
            logger.info(f"[mutate] DB: exact={'yes' if db_ctx.get('exact_match') else 'no'}, "
                        f"similar={len(db_ctx.get('similar_seqs', []))}")
        except Exception as e:
            logger.warning(f"[mutate] DB query failed (non-fatal): {e}")
            db_ctx = {}

    CATIONIC  = ["K", "R"]
    HELICAL   = ["A", "L", "I", "V", "M"]
    HEMOLYTIC = ["W", "F", "Y"]
    SAFE_SWAP = ["A", "S"]

    graph_principles = rag_ctx.get("graph_principles", [])
    principles_str   = " ".join(graph_principles).lower()
    if "hydrophobicity" in principles_str or "amphipathic" in principles_str:
        HEMOLYTIC = ["W", "F", "Y", "L"]
    if "arginine" in principles_str:
        CATIONIC = ["R", "K"]

    seq_list = list(seq)

    def _apply_mut(base_list, pos, new_aa, desc):
        v = list(base_list)
        v[pos] = new_aa
        return "".join(v), desc

    def _make_rag_variants(seq_str, goal_str, nv):
        candidates = []
        rng = random.Random(42)

        if goal_str in ("lower_mic", "balanced"):
            for pos in range(0, min(3, n)):
                if seq_list[pos] not in CATIONIC:
                    for r in CATIONIC:
                        s, d = _apply_mut(seq_list, pos, r, f"pos{pos+1}:{seq_list[pos]}\u2192{r} (+charge, membrane)")
                        candidates.append((s, d, "cationic_N_term"))
            for pos in range(n // 3, 2 * n // 3):
                if seq_list[pos] not in HELICAL and seq_list[pos] not in CATIONIC:
                    s, d = _apply_mut(seq_list, pos, "A", f"pos{pos+1}:{seq_list[pos]}\u2192A (helix-propensity)")
                    candidates.append((s, d, "helix_mid"))
            if db_ctx.get("similar_seqs"):
                sim_seqs = [r["sequence"] for r in db_ctx["similar_seqs"] if len(r["sequence"]) == n]
                for sim in sim_seqs[:2]:
                    for pos in range(min(5, n)):
                        if sim[pos] in CATIONIC and seq_list[pos] not in CATIONIC:
                            s, d = _apply_mut(seq_list, pos, sim[pos], f"pos{pos+1}:{seq_list[pos]}\u2192{sim[pos]} (DB-similar)")
                            candidates.append((s, d, "db_mirror"))

        if goal_str in ("lower_hemolysis", "balanced"):
            for pos in range(1, n - 1):
                if seq_list[pos] in HEMOLYTIC:
                    for swap in SAFE_SWAP:
                        s, d = _apply_mut(seq_list, pos, swap, f"pos{pos+1}:{seq_list[pos]}\u2192{swap} (-hemolysis, lit)")
                        candidates.append((s, d, "hemolysis_reduce"))

        seen = {seq_str}
        unique = []
        for s, d, rule in candidates:
            if s not in seen:
                seen.add(s)
                unique.append((s, d, rule))

        by_rule: Dict[str, list] = {}
        for item in unique:
            by_rule.setdefault(item[2], []).append(item)
        diverse: list = []
        rule_keys = list(by_rule.keys())
        while len(diverse) < nv and any(by_rule.values()):
            for rk in rule_keys:
                if by_rule.get(rk):
                    diverse.append(by_rule[rk].pop(0))
                    if len(diverse) >= nv:
                        break

        attempts = 0
        while len(diverse) < nv and attempts < 60:
            pos    = rng.randint(0, n - 1)
            new_aa = rng.choice(CATIONIC)
            s      = seq_str[:pos] + new_aa + seq_str[pos + 1:]
            if s not in seen:
                seen.add(s)
                diverse.append((s, f"pos{pos+1}:{seq_str[pos]}\u2192{new_aa} (random-charge)", "fallback"))
            attempts += 1

        return diverse[:nv]

    variants_raw = _make_rag_variants(seq, goal, num_variants)
    if not variants_raw:
        return {"error": "Could not generate mutant variants", "original_sequence": seq}

    all_seqs_input = [{"sequence": seq}] + [{"sequence": v[0]} for v in variants_raw]
    try:
        eval_results = tool_batch_evaluate(all_seqs_input)
    except Exception as e:
        logger.error(f"tool_mutate_sequence: batch evaluate failed: {e}")
        return {"error": f"Evaluation failed: {e}", "original_sequence": seq}

    if not eval_results:
        return {"error": "No evaluation results returned", "original_sequence": seq}

    def _composite(r):
        """Composite score for mutant comparison (lower = better).
        Uses same relative weights as _DEFAULT_SCORE_WEIGHTS activity/safety block:
        MIC 30%, Hemolysis 15%, CPP 5%  → normalized to 60:30:10 within 3-dim.
        MIC uses log-scale to avoid extreme outlier distortion.
        """
        import math as _math
        def _fnone(*keys):
            for k in keys:
                v = r.get(k)
                if v is not None: return v
            return None
        mic  = _fnone("mic_value", "mic_pred") or 99.0
        hemo = _fnone("hemolysis_score", "hemolysis_pred") or 1.0
        cpp  = _fnone("cpp_score", "cpp_pred") or 0.0
        if hemo > 1.5: hemo = hemo / 100.0
        # Log-normalize MIC relative to reference range [1, 128] µM
        mic_n  = min((_math.log(max(mic, 0.1)) - _math.log(1.0)) / (_math.log(128.0) - _math.log(1.0)), 1.0)
        hemo_n = min(max(hemo, 0.0), 1.0)
        cpp_n  = min(max(cpp,  0.0), 1.0)
        return round(0.60 * mic_n + 0.30 * hemo_n + 0.10 * cpp_n, 4)

    original_metrics = eval_results[0].copy() if eval_results else {}
    original_metrics["sequence"]             = seq
    original_metrics["composite_score"]      = _composite(original_metrics)
    original_metrics["mutation_description"] = "original"
    if db_ctx.get("exact_match"):
        original_metrics["db_record"] = db_ctx["exact_match"]

    variant_records = []
    for i, (v_seq, v_desc, v_rule) in enumerate(variants_raw):
        m = eval_results[i + 1].copy() if i + 1 < len(eval_results) else {}
        m["sequence"]             = v_seq
        m["composite_score"]      = _composite(m)
        m["mutation_description"] = v_desc
        m["mutation_rule"]        = v_rule
        variant_records.append(m)

    variant_records.sort(key=lambda x: x.get("composite_score", 99))
    best = variant_records[0] if variant_records else original_metrics

    orig_comp = original_metrics.get("composite_score", 99)
    best_comp = best.get("composite_score", 99)
    improvement = {
        "composite_score_delta": round(orig_comp - best_comp, 4),
        "mic_delta": round(
            (original_metrics.get("mic_value") or 99) - (best.get("mic_value") or 99), 2
        ),
        "hemolysis_delta": round(
            (original_metrics.get("hemolysis_score") or 1) - (best.get("hemolysis_score") or 1), 4
        ),
        "cpp_delta": round(
            (best.get("cpp_score") or 0) - (original_metrics.get("cpp_score") or 0), 4
        ),
    }

    return {
        "success"     : True,
        "original"    : original_metrics,
        "variants"    : variant_records,
        "best_variant": best,
        "improvement" : improvement,
        "rag_context" : rag_ctx,
        "db_context"  : db_ctx,
        "goal"        : goal,
        "target"      : target,
    }
