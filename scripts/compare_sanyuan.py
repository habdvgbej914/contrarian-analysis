"""
scripts/compare_sanyuan.py — 验证当前三元判断 vs 超神/接气精确方法的差异率

超神: 符头落在上一节气周期内 → 本旬沿用上一节气的局数
接气: 下一旬符头跨入下一节气 → 下一旬提前换局（本旬不受影响）

本脚本仅分析"超神"情况（接气不影响当天局数）。
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from fcas_engine_v2 import (
    get_day_ganzhi, get_current_term, get_sanyuan, get_ju_number,
)

def get_current_term_start(dt):
    """找当前节气的起始日期（向前扫描最近的节气切换点）"""
    term_idx, _, _ = get_current_term(dt)
    start = dt
    for back in range(1, 25):  # 节气间隔约15天，扫25天足够
        check = dt - timedelta(days=back)
        ct, _, _ = get_current_term(check)
        if ct != term_idx:
            start = dt - timedelta(days=back - 1)
            break
    return start

def get_futou_date(dt):
    """找当前日期的符头日期"""
    day_tg, day_dz = get_day_ganzhi(dt)
    if day_tg >= 5:
        days_since = day_tg - 5
    else:
        days_since = day_tg
    return dt - timedelta(days=days_since)

def analyze_chaoshen(dt):
    """判断当天是否处于超神状态"""
    term_start = get_current_term_start(dt)
    futou_date = get_futou_date(dt)
    # 超神：符头在节气起始之前
    return futou_date.date() < term_start.date()

# ============================================================
# 对比：连续730天（2年）
# ============================================================
start = datetime(2024, 1, 1)
total = 0
chaoshen_count = 0
diff_ju = 0

chaoshen_examples = []

for i in range(730):
    dt = start + timedelta(days=i)
    total += 1

    # 当前方法
    term_idx, _, is_yang = get_current_term(dt)
    day_tg, day_dz = get_day_ganzhi(dt)
    sy = get_sanyuan(day_tg, day_dz)
    ju_current = get_ju_number(term_idx, sy, is_yang)

    # 超神判断
    is_chaoshen = analyze_chaoshen(dt)
    if is_chaoshen:
        chaoshen_count += 1
        # 超神时精确方法：用上一节气的局数
        prev = dt - timedelta(days=1)
        while True:
            pt, _, _ = get_current_term(prev)
            if pt != term_idx:
                break
            prev -= timedelta(days=1)
        # 上一节气的最后一天
        prev_term_idx, _, prev_yang = get_current_term(prev)
        prev_tg, prev_dz = get_day_ganzhi(prev)
        prev_sy = get_sanyuan(prev_tg, prev_dz)
        ju_precise = get_ju_number(prev_term_idx, prev_sy, prev_yang)

        if ju_current != ju_precise:
            diff_ju += 1
            if len(chaoshen_examples) < 5:
                chaoshen_examples.append({
                    'date': dt.strftime('%Y-%m-%d'),
                    'current': f"{'阳' if is_yang else '阴'}遁{ju_current}局",
                    'precise': f"{'阳' if prev_yang else '阴'}遁{ju_precise}局",
                })

print(f"测试天数: {total}")
print(f"超神天数: {chaoshen_count} ({chaoshen_count/total*100:.1f}%)")
print(f"局数差异天数: {diff_ju} ({diff_ju/total*100:.1f}%)")
print()
if chaoshen_examples:
    print("超神且局数不同的示例:")
    for ex in chaoshen_examples:
        print(f"  {ex['date']}: 当前={ex['current']} 精确={ex['precise']}")
print()
if diff_ju / total < 0.05:
    print(f"✓ 差异率 {diff_ju/total*100:.1f}% < 5%，当前方法可接受，保持不变。")
else:
    print(f"⚠ 差异率 {diff_ju/total*100:.1f}% >= 5%，建议修正引擎。")
