#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
Skill 触发机制测试脚本
======================

测试不同的用户输入如何触发不同的 Skills。
"""

from agent.skills.intent_recognizer import SkillIntentRecognizer


def test_skill_trigger():
    """测试 Skill 触发逻辑"""
    
    recognizer = SkillIntentRecognizer()
    
    print("=" * 70)
    print("Skill 意图识别测试")
    print("=" * 70)
    
    test_cases = [
        # Rapid Design 触发词
        ("帮我快速设计 10 条抗大肠杆菌的肽", "rapid_design"),
        ("快设计一些 AMP，急用", "rapid_design"),
        ("Design 5 AMPs against E. coli quickly", "rapid_design"),
        
        # Structure Validated Design 触发词
        ("需要结构验证的设计，针对金黄色葡萄球菌", "structure_validated_design"),
        ("确保能正确折叠的穿膜肽", "structure_validated_design"),
        ("3D 结构验证后的 AMP 设计", "structure_validated_design"),
        
        # Knowledge Guided Design 触发词
        ("用 RAG 知识引导设计抗铜绿假单胞菌的肽", "knowledge_guided_design"),
        ("基于文献的 AMP 设计", "knowledge_guided_design"),
        ("Knowledge-guided design for Pseudomonas", "knowledge_guided_design"),
        
        # Multi-Generator Benchmark 触发词
        ("对比不同生成器的效果", "multi_generator_benchmark"),
        ("比较 Designer 和 Diff-AMP 的性能", "multi_generator_benchmark"),
        ("Run benchmark between generators", "multi_generator_benchmark"),
        
        # 不会触发 Skill 的情况（置信度低）
        ("什么是抗菌肽？", None),  # 普通问题
        ("你好", None),  # 打招呼
        ("设计一些肽", None),  # 太模糊
    ]
    
    success_count = 0
    fail_count = 0
    
    for user_input, expected_skill in test_cases:
        result = recognizer.recognize(user_input)
        
        print(f"\n📝 输入：{user_input}")
        
        if result:
            matched_skill = result['skill_name']
            confidence = result['confidence']
            
            print(f"   ✅ 匹配：{matched_skill}")
            print(f"   📊 置信度：{confidence:.2f}")
            print(f"   🎯 参数：{result.get('params', {})}")
            
            # 检查是否匹配预期
            if expected_skill == matched_skill:
                print(f"   ✓ 正确匹配预期技能")
                success_count += 1
            else:
                print(f"   ✗ 预期 {expected_skill}, 实际 {matched_skill}")
                fail_count += 1
        else:
            print(f"   ❌ 未匹配到意图")
            if expected_skill is None:
                print(f"   ✓ 符合预期（不应触发 Skill）")
                success_count += 1
            else:
                print(f"   ✗ 预期 {expected_skill} 但未匹配")
                fail_count += 1
    
    # 统计结果
    print("\n" + "=" * 70)
    print(f"测试结果：成功 {success_count} / 总计 {len(test_cases)}")
    print(f"         失败 {fail_count} / 总计 {len(test_cases)}")
    print(f"         准确率：{success_count/len(test_cases)*100:.1f}%")
    print("=" * 70)


def demo_real_usage():
    """演示真实使用场景"""
    
    print("\n\n")
    print("=" * 70)
    print("真实使用场景演示")
    print("=" * 70)
    
    recognizer = SkillIntentRecognizer()
    
    scenarios = [
        {
            'name': '场景 1: 紧急任务',
            'input': '我急需 10 条抗大肠杆菌的 AMP，要快！',
            'expected_skill': 'rapid_design'
        },
        {
            'name': '场景 2: 高风险靶标',
            'input': '设计针对肿瘤细胞的穿膜肽，必须确保能正确折叠',
            'expected_skill': 'structure_validated_design'
        },
        {
            'name': '场景 3: 探索性研究',
            'input': '我想用 RAG 检索的文献知识指导设计新型 AMP',
            'expected_skill': 'knowledge_guided_design'
        },
        {
            'name': '场景 4: 系统评估',
            'input': '对比一下我们平台三个生成器的性能差异',
            'expected_skill': 'multi_generator_benchmark'
        }
    ]
    
    for scenario in scenarios:
        print(f"\n\n{scenario['name']}")
        print(f"用户输入：{scenario['input']}")
        print("-" * 60)
        
        result = recognizer.recognize(scenario['input'])
        
        if result and result['confidence'] >= 0.6:
            print(f"✅ 触发 Skill: {result['skill_name']}")
            print(f"   置信度：{result['confidence']:.2f}")
            print(f"   提取参数：{result.get('params', {})}")
            print(f"\n🚀 自动执行工作流...")
            
            # 这里会调用对应的 Skill
            # skill_agent.execute_skill(result['skill_name'], **result['params'])
            
        else:
            print(f"⚠️ 未检测到明确意图，使用传统 ReAct 模式")


if __name__ == "__main__":
    test_skill_trigger()
    demo_real_usage()
    
    print("\n\n" + "=" * 70)
    print("总结")
    print("=" * 70)
    print("""
Skill 触发流程:

1. 用户输入自然语言
   ↓
2. SkillIntentRecognizer.recognize() 分析意图
   ↓
3. 如果置信度 >= 0.6:
   - 触发对应 Skill
   - 自动执行工作流
   - 返回结果
   ↓
4. 如果置信度 < 0.6:
   - 降级到传统 ReAct 模式
   - 使用 Tools 逐个调用

关键文件:
- skill_intent_recognizer.py: 意图识别器
- skill_integrated_agent.py: 集成 Agent
- skills.py: Skill 注册中心
- skill_implementations.py: Skill 实现
    """)
    print("=" * 70)
