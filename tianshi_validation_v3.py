"""
FCAS 天时层有效性检验 v3: 宝鉴"占求财" per-stock 方法
Validates assess_stock_tianshi_baojian() against 587w × 8 stocks backtest data.

v3 改动:
- 天时评估从全局 palace scoring 改为 per-stock 宝鉴"占求财"四维度评估
- 每个标的在每个时刻有自己的天时评分（因为日干不同，落宫不同）
- 对比旧方法: palace scoring p=0.507 ❌

原文依据（宝鉴卷四·占求财）:
  "当分体用，以生门主之。生门所落之宫分为体，生门天盘所落之星为用。"
  "吉格吉星，所求如意。有一不吉，所求仅半。休囚不吉，所求全无。"
"""

import json
import random
import statistics
import sys
import os
from datetime import datetime, timedelta
from collections import defaultdict, Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fcas_engine_v2 import paipan, evaluate_all_geju
from assess_stock_tianshi_baojian import assess_stock_tianshi_baojian

# === Config ===
BACKTEST_FILE = "backtest_587w_results.json"
CACHE_FILE = "tianshi_cache_v3_baojian.json"
N_TRIALS = 1000


def load_backtest():
    """Load 587w backtest results."""
    with open(BACKTEST_FILE, 'r') as f:
        data = json.load(f)
    # Data is a bare list (not wrapped in {"results": [...]})
    if isinstance(data, dict) and "results" in data:
        data = data["results"]
    return data


def classify_renshi(signal):
    """Map human-layer 5-level signal to 3-way."""
    if signal in ("STRONGLY_FAVORABLE", "FAVORABLE"):
        return "H_FAV"
    elif signal in ("ADVERSE", "CAUTIOUS"):
        return "H_ADV"
    else:
        return "H_NEU"


def classify_tianshi_3way(assessment):
    """Map baojian assessment to 3-way.
    
    Only clear directional signals get FAV/ADV.
    All ambiguous states (STAGNANT, VOLATILE, NEUTRAL) → T_NEU.
    Target: ~30% directional per 邵雍 "有效方向性信号≈30%"
    """
    if assessment in ("FAVORABLE", "PARTIAL_GOOD"):
        return "T_FAV"
    elif assessment in ("UNFAVORABLE", "PARTIAL_BAD"):
        return "T_ADV"
    else:
        # NEUTRAL, STAGNANT, VOLATILE
        return "T_NEU"


def compute_all_tianshi(results):
    """Compute per-stock tianshi for every (date, stock) pair.
    
    Uses caching to avoid recomputing paipan for same dates.
    Returns dict: {(date_str, stock_code): {assessment, score, label_3way}}
    """
    # Check cache
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            cache = json.load(f)
        # Cache key is "date|stock_code"
        needed = set()
        for r in results:
            key = f"{r['date']}|{r['stock_code']}"
            if key not in cache:
                needed.add(r['date'])
        if not needed:
            print(f"[Tianshi] Loaded {len(cache)} entries from cache")
            return cache
        print(f"[Tianshi] Cache has {len(cache)} entries, {len(needed)} dates need computing")
    else:
        cache = {}
        needed = set(r['date'] for r in results)
    
    # Group records by date
    date_stocks = defaultdict(set)
    for r in results:
        if r['date'] in needed:
            date_stocks[r['date']].add(r['stock_code'])
    
    print(f"[Tianshi] Computing {len(needed)} dates × per-stock assessments...")
    sorted_dates = sorted(needed)
    
    for i, date_str in enumerate(sorted_dates):
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        # Use Monday 08:00 of that week for paipan
        monday = dt - timedelta(days=dt.weekday())
        judgment_dt = monday.replace(hour=8, minute=0)
        
        try:
            ju = paipan(judgment_dt)
            all_geju = evaluate_all_geju(ju)
            
            for stock_code in date_stocks[date_str]:
                key = f"{date_str}|{stock_code}"
                assessment, score, detail = assess_stock_tianshi_baojian(
                    ju, stock_code, all_geju
                )
                cache[key] = {
                    "assessment": assessment,
                    "score": score,
                    "label_3way": classify_tianshi_3way(assessment),
                    "shengmen_env": detail.get("shengmen_env", 0),
                    "stock_env": detail.get("stock_env", 0),
                }
        except Exception as e:
            print(f"  ERROR on {date_str}: {e}")
            for stock_code in date_stocks[date_str]:
                key = f"{date_str}|{stock_code}"
                cache[key] = {
                    "assessment": "NEUTRAL",
                    "score": 0,
                    "label_3way": "T_NEU",
                }
        
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(sorted_dates)} dates done")
    
    # Save cache
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f)
    print(f"[Tianshi] Saved cache ({len(cache)} entries)")
    
    return cache


