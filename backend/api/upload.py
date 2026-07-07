"""File upload endpoint."""
import os
from fastapi import APIRouter, UploadFile, File, HTTPException
from config import MAX_UPLOAD_SIZE_MB
from services.parse_service import save_upload_file, preview_file

router = APIRouter()

ALLOWED_EXTENSIONS = {'.xlsx', '.xls', '.csv'}


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload an Excel or CSV file for energy data parsing."""
    # Validate extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {ext}。仅支持 .xlsx、.xls、.csv 文件"
        )

    # Validate size
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_UPLOAD_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"文件大小 {size_mb:.1f}MB 超过限制（{MAX_UPLOAD_SIZE_MB}MB）"
        )

    # Save file
    file_id, filepath = save_upload_file(file.filename, content)

    # Generate preview
    preview = preview_file(filepath, max_rows=5)

    return {
        "file_id": file_id,
        "filename": file.filename,
        "size_bytes": len(content),
        "preview": preview,
    }
