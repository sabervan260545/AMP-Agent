#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
Engine Tool Handler Test
========================
测试 Engine 的工具处理器功能
"""

import sys
from pathlib import Path

# Add agent to path
sys.path.insert(0, str(Path(__file__).parent / 'agent'))

def test_tool_imports():
    """测试工具导入"""
    print("📝 Testing tool imports...")
    
    try:
        from agent.core.amp_agent_engine import TOOLS_AVAILABLE
        print(f"✅ TOOLS_AVAILABLE: {TOOLS_AVAILABLE}")
        
        if TOOLS_AVAILABLE:
            from agent.tools.tools import (
                tool_generate_amp,
                tool_batch_evaluate,
                tool_rank_sequences,
                tool_structure_discrimination_pipeline
            )
            print("✅ All tools imported successfully")
        else:
            print("⚠️ Tools not available, using fallback")
        
        return True
    
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False


def test_engine_initialization():
    """测试 Engine 初始化"""
    print("\n🧪 Testing Engine initialization...")
    
    try:
        from agent.core.amp_agent_engine import AMPAgentEngine
        
        # Mock client (for testing only)
        class MockClient:
            class chat:
                class completions:
                    @staticmethod
                    def create(**kwargs):
                        return type('obj', (object,), {
                            'choices': [type('obj', (object,), {
                                'message': type('obj', (object,), {
                                    'content': 'Test response',
                                    'tool_calls': None
                                })()
                            })()]
                        })()
        
        engine = AMPAgentEngine(
            client=MockClient(),
            model_name="test-model",
            language="zh"
        )
        
        print(f"✅ Engine initialized: {engine.model}")
        print(f"✅ State manager: {engine.state is not None}")
        print(f"✅ Conversation manager: {engine.conversation is not None}")
        
        return True
    
    except Exception as e:
        print(f"❌ Engine initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tool_handlers():
    """测试工具处理器"""
    print("\n🔧 Testing tool handlers...")
    
    try:
        from agent.core.amp_agent_engine import AMPAgentEngine
        
        # Create mock engine
        engine = AMPAgentEngine(client=None, model_name="test")
        
        # Test generate handler
        result = engine._handle_generate_task({
            'num_samples': 5,
            'target': 'E. coli',
            'generator': 'default'
        })
        print(f"✅ Generate handler: {result[:50]}...")
        
        # Test design handler
        result = engine._handle_design_task({
            'target': 'S. aureus',
            'num_samples': 3
        })
        print(f"✅ Design handler: {result[:50]}...")
        
        # Test evaluate handler
        result = engine._handle_evaluate_task({
            'sequences': ['GLFDIVKKVVGALGSL', 'LL-37']
        })
        print(f"✅ Evaluate handler: {result[:50]}...")
        
        # Test rank handler
        result = engine._handle_rank_task({
            'data': [{'seq': 'A'}, {'seq': 'B'}],
            'strategy': 'pareto'
        })
        print(f"✅ Rank handler: {result[:50]}...")
        
        # Test structure handler
        result = engine._handle_structure_task({
            'target': 'E. coli',
            'sequences': ['GLFDIVKKVVGALGSL']
        })
        print(f"✅ Structure handler: {result[:50]}...")
        
        return True
    
    except Exception as e:
        print(f"❌ Tool handler test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("=" * 70)
    print("Engine Tool Handler Test Suite")
    print("=" * 70)
    
    tests = [
        ("Tool Imports", test_tool_imports),
        ("Engine Initialization", test_engine_initialization),
        ("Tool Handlers", test_tool_handlers)
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"\n💥 {name} crashed: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return True
    else:
        print(f"\n⚠️ {total - passed} tests failed")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
