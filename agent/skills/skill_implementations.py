# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
AMP Agent Core Skills - Core Skill Library
===========================================

Implements common AMP design, evaluation, and optimization skills.
Each skill encapsulates a complete workflow and best practices.
"""

import logging
from typing import Dict, Any, List, Optional
import time

logger = logging.getLogger(__name__)

from skills import (
    SkillResult, 
    SkillDefinition, 
    SkillPriority,
    get_skill_registry,
    skill_decorator
)

# ToolProxy: try importing real tools from parent directory, use stubs on failure to prevent import crashes
try:
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from tools import (
        tool_generate_amp as _real_generate,
        tool_batch_evaluate as _real_evaluate,
        tool_rank_sequences as _real_rank,
        tool_predict_structure as _real_structure,
        tool_search_knowledge as _real_search,
    )
    _TOOLS_AVAILABLE = True
    logger.info("✅ skill_implementations: real tools loaded")
except ImportError as _e:
    _TOOLS_AVAILABLE = False
    logger.warning(f"⚠️ skill_implementations: tools not available ({_e}), stubs active")
    def _stub(*a, **kw): return {"success": False, "error": "tools not loaded", "sequences": [], "results": [], "ranked_sequences": []}
    _real_generate = _real_evaluate = _real_rank = _real_structure = _real_search = _stub


# ============================================================================
# Design Skills
# ============================================================================

@skill_decorator
def rapid_design(target: str, 
                 num_candidates: int = 10,
                 generator: str = "default",
                 **kwargs) -> SkillResult:
    """
    Rapid design skill: Generate → Evaluate → Rank
    
    Use cases:
    - User needs to quickly obtain a batch of candidate sequences
    - No advanced features like structure validation required
    - Time-sensitive tasks
    
    Workflow:
    1. Create sequences using specified generator
    2. Batch evaluate (MIC + Hemolysis + CPP + Macrel)
    3. Pareto ranking returns Top-K
    
    Args:
        target: Target organism (e.g. "E. coli", "Gram-negative")
        num_candidates: Number of candidates
        generator: Generator choice ("default", "diff-amp", "hydramp")
    
    Returns:
        SkillResult: containing ranked sequence list
    """
    try:
        logger.info(f"🚀 Starting rapid design for target: {target}")
        start_time = time.time()
        
        # Step 1: Generate sequences
        logger.info(f"Step 1/3: Generating {num_candidates} sequences...")
        generation_result = _real_generate(
            num_samples=num_candidates,
            prompt=target,
            generator=generator
        )
        sequences = generation_result if isinstance(generation_result, list) else []
        
        if not sequences:
            return SkillResult(
                success=False,
                message=f"Generation returned no sequences",
                data={}
            )
        
        # Step 2: Evaluate all sequences
        logger.info("Step 2/3: Evaluating sequences (MIC + Hemolysis + CPP + Macrel)...")
        seq_strings = [s['sequence'] if isinstance(s, dict) else s for s in sequences]
        eval_result = _real_evaluate(sequences=seq_strings)
        evaluated_sequences = eval_result if isinstance(eval_result, list) else []
        
        # Step 3: Rank sequences using Pareto strategy
        logger.info("Step 3/3: Ranking sequences with Pareto optimization...")
        ranking_result = _real_rank(
            sequences=evaluated_sequences,
            strategy="pareto",
            target=target
        )
        ranked_sequences = ranking_result if isinstance(ranking_result, list) else evaluated_sequences
        
        # Extract top candidates
        top_candidates = []
        for seq_data in ranked_sequences[:min(num_candidates, len(ranked_sequences))]:
            top_candidates.append({
                'sequence': seq_data.get('sequence'),
                'amp_probability': seq_data.get('macrel_score'),
                'mic_um': seq_data.get('mic_um'),
                'hemolysis': seq_data.get('hemolysis_score'),
                'cpp': seq_data.get('cpp_score'),
                'is_pareto_optimal': seq_data.get('is_pareto_optimal', False),
                'rank': seq_data.get('rank', 0)
            })
        
        logger.info(f"✅ Rapid design completed: {len(top_candidates)} candidates")
        
        return SkillResult(
            success=True,
            message=f"Successfully designed {len(top_candidates)} AMP candidates",
            data={
                'candidates': top_candidates,
                'generator_used': generator,
                'total_generated': len(sequences),
                'total_evaluated': len(evaluated_sequences)
            },
            metadata={
                'execution_time': time.time() - start_time,
                'skill_name': 'rapid_design'
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Rapid design failed: {e}", exc_info=True)
        return SkillResult(
            success=False,
            message=f"Rapid design failed: {str(e)}",
            data={}
        )


@skill_decorator
def structure_validated_design(target: str,
                               num_candidates: int = 5,
                               min_fold_score: float = 0.6,
                               **kwargs) -> SkillResult:
    """
    Structure-validated design skill: Generate → Evaluate → Structure prediction → PGAT discrimination → Rank
    
    Use cases:
    - High-risk targets (e.g. tumor cell penetrating peptides)
    - Need to ensure sequences are foldable
    - Final candidate screening
    
    Workflow:
    1. Generate large candidate pool
    2. Preliminary evaluation (MIC + Hemolysis + CPP)
    3. ESMFold structure prediction
    4. PGAT-ABPp discrimination (filter unqualified)
    5. Return validated sequences
    
    Args:
        target: Target organism
        num_candidates: Required final candidate count
        min_fold_score: Minimum fold score threshold
    
    Returns:
        SkillResult: containing structure-validated sequences
    """
    try:
        logger.info(f"🔬 Starting structure-validated design for target: {target}")
        start_time = time.time()
        
        # Step 1: Generate larger pool (we'll filter down)
        logger.info("Step 1/5: Generating candidate pool...")
        sequences_raw = _real_generate(
            num_samples=num_candidates * 3,
            prompt=target,
            generator="default"
        )
        sequences = sequences_raw if isinstance(sequences_raw, list) else []
        
        if not sequences:
            return SkillResult(
                success=False,
                message="Generation returned no sequences",
                data={}
            )
        
        # Step 2: Initial evaluation
        logger.info("Step 2/5: Evaluating biochemical properties...")
        seq_strings = [s['sequence'] if isinstance(s, dict) else s for s in sequences]
        eval_raw = _real_evaluate(sequences=seq_strings)
        evaluated_seqs = eval_raw if isinstance(eval_raw, list) else []
        
        # Step 3: Structure prediction with ESMFold
        logger.info("Step 3/5: Predicting structures with ESMFold...")
        structure_results = []
        for seq_data in evaluated_seqs:
            seq = seq_data.get('sequence') if isinstance(seq_data, dict) else seq_data
            struct_result = _real_structure(sequence=seq)
            if isinstance(struct_result, dict) and struct_result.get('success'):
                if isinstance(seq_data, dict):
                    seq_data['structure'] = struct_result.get('pdb_structure')
                    seq_data['fold_score'] = struct_result.get('confidence_score', 0)
                structure_results.append(seq_data)
            else:
                logger.warning(f"⚠️ Structure prediction failed for: {str(seq)[:20]}...")
        
        # Step 4: PGAT-ABPp discrimination (filter by fold_score)
        logger.info(f"Step 4/5: Filtering by fold score (threshold: {min_fold_score})...")
        filtered_sequences = [
            seq for seq in structure_results 
            if seq.get('fold_score', 0) >= min_fold_score
        ]
        
        if len(filtered_sequences) == 0:
            logger.warning("⚠️ No sequences passed structure validation!")
            # Fallback: return top sequences without structure info
            filtered_sequences = evaluated_seqs[:num_candidates]
        
        # Step 5: Final ranking
        logger.info("Step 5/5: Ranking validated sequences...")
        rank_raw = _real_rank(
            sequences=filtered_sequences,
            strategy="pareto",
            target=target
        )
        ranked_sequences = rank_raw if isinstance(rank_raw, list) else filtered_sequences
        
        # Prepare final candidates
        final_candidates = []
        for seq_data in ranked_sequences[:num_candidates]:
            final_candidates.append({
                'sequence': seq_data.get('sequence'),
                'amp_probability': seq_data.get('macrel_score'),
                'mic_um': seq_data.get('mic_um'),
                'hemolysis': seq_data.get('hemolysis_score'),
                'cpp': seq_data.get('cpp_score'),
                'fold_score': seq_data.get('fold_score', 0),
                'structure_pdb': seq_data.get('structure'),
                'is_pareto_optimal': seq_data.get('is_pareto_optimal', False),
                'passed_structure_validation': seq_data.get('fold_score', 0) >= min_fold_score
            })
        
        execution_time = time.time() - start_time
        logger.info(f"✅ Structure-validated design completed in {execution_time:.2f}s")
        
        return SkillResult(
            success=True,
            message=f"Designed {len(final_candidates)} structure-validated AMPs",
            data={
                'candidates': final_candidates,
                'total_generated': len(sequences),
                'passed_structure_filter': len(filtered_sequences),
                'min_fold_score_threshold': min_fold_score
            },
            metadata={
                'execution_time': execution_time,
                'skill_name': 'structure_validated_design'
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Structure-validated design failed: {e}", exc_info=True)
        return SkillResult(
            success=False,
            message=f"Structure-validated design failed: {str(e)}",
            data={}
        )


@skill_decorator
def knowledge_guided_design(target: str,
                            query_keywords: Optional[str] = None,
                            use_rag: bool = True,
                            **kwargs) -> SkillResult:
    """
    Knowledge-guided design skill: Retrieve RAG → Inject into prompt → Generate → Evaluate
    
    Use cases:
    - Design targeting specific mechanisms
    - Need domain knowledge enhancement
    - Explore novel action mechanisms
    
    Workflow:
    1. Retrieve from knowledge base based on target/keywords
    2. Extract design principles and action mechanisms
    3. Inject into generator prompt
    4. Generate and evaluate sequences
    
    Args:
        target: Target organism
        query_keywords: Extra keywords (optional)
        use_rag: Whether to use RAG
    
    Returns:
        SkillResult: containing knowledge-guided generated sequences
    """
    try:
        logger.info(f"🧠 Starting knowledge-guided design for target: {target}")
        start_time = time.time()
        
        # Step 1: Retrieve knowledge from RAG
        design_principles = []
        mechanisms = []
        
        if use_rag:
            logger.info("Step 1/4: Retrieving knowledge from RAG...")
            query = f"{target} antimicrobial peptide design principles"
            if query_keywords:
                query += f" {query_keywords}"
            
            rag_result = _real_search(query=query)
            if isinstance(rag_result, dict) and rag_result.get('success'):
                documents = rag_result.get('documents', [])
                for doc in documents[:5]:
                    if doc.get('type') == 'design_principle':
                        design_principles.append(doc.get('content'))
                    elif doc.get('type') == 'mechanism':
                        mechanisms.append(doc.get('content'))
            logger.info(f"Retrieved {len(design_principles)} principles and {len(mechanisms)} mechanisms")
        
        # Step 2: Generate with knowledge injection
        logger.info("Step 2/4: Generating sequences with knowledge guidance...")
        context = ""
        if design_principles:
            context += "Design Principles:\n"
            for i, principle in enumerate(design_principles[:3], 1):
                context += f"{i}. {principle}\n"
        if mechanisms:
            context += "\nMechanisms of Action:\n"
            for i, mech in enumerate(mechanisms[:2], 1):
                context += f"{i}. {mech}\n"
        
        sequences_raw = _real_generate(
            num_samples=10,
            prompt=target,
            generator="default"
        )
        sequences = sequences_raw if isinstance(sequences_raw, list) else []
        
        if not sequences:
            return SkillResult(
                success=False,
                message="Generation returned no sequences",
                data={}
            )
        
        # Step 3: Evaluate
        logger.info("Step 3/4: Evaluating sequences...")
        seq_strings = [s['sequence'] if isinstance(s, dict) else s for s in sequences]
        eval_raw = _real_evaluate(sequences=seq_strings)
        evaluated_seqs = eval_raw if isinstance(eval_raw, list) else []
        
        # Step 4: Rank
        logger.info("Step 4/4: Ranking sequences...")
        rank_raw = _real_rank(
            sequences=evaluated_seqs,
            strategy="pareto",
            target=target
        )
        ranked_seqs = rank_raw if isinstance(rank_raw, list) else evaluated_seqs
        
        # Prepare results
        candidates = []
        for seq_data in ranked_seqs[:10]:
            candidates.append({
                'sequence': seq_data.get('sequence'),
                'amp_probability': seq_data.get('macrel_score'),
                'mic_um': seq_data.get('mic_um'),
                'hemolysis': seq_data.get('hemolysis_score'),
                'cpp': seq_data.get('cpp_score'),
                'is_pareto_optimal': seq_data.get('is_pareto_optimal', False),
                'knowledge_enhanced': use_rag
            })
        
        execution_time = time.time() - start_time
        logger.info(f"✅ Knowledge-guided design completed in {execution_time:.2f}s")
        
        return SkillResult(
            success=True,
            message=f"Designed {len(candidates)} knowledge-guided AMPs",
            data={
                'candidates': candidates,
                'design_principles_used': design_principles,
                'mechanisms_used': mechanisms,
                'rag_enabled': use_rag
            },
            metadata={
                'execution_time': execution_time,
                'skill_name': 'knowledge_guided_design'
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Knowledge-guided design failed: {e}", exc_info=True)
        return SkillResult(
            success=False,
            message=f"Knowledge-guided design failed: {str(e)}",
            data={}
        )


# ============================================================================
# Mutation Optimization Skill
# ============================================================================

@skill_decorator
def mutation_optimization(
    sequence: str,
    goal: str = "balanced",
    target: str = "Gram-negative",
    num_variants: int = 3,
    rag_enhanced: bool = True,
    **kwargs
) -> SkillResult:
    """
    Mutation Optimization Skill: RAG-guided AMP mutation + re-evaluation

    Workflow:
    1. Query Hybrid RAG (Vector literature + Graph mechanisms) for mutation rules
    2. Query database for historical performance of similar sequences
    3. Generate rule-based mutant variants informed by RAG evidence
    4. Batch re-evaluate all variants (MIC / Hemolysis / CPP)
    5. Rank by composite score and return comparison results

    Args:
        sequence      : Input AMP sequence to optimize
        goal          : 'lower_mic' | 'lower_hemolysis' | 'balanced'
        target        : Target organism
        num_variants  : Number of mutant variants to generate (1-5)
        rag_enhanced  : Whether to use Hybrid RAG context
    """
    import time
    start_time = time.time()

    if not sequence or len(sequence) < 5:
        return SkillResult(
            success=False,
            message="Sequence too short or empty (min 5 amino acids required)",
            data={}
        )

    try:
        logger.info(f"🧬 mutation_optimization skill: seq={sequence[:15]}... goal={goal}")

        from tools import tool_mutate_sequence
        result = tool_mutate_sequence(
            sequence=sequence,
            target=target,
            goal=goal,
            num_variants=num_variants,
            rag_enhanced=rag_enhanced,
        )

        if not result.get("success"):
            return SkillResult(
                success=False,
                message=result.get("error", "Mutation optimization failed"),
                data=result
            )

        execution_time = time.time() - start_time
        best = result.get("best_variant", {})
        improvement = result.get("improvement", {})
        rag_ctx = result.get("rag_context", {})
        db_ctx  = result.get("db_context", {})

        summary_lines = [
            f"Original: {sequence}",
            f"Best variant: {best.get('sequence', 'N/A')}",
            f"Mutation: {best.get('mutation_description', 'N/A')}",
            f"Composite score delta: {improvement.get('composite_score_delta', 0):+.4f}",
            f"MIC delta: {improvement.get('mic_delta', 0):+.2f} uM",
            f"Hemolysis delta: {improvement.get('hemolysis_delta', 0):+.4f}",
        ]
        if rag_ctx.get("summary"):
            summary_lines.append(f"RAG context: {rag_ctx['summary'][:120]}...")
        if db_ctx.get("exact_match"):
            summary_lines.append("DB: exact match found for original sequence")
        elif db_ctx.get("similar_seqs"):
            summary_lines.append(f"DB: {len(db_ctx['similar_seqs'])} similar sequences found")

        return SkillResult(
            success=True,
            message="\n".join(summary_lines),
            data=result,
            metadata={
                "execution_time": execution_time,
                "skill_name": "mutation_optimization",
                "goal": goal,
                "target": target,
                "num_variants": num_variants,
                "rag_hits": len(rag_ctx.get("vector_hits", [])),
                "db_similar": len(db_ctx.get("similar_seqs", [])),
            }
        )

    except Exception as e:
        logger.error(f"❌ mutation_optimization skill failed: {e}", exc_info=True)
        return SkillResult(
            success=False,
            message=f"Mutation optimization failed: {str(e)}",
            data={}
        )


# ============================================================================
# Skill Registration
# ============================================================================

def register_core_skills():
    """Register all core Skills"""
    registry = get_skill_registry()
    
    # Design Skills
    registry.register(
        name='rapid_design',
        func=rapid_design,
        definition=SkillDefinition(
            name='rapid_design',
            description='Rapid design: Generate → Evaluate → Rank (suitable for quickly obtaining candidates)',
            category='design',
            priority=SkillPriority.HIGH,
            required_params=['target'],
            optional_params={
                'num_candidates': 10,
                'generator': 'default'
            },
            tags=['fast', 'standard', 'production']
        )
    )
    
    registry.register(
        name='structure_validated_design',
        func=structure_validated_design,
        definition=SkillDefinition(
            name='structure_validated_design',
            description='Structure-validated design: Generate → Evaluate → Structure prediction → PGAT discrimination (suitable for high-risk targets)',
            category='design',
            priority=SkillPriority.HIGH,
            required_params=['target'],
            optional_params={
                'num_candidates': 5,
                'min_fold_score': 0.6
            },
            tags=['structure', 'validation', 'high-confidence']
        )
    )
    
    registry.register(
        name='knowledge_guided_design',
        func=knowledge_guided_design,
        definition=SkillDefinition(
            name='knowledge_guided_design',
            description='Knowledge-guided design: RAG retrieval → Knowledge injection → Generate (suitable for novel mechanism exploration)',
            category='design',
            priority=SkillPriority.MEDIUM,
            required_params=['target'],
            optional_params={
                'query_keywords': None,
                'use_rag': True
            },
            tags=['rag', 'knowledge', 'novel']
        )
    )

    registry.register(
        name='mutation_optimization',
        func=mutation_optimization,
        definition=SkillDefinition(
            name='mutation_optimization',
            description='Mutation optimization: Hybrid RAG retrieves mutation rules → Generate variants → Batch re-evaluate (for optimizing existing sequences)',
            category='optimization',
            priority=SkillPriority.HIGH,
            required_params=['sequence'],
            optional_params={
                'goal': 'balanced',
                'target': 'Gram-negative',
                'num_variants': 3,
                'rag_enhanced': True,
            },
            tags=['mutation', 'rag', 'optimization', 'refinement']
        )
    )
    
    logger.info(f"✅ Registered {len(registry.list_skills())} core skills")


# Auto-register on import
register_core_skills()