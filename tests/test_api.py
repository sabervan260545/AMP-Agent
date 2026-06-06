#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
FastAPI Test Script
===================
快速测试 FastAPI 应用是否正常启动
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / 'backend'))

def test_api_imports():
    """测试导入是否成功"""
    print("📝 Testing imports...")
    
    try:
        from fastapi import FastAPI
        print("✅ FastAPI imported")
    except ImportError as e:
        print(f"❌ FastAPI import failed: {e}")
        return False
    
    try:
        from backend.api.app import app
        print("✅ Backend API app imported")
    except ImportError as e:
        print(f"❌ Backend API import failed: {e}")
        return False
    
    try:
        from backend.api.routes.amp_design import router
        print("✅ AMP Design routes imported")
    except ImportError as e:
        print(f"❌ Routes import failed: {e}")
        return False
    
    return True


def test_app_structure():
    """测试应用结构"""
    print("\n📊 Testing app structure...")
    
    from backend.api.app import app
    
    # Check registered routes
    routes = []
    for route in app.routes:
        if hasattr(route, 'path'):
            routes.append(route.path)
    
    print(f"✅ Found {len(routes)} routes:")
    for route in routes[:10]:  # Show first 10
        print(f"   - {route}")
    
    if len(routes) > 10:
        print(f"   ... and {len(routes) - 10} more")
    
    return True


def test_pydantic_models():
    """测试 Pydantic 模型"""
    print("\n🧪 Testing Pydantic models...")
    
    from backend.api.routes.amp_design import (
        AMPDesignRequest,
        AMPSequence,
        AMPEvaluationRequest
    )
    
    # Test creating a request model
    try:
        req = AMPDesignRequest(
            target="E. coli",
            mechanism="membrane_disruption",
            num_candidates=10,
            generator="default",
            use_skill=True
        )
        print(f"✅ AMPDesignRequest created: {req.target}")
    except Exception as e:
        print(f"❌ Failed to create AMPDesignRequest: {e}")
        return False
    
    # Test creating a response model
    try:
        seq = AMPSequence(
            sequence="GLFDIVKKVVGALGSL",
            amp_probability=0.95,
            mic_um=2.5,
            hemolysis_score=0.12,
            cpp_score=0.08,
            generator="default"
        )
        print(f"✅ AMPSequence created: {seq.sequence}")
    except Exception as e:
        print(f"❌ Failed to create AMPSequence: {e}")
        return False
    
    return True


def main():
    """主测试函数"""
    print("=" * 70)
    print("FastAPI Application Test")
    print("=" * 70)
    
    # Test 1: Imports
    if not test_api_imports():
        print("\n❌ Import tests failed!")
        return False
    
    # Test 2: App structure
    if not test_app_structure():
        print("\n❌ App structure tests failed!")
        return False
    
    # Test 3: Pydantic models
    if not test_pydantic_models():
        print("\n❌ Pydantic model tests failed!")
        return False
    
    print("\n" + "=" * 70)
    print("✅ All tests passed!")
    print("=" * 70)
    print("\nTo start the API server, run:")
    print("  cd /data/amp-generator-platform")
    print("  uvicorn backend.api.app:app --host 0.0.0.0 --port 5000 --reload")
    print("\nThen visit:")
    print("  http://localhost:5000/api/docs")
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
