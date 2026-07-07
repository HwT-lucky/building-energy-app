"""Standards reference endpoints."""
from fastapi import APIRouter, Query
from services.carbon_service import match_standard, get_available_standards, get_grid_factors

router = APIRouter()


@router.get("/standards")
async def list_standards():
    """List all supported energy/emission standards."""
    return {"standards": get_available_standards()}


@router.get("/standards/match")
async def auto_match_standard(
    building_type: str = Query("", description="Building type"),
    province: str = Query("", description="Province or city"),
    city: str = Query("", description="City (optional, for climate zone detection)"),
):
    """Auto-match applicable standard based on building type and location."""
    if not building_type or not province:
        return {
            "matched": False,
            "message": "请提供建筑类型和所在省份/城市以匹配合适的标准",
            "standard": None,
        }

    standard = match_standard(building_type, province, city)
    return {
        "matched": True,
        "standard": standard,
    }


@router.get("/factors/grid")
async def list_grid_factors():
    """List all regional grid emission factors."""
    return {"factors": get_grid_factors()}
