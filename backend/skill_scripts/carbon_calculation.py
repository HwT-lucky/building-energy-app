"""
建筑碳排放计算与标准对标脚本
输入: JSON 数据（stdin 或参数）+ 省份/城市 + 建筑类型
输出: 碳排放计算结果 JSON 到 stdout

标准数据来源:
- 电网排放因子: 生态环境部
- 旅馆建筑限额: 《江苏省公共建筑用能和碳排放限额指南（试行）》
- 通用限额: GB/T 51161-2016
"""

import sys
import json
import os

# ============================================================
# 区域电网碳排放因子 (kgCO₂/kWh)
# ============================================================
GRID_FACTORS = {
    '北京': 0.7188, '天津': 0.7188, '河北': 0.7188, '山西': 0.7188, '内蒙古': 0.7188,
    '辽宁': 0.6568, '吉林': 0.6568, '黑龙江': 0.6568,
    '上海': 0.5698, '江苏': 0.5698, '浙江': 0.5698, '安徽': 0.5698, '福建': 0.5698, '山东': 0.5698,
    '河南': 0.4908, '湖北': 0.4908, '湖南': 0.4908, '江西': 0.4908,
    '陕西': 0.5598, '甘肃': 0.5598, '青海': 0.5598, '宁夏': 0.5598, '新疆': 0.5598,
    '广东': 0.4568, '广西': 0.4568, '云南': 0.4568, '贵州': 0.4568, '海南': 0.4568,
    '四川': 0.4908, '重庆': 0.4908, '西藏': 0.5810,
}

NATIONAL_AVG_FACTOR = 0.5810

# 城市→省份映射（用于电网因子和标准匹配）
CITY_TO_PROVINCE = {
    '苏州': '江苏', '南京': '江苏', '无锡': '江苏', '常州': '江苏', '镇江': '江苏',
    '南通': '江苏', '扬州': '江苏', '泰州': '江苏', '盐城': '江苏', '淮安': '江苏',
    '宿迁': '江苏', '徐州': '江苏', '连云港': '江苏',
    '杭州': '浙江', '宁波': '浙江', '温州': '浙江', '嘉兴': '浙江', '湖州': '浙江',
    '绍兴': '浙江', '金华': '浙江', '台州': '浙江',
    '广州': '广东', '深圳': '广东', '东莞': '广东', '佛山': '广东', '珠海': '广东',
    '成都': '四川', '武汉': '湖北', '长沙': '湖南', '西安': '陕西',
    '青岛': '山东', '济南': '山东', '厦门': '福建', '福州': '福建',
    '郑州': '河南', '合肥': '安徽', '沈阳': '辽宁', '大连': '辽宁',
    '哈尔滨': '黑龙江', '长春': '吉林',
}

# ============================================================
# 排放因子
# ============================================================
GAS_EMISSION_FACTOR = 1.997        # kgCO₂/m³ (天然气，通用值)
GAS_EMISSION_FACTOR_JIANGSU = 1.96  # kgCO₂/m³ (江苏省标准)
GRID_FACTOR_JIANGSU = 0.5978        # kgCO₂/kWh (江苏省电力排放因子)

HEAT_EMISSION_FACTORS = {
    'default': 0.10,    # tCO₂/GJ
    '燃煤': 0.11,
    '燃气': 0.06,
    '热电联产煤': 0.08,
    '热电联产气': 0.05,
}

