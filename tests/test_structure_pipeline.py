#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
测试结构判别 pipeline
验证完整流程：生成 → ESMFold → PGAT-ABPp → MIC/Hemo/CPP
"""

import sys
sys.path.append('/data/amp-generator-platform/agent')

from tools import tool_structure_discrimination_pipeline
import json

def test_structure_pipeline():
    """测试结构判别 pipeline"""
    print("=" * 80)
    print("测试结构判别 Pipeline")
    print("=" * 80)
    
    # 测试参数
    test_params = {
        "target": "Gram-negative",
        "num_samples": 3,  # 小批量测试
        "pgat_threshold": 0.5,
        "generator": "default",
        "mic_threshold": 32.0,
        "hemolysis_threshold": 10.0
    }
    
    print(f"\n🔧 测试参数:")
    print(json.dumps(test_params, indent=2))
    print()
    
    # 执行 pipeline
    print("🚀 开始执行 pipeline...\n")
    result = tool_structure_discrimination_pipeline(**test_params)
    
    # 显示结果
    print("\n" + "=" * 80)
    print("📊 Pipeline 结果")
    print("=" * 80)
    
    if result.get("success"):
        print("\n✅ Pipeline 执行成功!\n")
        
        stages = result.get("pipeline_stages", {})
        print("📈 各阶段统计:")
        print(f"  - 生成序列数: {stages.get('generated', 0)}")
        print(f"  - 结构预测成功: {stages.get('structure_predicted', 0)}")
        print(f"  - 通过 PGAT 筛选: {stages.get('passed_pgat', 0)}")
        print(f"  - 最终候选数: {stages.get('final_candidates', 0)}")
        
        sequences = result.get("sequences", [])
        if sequences:
            print(f"\n🏆 Top {min(3, len(sequences))} 候选序列:\n")
            for i, seq_data in enumerate(sequences[:3]):
                print(f"{i+1}. {seq_data['sequence']}")
                print(f"   Generator: {seq_data.get('generator', 'N/A')}")
                print(f"   PGAT Score: {seq_data.get('pgat_score', 0):.3f}")
                if seq_data.get('mic_pred'):
                    print(f"   MIC: {seq_data['mic_pred']:.2f} μg/mL")
                if seq_data.get('hemolysis_pred'):
                    print(f"   Hemolysis: {seq_data['hemolysis_pred']:.2f}%")
                if seq_data.get('cpp_pred'):
                    print(f"   CPP: {seq_data['cpp_pred']:.3f}")
                print(f"   Passes Thresholds: {seq_data.get('passes_thresholds', False)}")
                print()
        
        print("\n📝 摘要:")
        print(result.get("summary", "N/A"))
        
    else:
        print("\n❌ Pipeline 执行失败!\n")
        print("错误信息:")
        for err in result.get("errors", []):
            print(f"  - {err}")
        print(f"\n摘要: {result.get('summary', 'N/A')}")
    
    # 显示完整结果 (JSON 格式)
    print("\n" + "=" * 80)
    print("🔍 完整结果 (JSON)")
    print("=" * 80)
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    test_structure_pipeline()
