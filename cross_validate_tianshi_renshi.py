"""
FCAS 天时×人事 交叉验证
用115w人事层结果(452条) × 天时层v6评估 → 验证"变应反对"效应

核心假说（来自项目已验证的发现）：
- "阳不能独立"：纯天时spread≈0
- "变之与应，常反对也"：T_ADV×H_FAV 应该优于 T_FAV×H_FAV

使用方式:
    python3 cross_validate_tianshi_renshi.py
"""

import json
from datetime import datetime
from collections import defaultdict

from fcas_engine_v2 import paipan
from assess_tianshi_v6 import assess_stock_tianshi_v6, STOCK_CONFIG, \
    JIAZI_60, find_xun, XUN_TO_DUNGAN

# ============================================================
# 补充4个标的到STOCK_CONFIG（如果还没有）
# ============================================================

EXTRA_STOCKS = {
    '688256.SH': {
        'name': '寒武纪',
        'ipo_ganzhi': '甲子',
        'effective_gan': '戊',  # 甲子遁戊
        'pan_layer': 'tianpan',
    },
    '601138.SH': {
        'name': '工业富联',
        'ipo_ganzhi': '辛未',
        'effective_gan': '辛',
        'pan_layer': 'tianpan',
    },
    '600547.SH': {
        'name': '山东黄金',
        'ipo_ganzhi': '癸酉',
        'effective_gan': '癸',
        'pan_layer': 'tianpan',
    },
    '601899.SH': {
        'name': '紫金矿业',
        'ipo_ganzhi': '乙未',
        'effective_gan': '乙',
        'pan_layer': 'tianpan',
    },
}

# 合并到STOCK_CONFIG
for code, cfg in EXTRA_STOCKS.items():
    if code not in STOCK_CONFIG:
        STOCK_CONFIG[code] = cfg


# ============================================================
# 人事层信号映射
# ============================================================

# 人事层信号 → 简化分类
RENSHI_MAP = {
    'STRONGLY_FAVORABLE': 'H_FAV',
    'FAVORABLE': 'H_FAV',
    'MIXED': 'H_NEU',
    'CAUTIOUS': 'H_UNFAV',
    'ADVERSE': 'H_UNFAV',
}

# 天时层信号 → 简化分类
TIANSHI_MAP = {
    'FAVORABLE': 'T_FAV',
    'PARTIAL_GOOD': 'T_FAV',
    'NEUTRAL': 'T_NEU',
    'PARTIAL_BAD': 'T_UNFAV',
    'UNFAVORABLE': 'T_UNFAV',
    'STAGNANT': 'T_NEU',    # 伏吟归中性
    'VOLATILE': 'T_NEU',    # 反吟归中性
}