def calc_metrics(results, tianshi_cache, return_key="13w"):
    """Calculate spread, cross-table cells, and pure tianshi spread."""
    cells = defaultdict(list)
    t_fav_all = []
    t_adv_all = []
    
    for r in results:
        fr = r.get('forward_returns', {})
        ret = fr.get(return_key)
        if ret is None:
            continue
        
        key = f"{r['date']}|{r['stock_code']}"
        ts = tianshi_cache.get(key, {})
        ts_label = ts.get('label_3way', 'T_NEU')
        rs = classify_renshi(r['signal'])
        
        cells[(ts_label, rs)].append(ret)
        
        if ts_label == "T_FAV":
            t_fav_all.append(ret)
        elif ts_label == "T_ADV":
            t_adv_all.append(ret)
    
    # Cross spread: T_FAV×H_FAV vs T_ADV×H_ADV
    fav_fav = cells.get(("T_FAV", "H_FAV"), [])
    adv_adv = cells.get(("T_ADV", "H_ADV"), [])
    
    avg_ff = sum(fav_fav) / len(fav_fav) if fav_fav else 0
    avg_aa = sum(adv_adv) / len(adv_adv) if adv_adv else 0
    cross_spread = avg_ff - avg_aa
    
    # Pure tianshi spread
    pure_t = 0
    if t_fav_all and t_adv_all:
        pure_t = sum(t_fav_all)/len(t_fav_all) - sum(t_adv_all)/len(t_adv_all)
    
    # FAV group vs ADV group (for comparison with human-layer test)
    h_fav_all = []
    h_adv_all = []
    for r in results:
        fr = r.get('forward_returns', {})
        ret = fr.get(return_key)
        if ret is None:
            continue
        key = f"{r['date']}|{r['stock_code']}"
        ts = tianshi_cache.get(key, {})
        ts_label = ts.get('label_3way', 'T_NEU')
        rs = classify_renshi(r['signal'])
        
        combined = (ts_label, rs)
        if combined in [("T_FAV", "H_FAV"), ("T_FAV", "H_NEU"), ("T_NEU", "H_FAV")]:
            h_fav_all.append(ret)
        elif combined in [("T_ADV", "H_ADV"), ("T_ADV", "H_NEU"), ("T_NEU", "H_ADV")]:
            h_adv_all.append(ret)
    
    combined_spread = 0
    if h_fav_all and h_adv_all:
        combined_spread = sum(h_fav_all)/len(h_fav_all) - sum(h_adv_all)/len(h_adv_all)
    
    return {
        'cross_spread': cross_spread,
        'pure_tianshi_spread': pure_t,
        'combined_spread': combined_spread,
        'n_ff': len(fav_fav), 'n_aa': len(adv_adv),
        'avg_ff': avg_ff, 'avg_aa': avg_aa,
        'n_t_fav': len(t_fav_all), 'n_t_adv': len(t_adv_all),
        'n_combined_fav': len(h_fav_all), 'n_combined_adv': len(h_adv_all),
        'cells': {f"{k[0]}×{k[1]}": (sum(v)/len(v), len(v)) for k, v in cells.items() if v},
    }


