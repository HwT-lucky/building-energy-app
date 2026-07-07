/** TypeScript interfaces matching the Python backend JSON output */

export interface BuildingInfo {
  name: string;
  area: number;
  type: string;
  location: string;
  year: number;
  source?: string;
}

export interface EnergyMonthRecord {
  month: number;
  electricity_kwh: number;
  gas_m3: number;
  heat_gj: number;
  water_ton?: number;
}

export interface EnergyProportionItem {
  energy_type: string;
  label: string;
  unit: string;
  amount: number;
  coal_equiv_kgce: number;
  proportion_pct: number;
}

export interface EnergyProportion {
  energy_totals: Record<string, number>;
  coal_equiv: Record<string, number>;
  total_coal_kgce: number;
  proportions: EnergyProportionItem[];
}

export interface MonthlyDataPoint {
  month: number;
  electricity_kwh: number;
  gas_m3: number;
  heat_gj: number;
  total_coal_kgce: number;
}

export interface MonthlyTrend {
  monthly_data: MonthlyDataPoint[];
  peak_month: MonthlyDataPoint | null;
  valley_month: MonthlyDataPoint | null;
  monthly_avg_coal_kgce: number;
  total_annual_coal_kgce: number;
  anomalies: Array<{ month: number; type: string; value: number; avg: number; ratio: number }>;
  seasonal_analysis: Record<string, unknown>;
}

export interface UnitAreaIntensity {
  area_m2: number;
  electricity_per_m2: number;
  gas_per_m2: number;
  heat_per_m2: number;
  total_coal_per_m2: number;
  error?: string;
}

export interface AnalysisResult {
  building_info: BuildingInfo;
  energy_proportion: EnergyProportion;
  monthly_trend: MonthlyTrend;
  unit_area_intensity: UnitAreaIntensity;
  warnings: Array<{ type: string; message: string }>;
}

export interface EmissionBreakdown {
  electricity: { amount: number; unit: string; factor: number; factor_unit: string; co2_tons: number; pct: number };
  gas: { amount: number; unit: string; factor: number; factor_unit: string; co2_tons: number; pct: number };
  heat: { amount: number; unit: string; factor: number; factor_unit: string; co2_tons: number; pct: number };
}

export interface MonthlyEmission {
  month: number;
  co2_elec: number;
  co2_gas: number;
  co2_heat: number;
  co2_total: number;
}

export interface StandardComparison {
  status: string;
  standard_source?: string;
  building_type?: string;
  level?: string;
  icon?: string;
  suggestion?: string;
  message?: string;
  energy_level?: string;
  energy_icon?: string;
  energy_actual?: number;
  energy_constraint?: number;
  energy_benchmark?: number;
  energy_guide?: number;
  energy_unit?: string;
  energy_message?: string;
  carbon_level?: string;
  carbon_icon?: string;
  carbon_actual?: number;
  carbon_constraint?: number;
  carbon_benchmark?: number;
  carbon_guide?: number;
  carbon_unit?: string;
  carbon_message?: string;
  climate_zone?: string;
  coal_factors_used?: string;
  [key: string]: unknown;
}

export interface CarbonResult {
  total_emission_tons: number;
  carbon_intensity_kgco2_per_m2: number;
  emission_breakdown: EmissionBreakdown;
  monthly_emission: MonthlyEmission[];
  standard_comparison: StandardComparison;
  total_coal_kgce: number;
  coal_per_m2_kgce: number;
  grid_factor_used: number;
  region: string;
}

export interface ParsedData {
  building_info: BuildingInfo;
  energy_data: EnergyMonthRecord[];
  sheet_name?: string;
  data_type?: string;
  warnings: Array<{ type: string; message: string }>;
  error?: string;
}

export interface StandardInfo {
  standard_name: string;
  standard_full: string;
  coal_factors_preset: string;
  coal_electricity: number;
  coal_gas: number;
  is_equivalent_value: boolean;
  judgment_levels: number;
  needs_alpha: boolean;
  needs_star_rating: boolean;
  needs_climate_zone: boolean;
  climate_zone?: string;
  grid_factor: number;
  region: string;
}

export interface FullPipelineResult extends AnalysisResult {
  parsed_data: { energy_data: EnergyMonthRecord[]; sheet_name?: string; data_type?: string; warnings: unknown[] };
  carbon_emission: {
    total_emission_tons: number;
    carbon_intensity_kgco2_per_m2: number;
    emission_breakdown: EmissionBreakdown;
    monthly_emission: MonthlyEmission[];
    grid_factor_used: number;
    region: string;
  };
  standard_comparison: StandardComparison;
  total_coal_kgce: number;
  coal_per_m2_kgce: number;
  carbon_intensity_kgco2_per_m2: number;
}

/** Wizard state — holds all user input across steps */
export interface WizardState {
  // Step 1: Upload
  fileId: string | null;
  rawText: string | null;
  filename: string | null;

  // Step 2: Parsed data
  parsedData: ParsedData | null;
  columnMap: Record<string, string> | null;

  // Step 3: Config
  buildingName: string;
  area: number | null;
  buildingType: string;
  province: string;
  city: string;
  year: number;
  starRating: string;
  climateZone: string;

  // Step 4: Standard
  matchedStandard: StandardInfo | null;
  confirmedStandard: boolean;
  coalFactorsPreset: string;
  alpha1: number;
  alpha2: number;
  alpha4: number;

  // Step 5: Results
  analysisResult: AnalysisResult | null;
  carbonResult: CarbonResult | null;
  fullResult: FullPipelineResult | null;
  isLoading: boolean;
}
