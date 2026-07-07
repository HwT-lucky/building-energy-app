"""Pydantic request models for API endpoints."""
from typing import Optional
from pydantic import BaseModel, Field


class ParseRequest(BaseModel):
    """Request to parse uploaded file or pasted text."""
    file_id: Optional[str] = Field(None, description="Uploaded file ID from /api/upload")
    raw_text: Optional[str] = Field(None, description="Pasted table text (Markdown or plain)")
    column_map: Optional[dict] = Field(None, description='Manual column mapping, e.g. {"electricity_kwh": "E"}')
    daily: bool = Field(False, description="Whether data is daily cumulative meter readings")


class AnalysisRequest(BaseModel):
    """Request to run energy analysis."""
    energy_data: list[dict] = Field(..., description="Monthly energy data from parse step")
    building_info: dict = Field(..., description="Building metadata (name, area, type, location)")
    coal_factors_preset: str = Field("default", description="Coal factor preset: default|national|jiangsu_hotel|db31_783|db31_552|db31_1341")


class CarbonRequest(BaseModel):
    """Request to run carbon calculation and standard benchmark."""
    energy_data: list[dict] = Field(..., description="Monthly energy data")
    building_info: dict = Field(..., description="Building metadata")
    province: str = Field("", description="Province or city name")
    building_type: str = Field("", description="Building type: 办公/商业/酒店/学校/医院/住宅")
    star_rating: Optional[str] = Field(None, description="Star rating for hotel buildings")
    climate_zone: Optional[str] = Field(None, description="Climate zone for Jiangsu hotels")
    standard_choice: Optional[str] = Field(None, description="Manual standard override")


class ReportRequest(BaseModel):
    """Request to generate a Word report."""
    building_info: dict = Field(..., description="Building metadata")
    energy_proportion: dict = Field(..., description="Energy proportion analysis result")
    monthly_trend: dict = Field(..., description="Monthly trend analysis result")
    carbon_emission: dict = Field(..., description="Carbon emission calculation result")
    standard_comparison: dict = Field(..., description="Standard benchmark result")
    coal_per_m2_kgce: float = Field(0, description="Unit area coal consumption")
    carbon_intensity_kgco2_per_m2: float = Field(0, description="Unit area carbon intensity")
    data_notes: list[str] = Field(default_factory=list, description="Data quality notes")


class StandardMatchRequest(BaseModel):
    """Request to auto-match a standard."""
    building_type: str = Field("", description="Building type")
    province: str = Field("", description="Province or city name")
    city: str = Field("", description="City name (optional)")
