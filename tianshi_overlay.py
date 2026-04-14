"""
FCAS 天时层×人事层叠加分析
Overlay qimen tianshi layer on top of existing 448 renshi (human-affairs) results.

原文依据（《御定奇门宝鉴》）：
"阳将阴神，二气齐分。门仪细推，别主辨形。"
"直符所加用者天干——阳将不吉，视阴神吉，则可救；若阳将凶，阴神又凶，则无救。"
"大凶无气交为小，小凶有气亦丁宁"
"吉门被迫吉不就，凶门被迫凶不起"

交叉规则：
- 天时吉 + 人事吉 → 大吉 (STRONG_FAVORABLE)
- 天时吉 + 人事凶 → 可救 (TIANSHI_RESCUE)  
- 天时凶 + 人事吉 → 吉不就 (RENSHI_CAPPED)
- 天时凶 + 人事凶 → 无救 (NO_RESCUE)
"""

import json
import sys
import os
import statistics
from datetime import datetime, timedelta
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from fcas_engine_v2 import analyze

# ============================================================
# LOAD EXISTING RENSHI RESULTS
# ============================================================

def load_renshi():
    path = os.path.join(SCRIPT_DIR, "backtest_115w_results.json")
    with open(path, 'r') as f:
        data = json.load(f)
    
    # Deduplicate
    seen = set()
    clean = []
    for r in data["results"]:
        key = (r["date"], r["stock_code"])
        if key not in seen:
            seen.add(key)
            clean.append(r)
    return clean


# ============================================================
# TIANSHI LAYER: Run qimen for each unique date
# ============================================================

def classify_tianshi(final_assessment):
    """Map the detailed final_assessment to a simple 3-way classification.
    
    Per《宝鉴》原文分层:
    - 纯吉/强吉 → TIANSHI_JI  
    - 纯凶/强凶/compounded（base本身为ADVERSE/DRAINING）→ TIANSHI_XIONG
    - 中间状态 → TIANSHI_NEUTRAL
    
    关键原则：base=NEUTRAL的状态（比和），即使被凶格拉偏（LEANING_ADVERSE），
    本质仍是中性。原文"上下比兮自谦"——比和本身不吉不凶。
    只有base本身为ADVERSE/PRESSURED/DRAINING时才是真凶。
    """
    fa = final_assessment.upper()
    
    # === 明确的吉（base=FAVORABLE/SUPPORTIVE）===
    if "STRONGLY_FAVORABLE" in fa:
        return "TIANSHI_JI"
    if "FAVORABLE" in fa and "WEAKLY" not in fa and "CAUTION" not in fa:
        return "TIANSHI_JI"
    
    # === NEUTRAL_LEANING 系列：base=NEUTRAL，全部归NEUTRAL ===
    # 不管后缀是FAVORABLE还是ADVERSE，base是比和就是中性
    if fa.startswith("NEUTRAL"):
        return "TIANSHI_NEUTRAL"
    
    # === 减弱的吉/凶 → NEUTRAL ===
    if "WEAKLY_FAVORABLE" in fa:
        return "TIANSHI_NEUTRAL"
    if "CAUTION" in fa:  # FAVORABLE_WITH_CAUTION
        return "TIANSHI_NEUTRAL"
    if "MITIGATED" in fa:  # ADVERSE_MITIGATED, DRAINING_MITIGATED
        return "TIANSHI_NEUTRAL"
    if "WITH_OPENING" in fa:  # ADVERSE_WITH_OPENING  
        return "TIANSHI_NEUTRAL"
    if "DEPLETED" in fa:
        return "TIANSHI_NEUTRAL"
    
    # === 明确的凶（base=ADVERSE/DRAINING，无减弱后缀）===
    if "STRONGLY_ADVERSE" in fa or "ACTIVELY_ADVERSE" in fa:
        return "TIANSHI_XIONG"
    if "COMPOUNDED" in fa:
        return "TIANSHI_XIONG"
    if fa == "ADVERSE" or fa == "DRAINING" or fa == "ACTIVELY_DRAINING":
        return "TIANSHI_XIONG"
    
    # === 兜底 ===
    return "TIANSHI_NEUTRAL"


