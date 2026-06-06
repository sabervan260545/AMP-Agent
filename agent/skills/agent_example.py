# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
AMP Agent with Skills Integration - Example Code
=================================================

Demonstrates how to integrate and use the Skills system within the AMP Agent.
"""

import logging
from typing import Dict, Any, Optional
from skills import get_skill_registry, SkillResult

logger = logging.getLogger(__name__)


class SkillEnabledAgent:
    """
    AMP Agent extension with Skills support
    
    New capabilities:
    1. Intent recognition -> Route to appropriate Skill
    2. Skill orchestration -> Combine multiple Tools for complex tasks
    3. Dynamic decision -> Adjust workflow based on context
    """
    
    def __init__(self, base_agent):
        """
        Initialize Skill-enhanced Agent
        
        Args:
            base_agent: Existing AMPAgentV3 instance
        """
        self.base_agent = base_agent
        self.skill_registry = get_skill_registry()
        logger.info("✅ Skill-Enabled Agent initialized")
    
    def execute_skill(self, 
                     skill_name: str, 
                     **kwargs) -> SkillResult:
        """
        Execute a specified Skill
        
        Args:
            skill_name: Skill name
            **kwargs: Skill parameters
        
        Returns:
            SkillResult: Execution result
        """
        skill_func = self.skill_registry.get_skill(skill_name)
        
        if not skill_func:
            return SkillResult(
                success=False,
                message=f"Skill '{skill_name}' not found",
                data={}
            )
        
        try:
            logger.info(f"🚀 Executing skill: {skill_name}")
            logger.info(f"   Parameters: {kwargs}")
            
            result = skill_func(**kwargs)
            
            logger.info(f"✅ Skill {skill_name} completed")
            return result
            
        except Exception as e:
            logger.error(f"❌ Skill {skill_name} failed: {e}", exc_info=True)
            return SkillResult(
                success=False,
                message=f"Skill execution failed: {str(e)}",
                data={}
            )
    
    def list_available_skills(self, category: Optional[str] = None):
        """
        List all available Skills
        
        Args:
            category: Optional category filter ('design', 'evaluation', 'analysis')
        
        Returns:
            List[Dict]: List of Skill definitions
        """
        return self.skill_registry.list_skills(category=category)
    
    # ========================================================================
    # High-level skill methods (encapsulating common workflows)
    # ========================================================================
    
    def rapid_design_amp(self, 
                        target: str, 
                        num_candidates: int = 10) -> Dict[str, Any]:
        """
        Rapid AMP design (one-click invoke Rapid Design Skill)
        
        Args:
            target: Target organism
            num_candidates: Number of candidates
        
        Returns:
            Dict: Design results
        """
        result = self.execute_skill(
            'rapid_design',
            target=target,
            num_candidates=num_candidates
        )
        
        if result.success:
            return {
                'status': 'success',
                'message': result.message,
                'candidates': result.data.get('candidates', []),
                'metadata': result.metadata
            }
        else:
            return {
                'status': 'error',
                'message': result.message,
                'data': result.data
            }
    
    def structure_validated_design(self,
                                   target: str,
                                   num_candidates: int = 5) -> Dict[str, Any]:
        """
        Structure-validated design (one-click invoke Structure Validated Design Skill)
        
        Args:
            target: Target organism
            num_candidates: Number of candidates
        
        Returns:
            Dict: Design results (including structure info)
        """
        result = self.execute_skill(
            'structure_validated_design',
            target=target,
            num_candidates=num_candidates
        )
        
        if result.success:
            return {
                'status': 'success',
                'message': result.message,
                'candidates': result.data.get('candidates', []),
                'total_generated': result.data.get('total_generated'),
                'passed_structure_filter': result.data.get('passed_structure_filter'),
                'metadata': result.metadata
            }
        else:
            return {
                'status': 'error',
                'message': result.message,
                'data': result.data
            }
    
    def knowledge_guided_design(self,
                               target: str,
                               query_keywords: Optional[str] = None) -> Dict[str, Any]:
        """
        Knowledge-guided design (one-click invoke Knowledge Guided Design Skill)
        
        Args:
            target: Target organism
            query_keywords: Extra keywords
        
        Returns:
            Dict: Design results (including RAG-retrieved knowledge)
        """
        result = self.execute_skill(
            'knowledge_guided_design',
            target=target,
            query_keywords=query_keywords
        )
        
        if result.success:
            return {
                'status': 'success',
                'message': result.message,
                'candidates': result.data.get('candidates', []),
                'design_principles': result.data.get('design_principles_used'),
                'mechanisms': result.data.get('mechanisms_used'),
                'metadata': result.metadata
            }
        else:
            return {
                'status': 'error',
                'message': result.message,
                'data': result.data
            }


# ============================================================================
# Usage examples
# ============================================================================

def example_usage():
    """Example: How to use the Skill system"""
    
    # Assume base_agent exists
    # from amp_agent_v3 import AMPAgentV3
    # base_agent = AMPAgentV3(...)
    
    # Create Skill-enhanced Agent
    skill_agent = SkillEnabledAgent(base_agent=None)  # Pass real base_agent in production
    
    # Example 1: Rapid Design
    print("\n=== Example 1: Rapid Design ===")
    result = skill_agent.rapid_design_amp(
        target="E. coli",
        num_candidates=10
    )
    print(f"Status: {result['status']}")
    print(f"Message: {result['message']}")
    if result['status'] == 'success':
        print(f"Candidates: {len(result['candidates'])}")
        for i, cand in enumerate(result['candidates'][:3], 1):
            print(f"  {i}. {cand['sequence'][:20]}... (MIC: {cand['mic_um']})")
    
    # Example 2: Structure Validated Design
    print("\n=== Example 2: Structure Validated Design ===")
    result = skill_agent.structure_validated_design(
        target="S. aureus",
        num_candidates=5
    )
    print(f"Status: {result['status']}")
    print(f"Message: {result['message']}")
    if result['status'] == 'success':
        print(f"Total generated: {result['total_generated']}")
        print(f"Passed structure filter: {result['passed_structure_filter']}")
        for i, cand in enumerate(result['candidates'][:3], 1):
            print(f"  {i}. {cand['sequence'][:20]}... (Fold score: {cand['fold_score']})")
    
    # Example 3: Knowledge Guided Design
    print("\n=== Example 3: Knowledge Guided Design ===")
    result = skill_agent.knowledge_guided_design(
        target="P. aeruginosa",
        query_keywords="membrane disruption mechanism"
    )
    print(f"Status: {result['status']}")
    print(f"Message: {result['message']}")
    if result['status'] == 'success':
        print(f"Design principles used: {len(result['design_principles'])}")
        print(f"Mechanisms used: {len(result['mechanisms'])}")
        for i, cand in enumerate(result['candidates'][:3], 1):
            print(f"  {i}. {cand['sequence'][:20]}...")
    
    # List all available Skills
    print("\n=== Available Skills ===")
    skills = skill_agent.list_available_skills()
    for skill in skills:
        print(f"- {skill['name']} ({skill['category']}): {skill['description']}")


if __name__ == "__main__":
    example_usage()