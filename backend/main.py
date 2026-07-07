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


@app.get("/api/debug/paths")
async def debug_paths():
    """Debug endpoint to check file paths on deployed server."""
    return {
        "cwd": os.getcwd(),
        "file": __file__,
        "frontend_dist": FRONTEND_DIST,
        "dist_exists": os.path.isdir(FRONTEND_DIST),
        "dist_contents": os.listdir(FRONTEND_DIST) if os.path.isdir(FRONTEND_DIST) else [],
        "parent_contents": os.listdir(os.path.dirname(FRONTEND_DIST)) if os.path.isdir(os.path.dirname(FRONTEND_DIST)) else [],
    }


# MUST mount static files after all API routes
if os.path.isdir(FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
else:
    @app.get("/")
    async def root_fallback():
        from fastapi.responses import HTMLResponse
        return HTMLResponse(f"<h1>前端文件未找到</h1><p>路径: {FRONTEND_DIST}</p><p>存在: {os.path.isdir(FRONTEND_DIST)}</p><p>cwd: {os.getcwd()}</p>")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
