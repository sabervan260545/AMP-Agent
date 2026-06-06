# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
English text configuration (Chinese removed)
"""

TEXTS = {
    "en": {
        # Execution steps
        "step_generate": "⏳ [Step {current}/{total}] Generating candidates...",
        "step_evaluate": "⏳ [Step {current}-{end}/{total}] Comprehensive evaluation (AMP/MIC/Hemo/CPP)...",
        "step_rank": "⏳ [Step {current}/{total}] Intelligent ranking...",
        "step_structure": "\n🧬 [Additional Step] Predicting 3D structure of best sequence...",
        
        # Results
        "generated": " ✅ Generated {count} sequences ({time:.1f}s)\n",
        "generated_insufficient": " ⚠️ Generated {actual} (target {target}, insufficient) ({time:.1f}s)\n",
        "evaluated": " ✅ ({time:.1f}s)\n",
        "ranked": " ✅\n",
        "filtered": "⚠️ Filtered out {count} substandard sequences\n",
        "structure_success": " ✅ ({time:.1f}s)\n",
        "structure_failed": " ⚠️ Structure prediction failed\n",
        
        # Report
        "report_title": "\n🎯 Design Report\n",
        "report_target": "Target: {target}",
        "report_count": "Candidates: {count}",
        "report_best": "\n🏆 Best Sequence: {sequence}\n",
        "report_metrics": "\n Performance Metrics:\n",
        "metric_mic": "MIC Activity: {value} μM",
        "metric_amp": "AMP Probability: {value}",
        "metric_hemo": "Hemolysis Risk: {value}",
        "metric_cpp": "CPP Capability: {value}",
        "report_structure": "\n🧬 3D Structure Info:\n",
        "report_table": "\n⏳ Generating detailed data table...\n",
        
        # Task planning
        "plan_title": "\n📋 Task Plan ({total} steps):\n",
        "plan_step": "   {num}. {desc}\n",
        
        # Task completion
        "task_complete": "\n✅ **Task completed.**\n",
        "generation_complete": "✅ Generation completed: {count} sequences\n",
        "evaluation_complete": "✅ Evaluation completed: {count} sequences\n",
        "no_eval_data": "⚠️ Error: No evaluation data available, please call evaluate_amp first\n",
        "visualization_complete": "✅ {message}\n",
        
        # Visualization titles
        "viz_radar": "\n#### 🎯 Comprehensive Performance Radar Chart\n",
        "viz_success_rate": "\n#### 🏆 Valid AMP Generation Success Rate\n",
        "viz_mic_dist": "\n#### 💊 MIC Activity Distribution Comparison\n",
        "viz_mic_scatter": "\n#### 📈 MIC vs AMP Probability Scatter Plot\n",
        "viz_heatmap": "\n#### 🌡️ Quality Score Heatmap\n",
    },
    "zh": {
        # Execution steps
        "step_generate": "⏳ [步骤 {current}/{total}] 生成候选序列...",
        "step_evaluate": "⏳ [步骤 {current}-{end}/{total}] 综合评估 (AMP/MIC/溶血/CPP)...",
        "step_rank": "⏳ [步骤 {current}/{total}] 智能排序...",
        "step_structure": "\n🧬 [额外步骤] 预测最佳序列的3D结构...",
        
        # Results
        "generated": " ✅ 生成 {count} 条序列 ({time:.1f}秒)\n",
        "generated_insufficient": " ⚠️ 生成 {actual} 条 (目标 {target}，不足) ({time:.1f}秒)\n",
        "evaluated": " ✅ ({time:.1f}秒)\n",
        "ranked": " ✅\n",
        "filtered": "⚠️ 过滤掉 {count} 条不达标序列\n",
        "structure_success": " ✅ ({time:.1f}秒)\n",
        "structure_failed": " ⚠️ 结构预测失败\n",
        
        # Report
        "report_title": "\n🎯 设计报告\n",
        "report_target": "目标: {target}",
        "report_count": "候选数: {count}",
        "report_best": "\n🏆 最佳序列: {sequence}\n",
        "report_metrics": "\n 性能指标:\n",
        "metric_mic": "MIC活性: {value} μM",
        "metric_amp": "AMP概率: {value}",
        "metric_hemo": "溶血风险: {value}",
        "metric_cpp": "CPP能力: {value}",
        "report_structure": "\n🧬 3D结构信息:\n",
        "report_table": "\n⏳ 生成详细数据表...\n",
        
        # Task planning
        "plan_title": "\n📋 任务计划 (共{total}步):\n",
        "plan_step": "   {num}. {desc}\n",
        
        # Task completion
        "task_complete": "\n✅ **任务执行完毕。**\n",
        "generation_complete": "✅ 生成完成：{count} 条序列\n",
        "evaluation_complete": "✅ 评估完成：{count} 条序列\n",
        "no_eval_data": "⚠️ 错误：没有可用的评估数据，请先调用 evaluate_amp\n",
        "visualization_complete": "✅ {message}\n",
        
        # Visualization titles
        "viz_radar": "\n#### 🎯 综合性能雷达图\n",
        "viz_success_rate": "\n#### 🏆 有效AMP生成成功率\n",
        "viz_mic_dist": "\n#### 💊 MIC活性分布对比\n",
        "viz_mic_scatter": "\n#### 📈 MIC vs AMP概率散点图\n",
        "viz_heatmap": "\n#### 🌡️ 质量评分热力图\n",
    }
}
