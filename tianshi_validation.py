"""
FCAS 天时层有效性检验：真实奇门 vs 随机对照
Randomization test: does the real qimen tianshi layer add value,
or could any random 3-way split produce the same spread?

Method:
1. Load the 448 renshi (human-affairs) judgments — these stay fixed
2. Run the REAL qimen tianshi overlay → get real spread
3. Run N_TRIALS random tianshi assignments (preserving the ~30/40/30 distribution)
4. Compare: where does the real spread rank among random trials?

If real spread > 95% of random trials → qimen adds statistically significant value.
If real spread ~ median of random trials → qimen is no better than random labeling.

原文依据检验：
- "阳不能独立，必得阴而后立" → 纯天时spread应≈0
- "天之孽十之一犹可违，人之孽十之九不可逭" → 人事层主导
- Question: does REAL qimen do better than RANDOM qimen when crossed with renshi?
"""

import json
import random
import statistics
import sys
import os
from datetime import datetime, timedelta
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

# Try to import the real engine for live qimen calculation
try:
    from fcas_mcp import analyze as fcas_analyze
    HAS_ENGINE = True
except ImportError:
    HAS_ENGINE = False
    print("[WARN] fcas_mcp not available, will use cached tianshi if available")


# ============================================================
# CONFIG
# ============================================================

N_TRIALS = 1000  # Number of random permutations
RENSHI_FILE = os.path.join(SCRIPT_DIR, "backtest_115w_results.json")
CACHED_TIANSHI_FILE = os.path.join(SCRIPT_DIR, "tianshi_cache.json")  # Will be created on first real run
RESULTS_FILE = os.path.join(SCRIPT_DIR, "tianshi_validation_results.json")
POSITIVE_INTENTS = {"strongly_supported", "supported_with_resistance", "supported_but_weak", "contested"}
NEGATIVE_INTENTS = {"not_viable", "challenged"}


# ============================================================
# LOAD DATA
# ============================================================

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


def classify_renshi(record):
    """Map renshi output to 3-way.

    Prefer explicit `intent_assessment` when available; fall back to legacy
    5-level `signal` for older result files.
    """
    intent_assessment = record.get("intent_assessment")
    if intent_assessment in POSITIVE_INTENTS:
        return "H_FAV"
    elif intent_assessment in NEGATIVE_INTENTS:
        return "H_ADV"

    signal = record.get("signal")
    if signal in ("STRONGLY_FAVORABLE", "FAVORABLE"):
        return "H_FAV"
    elif signal in ("ADVERSE", "CAUTIOUS"):
        return "H_ADV"
    else:
        return "H_NEU"


# ============================================================
# REAL TIANSHI: Run qimen for each unique date
# ============================================================

def classify_tianshi(final_assessment):
    """Map detailed assessment to 3-way classification.
    Same logic as tianshi_overlay.py."""
    fa = final_assessment.upper()
    
    if "STRONGLY_FAVORABLE" in fa:
        return "T_FAV"
    if "FAVORABLE" in fa and "WEAKLY" not in fa and "CAUTION" not in fa:
        return "T_FAV"
    if fa.startswith("NEUTRAL"):
        return "T_NEU"
    if "WEAKLY_FAVORABLE" in fa or "CAUTION" in fa:
        return "T_NEU"
    if "MITIGATED" in fa or "WITH_OPENING" in fa or "DEPLETED" in fa:
        return "T_NEU"
    if "STRONGLY_ADVERSE" in fa or "ACTIVELY_ADVERSE" in fa:
        return "T_ADV"
    if "COMPOUNDED" in fa:
        return "T_ADV"
    if fa in ("ADVERSE", "DRAINING", "ACTIVELY_DRAINING"):
        return "T_ADV"
    return "T_NEU"


def get_real_tianshi(dates):
    """Get real qimen tianshi for each date.
    Uses Monday 辰时 (8:00 AM)."""
    
    # Try cache first
    if os.path.exists(CACHED_TIANSHI_FILE):
        with open(CACHED_TIANSHI_FILE, 'r') as f:
            cache = json.load(f)
        # Check if cache covers all dates
        missing = [d for d in dates if d not in cache]
        if not missing:
            print(f"[Tianshi] Loaded {len(cache)} dates from cache")
            return cache
        print(f"[Tianshi] Cache has {len(cache)} dates, {len(missing)} missing")
    else:
        cache = {}
        missing = list(dates)
    
    if not HAS_ENGINE:
        print("[ERROR] Engine not available and cache incomplete. Cannot proceed.")
        print("  Run this script in the same directory as fcas_mcp.py first.")
        sys.exit(1)
    
    print(f"[Tianshi] Computing {len(missing)} dates via qimen engine...")
    for i, date_str in enumerate(sorted(missing)):
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        weekday = dt.weekday()
        monday = dt - timedelta(days=weekday)
        judgment_dt = monday.replace(hour=8, minute=0)
        
        try:
            result = fcas_analyze(judgment_dt)
            assessment = result['assessment']
            cache[date_str] = classify_tianshi(assessment['final_assessment'])
        except Exception as e:
            print(f"  ERROR on {date_str}: {e}")
            cache[date_str] = "T_NEU"
        
        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{len(missing)} done")
    
    # Save cache
    with open(CACHED_TIANSHI_FILE, 'w') as f:
        json.dump(cache, f)
    print(f"[Tianshi] Saved cache ({len(cache)} dates)")
    
    return cache


