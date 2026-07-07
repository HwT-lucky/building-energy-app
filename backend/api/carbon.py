"""Carbon calculation and standard benchmark endpoint."""
from fastapi import APIRouter, HTTPException
from models.requests import CarbonRequest
from services.carbon_service import run_carbon_analysis

router = APIRouter()


@router.post("/carbon")
async def calculate_carbon(req: CarbonRequest):
    """Calculate carbon emissions and benchmark against applicable standard."""
    if not req.energy_data:
        raise HTTPException(status_code=400, detail="能耗数据为空，请先解析数据")

    try:
        result = run_carbon_analysis(
            energy_data=req.energy_data,
            building_info=req.building_info,
            province=req.province,
            building_type=req.building_type,
            star_rating=req.star_rating or '',
            climate_zone=req.climate_zone or '',
            standard_choice=req.standard_choice or '',
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"碳排放计算失败: {str(e)}")