# ============================================================
# 标准煤折算系数（按标准选择，默认 DB31/T 783-2026 附录A）
# 每个标准绑定其规定的折算系数
# ============================================================
COAL_FACTORS_PRESETS = {
    'db31_783': {  # DB31/T 783-2026 附录A（上海高校）
        'electricity_kwh': 0.28078,  # kgce/kWh (等价值)
        'gas_m3': 1.29971,           # kgce/m³
        'heat_gj': 34.12,            # kgce/GJ
    },
    'db31_552': {  # DB31/T 552-2017（上海商业建筑）— 等价值
        'electricity_kwh': 0.28232,
        'gas_m3': 1.29971,
        'heat_gj': 34.12,
    },
    'db31_1341': {  # DB31/T 1341-2021（上海商务办公）— 当量值
        'electricity_kwh': 0.1229,
        'gas_m3': 1.2143,
        'heat_gj': 34.12,
    },
    'jiangsu_hotel': {  # 江苏省旅馆标准
        'electricity_kwh': 0.298, 'gas_m3': 1.2143, 'heat_gj': 34.12,
    },
    'national': {  # GB/T 2589 通用
        'electricity_kwh': 0.1229, 'gas_m3': 1.2143, 'heat_gj': 34.12,
    },
}
COAL_FACTORS = COAL_FACTORS_PRESETS['db31_783']  # 默认上海高校
# 可通过 set_coal_factors('db31_xxx') 切换
def set_coal_factors(preset_name):
    global COAL_FACTORS
    if preset_name in COAL_FACTORS_PRESETS:
        COAL_FACTORS = COAL_FACTORS_PRESETS[preset_name]

# ============================================================
# 国家标准（通用型，GB/T 51161-2016）
# ============================================================
NATIONAL_STANDARDS = {
    '办公': {'constraint': 55, 'guide': 40},
    '商业': {'constraint': 80, 'guide': 55},
    '商场': {'constraint': 80, 'guide': 55},
    '酒店': {'constraint': 70, 'guide': 50},
    '医院': {'constraint': 75, 'guide': 55},
    '学校': {'constraint': 35, 'guide': 25},
    '住宅': {'constraint': 30, 'guide': 20},
    '居住': {'constraint': 30, 'guide': 20},
}

# ============================================================
# 江苏省旅馆建筑限额标准
# 来源: 《江苏省公共建筑用能和碳排放限额指南（试行）》
# ============================================================
# 按星级 + 气候地区细分
HOTEL_STANDARD_JIANGSU = {
    '五星级': {
        '夏热冬冷I区': {
            'energy': {'constraint': 56.85, 'benchmark': 45.60, 'guide': 33.86},
            'carbon': {'constraint': 123.25, 'benchmark': 98.24, 'guide': 72.24},
        },
        '夏热冬冷II区': {
            'energy': {'constraint': 55.78, 'benchmark': 42.94, 'guide': 30.76},
            'carbon': {'constraint': 120.58, 'benchmark': 93.58, 'guide': 66.76},
        },
        '寒冷地区': {
            'energy': {'constraint': 55.91, 'benchmark': 43.24, 'guide': 31.17},
            'carbon': {'constraint': 121.91, 'benchmark': 97.10, 'guide': 67.48},
        },
    },
    '四星级': {
        '夏热冬冷I区': {
            'energy': {'constraint': 49.34, 'benchmark': 38.59, 'guide': 27.21},
            'carbon': {'constraint': 106.15, 'benchmark': 83.54, 'guide': 58.90},
        },
        '夏热冬冷II区': {
            'energy': {'constraint': 47.22, 'benchmark': 35.78, 'guide': 25.94},
            'carbon': {'constraint': 102.72, 'benchmark': 77.45, 'guide': 53.95},
        },
        '寒冷地区': {
            'energy': {'constraint': 48.03, 'benchmark': 36.69, 'guide': 26.88},
            'carbon': {'constraint': 103.98, 'benchmark': 79.43, 'guide': 58.20},
        },
    },
    '三星级及以下': {
        '夏热冬冷I区': {
            'energy': {'constraint': 43.44, 'benchmark': 32.71, 'guide': 22.92},
            'carbon': {'constraint': 93.50, 'benchmark': 70.82, 'guide': 49.61},
        },
        '夏热冬冷II区': {
            'energy': {'constraint': 41.56, 'benchmark': 30.17, 'guide': 20.02},
            'carbon': {'constraint': 87.04, 'benchmark': 65.31, 'guide': 43.34},
        },
        '寒冷地区': {
            'energy': {'constraint': 42.37, 'benchmark': 31.42, 'guide': 21.71},
            'carbon': {'constraint': 89.33, 'benchmark': 66.82, 'guide': 47.00},
        },
    },
}