def print_cross_table(results, tianshi_cache, return_key="13w", label=""):
    """Print formatted cross-table."""
    cells = defaultdict(list)
    for r in results:
        fr = r.get('forward_returns', {})
        ret = fr.get(return_key)
        if ret is None:
            continue
        key = f"{r['date']}|{r['stock_code']}"
        ts = tianshi_cache.get(key, {})
        ts_label = ts.get('label_3way', 'T_NEU')
        rs = classify_renshi(r['signal'])
        cells[(ts_label, rs)].append(ret)
    
    print(f"\n{'='*70}")
    print(f"Cross Table: {label} ({return_key} return)")
    print(f"{'='*70}")
    print(f"{'':>14} {'H_FAV':>16} {'H_NEU':>16} {'H_ADV':>16}")
    for ts in ["T_FAV", "T_NEU", "T_ADV"]:
        row = f"{ts:>14}"
        for rs in ["H_FAV", "H_NEU", "H_ADV"]:
            vals = cells.get((ts, rs), [])
            if vals:
                avg = sum(vals)/len(vals)
                row += f" {avg:>+7.2f}%({len(vals):>4})"
            else:
                row += f" {'---':>16}"
        print(row)
    
    # Distribution
    ts_dist = defaultdict(int)
    for r in results:
        if r.get('forward_returns', {}).get(return_key) is None:
            continue
        key = f"{r['date']}|{r['stock_code']}"
        ts = tianshi_cache.get(key, {})
        ts_dist[ts.get('label_3way', 'T_NEU')] += 1
    total = sum(ts_dist.values())
    print(f"\nTianshi distribution: ", end="")
    for k in ["T_FAV", "T_NEU", "T_ADV"]:
        n = ts_dist.get(k, 0)
        pct = n/total*100 if total else 0
        print(f"{k}={n}({pct:.0f}%) ", end="")
    print()


def randomization_test(results, real_cache, return_key="13w"):
    """Randomization test: shuffle tianshi labels, compare spread."""
    real_metrics = calc_metrics(results, real_cache, return_key)
    real_cross = real_metrics['cross_spread']
    
    # Get per-record tianshi labels for shuffling
    records_with_ret = []
    for r in results:
        fr = r.get('forward_returns', {})
        ret = fr.get(return_key)
        if ret is None:
            continue
        key = f"{r['date']}|{r['stock_code']}"
        ts = real_cache.get(key, {})
        records_with_ret.append({
            'ret': ret,
            'rs': classify_renshi(r['signal']),
            'ts_real': ts.get('label_3way', 'T_NEU'),
        })
    
    # Get real distribution
    ts_labels = [r['ts_real'] for r in records_with_ret]
    
    print(f"\n--- Randomization Test ({N_TRIALS} trials, {return_key} return) ---")
    random_spreads = []
    
    for trial in range(N_TRIALS):
        # Shuffle tianshi labels (preserving distribution)
        shuffled = ts_labels.copy()
        random.shuffle(shuffled)
        
        # Build fake cache
        cells = defaultdict(list)
        for rec, fake_ts in zip(records_with_ret, shuffled):
            cells[(fake_ts, rec['rs'])].append(rec['ret'])
        
        fav_fav = cells.get(("T_FAV", "H_FAV"), [])
        adv_adv = cells.get(("T_ADV", "H_ADV"), [])
        avg_ff = sum(fav_fav)/len(fav_fav) if fav_fav else 0
        avg_aa = sum(adv_adv)/len(adv_adv) if adv_adv else 0
        random_spreads.append(avg_ff - avg_aa)
    
    mean_rs = statistics.mean(random_spreads)
    std_rs = statistics.stdev(random_spreads) if len(random_spreads) > 1 else 0
    better_count = sum(1 for x in random_spreads if x >= real_cross)
    p_value = better_count / N_TRIALS
    
    return real_cross, mean_rs, std_rs, p_value, real_metrics


