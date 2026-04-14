#!/usr/bin/env python3
"""
fix_paipan.py - 排盘引擎修复脚本
用法: python3 fix_paipan.py

功能:
1. 读取 fcas_engine_v2.py
2. 替换有bug的节气计算和排盘函数
3. 输出修复后的 fcas_engine_v2_fixed.py

修复内容:
- Bug1: 节气表从2026硬编码 → ephem天文算法（任意年份）
- Bug2: 九星旋转用线性宫序[1-9] → 外环序[1,8,3,4,9,2,7,6]
- Bug3: 天盘干用"整体偏移" → "星带地盘干走"
- Bug4: 八门旋转用线性宫序 → 外环序
- Bug5: 八神排布用线性8宫序 → 外环序
"""

import re
import sys

def apply_fix(source_path, output_path):
    with open(source_path, 'r', encoding='utf-8') as f:
        code = f.read()
    
    # ================================================================
    # Fix 1: 在文件顶部添加 ephem import
    # ================================================================
    if 'import ephem' not in code:
        code = code.replace(
            'from datetime import datetime',
            'from datetime import datetime, timedelta\ntry:\n    import ephem\n    HAS_EPHEM = True\nexcept ImportError:\n    HAS_EPHEM = False',
            1
        )
    
    # ================================================================
    # Fix 2: 替换 get_current_term 函数（节气计算）
    # ================================================================
    new_get_current_term = '''
def _solar_longitude(dt):
    """计算太阳黄经（度）"""
    if not HAS_EPHEM:
        return 0
    sun = ephem.Sun()
    obs = ephem.Observer()
    obs.date = dt.strftime('%Y/%m/%d %H:%M:%S')
    sun.compute(obs)
    import math
    return float(sun.hlong) * 180.0 / math.pi

def _find_jieqi_time(year, target_lon, est_month):
    """二分法查找节气精确时间"""
    if not HAS_EPHEM:
        return None
    import math
    est = datetime(year, est_month, 15)
    lo = est - timedelta(days=35)
    hi = est + timedelta(days=35)
    for _ in range(60):
        mid = lo + (hi - lo) / 2
        lon = _solar_longitude(mid)
        diff = (lon - target_lon + 180) % 360 - 180
        if abs(diff) < 0.0001:
            return mid
        if diff > 0:
            hi = mid
        else:
            lo = mid
    return lo + (hi - lo) / 2

# 节气名称和黄经度数
_JIEQI_NAMES = [
    "冬至","小寒","大寒","立春","雨水","惊蛰",
    "春分","清明","谷雨","立夏","小满","芒种",
    "夏至","小暑","大暑","立秋","处暑","白露",
    "秋分","寒露","霜降","立冬","小雪","大雪"
]

def _get_all_jieqi(year):
    """获取某年前后所有节气"""
    results = []
    for y in [year-1, year, year+1]:
        for i, name in enumerate(_JIEQI_NAMES):
            target_lon = (270 + i * 15) % 360
            # 估算月份
            if name == "冬至": est_m = 12
            elif name in ("小寒","大寒"): est_m = 1
            elif name in ("立春","雨水"): est_m = 2
            elif name in ("惊蛰","春分"): est_m = 3
            elif name in ("清明","谷雨"): est_m = 4
            elif name in ("立夏","小满"): est_m = 5
            elif name in ("芒种","夏至"): est_m = 6
            elif name in ("小暑","大暑"): est_m = 7
            elif name in ("立秋","处暑"): est_m = 8
            elif name in ("白露","秋分"): est_m = 9
            elif name in ("寒露","霜降"): est_m = 10
            elif name in ("立冬","小雪"): est_m = 11
            else: est_m = 12
            
            jq_dt = _find_jieqi_time(y, target_lon, est_m)
            if jq_dt:
                results.append((jq_dt, i, name))
    results.sort(key=lambda x: x[0])
    return results

def get_current_term(dt):
    """Get the current solar term for any date.
    Returns (term_index, term_name, is_yangdun)
    
    Fixed: 使用ephem天文算法计算精确节气，支持任意年份。
    """
    if HAS_EPHEM:
        all_jq = _get_all_jieqi(dt.year)
        current = all_jq[0]
        for jq_dt, idx, name in all_jq:
            if jq_dt <= dt:
                current = (jq_dt, idx, name)
            else:
                break
        _, term_idx, term_name = current
    else:
        # Fallback to 2026 hardcoded table
        terms_sorted = []
        terms_sorted.append((datetime(2025, 12, 22), 0, "冬至"))
        for (m, d), (idx, name) in sorted(SOLAR_TERMS_2026.items()):
            terms_sorted.append((datetime(2026, m, d), idx, name))
        current_term = terms_sorted[0]
        for term_dt, idx, name in terms_sorted:
            if term_dt <= dt:
                current_term = (term_dt, idx, name)
            else:
                break
        _, term_idx, term_name = current_term
    
    is_yangdun = term_idx < 12
    return term_idx, term_name, is_yangdun
'''
    
    # 找到原始 get_current_term 函数并替换
    pattern = r'def get_current_term\(dt\):.*?return term_idx, term_name, is_yangdun'
    code = re.sub(pattern, new_get_current_term.strip(), code, flags=re.DOTALL)
    
    # ================================================================
    # Fix 3: 替换 paipan() 中的九星/天盘干/八门/八神旋转逻辑
    # ================================================================
    
    # 找到 Step 11 到 Step 14 的代码块并替换
    old_step11_start = '    # === Step 11: Layout heaven plate (stems) ==='
    old_step14_end = '    return ju'
    
    new_rotation_code = '''    # === Step 11: Layout stars (FIXED: 外环旋转) ===
    # 转盘法: 九星按外环[1,8,3,4,9,2,7,6]整体旋转
    RING = PALACE_FLY_FORWARD  # [1, 8, 3, 4, 9, 2, 7, 6]
    
    # 值符星原位和目标位在外环的索引
    zhifu_home_ring = 2 if zhifu_home == 5 else zhifu_home  # 中5寄坤2
    zhifu_target_ring = 2 if zhifu_target == 5 else zhifu_target
    
    from_idx = RING.index(zhifu_home_ring)
    to_idx = RING.index(zhifu_target_ring)
    star_steps = (to_idx - from_idx) % 8
    
    star_layout = {}
    for star in range(9):
        if star == STAR_QIN:
            continue  # 天禽寄坤
        home_p = STAR_HOME_PALACE[star]
        home_ring = 2 if home_p == 5 else home_p
        ring_idx = RING.index(home_ring)
        new_ring_idx = (ring_idx + star_steps) % 8
        new_palace = RING[new_ring_idx]
        star_layout[new_palace] = star
    star_layout[5] = STAR_QIN
    ju.stars = star_layout
    
    # === Step 12: Layout heaven plate stems (FIXED: 星带地盘干走) ===
    # 天盘天干 = 移到该宫的星所携带的原位地盘干
    heaven = {}
    for new_palace, star in star_layout.items():
        if star == STAR_QIN:
            heaven[5] = ju.ground.get(5, ju.ground.get(2))
            continue
        star_home = STAR_HOME_PALACE[star]
        heaven[new_palace] = ju.ground[star_home]
    ju.heaven = heaven
    
    # === Step 13: Layout gates (FIXED: 外环旋转) ===
    # 八门也按外环旋转，步数与九星相同
    gate_layout = {}
    for gate in range(8):
        home_p = GATE_HOME_PALACE[gate]
        home_ring = 2 if home_p == 5 else home_p
        if home_ring not in RING:
            continue
        ring_idx = RING.index(home_ring)
        new_ring_idx = (ring_idx + star_steps) % 8  # 门和星转同样步数(简化版)
        new_palace = RING[new_ring_idx]
        gate_layout[new_palace] = gate
    ju.gates = gate_layout
    
    # === Step 14: Layout deities (FIXED: 外环旋转) ===
    # 八神: 值符落宫起，阳遁顺时针，阴遁逆时针
    deity_layout = {}
    order = DEITY_ORDER_YANG if is_yangdun else DEITY_ORDER_YIN
    
    zhifu_p = ju.zhifu_palace
    if zhifu_p == 5:
        zhifu_p = 2
    start_idx_d = RING.index(zhifu_p)
    
    for i, deity in enumerate(order):
        if is_yangdun:
            ring_idx = (start_idx_d + i) % 8
        else:
            ring_idx = (start_idx_d - i) % 8
        palace = RING[ring_idx]
        deity_layout[palace] = deity
    ju.deities = deity_layout
    
    return ju'''
    
    # 替换 Step 11 到 return ju
    idx_start = code.find(old_step11_start)
    idx_end = code.find(old_step14_end, idx_start)
    if idx_start > 0 and idx_end > idx_start:
        code = code[:idx_start] + new_rotation_code + code[idx_end + len(old_step14_end):]
    else:
        print("WARNING: Could not find Step 11-14 markers in paipan(). Manual fix needed.")
    
    # ================================================================
    # Write output
    # ================================================================
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(code)
    
    print(f"✓ Fixed engine written to: {output_path}")
    print(f"  - 节气计算: ephem天文算法 (任意年份)")
    print(f"  - 九星旋转: 外环序 PALACE_FLY_FORWARD")
    print(f"  - 天盘天干: 星带地盘干走")
    print(f"  - 八门旋转: 外环序 (简化版)")
    print(f"  - 八神排布: 外环序")

if __name__ == '__main__':
    src = sys.argv[1] if len(sys.argv) > 1 else 'fcas_engine_v2.py'
    out = sys.argv[2] if len(sys.argv) > 2 else 'fcas_engine_v2_fixed.py'
    apply_fix(src, out)