# 江苏旅馆建筑气候区划分
# 夏热冬冷I区: 苏南 (苏州、无锡、常州、南京、镇江等)
# 夏热冬冷II区: 苏中
# 寒冷地区: 苏北 (徐州、连云港等)
JIANGSU_CITY_ZONES = {
    '苏州': '夏热冬冷I区', '无锡': '夏热冬冷I区', '常州': '夏热冬冷I区',
    '南京': '夏热冬冷I区', '镇江': '夏热冬冷I区',
    '南通': '夏热冬冷II区', '扬州': '夏热冬冷II区', '泰州': '夏热冬冷II区',
    '盐城': '夏热冬冷II区', '淮安': '夏热冬冷II区', '宿迁': '夏热冬冷II区',
    '徐州': '寒冷地区', '连云港': '寒冷地区',
}

# 各省市通用限额（无星级细分）
PROVINCIAL_STANDARDS = {
    '北京': {
        '办公': {'constraint': 55, 'guide': 45},
        '商业': {'constraint': 75, 'guide': 55},
        '酒店': {'constraint': 65, 'guide': 50},
        '医院': {'constraint': 70, 'guide': 55},
    },
    '上海': {
        '办公': {'constraint': 50, 'guide': 40},
        '商业': {'constraint': 70, 'guide': 55},
        '酒店': {'constraint': 60, 'guide': 48},
        '医院': {'constraint': 65, 'guide': 50},
    },
    '广东': {
        '办公': {'constraint': 45, 'guide': 35},
        '商业': {'constraint': 65, 'guide': 50},
        '酒店': {'constraint': 55, 'guide': 45},
        '医院': {'constraint': 60, 'guide': 48},
    },
    '浙江': {
        '办公': {'constraint': 46, 'guide': 36},
        '商业': {'constraint': 66, 'guide': 52},
        '酒店': {'constraint': 56, 'guide': 45},
        '医院': {'constraint': 60, 'guide': 48},
    },
}


# ============================================================
# Helper functions
# ============================================================

def resolve_province(location):
    """将城市名或省份名解析为标准省份名"""
    if not location:
        return '', ''
    location = location.strip()
    # 直接匹配省份
    for p in GRID_FACTORS:
        if location.startswith(p):
            return p, location
    # 城市→省份映射
    for city, prov in CITY_TO_PROVINCE.items():
        if city in location:
            return prov, city
    # 去掉后缀再试
    clean = location.replace('省', '').replace('市', '').strip()
    for p in GRID_FACTORS:
        if clean.startswith(p) or p in clean or clean in p:
            return p, clean
    return '', location


def get_grid_factor(province):
    """获取指定省份的电网排放因子"""
    province_std, _ = resolve_province(province)
    if province_std and province_std in GRID_FACTORS:
        return GRID_FACTORS[province_std]
    return NATIONAL_AVG_FACTOR


def get_region_name(factor):
    """获取排放因子对应的区域名称"""
    regions = {
        0.7188: '华北区域', 0.6568: '东北区域', 0.5698: '华东区域',
        0.4908: '华中区域', 0.5598: '西北区域', 0.4568: '南方区域',
        0.5810: '全国平均',
    }
    return regions.get(factor, '全国平均')


def get_jiangsu_zone(city):
    """获取江苏城市的建筑气候分区"""
    for c, zone in JIANGSU_CITY_ZONES.items():
        if c in city:
            return zone
    return '夏热冬冷II区'  # 默认苏中


# ============================================================
# Core calculation functions
# ============================================================

