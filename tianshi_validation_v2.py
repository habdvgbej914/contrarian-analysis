"""
FCAS 天时层有效性检验 v2：真实奇门 vs 随机对照
Randomization test: does the real qimen tianshi layer add value?

v2 change: 天时评估从 three_layer_judgment() 改为直符宫+直使宫的
_score_palace() 评分。

原文依据：
- "占天子吉凶祸福，以坎宫为主" → 整体天时有明确主事宫位
- "占定一岁丰歉...看九宫以分九州，视九州有何星奇即知之" → per-宫评估
- 直符=君，直使=臣 → 天时整体由直符宫+直使宫决定
- "阳不能独立，必得阴而后立" → 纯天时spread应≈0
"""

import json
import random
import statistics
import sys
import os
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fcas_mcp import (
    paipan, evaluate_all_geju,
    GONG_WUXING, STAR_WUXING, GATE_WUXING, GATE_JIXIONG,
    shengke, calc_wangshuai, tg_wuxing,
    REL_WOKE, REL_SHENGWO, REL_KEWO,
    WS_WANG, WS_XIANG,
)

N_TRIALS = 1000
RENSHI_FILE = "backtest_115w_results.json"
CACHED_TIANSHI_FILE = "tianshi_cache_v2.json"


def load_renshi():
    with open(RENSHI_FILE, 'r') as f:
        data = json.load(f)
    seen = set()
    clean = []
    for r in data["results"]:
        key = (r["date"], r["stock_code"])
        if key not in seen:
            seen.add(key)
            clean.append(r)
    return clean


def classify_renshi(signal):
    if signal in ("STRONGLY_FAVORABLE", "FAVORABLE"):
        return "H_FAV"
    elif signal in ("ADVERSE", "CAUTIOUS"):
        return "H_ADV"
    else:
        return "H_NEU"


def score_tianshi_palace(ju, palace, all_geju):
    """Score a single palace using star/gate/geju/stem logic.
    
    Same logic as _score_palace() in stock_positioning.py,
    but WITHOUT the "palace-stem five-element relationship" section
    (because tianshi has no 本命干 — it's a global assessment).
    
    原文依据:
    - 星吉凶×旺衰: "凡星逢时旺相有气"
    - 门吉凶×旺衰×门迫: "吉门被迫吉不就，凶门被迫凶不起"
    - 宫位格局: per-palace geju
    - 天地盘干交互: "地盘属静，天盘属动。以动合静，则吉凶生焉"
    """
    if palace is None:
        return 0
    
    month_br = ju.month_branch
    star = ju.stars.get(palace)
    gate = ju.gates.get(palace) if palace != 5 else ju.gates.get(2)
    gong_wx = GONG_WUXING.get(palace)
    h_stem = ju.heaven.get(palace)
    g_stem = ju.ground.get(palace)
    score = 0
    
    # Star quality × wangshuai
    STAR_DAJI = {3, 4, 5}
    STAR_XIAOJI = {2, 7}
    STAR_DAXIONG = {0, 1}
    STAR_XIAOXIONG = {8, 6}
    
    if star is not None:
        sw = STAR_WUXING.get(star)
        ws = calc_wangshuai(sw, month_br) if sw else None
        hq = ws in (WS_WANG, WS_XIANG) if ws is not None else False
        if star in STAR_DAJI:
            score += 3 if hq else 1
        elif star in STAR_XIAOJI:
            score += 2 if hq else 1
        elif star in STAR_DAXIONG:
            score -= 3 if hq else 0
        elif star in STAR_XIAOXIONG:
            score -= 2 if hq else 0
    
    # Gate quality × wangshuai + menpo
    if gate is not None:
        gj = GATE_JIXIONG.get(gate, -1)
        gw = GATE_WUXING.get(gate)
        gws = calc_wangshuai(gw, month_br) if gw else None
        ghq = gws in (WS_WANG, WS_XIANG) if gws is not None else False
        if gj == 1:
            score += 3 if ghq else 1
        elif gj == 0:
            score -= 3 if ghq else 0
        # 门迫: 宫克门
        if gong_wx and gw and shengke(gong_wx, gw) == REL_WOKE:
            if gj == 1:
                score -= 2  # 吉门被迫→吉不就
            elif gj == 0:
                score += 2  # 凶门被迫→凶不起
    
    # Local geju patterns (per-palace only)
    local = [g for g in all_geju if g.palace == palace]
    score += sum(g.severity + 1 for g in local if g.jixiong == 1)
    score -= sum(g.severity + 1 for g in local if g.jixiong == 0)
    
    # Heaven-ground stem interaction
    if h_stem is not None and g_stem is not None:
        rel = shengke(tg_wuxing(g_stem), tg_wuxing(h_stem))
        if rel == REL_SHENGWO:
            score += 1
        elif rel == REL_KEWO:
            score -= 1
    
    return score


