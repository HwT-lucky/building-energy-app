"""
建筑能源分析脚本
输入: 标准 JSON 数据（来自 parse_data.py）
输出: 分析结果 JSON 到 stdout
"""

import sys
import json
import math


# 标准煤折算系数（可选不同标准）
# 默认使用上海市 DB31/T 783-2026 附录A 推荐值
COAL_FACTORS_PRESETS = {
    'default': {  # DB31/T 783-2026 附录A 推荐值
        'electricity_kwh': 0.28078,  # kgce/kWh (等价值)
        'gas_m3': 1.29971,           # kgce/m³
        'heat_gj': 34.12,            # kgce/GJ
    },
    'national': {  # GB/T 2589 通用值
        'electricity_kwh': 0.1229,   # kgce/kWh (当量值)
        'gas_m3': 1.2143,            # kgce/m³
        'heat_gj': 34.12,            # kgce/GJ
    },
    'jiangsu_hotel': {  # 江苏省旅馆建筑
        'electricity_kwh': 0.298,    # kgce/kWh (等价值)
        'gas_m3': 1.2143,            # kgce/m³
        'heat_gj': 34.12,            # kgce/GJ
    },
}

# 当前使用的折算系数（默认 DB31/T 783-2026）
COAL_FACTORS = COAL_FACTORS_PRESETS['default']

ENERGY_LABELS = {
    'electricity_kwh': '电力',
    'gas_m3': '天然气',
    'heat_gj': '热力',
}

ENERGY_UNITS = {
    'electricity_kwh': 'kWh',
    'gas_m3': 'm³',
    'heat_gj': 'GJ',
}


def calc_energy_proportion(energy_data):
    """计算能源比例"""
    totals = {}
    for key in ['electricity_kwh', 'gas_m3', 'heat_gj']:
        totals[key] = sum(r.get(key, 0) or 0 for r in energy_data)

    coal_equiv = {}
    total_coal = 0
    for key, factor in COAL_FACTORS.items():
        coal_equiv[key] = totals[key] * factor
        total_coal += coal_equiv[key]

    proportions = []
    for key in ['electricity_kwh', 'gas_m3', 'heat_gj']:
        ce = coal_equiv[key]
        pct = (ce / total_coal * 100) if total_coal > 0 else 0
        proportions.append({
            'energy_type': key,
            'label': ENERGY_LABELS[key],
            'unit': ENERGY_UNITS[key],
            'amount': round(totals[key], 2),
            'coal_equiv_kgce': round(ce, 2),
            'proportion_pct': round(pct, 1),
        })

    return {
        'energy_totals': totals,
        'coal_equiv': coal_equiv,
        'total_coal_kgce': round(total_coal, 2),
        'proportions': proportions,
    }


def calc_monthly_trend(energy_data):
    """计算逐月趋势"""
    monthly = []
    for r in energy_data:
        month = r.get('month', 0)
        elec = r.get('electricity_kwh', 0) or 0
        gas = r.get('gas_m3', 0) or 0
        heat = r.get('heat_gj', 0) or 0
        total_coal = (
            elec * COAL_FACTORS['electricity_kwh'] +
            gas * COAL_FACTORS['gas_m3'] +
            heat * COAL_FACTORS['heat_gj']
        )
        monthly.append({
            'month': int(month),
            'electricity_kwh': round(elec, 2),
            'gas_m3': round(gas, 2),
            'heat_gj': round(heat, 2),
            'total_coal_kgce': round(total_coal, 2),
        })

    monthly.sort(key=lambda x: x['month'])

    # 找峰值和谷值
    if monthly:
        peak = max(monthly, key=lambda x: x['total_coal_kgce'])
        valley = min(monthly, key=lambda x: x['total_coal_kgce'])
        avg_coal = sum(m['total_coal_kgce'] for m in monthly) / len(monthly)

        # 异常检测
        anomalies = []
        for m in monthly:
            if m['total_coal_kgce'] > avg_coal * 1.5:
                anomalies.append({
                    'month': m['month'],
                    'type': 'high',
                    'value': round(m['total_coal_kgce'], 2),
                    'avg': round(avg_coal, 2),
                    'ratio': round(m['total_coal_kgce'] / avg_coal, 2),
                })
            elif m['total_coal_kgce'] < avg_coal * 0.5:
                anomalies.append({
                    'month': m['month'],
                    'type': 'low',
                    'value': round(m['total_coal_kgce'], 2),
                    'avg': round(avg_coal, 2),
                    'ratio': round(m['total_coal_kgce'] / avg_coal, 2),
                })
    else:
        peak = valley = None
        avg_coal = 0
        anomalies = []

    # 季节性分析
    seasonal = analyze_seasonality(monthly)

    return {
        'monthly_data': monthly,
        'peak_month': peak,
        'valley_month': valley,
        'monthly_avg_coal_kgce': round(avg_coal, 2),
        'total_annual_coal_kgce': round(sum(m['total_coal_kgce'] for m in monthly), 2),
        'anomalies': anomalies,
        'seasonal_analysis': seasonal,
    }