def calc_carbon_emission(energy_data, province):
    """计算碳排放。江苏省使用特定排放因子。"""
    province_std, city = resolve_province(province)
    is_jiangsu = (province_std == '江苏')

    grid_factor = GRID_FACTOR_JIANGSU if is_jiangsu else get_grid_factor(province)
    gas_factor = GAS_EMISSION_FACTOR_JIANGSU if is_jiangsu else GAS_EMISSION_FACTOR
    region = '华东区域（江苏省）' if is_jiangsu else get_region_name(grid_factor)

    total_elec = sum(r.get('electricity_kwh', 0) or 0 for r in energy_data)
    total_gas = sum(r.get('gas_m3', 0) or 0 for r in energy_data)
    total_heat = sum(r.get('heat_gj', 0) or 0 for r in energy_data)

    co2_elec = total_elec * grid_factor / 1000   # tCO₂
    co2_gas = total_gas * gas_factor / 1000
    co2_heat = total_heat * HEAT_EMISSION_FACTORS['default']
    total_co2 = co2_elec + co2_gas + co2_heat

    monthly_emission = []
    for r in energy_data:
        month = r.get('month', 0)
        e = (r.get('electricity_kwh', 0) or 0) * grid_factor / 1000
        g = (r.get('gas_m3', 0) or 0) * gas_factor / 1000
        h = (r.get('heat_gj', 0) or 0) * HEAT_EMISSION_FACTORS['default']
        monthly_emission.append({
            'month': int(month),
            'co2_elec': round(e, 2),
            'co2_gas': round(g, 2),
            'co2_heat': round(h, 2),
            'co2_total': round(e + g + h, 2),
        })
    monthly_emission.sort(key=lambda x: x['month'])

    return {
        'grid_factor_used': grid_factor,
        'region': region,
        'emission_breakdown': {
            'electricity': {
                'amount': round(total_elec, 2), 'unit': 'kWh',
                'factor': grid_factor, 'factor_unit': 'kgCO₂/kWh',
                'co2_tons': round(co2_elec, 2),
                'pct': round(co2_elec / total_co2 * 100, 1) if total_co2 > 0 else 0,
            },
            'gas': {
                'amount': round(total_gas, 2), 'unit': 'm³',
                'factor': gas_factor, 'factor_unit': 'kgCO₂/m³',
                'co2_tons': round(co2_gas, 2),
                'pct': round(co2_gas / total_co2 * 100, 1) if total_co2 > 0 else 0,
            },
            'heat': {
                'amount': round(total_heat, 2), 'unit': 'GJ',
                'factor': HEAT_EMISSION_FACTORS['default'], 'factor_unit': 'tCO₂/GJ',
                'co2_tons': round(co2_heat, 2),
                'pct': round(co2_heat / total_co2 * 100, 1) if total_co2 > 0 else 0,
            },
        },
        'total_emission_tons': round(total_co2, 2),
        'monthly_emission': monthly_emission,
    }


def compare_shanghai_commercial(coal_per_m2, carbon_per_m2, building_type):
    """DB31/T 552-2017《大型商业建筑合理用能指南》（等价值 0.28232）"""
    btype = str(building_type)
    if any(kw in btype for kw in ['百货', '购物', '商场']):
        std = {'constraint': 90, 'benchmark': None, 'guide': 65}
        cat = '百货店及购物中心'
    elif any(kw in btype for kw in ['超市', '仓储']):
        std = {'constraint': 105, 'benchmark': None, 'guide': 75}
        cat = '超市及仓储店'
    elif any(kw in btype for kw in ['餐饮']):
        std = {'constraint': 150, 'benchmark': None, 'guide': None}
        cat = '餐饮店'
    else:
        std = {'constraint': 90, 'benchmark': None, 'guide': 65}
        cat = '百货店及购物中心（默认）'

    level, icon, msg = two_level_compare(coal_per_m2, std)
    return {
        'status': 'matched',
        'standard_source': 'DB31/T 552-2017《大型商业建筑合理用能指南》',
        'building_type': cat,
        'level': level, 'icon': icon,
        'energy_level': level, 'energy_icon': icon,
        'energy_actual': round(coal_per_m2, 2),
        'energy_constraint': std.get('constraint', 0),
        'energy_guide': std.get('guide', 0) or 0,
        'energy_unit': 'kgce/m²·a',
        'energy_message': msg,
        'message': f'{icon} {level} — {msg}',
        'suggestion': generate_suggestion(level, ''),
        'coal_factors_used': 'db31_552',
    }