def assess_tianshi(ju, all_geju):
    """Assess overall tianshi by scoring zhifu palace + zhishi palace.
    
    直符=君, 直使=臣. 天时整体由这两个宫位决定.
    直符宫权重0.6, 直使宫权重0.4.
    
    Returns (assessment_label, score).
    """
    zhifu_score = score_tianshi_palace(ju, ju.zhifu_palace, all_geju)
    zhishi_score = score_tianshi_palace(ju, ju.zhishi_palace, all_geju)
    
    # 直符宫(君)权重高于直使宫(臣)
    combined = zhifu_score * 0.6 + zhishi_score * 0.4
    combined = round(combined, 1)
    
    if combined >= 5:
        return "T_FAV", combined
    elif combined >= 2:
        return "T_SLIGHT_FAV", combined
    elif combined <= -5:
        return "T_ADV", combined
    elif combined <= -2:
        return "T_SLIGHT_ADV", combined
    else:
        return "T_NEU", combined


def classify_tianshi_3way(label):
    """Map 5-level tianshi to 3-way for cross-table."""
    if label in ("T_FAV", "T_SLIGHT_FAV"):
        return "T_FAV"
    elif label in ("T_ADV", "T_SLIGHT_ADV"):
        return "T_ADV"
    else:
        return "T_NEU"


def get_real_tianshi(dates):
    """Get real qimen tianshi for each date."""
    if os.path.exists(CACHED_TIANSHI_FILE):
        with open(CACHED_TIANSHI_FILE, 'r') as f:
            cache = json.load(f)
        missing = [d for d in dates if d not in cache]
        if not missing:
            print(f"[Tianshi] Loaded {len(cache)} dates from cache")
            return cache
        print(f"[Tianshi] Cache has {len(cache)} dates, {len(missing)} missing")
    else:
        cache = {}
        missing = list(dates)
    
    print(f"[Tianshi] Computing {len(missing)} dates via palace scoring...")
    for i, date_str in enumerate(sorted(missing)):
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        monday = dt - timedelta(days=dt.weekday())
        judgment_dt = monday.replace(hour=8, minute=0)
        
        try:
            ju = paipan(judgment_dt)
            all_geju = evaluate_all_geju(ju)
            label, score = assess_tianshi(ju, all_geju)
            cache[date_str] = {
                "label": label,
                "label_3way": classify_tianshi_3way(label),
                "score": score,
                "zhifu_palace": ju.zhifu_palace,
                "zhishi_palace": ju.zhishi_palace,
            }
        except Exception as e:
            print(f"  ERROR on {date_str}: {e}")
            cache[date_str] = {"label": "T_NEU", "label_3way": "T_NEU", "score": 0}
        
        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{len(missing)} done")
    
    with open(CACHED_TIANSHI_FILE, 'w') as f:
        json.dump(cache, f, indent=2)
    print(f"[Tianshi] Saved cache ({len(cache)} dates)")
    
    return cache


