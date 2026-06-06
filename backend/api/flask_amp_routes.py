# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
AMP Standardized API Routes for Flask
======================================
将 FastAPI 的标准化接口迁移到 Flask
保持与原有 /api/ 路由的一致性
"""

from flask import Blueprint, request, jsonify
import logging

logger = logging.getLogger(__name__)

# Create blueprint
amp_api = Blueprint('amp_api', __name__, url_prefix='/api/v1/amp')


# ============================================================================
# Health Check
# ============================================================================

@amp_api.route('/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({
        "status": "healthy",
        "service": "amp-flask-api",
        "version": "1.0.0"
    })


# ============================================================================
# AMP Design Endpoint
# ============================================================================

@amp_api.route('/design', methods=['POST'])
def design_amp():
    """
    设计 AMP 候选序列
    
    Request JSON:
    {
        "target": "E. coli",
        "mechanism": "membrane_disruption",
        "num_candidates": 10,
        "generator": "default",
        "use_skill": true
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No input data provided"}), 400
        
        target = data.get('target', 'E. coli')
        num_candidates = data.get('num_candidates', 10)
        generator = data.get('generator', 'default')
        use_skill = data.get('use_skill', True)
        
        logger.info(f"🎯 Design request: target={target}, num={num_candidates}, skill={use_skill}")
        
        # TODO: 调用 Agent Engine 或 Skill 系统
        # from agent.core import AMPAgentEngine
        # or
        # from agent.skills import SkillRegistry
        
        # Mock response (占位符)
        mock_sequences = [
            {
                "sequence": f"GLFDIVKKVVGALGSL{i}",
                "amp_probability": round(0.95 - i * 0.05, 2),
                "mic_um": round(2.5 + i * 0.5, 1),
                "hemolysis_score": round(0.12 + i * 0.02, 2),
                "cpp_score": round(0.08 + i * 0.01, 2),
                "generator": generator
            }
            for i in range(min(num_candidates, 5))
        ]
        
        return jsonify(mock_sequences)
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"❌ Design failed: {e}", exc_info=True)
        return jsonify({"error": f"设计失败：{str(e)}"}), 500


# ============================================================================
# AMP Evaluation Endpoint
# ============================================================================

@amp_api.route('/evaluate', methods=['POST'])
def evaluate_amp():
    """
    批量评估 AMP 序列
    
    Request JSON:
    {
        "sequences": ["GLFDIVKKVVGALGSL", "LL-37"]
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No input data provided"}), 400
        
        sequences = data.get('sequences', [])
        
        if not sequences:
            return jsonify({"error": "No sequences provided"}), 400
        
        logger.info(f"📊 Evaluate request: {len(sequences)} sequences")
        
        # TODO: 调用评估工具
        # from agent.tools import tool_batch_evaluate
        # results = tool_batch_evaluate(sequences)
        
        # Mock response (占位符)
        mock_results = [
            {
                "sequence": seq,
                "amp_probability": 0.9,
                "mic_um": 3.0,
                "hemolysis_score": 0.15,
                "cpp_score": 0.1,
                "macrel_score": 0.85
            }
            for seq in sequences[:5]  # Limit to 5 for demo
        ]
        
        return jsonify(mock_results)
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"❌ Evaluation failed: {e}", exc_info=True)
        return jsonify({"error": f"评估失败：{str(e)}"}), 500


# ============================================================================
# Error Handlers
# ============================================================================

@amp_api.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404


@amp_api.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500