def compare_shanghai_office(coal_per_m2, carbon_per_m2, building_type):
    """DB31/T 1341-2021《商务办公建筑合理用能指南》（当量值 0.1229）"""
    # I类：城市主中心内 + 集中式空调（默认）
    std = {'constraint': 14, 'benchmark': None, 'guide': 11}
    level, icon, msg = two_level_compare(coal_per_m2, std)
    return {
        'status': 'matched',
        'standard_source': 'DB31/T 1341-2021《商务办公建筑合理用能指南》',
        'building_type': 'I类商务办公建筑（城市主中心+集中空调）',
        'level': level, 'icon': icon,
        'energy_level': level, 'energy_icon': icon,
        'energy_actual': round(coal_per_m2, 2),
        'energy_constraint': std.get('constraint', 0),
        'energy_guide': std.get('guide', 0) or 0,
        'energy_unit': 'kgce/m²·a',
        'energy_message': f'{msg}（注：本指南使用当量值0.1229 kgce/kWh）',
        'message': f'{icon} {level} — {msg}',
        'suggestion': generate_suggestion(level, ''),
        'coal_factors_used': 'db31_1341',
    }


def compare_db31_783(coal_per_m2, carbon_per_m2, building_type,
                     alpha1=None, alpha2=None, alpha4=None):
    """
    DB31/T 783-2026《高等学校建筑合理用能指南》标准对标。
    公式: e1_corrected = E / (S × α1 × α2)  [本科院校]
          e1_corrected = E / (S × α1 × α3)  [高职院校]
    """
    # Table 1: 单位建筑面积年综合能耗指标 [kgce/(m²·a)]
    DB31_783_TABLE1 = {
        '本科院校/成人高等学校': {'constraint': 36.3, 'benchmark': 25.9, 'guide': 19.3},
        '高职（专科）院校':      {'constraint': 24.6, 'benchmark': 18.2, 'guide': 15.9},
    }

    # Table 3: 教学科研设备资产修正系数 α1
    DB31_783_ALPHA1 = [
        (500, 0.9), (1000, 1.0), (2000, 1.1), (3000, 1.2), (float('inf'), 1.25)
    ]

    # Table 4: 一流学科门类修正系数 α2
    DB31_783_ALPHA2 = {
        '艺术学': 1.05, '文学': 1.08, '经济学': 1.1, '教育学': 1.1,
        '理学': 1.3, '工学': 1.3, '医学': 2.0, '农学': 2.0, '三种及以上': 1.7,
    }

    # Determine school category
    is_vocational = any(kw in str(building_type) for kw in ['高职', '专科', '大专'])
    school_cat = '高职（专科）院校' if is_vocational else '本科院校/成人高等学校'
    std = DB31_783_TABLE1[school_cat]

    # Apply correction factors (formula 2 from standard)
    # User input or defaults
    if alpha1 is None:
        alpha1 = 1.0  # default: assume [500,1000)
    if alpha2 is None:
        alpha2 = 1.0  # default: no correction

    corrected_coal = coal_per_m2 / (alpha1 * alpha2) if (alpha1 and alpha2) else coal_per_m2

    # Energy comparison
    energy_level, energy_icon, energy_msg = three_level_compare(
        corrected_coal, std, 'kgce/m²·a')

    # Carbon comparison (DB31/T 783 doesn't have carbon limits, use energy results)
    carbon_level = carbon_icon = carbon_msg = None
    if carbon_per_m2 and carbon_per_m2 > 0:
        carbon_level, carbon_icon, carbon_msg = '—', '⚪', '本标准未规定碳排放限额，仅展示计算值。'

    return {
        'status': 'matched',
        'standard_source': 'DB31/T 783-2026《高等学校建筑合理用能指南》',
        'building_type': f'{school_cat}',
        'school_category': school_cat,
        # Corrected values
        'coal_per_m2_raw': round(coal_per_m2, 2),
        'coal_per_m2_corrected': round(corrected_coal, 2),
        'alpha1': alpha1, 'alpha2': alpha2,
        'correction_formula': f'e1 = E/(S×α1×α2) = {coal_per_m2:.2f}/({alpha1}×{alpha2}) = {corrected_coal:.2f}',
        # Energy limits
        'energy_level': energy_level, 'energy_icon': energy_icon,
        'energy_actual': round(corrected_coal, 2),
        'energy_constraint': std['constraint'],
        'energy_benchmark': std['benchmark'],
        'energy_guide': std['guide'],
        'energy_unit': 'kgce/m²·a',
        'energy_message': energy_msg,
        # Carbon (not in standard)
        'carbon_level': carbon_level, 'carbon_icon': carbon_icon,
        'carbon_actual': round(carbon_per_m2, 2) if carbon_per_m2 > 0 else None,
        'carbon_constraint': None, 'carbon_benchmark': None, 'carbon_guide': None,
        'carbon_unit': 'kgCO₂/m²·a',
        'carbon_message': carbon_msg or '本标准未规定碳排放限额。',
        # Combined
        'level': energy_level, 'icon': energy_icon,
        'message': f'能耗(修正后): {energy_msg}',
        'suggestion': generate_suggestion(energy_level, ''),
        'coal_factors_used': 'db31_783',
    }


