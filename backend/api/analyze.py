"""Energy analysis endpoint."""
from fastapi import APIRouter, HTTPException
from models.requests import AnalysisRequest
from services.energy_service import run_analysis

router = APIRouter()


@router.post("/analyze")
async def analyze_energy(req: AnalysisRequest):
    """Run energy proportion analysis, monthly trend, and intensity calculation."""
    if not req.energy_data:
        raise HTTPException(status_code=400, detail="能耗数据为空，请先解析数据")

    try:
        result = run_analysis(
            energy_data=req.energy_data,
            building_info=req.building_info,
            coal_factors_preset=req.coal_factors_preset,
        )
        result['building_info'] = req.building_info
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"能耗分析失败: {str(e)}")
