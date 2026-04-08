"""
cross_validate_3layer.py — 天时×人事×六亲 三层联合交叉验证

验证核心: 邵雍"变之与应常反对" — 跨层方向张力是否consistently跑赢同向叠加
"""
import json
from collections import defaultdict

# ============================================================
# 方向归类
# ============================================================
FAV_LABELS  = {'FAVORABLE','STRONGLY_FAVORABLE','PARTIAL_GOOD','SLIGHT_FAV','STAGNANT_JI'}
ADV_LABELS  = {'UNFAVORABLE','PARTIAL_BAD','ADVERSE','SLIGHT_ADV','STAGNANT_XIONG',
               'FAVORABLE_TRAPPED'}
NEU_LABELS  = {'NEUTRAL','STAGNANT','VOLATILE','STAGNANT_XIONG'}  # fallthrough

def direction(label, prefix=''):
    if label in FAV_LABELS:  return f'{prefix}FAV'
    if label in ADV_LABELS:  return f'{prefix}ADV'
    return f'{prefix}NEU'

# ============================================================
# 加载三层数据
# ============================================================
print("加载数据...")

with open('backtest_587w_results.json') as f:
    renshi_raw = json.load(f)
with open('tianshi_v6_backtest_results.json') as f:
    tianshi_raw = json.load(f)
with open('liuqin_backtest_results.json') as f:
    liuqin_raw = json.load(f)

# ============================================================
# 索引：(stock_code, date) → record
# ============================================================
def make_index(records, date_key, code_key):
    idx = {}
    for r in records:
        date = r.get(date_key) or r.get('week_start') or r.get('date')
        code = r.get(code_key)
        if date and code:
            idx[(code, date)] = r
    return idx

renshi_idx  = make_index(renshi_raw,  'date', 'stock_code')
tianshi_idx = make_index(tianshi_raw, 'date', 'stock_code')
liuqin_idx  = make_index(liuqin_raw,  'date', 'stock_code')

print(f"  人事层: {len(renshi_idx)} records")
print(f"  天时层: {len(tianshi_idx)} records")
print(f"  六亲层: {len(liuqin_idx)} records")

# ============================================================
# Inner join: 三层都有 → 保留
# ============================================================
joined = []
for key in renshi_idx:
    if key not in tianshi_idx or key not in liuqin_idx:
        continue
    rr = renshi_idx[key]
    tr = tianshi_idx[key]
    lr = liuqin_idx[key]

    # 收益率
    fwd = rr.get('forward_returns', {})
    r13w_h = fwd.get('13w') or fwd.get('13W')
    r1w_h  = fwd.get('1w')  or fwd.get('1W')
    r13w_t = tr.get('return_13w')
    r1w_t  = tr.get('return_1w')
    r13w_l = lr.get('13W') or lr.get('return_13w')
    r1w_l  = lr.get('1W')  or lr.get('return_1w')

    # 使用天时层的收益率作为基准（最完整）
    r13w = r13w_t
    r1w  = r1w_t
    if r13w is None:
        continue

    # 标签与方向
    h_label = rr.get('signal') or rr.get('label') or 'NEUTRAL'
    t_label = tr.get('label') or 'NEUTRAL'
    l_label = lr.get('label') or 'NEUTRAL'

    h_dir = direction(h_label, 'H_')
    t_dir = direction(t_label, 'T_')
    l_dir = direction(l_label, 'L_')

    joined.append({
        'date': key[1],
        'stock_code': key[0],
        'h_label': h_label, 'h_dir': h_dir,
        't_label': t_label, 't_dir': t_dir,
        'l_label': l_label, 'l_dir': l_dir,
        'combo': f"{t_dir}×{h_dir}×{l_dir}",
        'r1w': r1w,
        'r13w': r13w,
    })

print(f"  合并后: {len(joined)} records\n")

# ============================================================
# 统计函数
# ============================================================
def avg(vals):
    return sum(vals)/len(vals) if vals else 0.0

def stats_group(records):
    r1  = [r['r1w']  for r in records if r.get('r1w')  is not None]
    r13 = [r['r13w'] for r in records if r.get('r13w') is not None]
    return len(records), avg(r1)*100 if r1 else 0, avg(r13)*100 if r13 else 0

# ============================================================
# 1. 三层27种组合
# ============================================================
combos = defaultdict(list)
for r in joined:
    combos[r['combo']].append(r)

print("=" * 72)
print("三层联合交叉 (天时T × 人事H × 六亲L) — 按13W排序")
print("=" * 72)
print(f"{'组合':<35} {'N':>5} {'1W%':>8} {'13W%':>8}  备注")
print("-" * 72)

