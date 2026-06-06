# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
AMP Design API Routes
=====================
AMP 设计相关的 RESTful 接口
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/amp", tags=["AMP Design"])


# ============================================================================
# Request/Response Models
# ============================================================================

class AMPDesignRequest(BaseModel):
    """AMP 设计请求模型"""
    
    target: str = Field(..., description="靶标生物（如：'E. coli', 'S. aureus'）")
    mechanism: Optional[str] = Field(
        "membrane_disruption",
        description="作用机制（如：'membrane_disruption', 'intracellular_target'）"
    )
    num_candidates: int = Field(10, ge=1, le=100, description="候选序列数量")
    generator: Optional[str] = Field(
        "default",
        description="生成器选择（'default', 'designer', 'hydramp', 'diff_amp'）"
    )
    use_skill: bool = Field(True, description="是否使用 Skill 模式")
    
    class Config:
        json_schema_extra = {
            "example": {
                "target": "E. coli",
                "mechanism": "membrane_disruption",
                "num_candidates": 10,
                "generator": "default",
                "use_skill": True
            }
        }


class AMPSequence(BaseModel):
    """AMP 序列响应模型"""
    
    sequence: str = Field(..., description="氨基酸序列")
    amp_probability: float = Field(..., ge=0, le=1, description="AMP 概率")
    mic_um: Optional[float] = Field(None, ge=0, description="MIC (μM)")
    hemolysis_score: Optional[float] = Field(None, ge=0, le=1, description="溶血性评分")
    cpp_score: Optional[float] = Field(None, ge=0, le=1, description="穿膜肽评分")
    generator: Optional[str] = Field(None, description="使用的生成器")
    
    class Config:
        json_schema_extra = {
            "example": {
                "sequence": "GLFDIVKKVVGALGSL",
                "amp_probability": 0.95,
                "mic_um": 2.5,
                "hemolysis_score": 0.12,
                "cpp_score": 0.08,
                "generator": "default"
            }
        }


class AMPEvaluationRequest(BaseModel):
    """AMP 评估请求模型"""
    
    sequences: List[str] = Field(..., description="待评估的氨基酸序列列表")
    metrics: Optional[List[str]] = Field(
        ["mic", "hemolysis", "cpp", "macrel"],
        description="评估指标列表"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "sequences": ["GLFDIVKKVVGALGSL", "LL-37"],
                "metrics": ["mic", "hemolysis", "cpp"]
            }
        }


class EvaluatedSequence(BaseModel):
    """评估后的序列模型"""
    
    sequence: str
    amp_probability: Optional[float]
    mic_um: Optional[float]
    hemolysis_score: Optional[float]
    cpp_score: Optional[float]
    macrel_score: Optional[float]
    
    class Config:
        json_schema_extra = {
            "example": {
                "sequence": "GLFDIVKKVVGALGSL",
                "amp_probability": 0.95,
                "mic_um": 2.5,
                "hemolysis_score": 0.12,
                "cpp_score": 0.08,
                "macrel_score": 0.88
            }
        }


class APIResponse(BaseModel):
    """通用 API 响应模型"""
    
    success: bool
    message: str
    data: Optional[Any] = None
    error: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "操作成功完成",
                "data": {},
                "error": None
            }
        }


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("/design", response_model=List[AMPSequence])
async def design_amp(request: AMPDesignRequest):
    """
    设计 AMP 候选序列
    
    ## 功能说明
    - 根据靶标生物和作用机制生成 AMP 候选序列
    - 支持多种生成器（AMP-Designer, HydrAMP, Diff-AMP）
    - 可选 Skill 模式（自动化工作流）或传统 Tool 模式
    
    ## 参数说明
    - **target**: 靶标生物（必需）
    - **mechanism**: 作用机制（可选，默认：membrane_disruption）
    - **num_candidates**: 候选数量（可选，默认：10，范围：1-100）
    - **generator**: 生成器选择（可选，默认：default）
    - **use_skill**: 是否使用 Skill 模式（可选，默认：True）
    
    ## 返回说明
    - AMP 序列列表，包含序列、AMP 概率、MIC、溶血性、CPP 等指标
    
    ## 异常处理
    - 400: 参数错误
    - 500: 服务器内部错误（生成器故障、API 超时等）
    """
    try:
        logger.info(f"🎯 Design request: target={request.target}, num={request.num_candidates}")
        
        # TODO: 调用 Agent Engine
        # from agent.core import AMPAgentEngine
        # engine = AMPAgentEngine(...)
        # result = await engine.design(
        #     target=request.target,
        #     num_candidates=request.num_candidates,
        #     generator=request.generator,
        #     use_skill=request.use_skill
        # )
        
        # 模拟响应（占位符）
        mock_sequences = [
            AMPSequence(
                sequence=f"GLFDIVKKVVGALGSL{i}",
                amp_probability=0.95 - i * 0.05,
                mic_um=2.5 + i * 0.5,
                hemolysis_score=0.12 + i * 0.02,
                cpp_score=0.08 + i * 0.01,
                generator=request.generator
            )
            for i in range(min(request.num_candidates, 5))
        ]
        
        logger.info(f"✅ Generated {len(mock_sequences)} sequences")
        return mock_sequences
        
    except ValueError as e:
        logger.error(f"❌ Invalid parameter: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        logger.error(f"❌ Design failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"设计失败：{str(e)}")


@router.post("/evaluate", response_model=List[EvaluatedSequence])
async def evaluate_amp(request: AMPEvaluationRequest):
    """
    评估 AMP 序列
    
    ## 功能说明
    - 批量评估氨基酸序列的各项指标
    - 支持 MIC、溶血性、CPP、Macrel 等多种评估
    - 异步并行计算，快速返回结果
    
    ## 参数说明
    - **sequences**: 待评估的序列列表（必需）
    - **metrics**: 评估指标列表（可选，默认：全部指标）
    
    ## 返回说明
    - 评估结果列表，包含原始序列和各项指标评分
    
    ## 异常处理
    - 400: 序列格式错误或空列表
    - 500: 评估服务故障
    """
    try:
        if not request.sequences:
            raise ValueError("序列列表不能为空")
        
        logger.info(f"🧪 Evaluate request: {len(request.sequences)} sequences")
        
        # TODO: 调用评估服务
        # from backend.services import EvaluationService
        # service = EvaluationService()
        # results = await service.batch_evaluate(
        #     sequences=request.sequences,
        #     metrics=request.metrics
        # )
        
        # 模拟响应（占位符）
        mock_results = [
            EvaluatedSequence(
                sequence=seq,
                amp_probability=0.90,
                mic_um=3.0,
                hemolysis_score=0.15,
                cpp_score=0.10,
                macrel_score=0.85
            )
            for seq in request.sequences[:5]  # 限制返回数量
        ]
        
        logger.info(f"✅ Evaluated {len(mock_results)} sequences")
        return mock_results
        
    except ValueError as e:
        logger.error(f"❌ Invalid parameter: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        logger.error(f"❌ Evaluation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"评估失败：{str(e)}")


@router.get("/health")
async def health_check():
    """
    健康检查接口
    
    用于检测 AMP Design 服务是否正常运行
    """
    return {
        "status": "healthy",
        "service": "amp-design-api",
        "version": "1.0.0"
    }