def compare_with_standard(coal_per_m2, carbon_per_m2, building_type, province,
                          star_rating='', climate_zone='', standard_choice='',
                          alpha1=None, alpha2=None, alpha4=None):
    """
    标准对标（三级判定体系）。
    支持: DB31/T 783-2026 (上海高校), 江苏省旅馆标准, 省级标准, 国家标准。
    standard_choice: 'db31_783' | 'jiangsu_hotel' | 'provincial' | 'national' | '' (auto)
    """
    province_std, city = resolve_province(province)

    # ================================================================
    # 上海高等学校：DB31/T 783-2026
    # ================================================================
    is_shanghai = (province_std == '上海' or '上海' in str(province))
    is_shanghai_edu = is_shanghai and \
                      any(kw in str(building_type) for kw in ['学校', '大学', '高校', '学院', '教育'])
    if standard_choice == 'db31_783' or (is_shanghai_edu and not standard_choice):
        set_coal_factors('db31_783')
        return compare_db31_783(coal_per_m2, carbon_per_m2, building_type,
                                alpha1=alpha1, alpha2=alpha2, alpha4=alpha4)

    # ================================================================
    # 上海商业建筑：DB31/T 552-2017
    # ================================================================
    is_shanghai_commercial = is_shanghai and \
        any(kw in str(building_type) for kw in ['商业', '商场', '购物', '百货', '超市', '餐饮'])
    if standard_choice == 'db31_552' or (is_shanghai_commercial and not standard_choice):
        set_coal_factors('db31_552')
        return compare_shanghai_commercial(coal_per_m2, carbon_per_m2, building_type)

    # ================================================================
    # 上海商务办公：DB31/T 1341-2021
    # ================================================================
    is_shanghai_office = is_shanghai and \
        any(kw in str(building_type) for kw in ['办公', '商务'])
    if standard_choice == 'db31_1341' or (is_shanghai_office and not standard_choice):
        set_coal_factors('db31_1341')
        return compare_shanghai_office(coal_per_m2, carbon_per_m2, building_type)

    # ================================================================
    # 江苏旅馆建筑特殊处理：按星级+气候区查表
    # ================================================================
    if province_std == '江苏' and ('酒店' in building_type or '旅馆' in building_type or '宾馆' in building_type):
        # 推断星级
        if not star_rating:
            # 默认五星级
            star_rating = '五星级'
        if star_rating not in HOTEL_STANDARD_JIANGSU:
            star_rating = '五星级'  # fallback

        # 推断气候区
        if not climate_zone:
            climate_zone = get_jiangsu_zone(city or province)
        if climate_zone not in HOTEL_STANDARD_JIANGSU[star_rating]:
            climate_zone = '夏热冬冷I区'  # fallback

        std = HOTEL_STANDARD_JIANGSU[star_rating][climate_zone]

        # === 能耗对标 ===
        energy_std = std['energy']
        energy_level, energy_icon, energy_msg = three_level_compare(
            coal_per_m2, energy_std, 'kgce/m²·a')

        # === 碳排放对标 ===
        carbon_std = std['carbon']
        carbon_level, carbon_icon, carbon_msg = three_level_compare(
            carbon_per_m2, carbon_std, 'kgCO₂/m²·a')

        return {
            'status': 'matched',
            'standard_source': f'《江苏省公共建筑用能和碳排放限额指南》',
            'building_type': f'{star_rating}旅馆建筑',
            'climate_zone': climate_zone,
            # Energy
            'energy_level': energy_level,
            'energy_icon': energy_icon,
            'energy_actual': round(coal_per_m2, 2),
            'energy_constraint': energy_std['constraint'],
            'energy_benchmark': energy_std['benchmark'],
            'energy_guide': energy_std['guide'],
            'energy_unit': 'kgce/m²·a',
            'energy_message': energy_msg,
            # Carbon
            'carbon_level': carbon_level,
            'carbon_icon': carbon_icon,
            'carbon_actual': round(carbon_per_m2, 2) if carbon_per_m2 > 0 else None,
            'carbon_constraint': carbon_std['constraint'],
            'carbon_benchmark': carbon_std['benchmark'],
            'carbon_guide': carbon_std['guide'],
            'carbon_unit': 'kgCO₂/m²·a',
            'carbon_message': carbon_msg,
            # Combined
            'level': energy_level,
            'icon': energy_icon,
            'message': f"能耗: {energy_msg} | 碳排放: {carbon_msg}",
            'suggestion': generate_suggestion(energy_level, carbon_level),
        }

    # ================================================================
    # 省级标准（通用型）
    # ================================================================
    bt = building_type.strip()
    matched_type = None
    for key in NATIONAL_STANDARDS:
        if key in bt:
            matched_type = key
            break
    if not matched_type:
        matched_type = '酒店'  # default

    if province_std in PROVINCIAL_STANDARDS and matched_type in PROVINCIAL_STANDARDS[province_std]:
        std = PROVINCIAL_STANDARDS[province_std][matched_type]
        standard_source = f'{province_std}地方标准'
        level, icon, msg = two_level_compare(coal_per_m2, std)
    elif matched_type in NATIONAL_STANDARDS:
        std = NATIONAL_STANDARDS[matched_type]
        standard_source = '国家标准 (GB/T 51161-2016)'
        level, icon, msg = two_level_compare(coal_per_m2, std)
    else:
        return {
            'status': 'no_standard', 'level': '无匹配标准',
            'message': f'建筑类型"{building_type}"没有适用的能耗限额标准',
            'building_type': building_type,
        }

    return {
        'status': 'matched',
        'standard_source': standard_source,
        'building_type': matched_type,
        'level': level, 'icon': icon,
        'energy_level': level, 'energy_icon': icon,
        'energy_actual': round(coal_per_m2, 2),
        'energy_constraint': std.get('constraint', 0),
        'energy_guide': std.get('guide', 0),
        'energy_unit': 'kgce/m²·a',
        'energy_message': msg,
        'message': f'{icon} {level} — {msg}',
        'suggestion': generate_suggestion(level, ''),
    }