def main():
    print("=" * 70)
    print("FCAS Tianshi Validation v3: 宝鉴'占求财' Per-Stock Method")
    print("=" * 70)
    
    # Load data
    results = load_backtest()
    print(f"\nLoaded {len(results)} records")
    
    stocks = set(r['stock_code'] for r in results)
    dates = sorted(set(r['date'] for r in results))
    print(f"Stocks: {len(stocks)} | Dates: {len(dates)} | Range: {dates[0]} ~ {dates[-1]}")
    
    has_13w = sum(1 for r in results if r.get('forward_returns', {}).get('13w') is not None)
    print(f"Records with 13w return: {has_13w}/{len(results)}")
    
    # Compute per-stock tianshi
    tianshi_cache = compute_all_tianshi(results)
    
    # Assessment distribution
    assessments = Counter()
    for r in results:
        key = f"{r['date']}|{r['stock_code']}"
        ts = tianshi_cache.get(key, {})
        assessments[ts.get('assessment', 'UNKNOWN')] += 1
    
    print(f"\nPer-stock tianshi assessment distribution:")
    for k, v in assessments.most_common():
        print(f"  {k}: {v} ({v/len(results)*100:.1f}%)")
    
    # 3-way distribution
    ts3 = Counter()
    for r in results:
        key = f"{r['date']}|{r['stock_code']}"
        ts = tianshi_cache.get(key, {})
        ts3[ts.get('label_3way', 'T_NEU')] += 1
    print(f"\n3-way: {dict(ts3)}")
    
    # === Cross Tables ===
    print_cross_table(results, tianshi_cache, "13w", "BAOJIAN per-stock tianshi")
    print_cross_table(results, tianshi_cache, "1w", "BAOJIAN per-stock tianshi")
    
    # === Randomization Tests ===
    for rk in ["13w", "1w"]:
        real_spread, rand_mean, rand_std, p_val, metrics = randomization_test(
            results, tianshi_cache, rk
        )
        
        print(f"\n{'='*70}")
        print(f"VERDICT — {rk} return")
        print(f"{'='*70}")
        print(f"Real cross spread (T_FAV×H_FAV - T_ADV×H_ADV): {real_spread:+.2f}%")
        print(f"  T_FAV×H_FAV: {metrics['avg_ff']:+.2f}% (n={metrics['n_ff']})")
        print(f"  T_ADV×H_ADV: {metrics['avg_aa']:+.2f}% (n={metrics['n_aa']})")
        print(f"Random mean spread: {rand_mean:+.2f}% (std={rand_std:.2f}%)")
        print(f"p-value: {p_val:.4f}")
        print(f"Pure tianshi spread: {metrics['pure_tianshi_spread']:+.2f}%")
        print(f"Combined T+H spread: {metrics['combined_spread']:+.2f}%")
        
        if p_val < 0.05:
            print(f"\n✅ SIGNIFICANT (p<0.05): Baojian tianshi adds value!")
        elif p_val < 0.10:
            print(f"\n⚠️ MARGINAL (p<0.10): Weak evidence.")
        else:
            print(f"\n❌ NOT SIGNIFICANT (p≥0.10): Cannot distinguish from random.")
    
    # === Comparison with old method ===
    print(f"\n{'='*70}")
    print(f"COMPARISON: Old Palace Scoring vs New Baojian Method")
    print(f"{'='*70}")
    print(f"Old method (palace scoring):  p=0.507 ❌ spread=+0.84%")
    m_new = calc_metrics(results, tianshi_cache, "13w")
    print(f"New method (baojian):         spread={m_new['cross_spread']:+.2f}%")
    print(f"  (p-value shown in VERDICT section above)")
    
    # Save results
    output = {
        "method": "baojian_per_stock (占求财 4-dimension)",
        "n_records": len(results),
        "n_dates": len(dates),
        "n_stocks": len(stocks),
        "assessment_distribution": dict(assessments),
        "three_way_distribution": dict(ts3),
        "metrics_13w": {k: v for k, v in calc_metrics(results, tianshi_cache, "13w").items() if k != 'cells'},
        "metrics_1w": {k: v for k, v in calc_metrics(results, tianshi_cache, "1w").items() if k != 'cells'},
        "comparison": {
            "old_palace_scoring": {"p_value": 0.507, "spread": 0.84},
        }
    }
    
    with open("tianshi_validation_results_v3.json", 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to tianshi_validation_results_v3.json")


if __name__ == "__main__":
    main()