def calc_spread(results, tianshi_map, return_key="return_1w"):
    cells = defaultdict(list)
    for r in results:
        ret = r.get(return_key)
        if ret is None:
            continue
        ts = tianshi_map.get(r['date'], {})
        ts_label = ts.get('label_3way', 'T_NEU') if isinstance(ts, dict) else ts
        rs = classify_renshi(r['signal'])
        cells[(ts_label, rs)].append(ret)
    
    fav_fav = cells.get(("T_FAV", "H_FAV"), [])
    adv_adv = cells.get(("T_ADV", "H_ADV"), [])
    
    avg_ff = sum(fav_fav) / len(fav_fav) if fav_fav else 0
    avg_aa = sum(adv_adv) / len(adv_adv) if adv_adv else 0
    spread = avg_ff - avg_aa
    
    t_fav_all = []
    t_adv_all = []
    for r in results:
        ret = r.get(return_key)
        if ret is None:
            continue
        ts = tianshi_map.get(r['date'], {})
        ts_label = ts.get('label_3way', 'T_NEU') if isinstance(ts, dict) else ts
        if ts_label == "T_FAV":
            t_fav_all.append(ret)
        elif ts_label == "T_ADV":
            t_adv_all.append(ret)
    
    pure_t = 0
    if t_fav_all and t_adv_all:
        pure_t = sum(t_fav_all)/len(t_fav_all) - sum(t_adv_all)/len(t_adv_all)
    
    return {
        'spread': spread, 'pure_tianshi_spread': pure_t,
        'n_ff': len(fav_fav), 'n_aa': len(adv_adv),
        'avg_ff': avg_ff, 'avg_aa': avg_aa,
    }


def print_cross_table(results, tianshi_map, return_key="return_1w", label=""):
    cells = defaultdict(list)
    for r in results:
        ret = r.get(return_key)
        if ret is None:
            continue
        ts = tianshi_map.get(r['date'], {})
        ts_label = ts.get('label_3way', 'T_NEU') if isinstance(ts, dict) else ts
        rs = classify_renshi(r['signal'])
        cells[(ts_label, rs)].append(ret)
    
    print(f"\n{'='*65}")
    print(f"Cross Table: {label} ({return_key})")
    print(f"{'='*65}")
    print(f"{'':>12} {'H_FAV':>14} {'H_NEU':>14} {'H_ADV':>14}")
    for ts in ["T_FAV", "T_NEU", "T_ADV"]:
        row = f"{ts:>12}"
        for rs in ["H_FAV", "H_NEU", "H_ADV"]:
            vals = cells.get((ts, rs), [])
            if vals:
                avg = sum(vals)/len(vals)
                row += f" {avg:>+7.2f}%({len(vals):>3})"
            else:
                row += f" {'---':>14}"
        print(row)
    
    ts_dist = defaultdict(int)
    for r in results:
        if r.get(return_key) is None:
            continue
        ts = tianshi_map.get(r['date'], {})
        ts_label = ts.get('label_3way', 'T_NEU') if isinstance(ts, dict) else ts
        ts_dist[ts_label] += 1
    total = sum(ts_dist.values())
    print(f"\nTianshi distribution: ", end="")
    for k in ["T_FAV", "T_NEU", "T_ADV"]:
        n = ts_dist.get(k, 0)
        print(f"{k}={n}({n/total*100:.0f}%) ", end="")
    print()


def generate_random_tianshi(dates, real_dist_fracs, real_cache):
    """Generate random tianshi preserving real distribution fractions."""
    labels = []
    for label, frac in real_dist_fracs.items():
        labels.extend([label] * round(frac * len(dates)))
    while len(labels) < len(dates):
        labels.append("T_NEU")
    while len(labels) > len(dates):
        labels.pop()
    random.shuffle(labels)
    
    result = {}
    for d, lbl in zip(sorted(dates), labels):
        result[d] = {"label_3way": lbl}
    return result