def three_level_compare(actual, std, unit):
    """三级判定（约束值/基准值/引导值）"""
    if actual <= std['guide']:
        return ('达到引导值', '🟢',
                f'实际 {actual:.2f} {unit} ≤ 引导值 {std["guide"]}，达到先进水平')
    elif actual <= std['benchmark']:
        gap = actual - std['guide']
        return ('达到基准值', '🔵',
                f'实际 {actual:.2f} {unit}，介于引导值({std["guide"]})和基准值({std["benchmark"]})之间，距引导值差 {gap:.2f}')
    elif actual <= std['constraint']:
        gap = actual - std['benchmark']
        return ('达到约束值', '🟡',
                f'实际 {actual:.2f} {unit}，介于基准值({std["benchmark"]})和约束值({std["constraint"]})之间，距基准值差 {gap:.2f}')
    else:
        exceed = actual - std['constraint']
        return ('超出约束值', '🔴',
                f'实际 {actual:.2f} {unit} > 约束值 {std["constraint"]}，超出 {exceed:.2f}，需要整改')


def two_level_compare(actual, std):
    """二级判定（约束值/引导值）"""
    if actual <= std['guide']:
        return ('优良', '🟢',
                f'实际 {actual:.2f} ≤ 引导值 {std["guide"]} kgce/m²·a，能耗水平优良')
    elif actual <= std['constraint']:
        return ('达标', '🟡',
                f'实际 {actual:.2f} ≤ 约束值 {std["constraint"]} kgce/m²·a，能耗达标')
    else:
        exceed = actual - std['constraint']
        return ('超标', '🔴',
                f'实际 {actual:.2f} > 约束值 {std["constraint"]} kgce/m²·a，超出 {exceed:.2f}，需要整改')