def run_cross_validation():
    """
    天时×人事交叉验证主函数
    """
    print("=" * 70)
    print("  FCAS 天时×人事 交叉验证")
    print("  验证'变应反对'效应: T_UNFAV×H_FAV vs T_FAV×H_FAV")
    print("=" * 70)
    
    # ── 加载人事层结果 ──
    with open('backtest_115w_results.json') as f:
        renshi_data = json.load(f)
    renshi_results = renshi_data['results']
    
    print(f"\n人事层数据: {len(renshi_results)}条")
    print(f"标的: {set(r['stock_code'] for r in renshi_results)}")
    print(f"时间: {renshi_results[0]['date']} ~ {renshi_results[-1]['date']}")
    
    # 检查哪些标的在STOCK_CONFIG里
    valid_results = [r for r in renshi_results if r['stock_code'] in STOCK_CONFIG]
    print(f"有天时配置的: {len(valid_results)}条")
    
    if not valid_results:
        print("❌ 没有可交叉验证的数据")
        return
    
    # ── 排盘缓存（同一周同一局，多标的共享）──
    pan_cache = {}  # date_str → (ju, pan_dict)
    
    # ── 交叉验证循环 ──
    cross_results = []
    
    print(f"\n开始交叉验证...")
    for i, r in enumerate(valid_results):
        date_str = r['date']
        stock_code = r['stock_code']
        renshi_signal = r['signal']
        
        # 排盘（缓存）
        if date_str not in pan_cache:
            try:
                dt = datetime.strptime(date_str, '%Y-%m-%d')
                # 用周五的数据日期对应的周一开盘排盘
                weekday = dt.weekday()
                monday = dt  # 数据日期本身
                ju = paipan(datetime(monday.year, monday.month, monday.day, 9, 30))
                pan_cache[date_str] = ju
            except Exception as e:
                print(f"  ⚠️ 排盘失败 {date_str}: {e}")
                continue
        
        ju = pan_cache[date_str]
        
        # 天时评估
        try:
            tianshi = assess_stock_tianshi_v6(ju, stock_code)
            tianshi_label = tianshi['label']
        except Exception as e:
            print(f"  ⚠️ 天时评估失败 {date_str} {stock_code}: {e}")
            continue
        
        # 分类
        h_cat = RENSHI_MAP.get(renshi_signal, 'H_NEU')
        t_cat = TIANSHI_MAP.get(tianshi_label, 'T_NEU')
        cross_cat = f"{t_cat}×{h_cat}"
        
        cross_results.append({
            'date': date_str,
            'stock_code': stock_code,
            'renshi_signal': renshi_signal,
            'tianshi_label': tianshi_label,
            'h_cat': h_cat,
            't_cat': t_cat,
            'cross_cat': cross_cat,
            'return_1w': r.get('return_1w'),
            'return_13w': r.get('return_13w'),
            'tianshi_score': tianshi.get('combined_score', 0),
        })
        
        if (i + 1) % 100 == 0:
            print(f"  进度: {i+1}/{len(valid_results)}")
    
    print(f"\n✅ 交叉验证完成: {len(cross_results)}条")
    
    # ── 统计分析 ──
    print("\n" + "=" * 70)
    print("  交叉验证统计")
    print("=" * 70)
    
    # 交叉分类分布
    cross_counts = defaultdict(int)
    cross_1w = defaultdict(list)
    cross_13w = defaultdict(list)
    
    for cr in cross_results:
        cat = cr['cross_cat']
        cross_counts[cat] += 1
        if cr['return_1w'] is not None:
            cross_1w[cat].append(cr['return_1w'])
        if cr['return_13w'] is not None:
            cross_13w[cat].append(cr['return_13w'])
    
    # 打印交叉矩阵
    print("\n📊 交叉分类分布:")
    h_cats = ['H_FAV', 'H_NEU', 'H_UNFAV']
    t_cats = ['T_FAV', 'T_NEU', 'T_UNFAV']
    
    print(f"  {'':16s}", end='')
    for h in h_cats:
        print(f" {h:>10s}", end='')
    print()
    
    for t in t_cats:
        print(f"  {t:16s}", end='')
        for h in h_cats:
            key = f"{t}×{h}"
            n = cross_counts.get(key, 0)
            print(f" {n:10d}", end='')
        print()
    
    # 各交叉类别的收益率
    print(f"\n📈 各交叉类别收益率:")
    print(f"  {'Category':20s} | {'1W Avg':>8s} | {'13W Avg':>8s} | {'N':>6s}")
    print(f"  {'-'*20}-+-{'-'*8}-+-{'-'*8}-+-{'-'*6}")
    
    all_cats = sorted(cross_counts.keys())
    for cat in all_cats:
        r1w = cross_1w.get(cat, [])
        r13w = cross_13w.get(cat, [])
        avg_1w = sum(r1w) / len(r1w) if r1w else 0
        avg_13w = sum(r13w) / len(r13w) if r13w else 0
        n = cross_counts[cat]
        print(f"  {cat:20s} | {avg_1w:+7.2f}% | {avg_13w:+7.2f}% | {n:6d}")
    
    # ── 核心检验："变应反对" ──
    print(f"\n{'='*70}")
    print(f"  核心检验: 变应反对 (T_UNFAV×H_FAV vs T_FAV×H_FAV)")
    print(f"{'='*70}")
    
    key_oppose = 'T_UNFAV×H_FAV'
    key_align = 'T_FAV×H_FAV'
    
    if key_oppose in cross_1w and key_align in cross_1w:
        opp_1w = cross_1w[key_oppose]
        ali_1w = cross_1w[key_align]
        opp_13w = cross_13w.get(key_oppose, [])
        ali_13w = cross_13w.get(key_align, [])
        
        print(f"\n  T_UNFAV×H_FAV (反对): N={len(opp_1w)}, 1W={sum(opp_1w)/len(opp_1w):+.2f}%, 13W={sum(opp_13w)/len(opp_13w) if opp_13w else 0:+.2f}%")
        print(f"  T_FAV×H_FAV   (顺应): N={len(ali_1w)}, 1W={sum(ali_1w)/len(ali_1w):+.2f}%, 13W={sum(ali_13w)/len(ali_13w) if ali_13w else 0:+.2f}%")
        
        spread_1w = sum(opp_1w)/len(opp_1w) - sum(ali_1w)/len(ali_1w) if ali_1w else 0
        spread_13w = (sum(opp_13w)/len(opp_13w) - sum(ali_13w)/len(ali_13w)) if (opp_13w and ali_13w) else 0
        
        print(f"\n  变应反对 1W SPREAD: {spread_1w:+.2f}%")
        print(f"  变应反对 13W SPREAD: {spread_13w:+.2f}%")
        
        if spread_1w > 0 or spread_13w > 0:
            print(f"\n  ✅ 变应反对效应存在: 天时不利+人事有利 优于 天时有利+人事有利")
        else:
            print(f"\n  ❌ 变应反对效应未确认")
    else:
        print(f"\n  ⚠️ 数据不足:")
        if key_oppose not in cross_1w:
            print(f"    {key_oppose}: 无数据")
        if key_align not in cross_1w:
            print(f"    {key_align}: 无数据")
    
    # ── 人事层单独 vs 交叉 对比 ──
    print(f"\n{'='*70}")
    print(f"  人事层单独效果 vs 天时层调节")
    print(f"{'='*70}")
    
    # 按人事层分组
    for h in ['H_FAV', 'H_NEU', 'H_UNFAV']:
        h_1w_all = []
        h_13w_all = []
        for cat in cross_1w:
            if h in cat:
                h_1w_all.extend(cross_1w[cat])
        for cat in cross_13w:
            if h in cat:
                h_13w_all.extend(cross_13w[cat])
        
        if h_1w_all:
            print(f"\n  {h} (全部): N={len(h_1w_all)}, 1W={sum(h_1w_all)/len(h_1w_all):+.2f}%, 13W={sum(h_13w_all)/len(h_13w_all) if h_13w_all else 0:+.2f}%")
            
            # 按天时拆分
            for t in ['T_FAV', 'T_NEU', 'T_UNFAV']:
                key = f"{t}×{h}"
                if key in cross_1w:
                    r1 = cross_1w[key]
                    r13 = cross_13w.get(key, [])
                    print(f"    +{t}: N={len(r1)}, 1W={sum(r1)/len(r1):+.2f}%, 13W={sum(r13)/len(r13) if r13 else 0:+.2f}%")
    
    # 保存结果
    with open('cross_validation_results.json', 'w') as f:
        json.dump(cross_results, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 详细结果已保存: cross_validation_results.json")


if __name__ == '__main__':
    run_cross_validation()
