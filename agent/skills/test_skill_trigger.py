#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
Skill Trigger Mechanism Test Script
====================================

Tests how different user inputs trigger different Skills.
"""

from intent_recognizer import SkillIntentRecognizer


def test_skill_trigger():
    """Test Skill trigger logic"""
    
    recognizer = SkillIntentRecognizer()
    
    print("=" * 70)
    print("Skill Intent Recognition Test")
    print("=" * 70)
    
    test_cases = [
        # Rapid Design trigger words
        ("帮我快速设计 10 条抗大肠杆菌的肽", "rapid_design"),
        ("快设计一些 AMP，急用", "rapid_design"),
        ("Design 5 AMPs against E. coli quickly", "rapid_design"),
        
        # Structure Validated Design trigger words
        ("需要结构验证的设计，针对金黄色葡萄球菌", "structure_validated_design"),
        ("确保能正确折叠的穿膜肽", "structure_validated_design"),
        ("3D 结构验证后的 AMP 设计", "structure_validated_design"),
        
        # Knowledge Guided Design trigger words
        ("用 RAG 知识引导设计抗铜绿假单胞菌的肽", "knowledge_guided_design"),
        ("基于文献的 AMP 设计", "knowledge_guided_design"),
        ("Knowledge-guided design for Pseudomonas", "knowledge_guided_design"),
        
        # Multi-Generator Benchmark trigger words
        ("对比不同生成器的效果", "multi_generator_benchmark"),
        ("比较 Designer 和 Diff-AMP 的性能", "multi_generator_benchmark"),
        ("Run benchmark between generators", "multi_generator_benchmark"),
        
        # Cases that should NOT trigger a Skill (low confidence)
        ("什么是抗菌肽？", None),  # General question
        ("你好", None),  # Greeting
        ("设计一些肽", None),  # Too vague
    ]
    
    success_count = 0
    fail_count = 0
    
    for user_input, expected_skill in test_cases:
        result = recognizer.recognize(user_input)
        
        print(f"\n📝 Input: {user_input}")
        
        if result:
            matched_skill = result['skill_name']
            confidence = result['confidence']
            
            print(f"   ✅ Matched: {matched_skill}")
            print(f"   📊 Confidence: {confidence:.2f}")
            print(f"   🎯 Params: {result.get('params', {})}")
            
            # Check if matches expected
            if expected_skill == matched_skill:
                print(f"   ✓ Correctly matched expected skill")
                success_count += 1
            else:
                print(f"   ✗ Expected {expected_skill}, actual {matched_skill}")
                fail_count += 1
        else:
            print(f"   ❌ No intent matched")
            if expected_skill is None:
                print(f"   ✓ As expected (should not trigger a Skill)")
                success_count += 1
            else:
                print(f"   ✗ Expected {expected_skill} but no match")
                fail_count += 1
    
    # Summary statistics
    print("\n" + "=" * 70)
    print(f"Test Results: Success {success_count} / Total {len(test_cases)}")
    print(f"             Failed {fail_count} / Total {len(test_cases)}")
    print(f"             Accuracy: {success_count/len(test_cases)*100:.1f}%")
    print("=" * 70)


def demo_real_usage():
    """Demonstrate real-world usage scenarios"""
    
    print("\n\n")
    print("=" * 70)
    print("Real-World Usage Scenario Demo")
    print("=" * 70)
    
    recognizer = SkillIntentRecognizer()
    
    scenarios = [
        {
            'name': 'Scenario 1: Urgent task',
            'input': '我急需 10 条抗大肠杆菌的 AMP，要快！',
            'expected_skill': 'rapid_design'
        },
        {
            'name': 'Scenario 2: High-risk target',
            'input': '设计针对肿瘤细胞的穿膜肽，必须确保能正确折叠',
            'expected_skill': 'structure_validated_design'
        },
        {
            'name': 'Scenario 3: Exploratory research',
            'input': '我想用 RAG 检索的文献知识指导设计新型 AMP',
            'expected_skill': 'knowledge_guided_design'
        },
        {
            'name': 'Scenario 4: Systematic evaluation',
            'input': '对比一下我们平台三个生成器的性能差异',
            'expected_skill': 'multi_generator_benchmark'
        }
    ]
    
    for scenario in scenarios:
        print(f"\n\n{scenario['name']}")
        print(f"User Input: {scenario['input']}")
        print("-" * 60)
        
        result = recognizer.recognize(scenario['input'])
        
        if result and result['confidence'] >= 0.6:
            print(f"✅ Triggered Skill: {result['skill_name']}")
            print(f"   Confidence: {result['confidence']:.2f}")
            print(f"   Extracted Params: {result.get('params', {})}")
            print(f"\n🚀 Auto-executing workflow...")
            
            # This would call the corresponding Skill
            # skill_agent.execute_skill(result['skill_name'], **result['params'])
            
        else:
            print(f"⚠️ No clear intent detected, using traditional ReAct mode")


if __name__ == "__main__":
    test_skill_trigger()
    demo_real_usage()
    
    print("\n\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print("""
Skill Trigger Flow:

1. User enters natural language input
   ↓
2. SkillIntentRecognizer.recognize() analyzes intent
   ↓
3. If confidence >= 0.6:
   - Trigger the corresponding Skill
   - Auto-execute workflow
   - Return result
   ↓
4. If confidence < 0.6:
   - Fallback to traditional ReAct mode
   - Use Tools step by step

Key Files:
- intent_recognizer.py: Intent recognizer
- skill_integrated_agent.py: Integrated agent
- skills.py: Skill registry
- skill_implementations.py: Skill implementations
    """)
    print("=" * 70)