def generate_suggestion(energy_level, carbon_level=''):
    """根据对标等级生成节能建议"""
    suggestions = {
        '达到引导值': '能耗达到先进水平，建议持续监测，保持高效运行。',
        '达到基准值': '能耗处于良好水平，建议优化运行策略，向引导值看齐。重点关注空调系统、照明控制和设备能效提升。',
        '达到约束值': '能耗处于合格水平，距基准值仍有差距。建议开展能源审计，识别高耗能环节，制定节能改造计划。',
        '超出约束值': '能耗超标！建议立即开展能源审计，重点排查空调系统、供暖系统、照明系统等主要用能设备，制定并实施节能改造方案。',
    }
    return suggestions.get(energy_level, '')


# ============================================================
# Main entry point
# ============================================================

def main():
    args = sys.argv[1:]
    raw = ''
    province = ''
    building_type = ''
    star_rating = ''
    climate_zone = ''

    # 参数解析
    if len(args) == 0:
        raw = sys.stdin.read().strip()
    elif len(args) == 1:
        arg = args[0]
        if arg.strip().startswith('{') or arg.strip().startswith('['):
            raw = arg
        else:
            province = arg
            raw = sys.stdin.read().strip()
    elif len(args) == 2:
        if args[0].strip().startswith('{') or args[0].strip().startswith('['):
            raw = args[0]; province = args[1]
        else:
            province = args[0]; building_type = args[1]
            raw = sys.stdin.read().strip()
    elif len(args) >= 3:
        if args[0].strip().startswith('{') or args[0].strip().startswith('['):
            raw = args[0]; province = args[1]; building_type = args[2]
            star_rating = args[3] if len(args) > 3 else ''
            climate_zone = args[4] if len(args) > 4 else ''
        else:
            province = args[0]; building_type = args[1]
            star_rating = args[2] if len(args) > 2 else ''
            climate_zone = args[3] if len(args) > 3 else ''
            raw = sys.stdin.read().strip()

    # Parse JSON input
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print(json.dumps({"error": "无法解析输入 JSON"}, ensure_ascii=False))
        sys.exit(1)

    if isinstance(data, dict) and 'energy_data' in data:
        energy_data = data['energy_data']
        building_info = data.get('building_info', {})
    else:
        energy_data = data if isinstance(data, list) else []
        building_info = {}

    area = building_info.get('area', 0)
    if not building_type:
        building_type = building_info.get('type', '')
    if not province:
        province = building_info.get('location', '')

    # Calculate coal equivalent
    total_coal = 0
    for r in energy_data:
        total_coal += (
            (r.get('electricity_kwh', 0) or 0) * COAL_FACTORS['electricity_kwh'] +
            (r.get('gas_m3', 0) or 0) * COAL_FACTORS['gas_m3'] +
            (r.get('heat_gj', 0) or 0) * COAL_FACTORS['heat_gj']
        )
    coal_per_m2 = total_coal / area if area > 0 else 0

    # Carbon emission
    carbon_result = calc_carbon_emission(energy_data, province)
    carbon_per_m2 = carbon_result['total_emission_tons'] * 1000 / area if area > 0 else 0

    # Standard comparison
    standard_result = compare_with_standard(
        coal_per_m2, carbon_per_m2, building_type, province,
        star_rating=star_rating, climate_zone=climate_zone
    )

    result = {
        **carbon_result,
        'carbon_intensity_kgco2_per_m2': round(carbon_per_m2, 2),
        'total_coal_kgce': round(total_coal, 2),
        'coal_per_m2_kgce': round(coal_per_m2, 2),
        'standard_comparison': standard_result,
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