def analyze_seasonality(monthly):
    """季节性分析"""
    if len(monthly) < 12:
        return {'note': '数据不足12个月，无法进行完整季节性分析'}

    # 按季节分组
    seasons = {
        '冬季(12-2月)': [12, 1, 2],
        '春季(3-5月)': [3, 4, 5],
        '夏季(6-8月)': [6, 7, 8],
        '秋季(9-11月)': [9, 10, 11],
    }

    season_data = {}
    for name, months in seasons.items():
        season_months = [m for m in monthly if m['month'] in months]
        if season_months:
            season_data[name] = {
                'total_coal_kgce': round(sum(m['total_coal_kgce'] for m in season_months), 2),
                'avg_coal_kgce': round(sum(m['total_coal_kgce'] for m in season_months) / len(season_months), 2),
                'pct_of_annual': 0,
            }

    annual_total = sum(s['total_coal_kgce'] for s in season_data.values())
    if annual_total > 0:
        for s in season_data.values():
            s['pct_of_annual'] = round(s['total_coal_kgce'] / annual_total * 100, 1)

    # 判断主要能耗季节
    if season_data:
        dominant = max(season_data.items(), key=lambda x: x[1]['avg_coal_kgce'])
    else:
        dominant = (None, None)

    return {
        'season_data': season_data,
        'dominant_season': dominant[0],
    }


def calc_unit_area_intensity(energy_data, area):
    """计算单位面积能耗强度"""
    if area <= 0:
        return {'error': '建筑面积未提供或为0，无法计算单位面积强度', 'area_m2': area}

    totals = {}
    for key in ['electricity_kwh', 'gas_m3', 'heat_gj']:
        totals[key] = sum(r.get(key, 0) or 0 for r in energy_data)

    total_coal = sum(totals[k] * COAL_FACTORS[k] for k in COAL_FACTORS)

    return {
        'area_m2': area,
        'electricity_per_m2': round(totals['electricity_kwh'] / area, 2),
        'gas_per_m2': round(totals['gas_m3'] / area, 4),
        'heat_per_m2': round(totals['heat_gj'] / area, 4),
        'total_coal_per_m2': round(total_coal / area, 2),
    }


def calc_yoy_comparison(energy_data, prev_year_data=None):
    """同比分析"""
    if not prev_year_data:
        return {'note': '未提供往年数据，跳过同比分析'}

    current_total = sum(
        (r.get('electricity_kwh', 0) or 0) * COAL_FACTORS['electricity_kwh'] +
        (r.get('gas_m3', 0) or 0) * COAL_FACTORS['gas_m3'] +
        (r.get('heat_gj', 0) or 0) * COAL_FACTORS['heat_gj']
        for r in energy_data
    )

    prev_total = sum(
        (r.get('electricity_kwh', 0) or 0) * COAL_FACTORS['electricity_kwh'] +
        (r.get('gas_m3', 0) or 0) * COAL_FACTORS['gas_m3'] +
        (r.get('heat_gj', 0) or 0) * COAL_FACTORS['heat_gj']
        for r in prev_year_data
    )

    if prev_total > 0:
        change_pct = (current_total - prev_total) / prev_total * 100
    else:
        change_pct = 0

    return {
        'current_year_coal_kgce': round(current_total, 2),
        'prev_year_coal_kgce': round(prev_total, 2),
        'change_pct': round(change_pct, 1),
        'trend': '上升' if change_pct > 0 else ('下降' if change_pct < 0 else '持平'),
    }