def get_tianshi_for_dates(dates):
    """Run qimen engine for each unique date.
    Uses Monday 辰时 (8:00 AM) as the standard time."""
    
    tianshi_cache = {}
    
    for date_str in sorted(dates):
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        
        # Find the Monday of this week
        # date_str is typically a Friday (weekly close)
        # We want the Monday of the SAME week for the judgment
        weekday = dt.weekday()  # 0=Mon, 4=Fri
        monday = dt - timedelta(days=weekday)
        
        # Use 辰时 = 8:00 AM (market open period)
        judgment_dt = monday.replace(hour=8, minute=0)
        
        try:
            result = analyze(judgment_dt)
            assessment = result['assessment']
            
            tianshi_cache[date_str] = {
                'datetime': judgment_dt.strftime('%Y-%m-%d %H:%M'),
                'ju_type': result['ju_summary']['type'],
                'term': result['ju_summary']['term'],
                'sanyuan': result['ju_summary']['sanyuan'],
                'final_assessment': assessment['final_assessment'],
                'layer1_fuyi': assessment['layer1_fuyi'],
                'layer2_qi': assessment['layer2_qi'],
                'layer3_modifier': assessment['layer3_modifier'],
                'tianshi_class': classify_tianshi(assessment['final_assessment']),
            }
        except Exception as e:
            print(f"ERROR on {date_str}: {e}")
            tianshi_cache[date_str] = {
                'final_assessment': 'ERROR',
                'tianshi_class': 'TIANSHI_NEUTRAL',  # fallback
            }
    
    return tianshi_cache


# ============================================================
# CROSS-RULE: 天时 × 人事 → Combined Signal
# ============================================================

def classify_renshi(record):
    """Map renshi output to 3-way.

    Prefer explicit `intent_assessment` when present; fall back to legacy
    5-level `signal` values for older result files.
    """
    intent_assessment = record.get("intent_assessment")
    if intent_assessment in ("strongly_supported", "supported_with_resistance", "supported_but_weak", "contested"):
        return "RENSHI_JI"
    elif intent_assessment in ("not_viable", "challenged"):
        return "RENSHI_XIONG"

    signal = record.get("signal")
    if signal in ("STRONGLY_FAVORABLE", "FAVORABLE"):
        return "RENSHI_JI"
    elif signal in ("ADVERSE", "CAUTIOUS"):
        return "RENSHI_XIONG"
    else:
        return "RENSHI_NEUTRAL"


def combine_tianshi_renshi(tianshi_class, renshi_record):
    """Apply Baojian cross-rules.
    
    原文: "阳将不吉，视阴神吉，则可救；若阳将凶，阴神又凶，则无救。"
    天时=阳将, 人事=阴神
    """
    rc = classify_renshi(renshi_record)
    
    if tianshi_class == "TIANSHI_JI":
        if rc == "RENSHI_JI":
            return "STRONG_FAVORABLE"    # 天时吉+人事吉=大吉
        elif rc == "RENSHI_XIONG":
            return "TIANSHI_RESCUE"       # 天时吉+人事凶=可救
        else:
            return "TIANSHI_LEANING_JI"   # 天时吉+人事中=偏吉
    
    elif tianshi_class == "TIANSHI_XIONG":
        if rc == "RENSHI_JI":
            return "RENSHI_CAPPED"        # 天时凶+人事吉=吉不就
        elif rc == "RENSHI_XIONG":
            return "NO_RESCUE"            # 天时凶+人事凶=无救
        else:
            return "TIANSHI_LEANING_XIONG" # 天时凶+人事中=偏凶
    
    else:  # TIANSHI_NEUTRAL
        # 天时中性 → 以人事层判断为主
        if rc == "RENSHI_JI":
            return "RENSHI_DOMINANT_JI"
        elif rc == "RENSHI_XIONG":
            return "RENSHI_DOMINANT_XIONG"
        else:
            return "NEUTRAL"


# ============================================================
# SIMPLIFIED 5-LEVEL COMBINED SIGNAL (for comparison with pure renshi)
# ============================================================

