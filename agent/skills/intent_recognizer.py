# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
Skill Intent Recognition - Skill Intent Recognizer
===================================================

Automatically selects the appropriate Skill based on user input.
"""

import re
from typing import Dict, Optional, List


class SkillIntentRecognizer:
    """
    Skill Intent Recognizer
    
    Automatically matches the most appropriate Skill by analyzing keywords
    in user input.
    """
    
    def __init__(self):
        # Define intent pattern mapping
        self.intent_patterns = {
            'rapid_design': [
                r'快速.*设计',
                r'快.*设计',
                r'简单.*设计',
                r'直接.*设计',
                r'设计.*急用',
                r'design.*fast',
                r'quick.*design',
                r'rapid.*design'
            ],
            'structure_validated_design': [
                r'结构.*验证',
                r'结构.*设计',
                r'折叠.*验证',
                r'3D.*验证',
                r'可折叠',
                r'structure.*validat',
                r'fold.*validat',
                r'确保.*正确折叠'
            ],
            'knowledge_guided_design': [
                r'知识.*引导',
                r'知识.*增强',
                r'RAG.*设计',
                r'文献.*指导',
                r'机制.*设计',
                r'原理.*指导',
                r'knowledge.*guid',
                r'RAG.*design',
                r'literature.*based'
            ],
            'multi_generator_benchmark': [
                r'对比.*生成器',
                r'比较.*模型',
                r'benchmark',
                r'多个.*生成器',
                r'不同.*模型',
                r'compare.*generator',
                r'multiple.*model'
            ],
            'mutation_optimization': [
                r'突变.*序列',
                r'序列.*突变',
                r'优化.*序列',
                r'序列.*优化',
                r'改进.*序列',
                r'序列.*改进',
                r'改造.*序列',
                r'重设计',
                r'提升活性',
                r'降低溶血',
                r'突变改造',
                r'序列.*改造',
                r'mutate.*sequence',
                r'optimize.*sequence',
                r'improve.*sequence',
                r'redesign.*peptide',
                r'enhance.*amp',
                r'refine.*sequence',
                r'mutation.*optim',
                r'point.*mutation',
                r'amino.*acid.*substitut',
                r'mutate',
            ]
        }
        
        # Parameter extraction rules
        self.param_extractors = {
            'target': [
                r'针对 (.+?) 的',
                r'抗 (.+?) ',
                r'target[：:]\s*(.+?)(?:,|。|$)',
                r'against\s+(.+?)(?:\s|,|\.)'
            ],
            'num_candidates': [
                r'(\d+)\s*条',
                r'(\d+)\s*个',
                r'(\d+)\s*sequences?',
                r'num[=:]\s*(\d+)'
            ]
        }
    
    def recognize(self, user_input: str) -> Optional[Dict]:
        """
        Recognize user intent
        
        Args:
            user_input: User input in natural language
        
        Returns:
            Dict: {'skill_name': str, 'confidence': float, 'params': Dict}
            None: If no matching intent found
        """
        user_input_lower = user_input.lower()
        
        best_match = None
        best_score = 0
        
        # Iterate all intent patterns
        for skill_name, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, user_input_lower):
                    # Calculate match confidence
                    score = self._calculate_confidence(user_input, pattern)
                    
                    if score > best_score:
                        best_score = score
                        best_match = skill_name
                    break
        
        # Return None if no match
        if best_match is None:
            return None
        
        # Extract parameters
        params = self._extract_params(user_input)
        
        return {
            'skill_name': best_match,
            'confidence': best_score,
            'params': params
        }
    
    def _calculate_confidence(self, text: str, pattern: str) -> float:
        """Calculate match confidence (0.0 - 1.0)"""
        # Base match
        base_score = 0.7
        
        # Exact match bonus
        if re.search(pattern, text.lower()):
            base_score += 0.2
        
        # Multiple keyword match bonus
        keywords = pattern.split('.*')
        keyword_count = sum(1 for kw in keywords if kw and kw in text.lower())
        bonus = min(0.1 * keyword_count, 0.3)
        
        return min(base_score + bonus, 1.0)
    
    def _extract_params(self, text: str) -> Dict[str, any]:
        """Extract parameters"""
        params = {}
        
        # Extract target
        for pattern in self.param_extractors['target']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                params['target'] = match.group(1).strip()
                break
        
        # Extract num_candidates
        for pattern in self.param_extractors['num_candidates']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    params['num_candidates'] = int(match.group(1))
                except ValueError:
                    pass
                break
        
        return params
    
    def list_supported_intents(self) -> List[str]:
        """List all supported intents"""
        return list(self.intent_patterns.keys())


# Usage examples
if __name__ == "__main__":
    recognizer = SkillIntentRecognizer()
    
    test_cases = [
        "帮我快速设计 10 条抗大肠杆菌的肽",
        "Design 5 AMPs against E. coli quickly",
        "需要结构验证的设计，针对金黄色葡萄球菌",
        "用 RAG 知识引导设计抗铜绿假单胞菌的肽",
        "对比不同生成器的效果"
    ]
    
    for text in test_cases:
        result = recognizer.recognize(text)
        print(f"\nInput: {text}")
        if result:
            print(f"  Matched Skill: {result['skill_name']}")
            print(f"  Confidence: {result['confidence']:.2f}")
            print(f"  Params: {result['params']}")
        else:
            print("  ❌ No intent matched")