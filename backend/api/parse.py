"""Data parsing endpoints."""
import traceback
from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Query
from models.requests import ParseRequest
from services.parse_service import (
    parse_file, parse_text, parse_file_transposed, get_file_preview
)

router = APIRouter()


@router.post("/parse")
async def parse_data(req: ParseRequest):
    """Parse uploaded file or pasted text into structured energy data."""
    try:
        if req.file_id:
            result = parse_file(req.file_id, column_map=req.column_map, daily=req.daily)
        elif req.raw_text:
            result = parse_text(req.raw_text)
        else:
            raise HTTPException(
                status_code=400,
                detail="请提供 file_id（文件上传后获取）或 raw_text（粘贴表格数据）"
            )
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"数据解析异常: {str(e)}"
        )

    if result.get('error'):
        # Don't raise here — let the frontend decide what to do
        # Include error info + file_id so frontend can offer manual mapping
        return {
            **result,
            "parse_failed": True,
            "help": {
                "has_preview": bool(req.file_id),
                "suggestion": "自动解析失败，请尝试手动指定列映射或切换到「按建筑汇总」模式"
            }
        }

    energy_data = result.get('energy_data', [])
    if not energy_data:
        return {
            **result,
            "parse_failed": True,
            "help": {"suggestion": "未提取到能耗数据，请检查列名或使用手动映射"}
        }

    return result


class TransposedParseRequest(BaseModel):
    file_id: str
    sheet_name: Optional[str] = Field(None)
    start_row: int = Field(2, description="Data start row (1-based)")
    month_start_col: int = Field(2, description="First month column (1-based)")
    num_months: int = Field(12, description="Number of months")
    year: int = Field(2025)


@router.post("/parse/transposed")
async def parse_transposed(req: TransposedParseRequest):
    """Parse transposed data: rows=buildings, columns=months. Sums across rows."""
    try:
        result = parse_file_transposed(
            file_id=req.file_id,
            sheet_name=req.sheet_name,
            start_row=req.start_row,
            month_start_col=req.month_start_col,
            num_months=req.num_months,
            year=req.year,
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"转置解析异常: {str(e)}")

    if result.get('error'):
        raise HTTPException(status_code=400, detail=f"转置解析失败: {result['error']}")

    return result


@router.get("/preview/{file_id}")
async def preview_file(file_id: str):
    """Get a detailed preview of an uploaded file's structure."""
    try:
        preview = get_file_preview(file_id)
        if preview.get('error'):
            raise HTTPException(status_code=400, detail=preview['error'])
        return preview
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"文件预览异常: {str(e)}")