combo_stats = []
for combo, recs in combos.items():
    n, r1, r13 = stats_group(recs)
    if n < 5:
        continue
    # 检测跨层张力
    parts = combo.split('×')  # T_x, H_x, L_x
    dirs = [p.split('_')[1] for p in parts]  # FAV/NEU/ADV
    fav_count = dirs.count('FAV')
    adv_count = dirs.count('ADV')
    tension = fav_count > 0 and adv_count > 0
    note = '⚡TENSION' if tension else ('✓ALIGNED' if fav_count >= 2 else '')
    combo_stats.append((combo, n, r1, r13, note))

for combo, n, r1, r13, note in sorted(combo_stats, key=lambda x: -x[3]):
    print(f"{combo:<35} {n:>5} {r1:>+7.2f}% {r13:>+7.2f}%  {note}")

# ============================================================
# 2. 邵雍验证：同向 vs 跨层张力
# ============================================================
print()
print("=" * 72)
print("邵雍'变之与应常反对' — 张力 vs 同向 汇总")
print("=" * 72)

tension_recs = [r for r in joined if r['combo'] in
                {c for c,_,_,_,n in combo_stats if '⚡TENSION' in n}]
aligned_fav  = [r for r in joined
                if r['h_dir']=='H_FAV' and r['t_dir']=='T_FAV' and r['l_dir']=='L_FAV']
aligned_adv  = [r for r in joined
                if r['h_dir']=='H_ADV' and r['t_dir']=='T_ADV' and r['l_dir']=='L_ADV']
all_tension  = [r for r in joined if
                ({'FAV','ADV'} <= {r['h_dir'].split('_')[1],
                                   r['t_dir'].split('_')[1],
                                   r['l_dir'].split('_')[1]})]

groups = [
    ("三层全FAV (完全同向)", aligned_fav),
    ("三层全ADV (完全同向)", aligned_adv),
    ("含张力(至少1FAV+1ADV)", all_tension),
    ("全部样本",              joined),
]
print(f"{'组合':<30} {'N':>6} {'1W%':>8} {'13W%':>8}")
print("-" * 56)
for name, recs in groups:
    n, r1, r13 = stats_group(recs)
    print(f"{name:<30} {n:>6} {r1:>+7.2f}% {r13:>+7.2f}%")

# ============================================================
# 3. 两两交叉（忽略第三层）—— 找最强双层配对
# ============================================================
print()
print("=" * 72)
print("两两层交叉 — 天时×人事 / 天时×六亲 / 人事×六亲")
print("=" * 72)

for label_a, label_b, key_a, key_b in [
    ("天时×人事", "T×H", 't_dir', 'h_dir'),
    ("天时×六亲", "T×L", 't_dir', 'l_dir'),
    ("人事×六亲", "H×L", 'h_dir', 'l_dir'),
]:
    print(f"\n  {label_a}:")
    pairs = defaultdict(list)
    for r in joined:
        pairs[f"{r[key_a]}×{r[key_b]}"].append(r)
    pair_stats = []
    for k, recs in pairs.items():
        n, r1, r13 = stats_group(recs)
        if n < 10: continue
        pair_stats.append((k, n, r1, r13))
    print(f"  {'组合':<25} {'N':>6} {'1W%':>8} {'13W%':>8}")
    print(f"  {'-'*50}")
    for k, n, r1, r13 in sorted(pair_stats, key=lambda x: -x[3]):
        dirs = [p.split('_')[1] for p in k.split('×')]
        tension = 'FAV' in dirs and 'ADV' in dirs
        note = ' ⚡' if tension else ''
        print(f"  {k:<25} {n:>6} {r1:>+7.2f}% {r13:>+7.2f}%{note}")

# ============================================================
# 4. 保存结果
# ============================================================
output = {
    'meta': {
        'total_joined': len(joined),
        'description': '天时v6 × 人事层 × 六亲v2 三层联合交叉验证',
    },
    'combo_stats': [
        {'combo': c, 'n': n, 'r1w_pct': round(r1,3), 'r13w_pct': round(r13,3), 'note': note}
        for c, n, r1, r13, note in sorted(combo_stats, key=lambda x: -x[3])
    ],
    'records': [
        {k: v for k, v in r.items()}
        for r in joined
    ]
}

with open('cross_validate_3layer_results.json', 'w') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print()
print(f"结果已保存: cross_validate_3layer_results.json ({len(joined)} records)")
