"""
建筑能耗分析平台 — FastAPI 后端入口
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import CORS_ORIGINS, REPORT_DIR, UPLOAD_DIR
from api.router import router as api_router

# Create FastAPI app
app = FastAPI(
    title="建筑能耗分析平台 API",
    description="建筑能耗数据分析、碳排放计算与标准对标 API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api")

# Mount report downloads directory
app.mount("/api/report/download", StaticFiles(directory=REPORT_DIR), name="report_downloads")


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "建筑能耗分析平台",
        "version": "1.0.0",
    }


# ---- Production: serve frontend static files ----
# In development, the Vite dev server handles the frontend.
# In production, FastAPI serves the built React app.
FRONTEND_DIST = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'dist')
if os.path.isdir(FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
