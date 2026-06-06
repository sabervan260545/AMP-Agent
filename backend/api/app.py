# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
AMP Backend API - FastAPI Application
=====================================
后端 API 服务主应用
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title="AMP Generator Platform API",
    description="Antimicrobial Peptide Design and Evaluation API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and register routers
from backend.api.routes import amp_design

app.include_router(amp_design.router)  # Router already has prefix="/api/v1/amp"


# ============================================================================
# Root Endpoint
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Welcome to AMP Generator Platform API",
        "version": "1.0.0",
        "docs": "/api/docs",
        "redoc": "/api/redoc",
        "health": "/api/v1/amp/health"
    }


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
async def health():
    """Global health check"""
    return {
        "status": "healthy",
        "service": "amp-backend-api"
    }


# ============================================================================
# Startup Event
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Application startup handler"""
    logger.info("🚀 AMP Backend API starting...")
    logger.info("✅ Registered routes:")
    
    for route in app.routes:
        if hasattr(route, 'methods'):
            for method in route.methods:
                logger.info(f"   {method} {route.path}")
    
    logger.info("✅ Startup complete!")


# ============================================================================
# Shutdown Event
# ============================================================================

@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown handler"""
    logger.info("🛑 AMP Backend API shutting down...")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
