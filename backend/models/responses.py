"""Pydantic response models for API endpoints."""
from typing import Optional
from pydantic import BaseModel, Field


class BuildingInfo(BaseModel):
    """Building metadata extracted from uploaded file."""
    name: str = ""
    area: float = 0
    type: str = ""
    location: str = ""
    year: int = 0
    source: str = ""


class EnergyMonthRecord(BaseModel):
    """One month of energy consumption data."""
    month: int
    electricity_kwh: float = 0
    gas_m3: float = 0
    heat_gj: float = 0
    water_ton: float = 0


class ParsedData(BaseModel):
    """Response from parse step."""
    building_info: dict = Field(default_factory=dict)
    energy_data: list[dict] = Field(default_factory=list)
    sheet_name: Optional[str] = None
    data_type: Optional[str] = None
    warnings: list[dict] = Field(default_factory=list)
    error: Optional[str] = None


class StandardComparisonResult(BaseModel):
    """Standard benchmark comparison result."""
    status: str = ""
    standard_source: Optional[str] = None
    building_type: Optional[str] = None
    level: Optional[str] = None
    icon: Optional[str] = None
    suggestion: Optional[str] = None
    # Energy metrics
    energy_level: Optional[str] = None
    energy_icon: Optional[str] = None
    energy_actual: Optional[float] = None
    energy_constraint: Optional[float] = None
    energy_benchmark: Optional[float] = None
    energy_guide: Optional[float] = None
    energy_unit: Optional[str] = None
    energy_message: Optional[str] = None
    # Carbon metrics (Jiangsu hotel standard)
    carbon_level: Optional[str] = None
    carbon_icon: Optional[str] = None
    carbon_actual: Optional[float] = None
    carbon_constraint: Optional[float] = None
    carbon_benchmark: Optional[float] = None
    carbon_guide: Optional[float] = None
    carbon_unit: Optional[str] = None
    carbon_message: Optional[str] = None
    # Combined
    message: Optional[str] = None
    # DB31/T 783 specific
    coal_per_m2_raw: Optional[float] = None
    coal_per_m2_corrected: Optional[float] = None
    alpha1: Optional[float] = None
    alpha2: Optional[float] = None
    correction_formula: Optional[str] = None


class AnalysisResult(BaseModel):
    """Complete analysis result combining all steps."""
    building_info: dict = Field(default_factory=dict)
    energy_proportion: dict = Field(default_factory=dict)
    monthly_trend: dict = Field(default_factory=dict)
    unit_area_intensity: dict = Field(default_factory=dict)
    warnings: list[dict] = Field(default_factory=list)


class CarbonResult(BaseModel):
    """Complete carbon calculation result."""
    total_emission_tons: float = 0
    carbon_intensity_kgco2_per_m2: float = 0
    emission_breakdown: dict = Field(default_factory=dict)
    monthly_emission: list[dict] = Field(default_factory=list)
    standard_comparison: dict = Field(default_factory=dict)
    total_coal_kgce: float = 0
    coal_per_m2_kgce: float = 0
    grid_factor_used: float = 0
    region: str = ""


class ReportTaskStatus(BaseModel):
    """Async report generation status."""
    task_id: str
    status: str  # "processing" | "completed" | "failed"
    progress: int = 0
    download_url: Optional[str] = None
    error: Optional[str] = None


class FileUploadResponse(BaseModel):
    """Response from file upload."""
    file_id: str
    filename: str
    size_bytes: int
    preview: Optional[dict] = None


class StandardInfo(BaseModel):
    """Information about a supported standard."""
    name: str
    full_name: str
    description: str
    applicable_building_types: list[str] = Field(default_factory=list)
    applicable_regions: list[str] = Field(default_factory=list)
    judgment_levels: int = 2  # 2 or 3
    coal_electricity: float = 0
    coal_gas: float = 0
    is_equivalent_value: bool = True


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None
    hint: Optional[str] = None