def main():
    print("=" * 65)
    print("FCAS Tianshi Validation v2: Palace Scoring Method")
    print("=" * 65)
    
    results = load_renshi()
    print(f"\nLoaded {len(results)} renshi judgments")
    
    unique_dates = sorted(set(r['date'] for r in results))
    print(f"Unique dates: {len(unique_dates)}")
    
    valid = [r for r in results if r.get('return_1w') is not None]
    print(f"Valid (with return_1w): {len(valid)}")
    
    # === REAL TIANSHI ===
    print(f"\n--- Real Qimen Tianshi (palace scoring) ---")
    real_tianshi = get_real_tianshi(unique_dates)
    
    # Show 5-level distribution
    from collections import Counter
    label_dist = Counter(v['label'] for v in real_tianshi.values())
    print(f"\n5-level tianshi distribution:")
    for k in ["T_FAV", "T_SLIGHT_FAV", "T_NEU", "T_SLIGHT_ADV", "T_ADV"]:
        print(f"  {k}: {label_dist.get(k, 0)}")
    
    # 3-way distribution
    real_3way = defaultdict(int)
    for d in unique_dates:
        real_3way[real_tianshi[d]['label_3way']] += 1
    total_d = sum(real_3way.values())
    dist_fracs = {k: v/total_d for k, v in real_3way.items()}
    print(f"\n3-way: {dict(real_3way)} → {dict(dist_fracs)}")
    
    # Score distribution
    scores = [real_tianshi[d]['score'] for d in unique_dates]
    print(f"\nScore stats: min={min(scores)}, max={max(scores)}, mean={sum(scores)/len(scores):.1f}, median={sorted(scores)[len(scores)//2]}")
    
    # Print cross table
    print_cross_table(valid, real_tianshi, "return_1w", "REAL QIMEN (palace scoring)")
    
    real_spread = calc_spread(valid, real_tianshi, "return_1w")
    print(f"\n>>> Real spread (T_FAV×H_FAV - T_ADV×H_ADV): {real_spread['spread']:+.2f}%")
    print(f"    T_FAV×H_FAV: {real_spread['avg_ff']:+.2f}% (n={real_spread['n_ff']})")
    print(f"    T_ADV×H_ADV: {real_spread['avg_aa']:+.2f}% (n={real_spread['n_aa']})")
    print(f">>> Pure tianshi spread: {real_spread['pure_tianshi_spread']:+.2f}%")
    
    # === RANDOM TRIALS ===
    print(f"\n--- Random Control ({N_TRIALS} trials) ---")
    random_spreads = []
    
    for i in range(N_TRIALS):
        rand = generate_random_tianshi(unique_dates, dist_fracs, real_tianshi)
        s = calc_spread(valid, rand, "return_1w")
        random_spreads.append(s['spread'])
    
    mean_rs = statistics.mean(random_spreads)
    std_rs = statistics.stdev(random_spreads)
    
    rank = sum(1 for x in random_spreads if x < real_spread['spread'])
    percentile = rank / N_TRIALS * 100
    better_count = sum(1 for x in random_spreads if x >= real_spread['spread'])
    p_value = better_count / N_TRIALS
    
    print(f"\nRandom spread: mean={mean_rs:+.2f}%, std={std_rs:.2f}%, min={min(random_spreads):+.2f}%, max={max(random_spreads):+.2f}%")
    
    print(f"\n{'='*65}")
    print(f"VERDICT")
    print(f"{'='*65}")
    print(f"Real qimen spread:  {real_spread['spread']:+.2f}%")
    print(f"Random mean spread: {mean_rs:+.2f}%")
    print(f"Percentile rank:    {percentile:.1f}%")
    print(f"p-value:            {p_value:.4f}")
    
    if p_value < 0.05:
        print(f"\n✅ SIGNIFICANT (p<0.05): Palace-based tianshi adds value.")
    elif p_value < 0.10:
        print(f"\n⚠️ MARGINAL (p<0.10): Weak evidence of tianshi value.")
    else:
        print(f"\n❌ NOT SIGNIFICANT (p≥0.10): Cannot distinguish from random.")
    
    print(f"\nPure tianshi spread: {real_spread['pure_tianshi_spread']:+.2f}% (expected ≈0)")
    
    output = {
        "method": "palace_scoring (zhifu+zhishi)",
        "real_spread": real_spread['spread'],
        "real_pure_tianshi_spread": real_spread['pure_tianshi_spread'],
        "random_mean": mean_rs,
        "random_std": std_rs,
        "percentile_rank": percentile,
        "p_value": p_value,
        "n_trials": N_TRIALS,
        "n_results": len(valid),
        "n_dates": len(unique_dates),
        "real_distribution_3way": dict(real_3way),
        "real_distribution_5level": dict(label_dist),
    }
    with open("tianshi_validation_results_v2.json", 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to tianshi_validation_results_v2.json")


if __name__ == "__main__":
    main()