def validate_data(energy_data):
    """数据质量检查，返回 warnings 数组。绝不抛异常，任何输入都能处理。"""
    warnings = []

    # 0. 输入类型防御
    if energy_data is None:
        return [{'type': 'empty', 'message': '能耗数据为 None。'}]
    if isinstance(energy_data, str):
        try:
            import json as _json
            energy_data = _json.loads(energy_data)
        except Exception:
            return [{'type': 'parse_error', 'message': '能耗数据为字符串且无法解析为 JSON。'}]
    if isinstance(energy_data, dict):
        if 'energy_data' in energy_data:
            energy_data = energy_data['energy_data']
        elif not any(isinstance(v, list) for v in energy_data.values()):
            return [{'type': 'unknown_format', 'message': '能耗数据格式无法识别（dict 中未找到列表）。'}]
    if not isinstance(energy_data, list):
        return [{'type': 'unknown_format', 'message': f'能耗数据类型异常: {type(energy_data).__name__}。'}]
    if len(energy_data) == 0:
        return [{'type': 'empty', 'message': '能耗数据为空列表，无法分析。'}]

    # 本地折算系数（不依赖外部 COAL_FACTORS）
    _coal = {'electricity_kwh': 0.28078, 'gas_m3': 1.29971, 'heat_gj': 34.12}

    # 1. 月份检查
    months = []
    energy_types = set()
    for r in energy_data:
        if not isinstance(r, dict):
            continue
        m = r.get('month')
        if m is not None:
            try:
                months.append(int(m))
            except (ValueError, TypeError):
                pass
        for k in ['electricity_kwh', 'gas_m3', 'heat_gj', 'water_ton']:
            v = r.get(k)
            if v is not None and v != 0:
                energy_types.add(k)

    months = sorted(set(months))
    if months:
        expected = set(range(1, 13))
        actual = set(months)
        missing = expected - actual
        if missing:
            warnings.append({
                'type': 'missing_months',
                'message': f'缺少以下月份数据: {sorted(missing)}（共{len(missing)}个月），可能影响年度总量准确性。',
                'missing': sorted(missing),
            })
        if len(months) > 12:
            warnings.append({
                'type': 'extra_months',
                'message': f'检测到超过12个月的数据（{len(months)}行），可能存在跨年度数据或重复。',
            })

    # 2. 负值检查
    for r in energy_data:
        if not isinstance(r, dict):
            continue
        m = r.get('month', '?')
        for field in ['electricity_kwh', 'gas_m3', 'heat_gj']:
            val = r.get(field)
            if val is None:
                continue
            try:
                val = float(val)
            except (ValueError, TypeError):
                continue
            if val < 0:
                warnings.append({
                    'type': 'negative_value',
                    'message': f'{m}月{field}为负值({val})，可能是抄表错误或数据录入问题。',
                    'month': m, 'field': field, 'value': val,
                })

    # 3. 异常峰值检查（超过月均 3 倍）
    totals = []
    for r in energy_data:
        if not isinstance(r, dict):
            continue
        try:
            coal = (
                (float(r.get('electricity_kwh', 0) or 0)) * _coal['electricity_kwh'] +
                (float(r.get('gas_m3', 0) or 0)) * _coal['gas_m3'] +
                (float(r.get('heat_gj', 0) or 0)) * _coal['heat_gj']
            )
        except (ValueError, TypeError, KeyError):
            coal = 0
        m = r.get('month', 0)
        try:
            m = int(m)
        except (ValueError, TypeError):
            m = 0
        totals.append((m, coal))

    if len(totals) >= 3:
        avg = sum(t for _, t in totals) / len(totals)
        if avg > 0:
            for m, coal in totals:
                ratio = coal / avg
                if ratio > 3:
                    warnings.append({
                        'type': 'spike',
                        'message': f'{m}月能耗({coal:,.0f} kgce)是月均值({avg:,.0f} kgce)的{ratio:.1f}倍，可能为异常值。',
                        'month': m, 'ratio': round(ratio, 1),
                    })

    # 4. 缺少主要能源类型
    if 'electricity_kwh' not in energy_types:
        warnings.append({
            'type': 'missing_energy',
            'message': '未检测到电力数据（electricity_kwh），电力通常是建筑能耗的主要组成部分。',
        })

    return warnings


def main():
    # 支持 stdin 或命令行参数传入 JSON
    args = sys.argv[1:]
    if len(args) == 0:
        raw = sys.stdin.read().strip()
    elif len(args) >= 1:
        arg = args[0]
        if arg.strip().startswith('{') or arg.strip().startswith('['):
            raw = arg
        else:
            # 可能是文件路径，尝试读取
            try:
                with open(arg, 'r', encoding='utf-8') as f:
                    raw = f.read().strip()
            except (FileNotFoundError, OSError):
                raw = sys.stdin.read().strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print(json.dumps({"error": "无法解析输入 JSON"}, ensure_ascii=False))
        sys.exit(1)

    # 如果有顶层包装，展开
    if isinstance(data, dict) and 'energy_data' in data:
        energy_data = data['energy_data']
        building_info = data.get('building_info', {})
    else:
        energy_data = data if isinstance(data, list) else []
        building_info = {}

    area = building_info.get('area', 0)

    warnings = validate_data(energy_data)
    result = {
        'energy_proportion': calc_energy_proportion(energy_data),
        'monthly_trend': calc_monthly_trend(energy_data),
        'unit_area_intensity': calc_unit_area_intensity(energy_data, area),
        'warnings': warnings if warnings else [],
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