COMBINED_TO_5LEVEL = {
    "STRONG_FAVORABLE": "STRONGLY_FAVORABLE",
    "TIANSHI_LEANING_JI": "FAVORABLE",
    "RENSHI_DOMINANT_JI": "FAVORABLE",
    "TIANSHI_RESCUE": "MIXED",
    "RENSHI_CAPPED": "MIXED",
    "NEUTRAL": "MIXED",
    "TIANSHI_LEANING_XIONG": "CAUTIOUS",
    "RENSHI_DOMINANT_XIONG": "CAUTIOUS",
    "NO_RESCUE": "ADVERSE",
}


# ============================================================
# MAIN ANALYSIS
# ============================================================

def main():
    print("=" * 70)
    print("FCAS 天时×人事叠加分析")
    print("=" * 70)
    
    # Load renshi results
    results = load_renshi()
    print(f"\n人事层: {len(results)} judgments loaded")
    
    # Get unique dates
    unique_dates = sorted(set(r['date'] for r in results))
    print(f"唯一日期: {len(unique_dates)} weeks")
    
    # Run tianshi for all dates
    print(f"\n正在计算天时层（奇门排盘）...")
    tianshi = get_tianshi_for_dates(unique_dates)
    
    # Show tianshi distribution
    ts_dist = defaultdict(int)
    for d, t in tianshi.items():
        ts_dist[t['tianshi_class']] += 1
    print(f"\n天时层分布:")
    for k, v in sorted(ts_dist.items()):
        print(f"  {k}: {v} weeks ({v/len(tianshi)*100:.0f}%)")
    
    # Combine
    print(f"\n正在叠加天时×人事...")
    combined_results = []
    for r in results:
        ts = tianshi.get(r['date'], {})
        ts_class = ts.get('tianshi_class', 'TIANSHI_NEUTRAL')
        
        combined_raw = combine_tianshi_renshi(ts_class, r)
        combined_5 = COMBINED_TO_5LEVEL.get(combined_raw, "MIXED")
        
        combined_results.append({
            **r,
            'tianshi_assessment': ts.get('final_assessment', 'N/A'),
            'tianshi_class': ts_class,
            'combined_raw': combined_raw,
            'combined_signal': combined_5,
        })
    
    # ============================================================
    # ANALYSIS: Compare pure renshi vs combined
    # ============================================================
    
    print(f"\n{'='*70}")
    print("对比分析: 纯人事层 vs 天时×人事叠加")
    print(f"{'='*70}")
    
    for label, sig_key in [("纯人事层(signal)", "signal"), ("天时×人事(combined_signal)", "combined_signal")]:
        print(f"\n--- {label} ---")
        by_sig = defaultdict(list)
        for r in combined_results:
            by_sig[r[sig_key]].append(r)
        
        print(f"{'Signal':<25} {'N':>5} {'1W%':>8} {'4W%':>8} {'13W%':>8} {'13W_win':>8}")
        for sig in ["STRONGLY_FAVORABLE", "FAVORABLE", "MIXED", "CAUTIOUS", "ADVERSE"]:
            recs = by_sig.get(sig, [])
            if not recs:
                continue
            r1 = [r['return_1w'] for r in recs if r['return_1w'] is not None]
            r4 = [r['return_4w'] for r in recs if r['return_4w'] is not None]
            r13 = [r['return_13w'] for r in recs if r['return_13w'] is not None]
            
            avg1 = sum(r1)/len(r1) if r1 else 0
            avg4 = sum(r4)/len(r4) if r4 else 0
            avg13 = sum(r13)/len(r13) if r13 else 0
            win13 = sum(1 for x in r13 if x > 0)/len(r13)*100 if r13 else 0
            
            print(f"{sig:<25} {len(recs):>5} {avg1:>+8.2f} {avg4:>+8.2f} {avg13:>+8.2f} {win13:>7.0f}%")
        
        # Spread
        fav_r = [r['return_13w'] for r in combined_results 
                 if r[sig_key] in ("STRONGLY_FAVORABLE","FAVORABLE") and r['return_13w'] is not None]
        adv_r = [r['return_13w'] for r in combined_results 
                 if r[sig_key] in ("CAUTIOUS","ADVERSE") and r['return_13w'] is not None]
        if fav_r and adv_r:
            fa, aa = sum(fav_r)/len(fav_r), sum(adv_r)/len(adv_r)
            print(f"\n  FAV group: {fa:+.2f}% ({len(fav_r)}) | ADV group: {aa:+.2f}% ({len(adv_r)})")
            print(f"  >>> SPREAD: {fa-aa:+.2f}% <<<")
    
    # ============================================================
    # DETAILED CROSS-TABLE
    # ============================================================
    
    print(f"\n{'='*70}")
    print("交叉表: 天时×人事 → 13W平均收益")
    print(f"{'='*70}")
    
    cross = defaultdict(list)
    for r in combined_results:
        key = (r['tianshi_class'], classify_renshi(r))
        if r['return_13w'] is not None:
            cross[key].append(r['return_13w'])
    
    print(f"\n{'':>20} {'RENSHI_JI':>15} {'RENSHI_NEUTRAL':>15} {'RENSHI_XIONG':>15}")
    for ts in ["TIANSHI_JI", "TIANSHI_NEUTRAL", "TIANSHI_XIONG"]:
        row = f"{ts:>20}"
        for rs in ["RENSHI_JI", "RENSHI_NEUTRAL", "RENSHI_XIONG"]:
            vals = cross.get((ts, rs), [])
            if vals:
                avg = sum(vals)/len(vals)
                row += f" {avg:>+8.1f}%({len(vals):>3})"
            else:
                row += f" {'---':>15}"
        print(row)
    
    # ============================================================
    # TIMING VALUE: Combined FAV-only vs B&H
    # ============================================================
    
    print(f"\n{'='*70}")
    print("择时价值: Combined FAV-only vs B&H")
    print(f"{'='*70}")
    
    for sc in ["688256.SH","600547.SH","601138.SH","601899.SH"]:
        sr = [r for r in combined_results if r['stock_code']==sc and r['return_1w'] is not None]
        if not sr:
            continue
        nm = sr[0]['stock_name']
        
        bh_total = sum(r['return_1w'] for r in sr)
        bh_per = bh_total / len(sr)
        
        # Pure renshi FAV
        fav_r = [r for r in sr if r['signal'] in ("FAVORABLE","STRONGLY_FAVORABLE")]
        fav_ret = sum(r['return_1w'] for r in fav_r) if fav_r else 0
        fav_per = fav_ret / len(fav_r) if fav_r else 0
        
        # Combined FAV
        cfav = [r for r in sr if r['combined_signal'] in ("FAVORABLE","STRONGLY_FAVORABLE")]
        cfav_ret = sum(r['return_1w'] for r in cfav) if cfav else 0
        cfav_per = cfav_ret / len(cfav) if cfav else 0
        
        print(f"\n{nm}:")
        print(f"  B&H:         {bh_per:+.2f}%/周 ({len(sr)}周)")
        print(f"  纯人事FAV:   {fav_per:+.2f}%/周 ({len(fav_r)}周)")
        print(f"  天时×人事FAV: {cfav_per:+.2f}%/周 ({len(cfav)}周)")
    
    # ============================================================
    # WORST/BEST CAPTURE
    # ============================================================
    
    print(f"\n{'='*70}")
    print("最大跌幅保护率")
    print(f"{'='*70}")
    
    worst15 = sorted([r for r in combined_results if r['return_1w'] is not None], 
                     key=lambda x: x['return_1w'])[:15]
    
    # Pure renshi warned
    warned_r = sum(1 for r in worst15 if r['signal'] in ("CAUTIOUS","ADVERSE"))
    # Combined warned
    warned_c = sum(1 for r in worst15 if r['combined_signal'] in ("CAUTIOUS","ADVERSE"))
    
    print(f"  纯人事层:     {warned_r}/15 ({warned_r/15*100:.0f}%)")
    print(f"  天时×人事:    {warned_c}/15 ({warned_c/15*100:.0f}%)")
    
    # Save combined results
    output = {
        "meta": {
            "description": "天时层×人事层叠加分析",
            "tianshi_source": "fcas_mcp.py qimen engine",
            "renshi_source": "backtest_115w_results.json (448 Claude Opus judgments)",
            "cross_rule": "Baojian: 阳将(天时)定大局, 阴神(人事)做修正",
            "total_results": len(combined_results),
        },
        "tianshi_by_date": tianshi,
        "results": combined_results,
    }
    
    out_path = os.path.join(SCRIPT_DIR, "backtest_115w_combined.json")
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n结果已保存: {out_path}")


if __name__ == "__main__":
    main()
