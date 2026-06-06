#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
AMP-RAG Knowledge Base Builder
基于SpeLL论文构建AMP专用RAG知识库
"""

import json
import pickle
import pandas as pd
from pathlib import Path
from typing import Dict, List
import numpy as np
from sentence_transformers import SentenceTransformer


class AMPKnowledgeBuilder:
    """AMP知识库构建器"""
    
    def __init__(self, output_dir: str = "amp_knowledge_base"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # 编码器
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
    
    def build_code_rag_database(self):
        """构建AMP Code RAG数据库"""
        print("🔨 构建AMP Code RAG数据库...")
        
        # 扩展的AMP代码示例库
        amp_code_examples = {
            "sequence_generation_basic": {
                "description": "基础AMP序列生成算法",
                "keywords": ["生成", "序列", "抗菌肽", "随机"],
                "code": '''
# 基础AMP序列生成
import random
from typing import List

def generate_basic_amp(length: int = 20) -> str:
    """生成基础抗菌肽序列"""
    # 抗菌肽偏好氨基酸
    amp_aa = "KWRLIFGAPV"
    return ''.join(random.choices(amp_aa, k=length))

# 使用示例
sequence = generate_basic_amp(15)
print(f"Generated AMP: {sequence}")
                ''',
                "category": "generation"
            },
            
            "sequence_generation_advanced": {
                "description": "高级AMP序列生成，基于已知模式",
                "keywords": ["生成", "模式", "优化", "活性"],
                "code": '''
# 高级AMP序列生成
import numpy as np
from collections import Counter

def generate_pattern_based_amp(length: int, pattern: str = "cationic") -> str:
    """基于特定模式生成AMP序列"""
    patterns = {
        "cationic": {"K": 0.2, "R": 0.15, "H": 0.1, "L": 0.12, "I": 0.08, 
                    "F": 0.08, "W": 0.07, "G": 0.06, "A": 0.06, "V": 0.08},
        "hydrophobic": {"L": 0.15, "I": 0.15, "V": 0.12, "F": 0.12, "W": 0.1,
                       "A": 0.1, "G": 0.08, "P": 0.08, "K": 0.05, "R": 0.05}
    }
    
    aa_weights = patterns.get(pattern, patterns["cationic"])
    aa_list = list(aa_weights.keys())
    weights = list(aa_weights.values())
    
    sequence = ''.join(np.random.choice(aa_list, size=length, p=weights))
    return sequence

# 使用示例
cationic_amp = generate_pattern_based_amp(18, "cationic")
print(f"Cationic AMP: {cationic_amp}")
                ''',
                "category": "generation"
            },
            
            "activity_prediction_mic": {
                "description": "MIC活性预测模块",
                "keywords": ["MIC", "预测", "活性", "最小抑菌"],
                "code": '''
# MIC活性预测
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from modlamp.descriptors import PeptideDescriptor

def predict_mic_activity(sequence: str) -> Dict[str, float]:
    """预测最小抑菌浓度(MIC)"""
    # 计算肽描述符
    desc = PeptideDescriptor(sequence, 'eisenberg')
    desc.calculate_global()
    
    # 简化特征
    features = {
        'length': len(sequence),
        'charge': sequence.count('K') + sequence.count('R') - sequence.count('D') - sequence.count('E'),
        'hydrophobicity': desc.descriptor[0] if desc.descriptor else 0,
        'aromatic_ratio': (sequence.count('F') + sequence.count('W') + sequence.count('Y')) / len(sequence)
    }
    
    # 模拟MIC预测（实际应使用训练好的模型）
    base_mic = 64  # μg/ml
    charge_factor = max(0.1, 1 - features['charge'] * 0.1)
    hydro_factor = 1 - abs(features['hydrophobicity']) * 0.3
    
    predicted_mic = base_mic * charge_factor * hydro_factor
    
    return {
        'mic_ug_ml': round(predicted_mic, 2),
        'activity_class': 'high' if predicted_mic < 16 else 'medium' if predicted_mic < 64 else 'low'
    }

# 使用示例
mic_result = predict_mic_activity("KWKLFKKIEKVGQNIR")
print(f"MIC预测: {mic_result}")
                ''',
                "category": "prediction"
            },
            
            "hemolysis_prediction": {
                "description": "溶血活性预测模块",
                "keywords": ["溶血", "预测", "毒性", "安全性"],
                "code": '''
# 溶血活性预测
import math
from typing import Dict

def predict_hemolysis(sequence: str) -> Dict[str, float]:
    """预测溶血活性"""
    # 溶血相关特征
    length = len(sequence)
    hydrophobic_aa = "ILVFWMA"
    cationic_aa = "KRH"
    
    hydrophobic_ratio = sum(1 for aa in sequence if aa in hydrophobic_aa) / length
    cationic_ratio = sum(1 for aa in sequence if aa in cationic_aa) / length
    
    # 简化溶血预测模型
    # 基于文献: 疏水性越高、阳离子比例过高可能增加溶血
    hydro_factor = hydrophobic_ratio ** 2
    charge_factor = max(0, cationic_ratio - 0.3) * 2
    length_factor = max(0, (length - 25) / 10) if length > 25 else 0
    
    hemolysis_score = (hydro_factor + charge_factor + length_factor) / 3
    hemolysis_score = min(1.0, max(0.0, hemolysis_score))
    
    return {
        'hemolysis_score': round(hemolysis_score, 3),
        'safety_level': 'safe' if hemolysis_score < 0.3 else 'moderate' if hemolysis_score < 0.7 else 'high_risk',
        'hydrophobic_ratio': round(hydrophobic_ratio, 3),
        'cationic_ratio': round(cationic_ratio, 3)
    }

# 使用示例  
hemo_result = predict_hemolysis("KWKLFKKIEKVGQNIR")
print(f"溶血预测: {hemo_result}")
                ''',
                "category": "prediction"
            },
            
            "structure_optimization": {
                "description": "AMP结构优化算法",
                "keywords": ["优化", "结构", "改进", "设计"],
                "code": '''
# AMP结构优化
from typing import List, Tuple
import random

def optimize_amp_properties(sequence: str, target_charge: int = None, 
                           target_hydrophobicity: float = None) -> str:
    """优化AMP序列属性"""
    current_seq = list(sequence)
    
    # 当前属性计算
    current_charge = current_seq.count('K') + current_seq.count('R') - current_seq.count('D') - current_seq.count('E')
    
    # 电荷优化
    if target_charge is not None and current_charge != target_charge:
        if current_charge < target_charge:
            # 需要增加正电荷
            neutral_aa = [i for i, aa in enumerate(current_seq) if aa in 'AGILVFYW']
            if neutral_aa:
                pos = random.choice(neutral_aa)
                current_seq[pos] = random.choice(['K', 'R'])
        elif current_charge > target_charge:
            # 需要减少正电荷
            charged_aa = [i for i, aa in enumerate(current_seq) if aa in 'KR']
            if charged_aa:
                pos = random.choice(charged_aa)
                current_seq[pos] = random.choice(['A', 'G', 'L'])
    
    optimized_sequence = ''.join(current_seq)
    return optimized_sequence

def multi_objective_optimization(sequence: str, max_iterations: int = 100) -> List[str]:
    """多目标优化生成多个候选序列"""
    candidates = [sequence]
    
    for _ in range(max_iterations):
        # 随机选择优化目标
        if random.random() < 0.5:
            # 电荷优化
            target_charge = random.randint(2, 6)
            optimized = optimize_amp_properties(sequence, target_charge=target_charge)
        else:
            # 长度微调
            if len(sequence) < 25 and random.random() < 0.3:
                optimized = sequence + random.choice('KRL')
            else:
                optimized = optimize_amp_properties(sequence)
        
        if optimized not in candidates:
            candidates.append(optimized)
            if len(candidates) >= 5:  # 限制候选数量
                break
    
    return candidates[:5]

# 使用示例
original = "KWKLFKKIEKVGQNIR"
optimized_candidates = multi_objective_optimization(original)
print(f"优化候选: {optimized_candidates}")
                ''',
                "category": "optimization"
            }
        }
        
        # 保存Code RAG数据库
        code_rag_path = self.output_dir / "code_rag.pkl"
        with open(code_rag_path, 'wb') as f:
            pickle.dump(amp_code_examples, f)
        
        print(f"✅ Code RAG数据库已保存: {code_rag_path}")
        print(f"📊 包含 {len(amp_code_examples)} 个代码示例")
        
        return amp_code_examples
    
    def build_data_rag_database(self):
        """构建AMP Data RAG数据库"""
        print("🔨 构建AMP Data RAG数据库...")
        
        # 扩展的AMP历史数据集
        amp_datasets = [
            {
                "name": "antibacterial_short_peptides",
                "description": "短链抗菌肽数据集(10-20 AA)",
                "sequences": [
                    "KWKLFKKIEKVGQNIR",
                    "GLLGPLLKIAAKVG", 
                    "KWKLFKKIGAVLKVL",
                    "GFGCPFNQGACHRHF"
                ],
                "activities": {
                    "mic_ecoli": [8.2, 16.5, 12.1, 6.8],
                    "mic_staph": [4.1, 12.3, 8.9, 3.2],
                    "hemolysis": [0.15, 0.08, 0.12, 0.22]
                },
                "target_properties": {
                    "length_range": "10-20",
                    "charge_range": "2-6", 
                    "target_organisms": ["E.coli", "S.aureus"],
                    "activity_type": "antibacterial"
                },
                "preferred_methods": [
                    "sequence_generation_basic",
                    "activity_prediction_mic",
                    "hemolysis_prediction"
                ],
                "success_patterns": {
                    "high_lysine_content": True,
                    "moderate_hydrophobicity": True,
                    "amphipathic_structure": True
                }
            },
            
            {
                "name": "antifungal_medium_peptides", 
                "description": "中等长度抗真菌肽数据集(20-30 AA)",
                "sequences": [
                    "GFGCPFNQGACHRHFRRGGRSYWKGSLDDLL",
                    "KWKLFKKIGAVLKVLTTGLPALISWIKNR",
                    "GLFDIVKKVVGALGSL",
                    "KRFWWWTRKLTRKAGSDDMRIGGSGLGKLAAHVM"
                ],
                "activities": {
                    "mic_candida": [32.1, 16.8, 28.5, 12.3],
                    "mic_aspergillus": [64.2, 32.1, 48.7, 24.6],
                    "hemolysis": [0.18, 0.25, 0.14, 0.31]
                },
                "target_properties": {
                    "length_range": "20-35",
                    "charge_range": "3-8",
                    "target_organisms": ["C.albicans", "A.fumigatus"],
                    "activity_type": "antifungal"
                },
                "preferred_methods": [
                    "sequence_generation_advanced",
                    "structure_optimization",
                    "activity_prediction_mic"
                ],
                "success_patterns": {
                    "tryptophan_enriched": True,
                    "higher_charge_density": True,
                    "cyclic_preference": False
                }
            },
            
            {
                "name": "broad_spectrum_peptides",
                "description": "广谱抗菌肽数据集",
                "sequences": [
                    "GIGKFLHSAKKFGKAFVGEIMNS",
                    "KWKLFKKIEKVGQNIRDGIIKAG",
                    "LLGDFFRKSKEKIGKEFKRIVQRIKDFLRNLVPRTES"
                ],
                "activities": {
                    "mic_gram_positive": [4.2, 8.1, 6.5],
                    "mic_gram_negative": [8.7, 12.3, 11.2],
                    "antifungal_activity": [0.65, 0.78, 0.82],
                    "hemolysis": [0.09, 0.13, 0.16]
                },
                "target_properties": {
                    "length_range": "20-40",
                    "charge_range": "4-10",
                    "target_organisms": ["多种细菌", "真菌"],
                    "activity_type": "broad_spectrum"
                },
                "preferred_methods": [
                    "sequence_generation_advanced",
                    "multi_objective_optimization",
                    "activity_prediction_mic",
                    "hemolysis_prediction"
                ],
                "success_patterns": {
                    "balanced_composition": True,
                    "optimal_charge_distribution": True,
                    "low_hemolysis": True
                }
            }
        ]
        
        # 计算特征向量用于相似度匹配
        for dataset in amp_datasets:
            features = self._calculate_dataset_features(dataset)
            dataset['feature_vector'] = features
        
        # 保存Data RAG数据库
        data_rag_path = self.output_dir / "data_rag.pkl"
        with open(data_rag_path, 'wb') as f:
            pickle.dump(amp_datasets, f)
        
        print(f"✅ Data RAG数据库已保存: {data_rag_path}")
        print(f"📊 包含 {len(amp_datasets)} 个数据集")
        
        return amp_datasets
    
    def _calculate_dataset_features(self, dataset: Dict) -> np.ndarray:
        """计算数据集特征向量用于相似度匹配"""
        sequences = dataset['sequences']
        
        # 序列长度统计
        lengths = [len(seq) for seq in sequences]
        avg_length = np.mean(lengths)
        
        # 氨基酸组成统计
        all_seq = ''.join(sequences)
        aa_counts = {aa: all_seq.count(aa) for aa in 'ACDEFGHIKLMNPQRSTVWY'}
        total_aa = len(all_seq)
        aa_freqs = [aa_counts[aa] / total_aa for aa in 'ACDEFGHIKLMNPQRSTVWY']
        
        # 电荷和疏水性
        avg_charge = np.mean([seq.count('K') + seq.count('R') - seq.count('D') - seq.count('E') 
                             for seq in sequences])
        
        hydrophobic_aa = 'ILVFWM'
        avg_hydrophobic = np.mean([sum(1 for aa in seq if aa in hydrophobic_aa) / len(seq) 
                                  for seq in sequences])
        
        # 组合特征向量 [长度, 电荷, 疏水性, AA组成(20维)]
        features = [avg_length, avg_charge, avg_hydrophobic] + aa_freqs
        return np.array(features)
    
    def create_config_file(self):
        """创建RAG配置文件"""
        config = {
            "knowledge_base_info": {
                "code_rag": {
                    "description": "AMP设计代码示例库",
                    "categories": ["generation", "prediction", "optimization"],
                    "total_examples": 5
                },
                "data_rag": {
                    "description": "AMP历史数据集库", 
                    "categories": ["antibacterial", "antifungal", "broad_spectrum"],
                    "total_datasets": 3
                }
            },
            "retrieval_settings": {
                "similarity_threshold": 0.7,
                "max_code_examples": 3,
                "max_data_matches": 2,
                "embedding_model": "all-MiniLM-L6-v2"
            },
            "amp_design_workflows": {
                "basic_design": ["generation", "prediction"],
                "advanced_design": ["generation", "prediction", "optimization"],
                "safety_evaluation": ["prediction", "hemolysis", "optimization"]
            }
        }
        
        config_path = self.output_dir / "rag_config.json"
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        print(f"✅ RAG配置文件已创建: {config_path}")
        return config


def main():
    """主函数"""
    print("🏗️  开始构建AMP-RAG知识库...")
    
    builder = AMPKnowledgeBuilder()
    
    # 构建Code RAG
    code_examples = builder.build_code_rag_database()
    
    # 构建Data RAG  
    data_sets = builder.build_data_rag_database()
    
    # 创建配置文件
    config = builder.create_config_file()
    
    print("\n📋 知识库构建完成!")
    print(f"📁 输出目录: {builder.output_dir}")
    print(f"🔧 Code RAG: {len(code_examples)} 个示例")
    print(f"📊 Data RAG: {len(data_sets)} 个数据集")
    
    # 生成使用说明
    readme_content = f"""
# AMP-RAG Knowledge Base

基于SpeLL论文架构构建的抗菌肽(AMP)专用RAG知识库

## 目录结构
- `code_rag.pkl`: Code RAG代码示例库
- `data_rag.pkl`: Data RAG历史数据集库  
- `rag_config.json`: RAG系统配置文件

## 使用方式
```python
from agent.spell_enhanced_amp_agent import SpellEnhancedAmpAgent

# 创建Agent实例
agent = SpellEnhancedAmpAgent()

# 使用示例
result = agent.chat_with_spell_prm("设计一个抗菌肽序列")
print(result)
```

## 知识库统计
- Code RAG: {len(code_examples)} 个代码示例
- Data RAG: {len(data_sets)} 个数据集
- 构建时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    readme_path = builder.output_dir / "README.md"
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    print(f"📖 使用说明已生成: {readme_path}")


if __name__ == "__main__":
    main()