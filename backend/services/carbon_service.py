"""Service layer wrapping the skill's carbon_calculation.py functions."""
import sys
import os

from config import SKILL_SCRIPTS_DIR
if SKILL_SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SKILL_SCRIPTS_DIR)

import carbon_calculation


def run_carbon_analysis(
    energy_data: list,
    building_info: dict,
    province: str = '',
    building_type: str = '',
    star_rating: str = '',
    climate_zone: str = '',
    standard_choice: str = '',
    alpha1: float = None,
    alpha2: float = None,
    alpha4: float = None,
) -> dict:
    """Run carbon emission calculation and standard benchmarking."""
    area = building_info.get('area', 0)
    if not building_type:
        building_type = building_info.get('type', '')
    if not province:
        province = building_info.get('location', '')

    # Set coal factors based on standard choice
    if standard_choice == 'db31_783':
        carbon_calculation.set_coal_factors('db31_783')
    elif standard_choice == 'jiangsu_hotel':
        carbon_calculation.set_coal_factors('jiangsu_hotel')
    elif standard_choice == 'db31_552':
        carbon_calculation.set_coal_factors('db31_552')
    elif standard_choice == 'db31_1341':
        carbon_calculation.set_coal_factors('db31_1341')
    else:
        # Auto-detect
        province_std, city = carbon_calculation.resolve_province(province)
        if province_std == '上海' and any(kw in str(building_type) for kw in ['学校', '大学', '高校', '学院', '教育']):
            carbon_calculation.set_coal_factors('db31_783')
        elif province_std == '上海' and any(kw in str(building_type) for kw in ['商业', '商场', '购物', '百货', '超市', '餐饮']):
            carbon_calculation.set_coal_factors('db31_552')
        elif province_std == '上海' and any(kw in str(building_type) for kw in ['办公', '商务']):
            carbon_calculation.set_coal_factors('db31_1341')
        elif province_std == '江苏' and any(kw in str(building_type) for kw in ['酒店', '旅馆', '宾馆']):
            carbon_calculation.set_coal_factors('jiangsu_hotel')
        else:
            carbon_calculation.set_coal_factors('national')

    # Calculate total coal
    total_coal = 0
    for r in energy_data:
        total_coal += (
            (r.get('electricity_kwh', 0) or 0) * carbon_calculation.COAL_FACTORS['electricity_kwh'] +
            (r.get('gas_m3', 0) or 0) * carbon_calculation.COAL_FACTORS['gas_m3'] +
            (r.get('heat_gj', 0) or 0) * carbon_calculation.COAL_FACTORS['heat_gj']
        )
    coal_per_m2 = total_coal / area if area > 0 else 0

    # Carbon emission
    emission = carbon_calculation.calc_carbon_emission(energy_data, province)
    carbon_per_m2 = emission['total_emission_tons'] * 1000 / area if area > 0 else 0

    # Standard comparison
    comparison = carbon_calculation.compare_with_standard(
        coal_per_m2, carbon_per_m2, building_type, province,
        star_rating=star_rating or '',
        climate_zone=climate_zone or '',
        standard_choice=standard_choice or '',
        alpha1=alpha1,
        alpha2=alpha2,
        alpha4=alpha4,
    )

    return {
        **emission,
        'carbon_intensity_kgco2_per_m2': round(carbon_per_m2, 2),
        'total_coal_kgce': round(total_coal, 2),
        'coal_per_m2_kgce': round(coal_per_m2, 2),
        'standard_comparison': comparison,
    }


