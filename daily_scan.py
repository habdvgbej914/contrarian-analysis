"""
FCAS Daily Scanner v2.1
气象分析系统 每日扫描器

Architecture:
- Qimen engine (fcas_engine_v2.py) does ALL structural judgment — no LLM involved
- stock_positioning.py provides per-stock palace lookup
- Claude API is OPTIONAL annotation layer (news context only, not structural)
- Output in business language, zero metaphysical terms
- Telegram push with multi-message support (4096 char limit)

v2.1 changes (2026-04-03, per 皇极经世书 10-round reading):
- #88: Max single-step change constraint — "自极乱至极治必三变"
- #83: 未然之防 — TAILWIND+ warns of 姤, HEADWIND+ notes 复 opportunity
- #82: Flip layer priority — 复=C5/C6 flip first, 姤=C1/C2 flip first (logged)

Usage: python3 daily_scan.py
Crontab: H4 frequency (08:00/12:00/16:00/20:00/00:00 London time)
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)


from fcas_engine_v2 import (
    paipan, analyze, evaluate_all_geju,
    TIANGAN_NAMES, GONG_GUA_NAMES, GONG_WUXING,
    STAR_NAMES, GATE_NAMES, DEITY_NAMES,
    STAR_WUXING, GATE_WUXING, GATE_JIXIONG,
    shengke, calc_wangshuai, tg_wuxing,
    REL_WOKE, REL_SHENGWO, REL_KEWO,
    WS_WANG, WS_XIANG, WS_QIU, WS_SI, WS_NAMES,
    WUXING_NAMES,
)
from stock_positioning import STOCK_POSITIONING, find_stock_palace
from assess_stock_tianshi_baojian import assess_stock_tianshi_baojian
from assess_fushi import assess_fushi, FUSHI_SIGNAL, apply_fushi_modifier
from fcas_utils import load_json_file, save_json_file, send_telegram

# === Config ===
HISTORY_FILE = os.path.join(_SCRIPT_DIR, "daily_scan_history.json")
MAX_HISTORY_RECORDS = 500  # Keep at most this many records in the history file

# Scan these stocks (subset of 10 — the 4 we have data for now)
SCAN_STOCKS = [
    "601899.SH",  # 紫金矿业
    "600547.SH",  # 山东黄金
    "600036.SH",  # 招商银行
    "601318.SH",  # 中国平安
    "000858.SZ",  # 五粮液
    "000651.SZ",  # 格力电器
    "000063.SZ",  # 中兴通讯
    "601012.SH",  # 隆基绿能
    "600276.SH",  # 恒瑞医药
    "601857.SH",  # 中国石油
]

# Business language mapping
ASSESSMENT_TAG = {
    "FAVORABLE":      "TAILWIND+",
    "PARTIAL_GOOD":   "TAILWIND",
    "NEUTRAL":        "NEUTRAL",
    "PARTIAL_BAD":    "HEADWIND",
    "UNFAVORABLE":    "HEADWIND+",
    # Legacy labels (for history compatibility)
    "SLIGHT_FAV":     "TAILWIND",
    "SLIGHT_ADV":     "HEADWIND",
    "ADVERSE":        "HEADWIND+",
    # Special states
    "STAGNANT_JI":    "STASIS+",
    "STAGNANT":       "STASIS",
    "STAGNANT_XIONG": "TRAPPED",
    "VOLATILE":       "VOLATILE",
    # Fushi-modified labels
    "STRONG_FAVORABLE":   "TAILWIND++",
    "FAVORABLE_TRAPPED":  "TAILWIND⚠",
    "PARTIAL_GOOD_PLUS":  "TAILWIND+",
}

ASSESSMENT_GUIDANCE = {
    "FAVORABLE":      "Strong support. Expand.",
    "PARTIAL_GOOD":   "Mild support. Proceed with caution.",
    "NEUTRAL":        "No directional bias. Hold course.",
    "PARTIAL_BAD":    "Mild resistance. Reduce exposure.",
    "UNFAVORABLE":    "Hostile environment. Defensive posture.",
    # Legacy
    "SLIGHT_FAV":     "Mild support. Proceed with caution.",
    "SLIGHT_ADV":     "Mild resistance. Reduce exposure.",
    "ADVERSE":        "Hostile environment. Defensive posture.",
    # Special
    "STAGNANT_JI":    "Positive lock. Hold for release.",
    "STAGNANT":       "Neutral lock. No new commitments.",
    "STAGNANT_XIONG": "Negative lock. Minimize exposure.",
    "VOLATILE":       "Expect reversals. Maintain flexibility.",
    # Fushi-modified
    "STRONG_FAVORABLE":  "Prime window. Expand with conviction.",
    "FAVORABLE_TRAPPED": "Apparent tailwind, structural block. Hold, don't add.",
    "PARTIAL_GOOD_PLUS": "Momentum boosted. Cautiously expand.",
}

# Zone mapping (宫 → business zone)
ZONE_NAMES = {
    1: "Reserve",    # 坎
    2: "Yield",      # 坤
    3: "Growth",     # 震
    4: "Expansion",  # 巽
    5: "Central",    # 中
    6: "Command",    # 乾
    7: "Harvest",    # 兑
    8: "Stability",  # 艮
    9: "Signal",     # 离
}

# Asset mapping (星 → asset type)
ASSET_NAMES = {
    0: "Deep",        # 天蓬
    1: "Distressed",  # 天芮
    2: "Momentum",    # 天冲
    3: "Support",     # 天辅
    4: "Anchor",      # 天禽
    5: "Core",        # 天心
    6: "Decay",       # 天柱
    7: "Stable",      # 天任
    8: "Volatile",    # 天英
}

# Channel mapping (门 → channel type)
CHANNEL_NAMES = {
    0: "Rest",       # 休门
    1: "Exit",       # 死门
    2: "Lateral",    # 伤门
    3: "Shelter",    # 杜门
    4: "Display",    # 景门
    5: "Alert",      # 惊门
    6: "Entry",      # 生门
    7: "Primary",    # 开门
}

DISCLAIMER = (
    "\n---\n"
    "⚠️ Structural diagnosis only. No directional forecast implied.\n"
    "~30% directional / ~70% neutral — by design.\n"
    "Precision target: 70%."
)


def load_history():
    """Load persisted scan history with schema validation."""
    return load_json_file(HISTORY_FILE, [], label="History", expected_type=list)

# ============================================================
# #88: Grade ordering for max single-step constraint
# 原文: "自极乱至于极治，必三变矣" — 不可跳级
# ============================================================
GRADE_ORDER = [
    "UNFAVORABLE",   # 0 = HEADWIND+
    "PARTIAL_BAD",   # 1 = HEADWIND
    "NEUTRAL",       # 2 = NEUTRAL
    "PARTIAL_GOOD",  # 3 = TAILWIND
    "FAVORABLE",     # 4 = TAILWIND+
]
GRADE_RANK = {g: i for i, g in enumerate(GRADE_ORDER)}
# Legacy labels mapped to same rank for history compatibility
GRADE_RANK["ADVERSE"] = 0
GRADE_RANK["SLIGHT_ADV"] = 1
GRADE_RANK["SLIGHT_FAV"] = 3
# Special states sit between nearby core grades rather than bypassing
# the scale entirely. This prevents one-scan jumps from a locked/volatile
# state straight to an extreme directional call.
SPECIAL_STATE_NEIGHBORS = {
    "STAGNANT_JI": {"SLIGHT_FAV", "FAVORABLE"},
    "STAGNANT": {"SLIGHT_ADV", "NEUTRAL", "SLIGHT_FAV"},
    "STAGNANT_XIONG": {"ADVERSE", "SLIGHT_ADV"},
    "VOLATILE": {"SLIGHT_ADV", "NEUTRAL", "SLIGHT_FAV"},
}
MAX_STEP = 2  # Allow at most 2 grades of change per scan


def constrain_assessment(new_assessment, prev_assessment):
    """#88: Clamp assessment change to MAX_STEP grades.
    
    原文依据: "伯一变至于王矣，王一变至于帝矣，帝一变至于皇矣"
    从极端到极端需要经历中间状态，不可一步到位。
    
    Returns (clamped_assessment, was_clamped).
    """
    if new_assessment == prev_assessment:
        return new_assessment, False

    new_is_grade = new_assessment in GRADE_RANK
    prev_is_grade = prev_assessment in GRADE_RANK

    if new_is_grade and prev_is_grade:
        new_r = GRADE_RANK[new_assessment]
        prev_r = GRADE_RANK[prev_assessment]
        delta = new_r - prev_r

        if abs(delta) <= MAX_STEP:
            return new_assessment, False

        # Clamp: move at most MAX_STEP toward the new direction
        clamped_r = prev_r + (MAX_STEP if delta > 0 else -MAX_STEP)
        clamped_r = max(0, min(len(GRADE_ORDER) - 1, clamped_r))
        return GRADE_ORDER[clamped_r], True

    # Special→special transitions are not on the linear scale; keep them as-is.
    if not new_is_grade and not prev_is_grade:
        return new_assessment, False

    if prev_is_grade:
        allowed = SPECIAL_STATE_NEIGHBORS.get(new_assessment)
        reference_rank = GRADE_RANK[prev_assessment]
        tie_break_rank = reference_rank
        if allowed and prev_assessment in allowed:
            return new_assessment, False
    else:
        allowed = SPECIAL_STATE_NEIGHBORS.get(prev_assessment)
        reference_rank = GRADE_RANK[new_assessment]
        tie_break_rank = reference_rank
        if allowed and new_assessment in allowed:
            return new_assessment, False

    if allowed is None:
        return new_assessment, False

    # Clamp grade transitions involving a special state to its neighboring band.
    closest = min(
        allowed,
        key=lambda grade: (
            abs(GRADE_RANK[grade] - reference_rank),
            abs(GRADE_RANK[grade] - tie_break_rank),
        ),
    )
    return closest, True


# ============================================================
# #83: 未然之防 — early warnings at extremes
# 原文: "未有剥而不复，未有夬而不姤者，圣人贵未然之防"
# ============================================================
def get_weiran_warning(assessment):
    """Return a '未然之防' warning string if at extreme state, else empty."""
    if assessment == "FAVORABLE":
        return "⚡ Peak conditions. Watch for early reversal signals (C1/C2)."
    elif assessment == "ADVERSE":
        return "🌱 Trough conditions. Watch for recovery signals (C5/C6)."
    return ""


def get_channel_name(gate_idx):
    """Map gate index to business label without hiding missing data."""
    if gate_idx is None:
        return "Unknown"
    return CHANNEL_NAMES.get(gate_idx, "Unknown")


# ============================================================
# #82: Flip layer priority detection
# 原文: "易根于乾坤而生于复姤，刚交柔而为复，柔交刚而为姤"
# 复=初爻(C5/C6)先翻→自下而上的恢复
# 姤=上爻(C1/C2)先动→自上而下的衰退
# ============================================================
def detect_flip_pattern(prev_record, current_result):
    """Compare previous scan's per-stock assessments with current.
    
    Returns dict of {stock_code: flip_info} for stocks that changed.
    flip_info = {'type': 'improving'|'deteriorating'|None, 'detail': str}
    """
    if prev_record is None or 'stocks' not in prev_record:
        return {}
    
    flips = {}
    prev_stocks = prev_record.get('stocks', {})
    
    for sr in current_result['stocks']:
        code = sr['code']
        prev = prev_stocks.get(code)
        if prev is None:
            continue
        
        prev_a = prev.get('assessment', '')
        curr_a = sr['assessment']
        
        if prev_a == curr_a:
            continue
        
        # Determine direction of change
        prev_r = GRADE_RANK.get(prev_a)
        curr_r = GRADE_RANK.get(curr_a)
        
        if prev_r is None or curr_r is None:
            # Special state transition — log but don't classify
            flips[code] = {'type': None, 'detail': f'{prev_a}→{curr_a}'}
            continue
        
        direction = "improving" if curr_r > prev_r else "deteriorating"
        
        # For now we log the transition; full C1-C6 level tracking
        # requires per-stock C-level history which isn't stored yet.
        # This is a first step — future versions will track which
        # C-criterion flipped to determine fu(复) vs gou(姤) pattern.
        flips[code] = {
            'type': 'improving' if direction == "improving" else 'deteriorating',
            'detail': f'{prev_a}→{curr_a} ({direction})',
        }
    
    return flips


def run_qimen_scan():
    """Run qimen paipan for current time, assess each stock."""
    now = datetime.now()
    
    # Load previous scan for flip detection (#82) and clamping (#88)
    prev_record = None
    history = load_history()
    for r in reversed(history):
        if isinstance(r, dict) and "stocks" in r:
            prev_record = r
            break
    
    # Paipan
    ju = paipan(now)
    all_geju = evaluate_all_geju(ju)

    # 符使评估（全局，每局一次）
    fushi_r = assess_fushi(ju)
    fushi_signal = FUSHI_SIGNAL.get(fushi_r['relation_type'], 'NEUTRAL')

    # Per-stock assessment
    stock_results = []
    for sc in SCAN_STOCKS:
        cfg = STOCK_POSITIONING.get(sc)
        if cfg is None:
            continue

        assessment, score, details = assess_stock_tianshi_baojian(ju, sc, all_geju)

        # 符使修正
        assessment = apply_fushi_modifier(assessment, fushi_signal)

        # #88: Apply max single-step constraint
        clamped = False
        original_assessment = assessment
        if prev_record and 'stocks' in prev_record:
            prev_stock = prev_record['stocks'].get(sc)
            if prev_stock:
                assessment, clamped = constrain_assessment(
                    assessment, prev_stock.get('assessment', 'NEUTRAL')
                )
        
        # Get palace info
        palace_num, plate = find_stock_palace(ju, sc)
        
        # Get star/gate indices at the primary palace
        star_idx = ju.stars.get(palace_num) if palace_num else None
        # 中宫寄坤: P5 has no gate, use P2's gate
        if palace_num == 5:
            gate_idx = ju.gates.get(2)
        else:
            gate_idx = ju.gates.get(palace_num) if palace_num else None
        
        # Convert to business names
        zone = ZONE_NAMES.get(palace_num, '?') if palace_num else '?'
        asset = ASSET_NAMES.get(star_idx, '—') if star_idx is not None else '—'
        channel = get_channel_name(gate_idx)
        
        stock_results.append({
            'code': sc,
            'name': cfg['name'],
            'assessment': assessment,
            'score': score,
            'palace_num': palace_num,
            'zone': zone,
            'asset': asset,
            'channel': channel,
            'plate': 'Surface' if cfg['plate'] == 'heaven' else 'Foundation',
            'special': details.get('special', ''),
            'clamped': clamped,
            'original_assessment': original_assessment if clamped else None,
            'fushi_relation': fushi_r['relation_type'],
            'fushi_signal': fushi_signal,
        })
    
    # Cycle info (business language)
    yang_yin = 'Y' if ju.is_yangdun else 'X'
    
    result = {
        'timestamp': now.strftime('%Y-%m-%d %H:%M'),
        'cycle': f"{yang_yin}{ju.ju_number}",
        'fushi_relation': fushi_r['relation_type'],
        'fushi_signal': fushi_signal,
        'stocks': stock_results,
    }
    
    # #82: Detect flip patterns
    result['flips'] = detect_flip_pattern(prev_record, result)
    
    return result


def format_output(result):
    """Format scan results in B+C hybrid style."""
    lines = []
    
    lines.append(f"FCAS DAILY SCAN v2.1 | {result['timestamp']}")
    lines.append(f"Cycle: {result['cycle']}")
    if result.get('fushi_relation'):
        lines.append(f"符使: {result['fushi_relation']} [{result['fushi_signal']}]")
    lines.append("══════════════════════════════════════")
    
    flips = result.get('flips', {})
    
    for sr in result['stocks']:
        tag = ASSESSMENT_TAG.get(sr['assessment'], sr['assessment'])
        guidance = ASSESSMENT_GUIDANCE.get(sr['assessment'], '')
        p = sr['palace_num'] if sr['palace_num'] else '?'
        
        lines.append("")
        lines.append(f"━━━ {sr['name']} ({sr['code']}) ━━━")
        lines.append(f"[{tag}] {sr['score']:+.1f} | P{p}:{sr['zone']}-{sr['asset']}-{sr['channel']}")
        
        # #88: Show clamped annotation
        if sr.get('clamped'):
            orig_tag = ASSESSMENT_TAG.get(sr['original_assessment'], sr['original_assessment'])
            lines.append(f"⛔ Clamped from {orig_tag} (max 2-step rule)")
        
        if sr['special']:
            if sr['special'] == '伏吟':
                lines.append(f"Surface = Foundation → locked")
            elif sr['special'] == '反吟':
                lines.append(f"Surface ↔ Foundation → reversal")
        
        # #82: Show flip detection
        flip = flips.get(sr['code'])
        if flip:
            lines.append(f"↕ {flip['detail']}")
        
        lines.append(f"→ {guidance}")
        
        # #83: 未然之防 warning at extremes
        warning = get_weiran_warning(sr['assessment'])
        if warning:
            lines.append(warning)
    
    lines.append("")
    lines.append("══════════════════════════════════════")
    lines.append(DISCLAIMER)
    
    return "\n".join(lines)



def save_history(result):
    """Append scan result to history file, trimming to MAX_HISTORY_RECORDS."""
    history = load_history()

    # Compact record for history
    record = {
        'timestamp': result['timestamp'],
        'ju': result['cycle'],
        'stocks': {}
    }
    for sr in result['stocks']:
        rec = {
            'assessment': sr['assessment'],
            'score': sr['score'],
            'special': sr['special'],
            'zone': sr['zone'],
        }
        if sr.get('clamped'):
            rec['clamped_from'] = sr['original_assessment']
        record['stocks'][sr['code']] = rec

    # Save flip info if any
    if result.get('flips'):
        record['flips'] = {k: v['detail'] for k, v in result['flips'].items()}

    history.append(record)

    # Trim to avoid unbounded growth (keep most recent records)
    if len(history) > MAX_HISTORY_RECORDS:
        trimmed = len(history) - MAX_HISTORY_RECORDS
        history = history[-MAX_HISTORY_RECORDS:]
        print(f"[History] Trimmed {trimmed} old records")

    save_json_file(HISTORY_FILE, history)

    print(f"[History] Saved ({len(history)} total records)")


def main():
    print("=" * 50)
    print("FCAS Daily Scanner v2.1")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)
    
    # Run scan
    print("\n[1/3] Running qimen scan...")
    result = run_qimen_scan()
    
    # Format output
    print("[2/3] Formatting output...")
    output = format_output(result)
    print(output)
    
    # Save history
    save_history(result)
    
    # Push to Telegram
    print("\n[3/3] Pushing to Telegram...")
    send_telegram(output)
    
    print("\n[Done]")


if __name__ == "__main__":
    main()