# ============================================================
# SPREAD CALCULATION
# ============================================================

def calc_spread(results, tianshi_map, return_key="return_1w"):
    """Calculate the FAV-ADV spread given a tianshi mapping.
    
    Cross-table: 3×3 (T_FAV/T_NEU/T_ADV × H_FAV/H_NEU/H_ADV)
    Spread = avg(T_FAV×H_FAV) - avg(T_ADV×H_ADV)
    """
    cells = defaultdict(list)
    
    for r in results:
        ret = r.get(return_key)
        if ret is None:
            continue
        
        ts = tianshi_map.get(r['date'], 'T_NEU')
        rs = classify_renshi(r)
        cells[(ts, rs)].append(ret)
    
    # Spread: best corner vs worst corner
    fav_fav = cells.get(("T_FAV", "H_FAV"), [])
    adv_adv = cells.get(("T_ADV", "H_ADV"), [])
    
    avg_ff = sum(fav_fav) / len(fav_fav) if fav_fav else 0
    avg_aa = sum(adv_adv) / len(adv_adv) if adv_adv else 0
    
    spread = avg_ff - avg_aa
    
    # Also calculate pure tianshi spread (ignoring renshi)
    t_fav_all = []
    t_adv_all = []
    for r in results:
        ret = r.get(return_key)
        if ret is None:
            continue
        ts = tianshi_map.get(r['date'], 'T_NEU')
        if ts == "T_FAV":
            t_fav_all.append(ret)
        elif ts == "T_ADV":
            t_adv_all.append(ret)
    
    pure_t_spread = 0
    if t_fav_all and t_adv_all:
        pure_t_spread = sum(t_fav_all)/len(t_fav_all) - sum(t_adv_all)/len(t_adv_all)
    
    return {
        'spread': spread,
        'pure_tianshi_spread': pure_t_spread,
        'n_ff': len(fav_fav),
        'n_aa': len(adv_adv),
        'avg_ff': avg_ff,
        'avg_aa': avg_aa,
    }


def print_cross_table(results, tianshi_map, return_key="return_1w", label=""):
    """Print the full 3×3 cross table."""
    cells = defaultdict(list)
    for r in results:
        ret = r.get(return_key)
        if ret is None:
            continue
        ts = tianshi_map.get(r['date'], 'T_NEU')
        rs = classify_renshi(r)
        cells[(ts, rs)].append(ret)
    
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
    
    # Distribution
    ts_dist = defaultdict(int)
    for r in results:
        if r.get(return_key) is None:
            continue
        ts_dist[tianshi_map.get(r['date'], 'T_NEU')] += 1
    total = sum(ts_dist.values())
    print(f"\nTianshi distribution: ", end="")
    for k in ["T_FAV", "T_NEU", "T_ADV"]:
        n = ts_dist.get(k, 0)
        print(f"{k}={n}({n/total*100:.0f}%) ", end="")
    print()


# ============================================================
# RANDOM CONTROL
# ============================================================

