# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
Skill-Integrated AMP Agent (V3 Enhanced)
========================================

Integrated agent that combines:
1. AMPAgentV3: existing AMP design capabilities
2. Skills system: high-level task orchestration
3. Intent recognition: automatic Skill selection

Provides:
- Backward compatible: supports existing API
- Skills enabled: can call high-level Skills
- Auto routing: automatically selects appropriate Skill
- Fallback: if Skill fails, falls back to base agent behavior
"""

import logging
from typing import Dict, Any, Optional
from .intent_recognizer import SkillIntentRecognizer
from .agent_example import SkillEnabledAgent

logger = logging.getLogger(__name__)


class SkillIntegratedAgent:
    """
    Skill-integrated AMP Agent
    
    Workflow:
    1. Recognize user intent
    2. Route to appropriate Skill
    3. Execute Skill workflow
    4. Fallback to base agent if needed
    """
    
    def __init__(self, base_agent=None):
        """
        Initialize Skill-integrated Agent
        
        Args:
            base_agent: AMPAgentV3 instance (or None for demo mode)
        """
        self.base_agent = base_agent
        self.skill_agent = SkillEnabledAgent(base_agent)
        self.intent_recognizer = SkillIntentRecognizer()
        
        # Supported Skills mapping
        self.skill_methods = {
            'rapid_design': self.skill_agent.rapid_design_amp,
            'structure_validated_design': self.skill_agent.structure_validated_design,
            'knowledge_guided_design': self.skill_agent.knowledge_guided_design,
        }
        
        logger.info("✅ Skill-Integrated Agent initialized")
    
    def process(self, user_input: str, **kwargs) -> Dict[str, Any]:
        """
        Process user request (main entry point)
        
        Args:
            user_input: User input in natural language
            **kwargs: Additional parameters
        
        Returns:
            Dict: Processing result
        """
        logger.info(f"🔍 Processing user request: {user_input[:100]}...")
        
        # Step 1: Recognize intent
        intent = self.intent_recognizer.recognize(user_input)
        
        if intent is None:
            logger.warning("⚠️ No intent matched, falling back to base agent")
            return self._fallback_to_base(user_input, **kwargs)
        
        skill_name = intent['skill_name']
        confidence = intent['confidence']
        params = intent['params']
        
        logger.info(f"🎯 Recognized intent: {skill_name} (confidence: {confidence:.2f})")
        
        # Merge params (user-provided kwargs override extracted params)
        merged_params = {**params, **kwargs}
        
        # Step 2: Route to Skill
        if skill_name in self.skill_methods:
            try:
                result = self.skill_methods[skill_name](**merged_params)
                result['_intent'] = {
                    'skill_name': skill_name,
                    'confidence': confidence
                }
                return result
            except Exception as e:
                logger.error(f"❌ Skill {skill_name} failed: {e}", exc_info=True)
                return self._fallback_to_base(user_input, **kwargs)
        else:
            logger.warning(f"⚠️ Skill {skill_name} not implemented, falling back to base")
            return self._fallback_to_base(user_input, **kwargs)
    
    def _fallback_to_base(self, user_input: str, **kwargs) -> Dict[str, Any]:
        """Fallback to base agent behavior"""
        if self.base_agent:
            logger.info("🔄 Falling back to base agent")
            try:
                return self.base_agent.process(user_input, **kwargs)
            except Exception as e:
                logger.error(f"❌ Base agent also failed: {e}")
                return {
                    'status': 'error',
                    'message': f'Both skill and base agent failed: {str(e)}',
                    'user_input': user_input
                }
        else:
            return {
                'status': 'info',
                'message': 'No base agent configured. Please provide required parameters.',
                'user_input': user_input,
                'available_skills': self.skill_agent.list_available_skills()
            }
    
    def execute_skill_by_name(self, skill_name: str, **kwargs) -> Dict[str, Any]:
        """Directly execute a specified skill"""
        if skill_name in self.skill_methods:
            return self.skill_methods[skill_name](**kwargs)
        else:
            return {
                'status': 'error',
                'message': f'Unknown skill: {skill_name}',
                'available_skills': list(self.skill_methods.keys())
            }
    
    def list_capabilities(self) -> Dict[str, Any]:
        """List all capabilities"""
        return {
            'skills': self.skill_agent.list_available_skills(),
            'supports_intent_recognition': True,
            'fallback_to_base': self.base_agent is not None,
            'supported_intents': self.intent_recognizer.list_supported_intents()
        }


# ============================================================================
# Demo / Testing
# ============================================================================

def demo():
    """Demonstrate Skill-Integrated Agent functionality"""
    
    print("=" * 70)
    print("Skill-Integrated AMP Agent Demo")
    print("=" * 70)
    
    # Create agent (demo mode, no real base agent)
    agent = SkillIntegratedAgent(base_agent=None)
    
    # List capabilities
    print("\n📋 Available Capabilities:")
    capabilities = agent.list_capabilities()
    print(f"  Skills: {len(capabilities['skills'])}")
    for skill in capabilities['skills']:
        print(f"    - {skill['name']} ({skill['category']}): {skill['description']}")
    print(f"  Supported intents: {capabilities['supported_intents']}")
    print(f"  Has base agent fallback: {capabilities['fallback_to_base']}")
    
    # Test cases
    test_queries = [
        "帮我快速设计 10 条抗大肠杆菌的肽",
        "Design 5 structure-validated AMPs against S. aureus",
        "用知识引导设计抗铜绿假单胞菌的 AMP",
        "你好，今天天气怎么样？",  # No matching intent
    ]
    
    print("\n" + "=" * 70)
    print("Testing Intent Recognition + Skill Routing")
    print("=" * 70)
    
    for query in test_queries:
        print(f"\n{'─' * 60}")
        print(f"📝 User Input: {query}")
        print(f"{'─' * 60}")
        
        result = agent.process(query)
        
        if result.get('status') == 'info':
            # No matching intent or no base agent
            print(f"  Response: {result['message']}")
            if 'available_skills' in result:
                print(f"  Hint: available skills: {[s['name'] for s in result['available_skills']]}")
        elif result.get('status') == 'success':
            print(f"  ✅ Intent: {result.get('_intent', {}).get('skill_name', 'unknown')}")
            print(f"  ✅ Message: {result['message']}")
        else:
            print(f"  ❌ Status: {result.get('status')}")
            print(f"  ❌ Message: {result.get('message')}")
    
    print("\n" + "=" * 70)
    print("Demo Complete!")
    print("=" * 70)


if __name__ == "__main__":
    demo()