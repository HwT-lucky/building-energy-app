"""Main API router — includes all sub-routers and the full pipeline convenience endpoint."""
from fastapi import APIRouter, HTTPException
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from services.parse_service import parse_file, parse_text
from services.energy_service import run_analysis
from services.carbon_service import run_carbon_analysis

from api.upload import router as upload_router
from api.parse import router as parse_router
from api.analyze import router as analyze_router
from api.carbon import router as carbon_router
from api.report import router as report_router
from api.standards import router as standards_router
from api.chat import router as chat_router

router = APIRouter()

# Include sub-routers
router.include_router(upload_router, tags=["upload"])
router.include_router(parse_router, tags=["parse"])
router.include_router(analyze_router, tags=["analyze"])
router.include_router(carbon_router, tags=["carbon"])
router.include_router(report_router, tags=["report"])
router.include_router(standards_router, tags=["standards"])
router.include_router(chat_router, tags=["chat"])


# ---- Convenience: Full pipeline in one call ----

class PipelineRequest(BaseModel):
    """Combined request for running the full pipeline — all optional."""
    file_id: Optional[str] = Field(None)
    raw_text: Optional[str] = Field(None)
    energy_data: Optional[List[Dict[str, Any]]] = Field(None)
    column_map: Optional[Dict[str, str]] = Field(None)
    daily: bool = Field(False)
    building_info: Optional[Dict[str, Any]] = Field(default_factory=dict)
    coal_factors_preset: str = Field("default")
    province: str = Field("")
    building_type: str = Field("")
    star_rating: Optional[str] = Field(None)
    climate_zone: Optional[str] = Field(None)
    standard_choice: Optional[str] = Field(None)


@router.post("/pipeline/full")
async def pipeline_full(req: PipelineRequest):
    """
    Run the full analysis pipeline in one call.

    Steps:
    1. Parse data (from file_id or raw_text)
    2. Run energy analysis
    3. Run carbon calculation + standard benchmark
    """
    # Step 1: Parse (or use pre-parsed data)
    if req.energy_data:
        energy_data = req.energy_data
        building_info = req.building_info or {}
        sheet_name = None
        data_type = "pre_parsed"
        parse_warnings = []
    elif req.file_id:
        parsed = parse_file(req.file_id, column_map=req.column_map, daily=req.daily)
        if parsed.get('error'):
            raise HTTPException(status_code=400, detail=f"数据解析失败: {parsed['error']}")
        energy_data = parsed.get('energy_data', [])
        building_info = parsed.get('building_info', {})
        sheet_name = parsed.get('sheet_name')
        data_type = parsed.get('data_type')
        parse_warnings = parsed.get('warnings', [])
    elif req.raw_text:
        parsed = parse_text(req.raw_text)
        if parsed.get('error'):
            raise HTTPException(status_code=400, detail=f"数据解析失败: {parsed['error']}")
        energy_data = parsed.get('energy_data', [])
        building_info = parsed.get('building_info', {})
        sheet_name = parsed.get('sheet_name')
        data_type = parsed.get('data_type')
        parse_warnings = parsed.get('warnings', [])
    else:
        raise HTTPException(status_code=400, detail="请提供 energy_data、file_id 或 raw_text")

    # Merge with request-level building_info (request takes priority)
    if req.building_info:
        for k, v in req.building_info.items():
            if v:
                building_info[k] = v

    # Step 2: Energy Analysis
    try:
        analysis = run_analysis(
            energy_data=energy_data,
            building_info=building_info,
            coal_factors_preset=req.coal_factors_preset,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"能耗分析失败: {str(e)}")

    # Step 3: Carbon + Benchmark
    province = req.province or building_info.get('location', '')
    building_type = req.building_type or building_info.get('type', '')

    try:
        carbon = run_carbon_analysis(
            energy_data=energy_data,
            building_info=building_info,
            province=province,
            building_type=building_type,
            star_rating=req.star_rating or '',
            climate_zone=req.climate_zone or '',
            standard_choice=req.standard_choice or '',
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"碳排放计算失败: {str(e)}")

    return {
        "building_info": building_info,
        "parsed_data": {
            "energy_data": energy_data,
            "sheet_name": parsed.get('sheet_name'),
            "data_type": parsed.get('data_type'),
            "warnings": parsed.get('warnings', []),
        },
        **analysis,
        "carbon_emission": {
            "total_emission_tons": carbon.get('total_emission_tons', 0),
            "carbon_intensity_kgco2_per_m2": carbon.get('carbon_intensity_kgco2_per_m2', 0),
            "emission_breakdown": carbon.get('emission_breakdown', {}),
            "monthly_emission": carbon.get('monthly_emission', []),
            "grid_factor_used": carbon.get('grid_factor_used', 0),
            "region": carbon.get('region', ''),
        },
        "standard_comparison": carbon.get('standard_comparison', {}),
        "total_coal_kgce": carbon.get('total_coal_kgce', 0),
        "coal_per_m2_kgce": carbon.get('coal_per_m2_kgce', 0),
        "carbon_intensity_kgco2_per_m2": carbon.get('carbon_intensity_kgco2_per_m2', 0),
    }
