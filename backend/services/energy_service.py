"""Service layer wrapping the skill's energy_analysis.py functions."""
import sys
import os

from config import SKILL_SCRIPTS_DIR
if SKILL_SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SKILL_SCRIPTS_DIR)

import energy_analysis


# Preset name to energy_analysis key mapping
PRESET_MAP = {
    'default': 'default',        # DB31/T 783-2026
    'national': 'national',      # GB/T 2589
    'jiangsu_hotel': 'jiangsu_hotel',
    'db31_783': 'default',
    'db31_552': 'default',
    'db31_1341': 'national',
}


def run_analysis(energy_data: list, building_info: dict, coal_factors_preset: str = 'default') -> dict:
    """Run energy proportion, monthly trend, and intensity analysis."""
    preset_key = PRESET_MAP.get(coal_factors_preset, 'default')
    energy_analysis.COAL_FACTORS = energy_analysis.COAL_FACTORS_PRESETS[preset_key]

    area = building_info.get('area', 0)

    proportion = energy_analysis.calc_energy_proportion(energy_data)
    trend = energy_analysis.calc_monthly_trend(energy_data)
    intensity = energy_analysis.calc_unit_area_intensity(energy_data, area)
    warnings = energy_analysis.validate_data(energy_data)

    return {
        'energy_proportion': proportion,
        'monthly_trend': trend,
        'unit_area_intensity': intensity,
        'warnings': warnings,
    }