def generate_random_tianshi(dates, real_distribution):
    """Generate a random tianshi assignment preserving the real distribution.
    
    real_distribution: dict like {"T_FAV": 0.35, "T_NEU": 0.30, "T_ADV": 0.35}
    """
    labels = []
    for label, frac in real_distribution.items():
        labels.extend([label] * round(frac * len(dates)))
    
    # Adjust for rounding
    while len(labels) < len(dates):
        labels.append("T_NEU")
    while len(labels) > len(dates):
        labels.pop()
    
    random.shuffle(labels)
    return dict(zip(sorted(dates), labels))


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 65)
    print("FCAS Tianshi Validation: Real Qimen vs Random Control")
    print("=" * 65)
    
    # Load renshi
    results = load_renshi()
    print(f"\nLoaded {len(results)} renshi judgments")
    
    unique_dates = sorted(set(r['date'] for r in results))
    print(f"Unique dates: {len(unique_dates)}")
    
    # Get valid results (have return data)
    valid = [r for r in results if r.get('return_1w') is not None]
    print(f"Valid (with return_1w): {len(valid)}")
    
    # === REAL TIANSHI ===
    print(f"\n--- Real Qimen Tianshi ---")
    real_tianshi = get_real_tianshi(unique_dates)
    
    # Get distribution
    real_dist = defaultdict(int)
    for d in unique_dates:
        real_dist[real_tianshi.get(d, 'T_NEU')] += 1
    total_d = sum(real_dist.values())
    dist_fracs = {k: v/total_d for k, v in real_dist.items()}
    print(f"Real distribution: {dict(real_dist)} → {dict(dist_fracs)}")
    
    # Print real cross table
    print_cross_table(valid, real_tianshi, "return_1w", "REAL QIMEN")
    
    real_spread = calc_spread(valid, real_tianshi, "return_1w")
    print(f"\n>>> Real spread (T_FAV×H_FAV - T_ADV×H_ADV): {real_spread['spread']:+.2f}%")
    print(f">>> Pure tianshi spread (T_FAV_all - T_ADV_all): {real_spread['pure_tianshi_spread']:+.2f}%")
    
    # === RANDOM TRIALS ===
    print(f"\n--- Random Control ({N_TRIALS} trials) ---")
    random_spreads = []
    random_pure_spreads = []
    
    for i in range(N_TRIALS):
        rand_tianshi = generate_random_tianshi(unique_dates, dist_fracs)
        s = calc_spread(valid, rand_tianshi, "return_1w")
        random_spreads.append(s['spread'])
        random_pure_spreads.append(s['pure_tianshi_spread'])
    
    # Statistics
    mean_rs = statistics.mean(random_spreads)
    std_rs = statistics.stdev(random_spreads)
    median_rs = statistics.median(random_spreads)
    
    # Percentile rank of real spread
    rank = sum(1 for x in random_spreads if x < real_spread['spread'])
    percentile = rank / N_TRIALS * 100
    
    # p-value (one-sided: is real better than random?)
    better_count = sum(1 for x in random_spreads if x >= real_spread['spread'])
    p_value = better_count / N_TRIALS
    
    print(f"\nRandom spread distribution:")
    print(f"  Mean:   {mean_rs:+.2f}%")
    print(f"  Median: {median_rs:+.2f}%")
    print(f"  StdDev: {std_rs:.2f}%")
    print(f"  Min:    {min(random_spreads):+.2f}%")
    print(f"  Max:    {max(random_spreads):+.2f}%")
    
    print(f"\n{'='*65}")
    print(f"VERDICT")
    print(f"{'='*65}")
    print(f"Real qimen spread:  {real_spread['spread']:+.2f}%")
    print(f"Random mean spread: {mean_rs:+.2f}%")
    print(f"Percentile rank:    {percentile:.1f}% (real > {rank}/{N_TRIALS} random)")
    print(f"p-value:            {p_value:.4f}")
    
    if p_value < 0.05:
        print(f"\n✅ SIGNIFICANT (p<0.05): Qimen tianshi adds value beyond random labeling.")
    elif p_value < 0.10:
        print(f"\n⚠️ MARGINAL (p<0.10): Weak evidence that qimen adds value.")
    else:
        print(f"\n❌ NOT SIGNIFICANT (p≥0.10): Cannot distinguish qimen from random labeling.")
    
    # Pure tianshi comparison
    mean_pt = statistics.mean(random_pure_spreads)
    print(f"\nPure tianshi spread (no renshi): real={real_spread['pure_tianshi_spread']:+.2f}% vs random mean={mean_pt:+.2f}%")
    print(f"  (Expected ≈0 per 原文: '阳不能独立，必得阴而后立')")
    
    # Print one sample random cross table for reference
    sample_rand = generate_random_tianshi(unique_dates, dist_fracs)
    print_cross_table(valid, sample_rand, "return_1w", "SAMPLE RANDOM")
    
    # Save results
    output = {
        "real_spread": real_spread['spread'],
        "real_pure_tianshi_spread": real_spread['pure_tianshi_spread'],
        "random_mean": mean_rs,
        "random_std": std_rs,
        "percentile_rank": percentile,
        "p_value": p_value,
        "n_trials": N_TRIALS,
        "n_results": len(valid),
        "n_dates": len(unique_dates),
        "real_distribution": dict(real_dist),
    }
    with open(RESULTS_FILE, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to {RESULTS_FILE}")


if __name__ == "__main__":
    main()