def match_standard(building_type: str, province: str, city: str = '') -> dict:
    """Auto-match applicable standard for the given building type and location."""
    province_std, city_name = carbon_calculation.resolve_province(province)
    btype = str(building_type)

    result = {
        'standard_name': '',
        'standard_full': '',
        'coal_factors_preset': 'national',
        'coal_electricity': 0.1229,
        'coal_gas': 1.2143,
        'is_equivalent_value': False,
        'judgment_levels': 2,
        'needs_alpha': False,
        'needs_star_rating': False,
        'needs_climate_zone': False,
        'grid_factor': carbon_calculation.get_grid_factor(province),
        'region': '',
    }

    # Shanghai + University
    if province_std == '上海' and any(kw in btype for kw in ['学校', '大学', '高校', '学院', '教育']):
        result.update({
            'standard_name': 'DB31/T 783-2026',
            'standard_full': '《高等学校建筑合理用能指南》',
            'coal_factors_preset': 'db31_783',
            'coal_electricity': 0.28078,
            'coal_gas': 1.29971,
            'is_equivalent_value': True,
            'judgment_levels': 3,
            'needs_alpha': True,
        })

    # Shanghai + Commercial
    elif province_std == '上海' and any(kw in btype for kw in ['商业', '商场', '购物', '百货', '超市', '餐饮']):
        result.update({
            'standard_name': 'DB31/T 552-2017',
            'standard_full': '《大型商业建筑合理用能指南》',
            'coal_factors_preset': 'db31_552',
            'coal_electricity': 0.28232,
            'coal_gas': 1.29971,
            'is_equivalent_value': True,
            'judgment_levels': 2,
        })

    # Shanghai + Office
    elif province_std == '上海' and any(kw in btype for kw in ['办公', '商务']):
        result.update({
            'standard_name': 'DB31/T 1341-2021',
            'standard_full': '《商务办公建筑合理用能指南》',
            'coal_factors_preset': 'db31_1341',
            'coal_electricity': 0.1229,
            'coal_gas': 1.2143,
            'is_equivalent_value': False,
            'judgment_levels': 2,
        })

    # Jiangsu + Hotel
    elif province_std == '江苏' and any(kw in btype for kw in ['酒店', '旅馆', '宾馆']):
        zone = carbon_calculation.get_jiangsu_zone(city_name or city or province)
        result.update({
            'standard_name': '江苏省旅馆限额标准',
            'standard_full': '《江苏省公共建筑用能和碳排放限额指南》',
            'coal_factors_preset': 'jiangsu_hotel',
            'coal_electricity': 0.298,
            'coal_gas': 1.2143,
            'is_equivalent_value': True,
            'judgment_levels': 3,
            'needs_star_rating': True,
            'needs_climate_zone': True,
            'climate_zone': zone,
        })

    # Provincial standard
    elif province_std in carbon_calculation.PROVINCIAL_STANDARDS:
        matched = None
        for key in carbon_calculation.NATIONAL_STANDARDS:
            if key in btype:
                matched = key
                break
        if matched and matched in carbon_calculation.PROVINCIAL_STANDARDS.get(province_std, {}):
            result.update({
                'standard_name': f'{province_std}地方标准',
                'standard_full': f'{province_std}公共建筑能耗限额标准',
                'coal_factors_preset': 'national',
                'coal_electricity': 0.1229,
                'coal_gas': 1.2143,
                'is_equivalent_value': False,
                'judgment_levels': 2,
            })
        else:
            result.update({
                'standard_name': 'GB/T 51161-2016',
                'standard_full': '《民用建筑能耗标准》',
                'coal_factors_preset': 'national',
                'coal_electricity': 0.1229,
                'coal_gas': 1.2143,
                'is_equivalent_value': False,
                'judgment_levels': 2,
            })

    # National standard (fallback)
    else:
        result.update({
            'standard_name': 'GB/T 51161-2016',
            'standard_full': '《民用建筑能耗标准》',
            'coal_factors_preset': 'national',
            'coal_electricity': 0.1229,
            'coal_gas': 1.2143,
            'is_equivalent_value': False,
            'judgment_levels': 2,
        })

    region_info = carbon_calculation.get_region_name(result['grid_factor'])
    result['region'] = region_info

    return result


def get_available_standards() -> list:
    """Get list of all available standards."""
    return [
        {
            'name': 'GB/T 51161-2016',
            'full_name': '《民用建筑能耗标准》',
            'description': '国家标准，适用于无地方标准的地区',
            'applicable_building_types': ['办公', '商业', '酒店', '医院', '学校', '住宅'],
            'applicable_regions': ['全国'],
            'judgment_levels': 2,
            'coal_electricity': 0.1229,
            'coal_gas': 1.2143,
            'is_equivalent_value': False,
        },
        {
            'name': 'DB31/T 783-2026',
            'full_name': '《高等学校建筑合理用能指南》',
            'description': '上海市地方标准，适用于高等学校建筑',
            'applicable_building_types': ['学校', '大学', '高校'],
            'applicable_regions': ['上海'],
            'judgment_levels': 3,
            'coal_electricity': 0.28078,
            'coal_gas': 1.29971,
            'is_equivalent_value': True,
        },
        {
            'name': 'DB31/T 552-2017',
            'full_name': '《大型商业建筑合理用能指南》',
            'description': '上海市地方标准，适用于大型商业建筑',
            'applicable_building_types': ['商业', '商场', '购物中心', '超市'],
            'applicable_regions': ['上海'],
            'judgment_levels': 2,
            'coal_electricity': 0.28232,
            'coal_gas': 1.29971,
            'is_equivalent_value': True,
        },
        {
            'name': 'DB31/T 1341-2021',
            'full_name': '《商务办公建筑合理用能指南》',
            'description': '上海市地方标准，适用于商务办公建筑',
            'applicable_building_types': ['办公', '商务办公'],
            'applicable_regions': ['上海'],
            'judgment_levels': 2,
            'coal_electricity': 0.1229,
            'coal_gas': 1.2143,
            'is_equivalent_value': False,
        },
        {
            'name': '江苏省旅馆限额标准',
            'full_name': '《江苏省公共建筑用能和碳排放限额指南》',
            'description': '江苏省地方标准，适用于旅馆/酒店建筑，按星级和气候区细分',
            'applicable_building_types': ['酒店', '旅馆', '宾馆'],
            'applicable_regions': ['江苏'],
            'judgment_levels': 3,
            'coal_electricity': 0.298,
            'coal_gas': 1.2143,
            'is_equivalent_value': True,
        },
    ]


def get_grid_factors() -> list:
    """Get list of all regional grid emission factors."""
    return [
        {'region': '华北区域', 'factor': 0.7188, 'provinces': ['北京', '天津', '河北', '山西', '内蒙古']},
        {'region': '东北区域', 'factor': 0.6568, 'provinces': ['辽宁', '吉林', '黑龙江']},
        {'region': '华东区域', 'factor': 0.5698, 'provinces': ['上海', '江苏', '浙江', '安徽', '福建', '山东']},
        {'region': '华中区域', 'factor': 0.4908, 'provinces': ['河南', '湖北', '湖南', '江西']},
        {'region': '西北区域', 'factor': 0.5598, 'provinces': ['陕西', '甘肃', '青海', '宁夏', '新疆']},
        {'region': '南方区域', 'factor': 0.4568, 'provinces': ['广东', '广西', '云南', '贵州', '海南']},
        {'region': '全国平均', 'factor': 0.5810, 'provinces': []},
    ]
