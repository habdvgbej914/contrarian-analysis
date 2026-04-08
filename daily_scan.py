"""
FCAS Daily Scanner v4.0
气象分析系统 每日扫描器

Architecture:
- Qimen engine (fcas_engine_v2.py) does ALL structural judgment — no LLM involved
- stock_positioning.py provides per-stock palace lookup
- assess_fuhua_liuqin.py provides per-stock 六亲 assessment (13W signal)
- assess_renshi.py provides 人事层 C1-C6 judgment via Claude API (13W-level)
- fetch_tushare.py builds evidence packs from local data/json/ files
- Output in business language, zero metaphysical terms
- Telegram push with multi-message support (4096 char limit)

v4.0 changes (2026-04-08, 三层整合):
- 人事层 C1-C6 judgment integrated per stock (Sonnet API)
- CROSS_3LAYER 三层联合信号 (天时×人事×六亲)
- 回测验证: 含张力=+2.65%、三层全FAV=+0.52% (邵雍原则三层确认)
- PRIME★★★ / STRONG★★ annotations for highest-alpha combos

v3.0 changes (2026-04-07, 符化六亲整合):
- 六亲v2 per-stock assessment integrated (13W-level signal)
- Cross-signal: 天时×六亲 interaction label (邵雍"变之与应常反对")
- Liuqin labels added to output and history

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
from assess_fuhua_liuqin import assess_stock_liuqin
from fetch_tushare import build_evidence_pack
from assess_renshi import assess_stock_renshi
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

# 六亲标签 → 商业语言 (13W信号)
LIUQIN_TAG = {
    "STRONGLY_FAVORABLE": "FLOW++",    # 六亲结构极佳
    "FAVORABLE":          "FLOW+",     # 六亲结构良好
    "PARTIAL_GOOD":       "FLOW",      # 六亲结构偏正
    "NEUTRAL":            "STEADY",    # 六亲结构中性
    "PARTIAL_BAD":        "DRAIN",     # 六亲结构偏负
    "UNFAVORABLE":        "DRAIN+",    # 六亲结构不利
}

# 天时×六亲 交叉信号 (基于"变之与应常反对"原则)
# 回测验证: T_FAV×L_UNFAV=+3.93% > T_FAV×L_FAV=+2.38%
# 跨层张力产生价格运动，同向叠加无增益
CROSS_SIGNAL_MAP = {
    # (tianshi_direction, liuqin_direction) → cross_signal
    ('FAV', 'UNFAV'): 'TENSION+',    # 天时好×六亲差 = 最强信号(+3.93%)
    ('ADV', 'FAV'):   'TENSION',     # 天时差×六亲好 = 次强(+3.71%)
    ('FAV', 'FAV'):   'ALIGNED',     # 双吉 = 反而最弱(+2.38%)
    ('ADV', 'UNFAV'): 'ALIGNED-',    # 双凶
    ('NEU', 'FAV'):   'LEAN+',       # 中性×好
    ('NEU', 'UNFAV'): 'LEAN-',       # 中性×差
    ('FAV', 'NEU'):   'LEAN+',       # 好×中性
    ('ADV', 'NEU'):   'LEAN-',       # 差×中性
    ('NEU', 'NEU'):   'FLAT',        # 双中性
}

# 三层联合信号表: (T_dir, H_dir, L_dir) → (grade, r13w_pct, n)
# 基于 cross_validate_3layer_results.json
# N<30 的组合在 get_3layer_grade() 中降级为 SPARSE，不显示★注释
# T/H/L 方向: 'FAV' / 'ADV' / 'NEU'
# H方向对应: FAVORABLE/STRONGLY_FAVORABLE→FAV, MIXED→NEU, CAUTIOUS/ADVERSE→ADV
# L方向对应: STRONGLY_FAVORABLE/FAVORABLE→FAV, UNFAVORABLE/PARTIAL_BAD→ADV, 其余→NEU
_MIN_N = 30  # 低于此样本量的组合标记为SPARSE

CROSS_3LAYER = {
    # (grade, r13w_pct, n)
    # N<30 → SPARSE at runtime (high r13w not reliable)
    ('NEU', 'ADV', 'ADV'): ('PRIME★★★',  +15.84,   9),   # N=9  → SPARSE
    ('ADV', 'ADV', 'FAV'): ('PRIME★★★',   +7.39,   5),   # N=5  → SPARSE
    ('NEU', 'ADV', 'FAV'): ('PRIME★★★',   +5.82,  22),   # N=22 → SPARSE
    # STRONG★★ (N≥30, reliable)
    ('FAV', 'NEU', 'ADV'): ('STRONG★★',   +4.77,  43),
    ('FAV', 'FAV', 'ADV'): ('STRONG★★',   +4.50,  63),
    # GOOD★ (r13w 3-4%)
    ('FAV', 'NEU', 'FAV'): ('GOOD★',      +3.84, 180),
    ('NEU', 'FAV', 'FAV'): ('GOOD★',      +3.71, 850),
    ('FAV', 'FAV', 'NEU'): ('GOOD★',      +3.45,  80),
    ('ADV', 'NEU', 'FAV'): ('GOOD★',      +3.31, 264),
    ('FAV', 'NEU', 'NEU'): ('GOOD★',      +3.20,  34),
    ('ADV', 'FAV', 'FAV'): ('GOOD★',      +3.11, 417),
    # MODERATE (r13w 2-3%)
    ('ADV', 'FAV', 'NEU'): ('MODERATE',   +2.85, 110),
    ('NEU', 'FAV', 'NEU'): ('MODERATE',   +2.73, 239),
    ('NEU', 'NEU', 'ADV'): ('MODERATE',   +2.11, 207),
    ('NEU', 'NEU', 'FAV'): ('MODERATE',   +1.99, 552),
    # NEUTRAL (r13w 1-2%)
    ('NEU', 'NEU', 'NEU'): ('NEUTRAL',    +1.65, 169),
    ('ADV', 'NEU', 'ADV'): ('NEUTRAL',    +1.50,  75),
    ('NEU', 'FAV', 'ADV'): ('NEUTRAL',    +1.45, 265),
    # WEAK (r13w 0-1%)
    ('FAV', 'FAV', 'FAV'): ('WEAK',       +0.52, 237),
    ('ADV', 'FAV', 'ADV'): ('WEAK',       +0.49,  93),
    ('ADV', 'NEU', 'NEU'): ('WEAK',       +0.49,  76),
    # ADVERSE (r13w < 0%) — both N<30, SPARSE at runtime
    ('NEU', 'ADV', 'NEU'): ('ADVERSE',    -2.66,   7),   # N=7  → SPARSE
    ('FAV', 'ADV', 'FAV'): ('ADVERSE',    -6.95,   7),   # N=7  → SPARSE
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

# ============================================================
# 六亲辅助函数
# ============================================================

# 地支索引 → 中文
_DIZHI_DECODE = {
    0: '子', 1: '丑', 2: '寅', 3: '卯', 4: '辰', 5: '巳',
    6: '午', 7: '未', 8: '申', 9: '酉', 10: '戌', 11: '亥',
}

# 宫位对应地支（用于空亡计算）
_GONG_DIZHI = {
    1: ['子'], 2: ['丑', '未'], 3: ['卯'], 4: ['辰', '巳'],
    6: ['戌', '亥'], 7: ['酉'], 8: ['丑', '寅'], 9: ['午'],
}


def get_month_branch_str(ju):
    """从QimenJu获取月支中文字符串（六亲模块需要）"""
    if hasattr(ju, 'month_gz') and ju.month_gz:
        _, mz = ju.month_gz
        return _DIZHI_DECODE.get(mz, '辰')
    # fallback: 宫号近似
    _gong_to_zhi = {
        1: '子', 2: '丑', 3: '卯', 4: '辰',
        6: '戌', 7: '酉', 8: '丑', 9: '午',
    }
    if hasattr(ju, 'month_branch'):
        return _gong_to_zhi.get(ju.month_branch, '辰')
    return '辰'


def get_kongwang_palaces(ju):
    """从QimenJu获取空亡宫位集合（palace IDs）"""
    kw_palaces = set()
    if not ju.kongwang:
        return kw_palaces
    # 引擎的kongwang是地支索引 → 转中文 → 找对应宫位
    kw_zhis = set()
    for kw in ju.kongwang:
        zhi_str = _DIZHI_DECODE.get(kw)
        if zhi_str:
            kw_zhis.add(zhi_str)
    for palace_id, dizhi_list in _GONG_DIZHI.items():
        for dz in dizhi_list:
            if dz in kw_zhis:
                kw_palaces.add(palace_id)
                break
    return kw_palaces


def _tianshi_direction(assessment):
    """将天时标签归类为方向（用于交叉信号）"""
    if assessment in ('FAVORABLE', 'STRONG_FAVORABLE', 'PARTIAL_GOOD',
                      'PARTIAL_GOOD_PLUS', 'STAGNANT_JI',
                      'SLIGHT_FAV'):
        return 'FAV'
    elif assessment in ('UNFAVORABLE', 'PARTIAL_BAD', 'ADVERSE',
                        'SLIGHT_ADV', 'STAGNANT_XIONG', 'FAVORABLE_TRAPPED'):
        return 'ADV'
    else:  # NEUTRAL, STAGNANT, VOLATILE, etc.
        return 'NEU'


def _liuqin_direction(label):
    """将六亲标签归类为方向（用于交叉信号）"""
    if label in ('STRONGLY_FAVORABLE', 'FAVORABLE'):
        return 'FAV'
    elif label in ('UNFAVORABLE', 'PARTIAL_BAD'):
        return 'UNFAV'
    else:  # PARTIAL_GOOD, NEUTRAL
        return 'NEU'


def get_cross_signal(tianshi_assessment, liuqin_label):
    """
    计算天时×六亲交叉信号

    原文依据: 邵雍《皇极经世》"变之与应，常反对也"
    回测验证: T_FAV×L_UNFAV=+3.93% > T_FAV×L_FAV=+2.38%
    """
    t_dir = _tianshi_direction(tianshi_assessment)
    l_dir = _liuqin_direction(liuqin_label)
    return CROSS_SIGNAL_MAP.get((t_dir, l_dir), 'FLAT')


def _renshi_direction(h_direction: str) -> str:
    """将人事层h_direction ('H_FAV'/'H_NEU'/'H_ADV') 转为三层键方向"""
    if h_direction == 'H_FAV':
        return 'FAV'
    elif h_direction == 'H_ADV':
        return 'ADV'
    return 'NEU'


def _liuqin_dir3(liuqin_label: str) -> str:
    """将六亲标签转为三层键方向 (FAV/ADV/NEU)

    注意: 与_liuqin_direction()不同，这里使用ADV（与backtest一致）
    """
    if liuqin_label in ('STRONGLY_FAVORABLE', 'FAVORABLE'):
        return 'FAV'
    elif liuqin_label in ('UNFAVORABLE', 'PARTIAL_BAD'):
        return 'ADV'
    return 'NEU'


def get_3layer_grade(tianshi_assessment, h_direction, liuqin_label):
    """
    计算三层联合信号等级

    返回 (grade_str, r13w_pct, combo_key, n)
    - N<_MIN_N 的组合 grade 降级为 'SPARSE'
    - 未找到组合时返回 ('UNKNOWN', None, combo_key, None)
    """
    t_dir = _tianshi_direction(tianshi_assessment)
    h_dir = _renshi_direction(h_direction)
    l_dir = _liuqin_dir3(liuqin_label)
    combo = (t_dir, h_dir, l_dir)
    combo_str = f"T_{t_dir}×H_{h_dir}×L_{l_dir}"
    entry = CROSS_3LAYER.get(combo)
    if entry is None:
        return 'UNKNOWN', None, combo_str, None
    grade, r13w, n = entry
    if n < _MIN_N:
        grade = 'SPARSE'
    return grade, r13w, combo_str, n


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

    # 六亲评估准备（全局参数，per-stock调用）
    month_branch_str = get_month_branch_str(ju)
    kw_palaces = get_kongwang_palaces(ju)

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
        
        # 六亲评估（per-stock, 13W信号）
        liuqin_r = assess_stock_liuqin(ju, sc, month_branch_str, kw_palaces)
        liuqin_label = liuqin_r['label'] if liuqin_r else 'NEUTRAL'
        liuqin_score = liuqin_r['total_score'] if liuqin_r else 0.0

        # 天时×六亲 交叉信号
        cross_signal = get_cross_signal(assessment, liuqin_label)

        # 人事层评估（per-stock, C1-C6, 13W信号）
        h_label = 'MIXED'
        h_direction = 'H_NEU'
        h_ones = None
        ep = build_evidence_pack(sc, cfg['name'], now)
        if ep['error'] is None:
            renshi_r = assess_stock_renshi(sc, cfg['name'], ep['text'])
            h_label = renshi_r.get('h_label', 'MIXED')
            h_direction = renshi_r.get('h_direction', 'H_NEU')
            h_ones = renshi_r.get('ones')

        # 三层联合信号
        cross3_grade, cross3_r13w, cross3_combo, cross3_n = get_3layer_grade(
            assessment, h_direction, liuqin_label
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
            'liuqin_label': liuqin_label,
            'liuqin_score': liuqin_score,
            'cross_signal': cross_signal,
            'h_label': h_label,
            'h_direction': h_direction,
            'h_ones': h_ones,
            'cross3_grade': cross3_grade,
            'cross3_r13w': cross3_r13w,
            'cross3_combo': cross3_combo,
            'cross3_n': cross3_n,
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
    
    lines.append(f"FCAS DAILY SCAN v4.0 | {result['timestamp']}")
    lines.append(f"Cycle: {result['cycle']}")
    if result.get('fushi_relation'):
        lines.append(f"符使: {result['fushi_relation']} [{result['fushi_signal']}]")
    lines.append("══════════════════════════════════════")
    
    flips = result.get('flips', {})
    
    for sr in result['stocks']:
        tag = ASSESSMENT_TAG.get(sr['assessment'], sr['assessment'])
        guidance = ASSESSMENT_GUIDANCE.get(sr['assessment'], '')
        p = sr['palace_num'] if sr['palace_num'] else '?'
        
        # 六亲标签
        lq_tag = LIUQIN_TAG.get(sr.get('liuqin_label', 'NEUTRAL'), 'STEADY')
        lq_score = sr.get('liuqin_score', 0.0)
        cross = sr.get('cross_signal', 'FLAT')

        # 人事层
        h_label = sr.get('h_label', 'MIXED')
        h_ones = sr.get('h_ones')
        h_display = f"{h_label}" + (f" {h_ones}/6" if h_ones is not None else "")

        # 三层联合
        cross3_grade = sr.get('cross3_grade', 'UNKNOWN')
        cross3_r13w = sr.get('cross3_r13w')
        cross3_combo = sr.get('cross3_combo', '')
        cross3_n = sr.get('cross3_n')
        if cross3_grade == 'SPARSE':
            cross3_str = f"SPARSE ({cross3_r13w:+.1f}%, N={cross3_n})"
        elif cross3_r13w is not None:
            cross3_str = f"{cross3_grade} ({cross3_r13w:+.1f}%)"
        else:
            cross3_str = cross3_grade

        lines.append("")
        lines.append(f"━━━ {sr['name']} ({sr['code']}) ━━━")
        lines.append(f"[{tag}] {sr['score']:+.1f} | P{p}:{sr['zone']}-{sr['asset']}-{sr['channel']}")
        lines.append(f"[{lq_tag}] {lq_score:+.1f} | ×{cross}")
        lines.append(f"[人事] {h_display} | 3L:{cross3_str}")
        
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
        
        # Cross-signal guidance (TENSION = strongest alpha source)
        if cross == 'TENSION+':
            lines.append(f"⚡ Max tension (T×L opposing). Prime 13W window.")
        elif cross == 'TENSION':
            lines.append(f"⚡ Tension signal. Watch for 13W opportunity.")

        # 三层联合信号注释（SPARSE不触发★注释）
        if cross3_grade == 'PRIME★★★':
            lines.append(f"★★★ PRIME 3-layer combo. {cross3_combo}. Highest alpha.")
        elif cross3_grade == 'STRONG★★':
            lines.append(f"★★ STRONG 3-layer combo. {cross3_combo}.")
        
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
            'liuqin_label': sr.get('liuqin_label', 'NEUTRAL'),
            'liuqin_score': sr.get('liuqin_score', 0.0),
            'cross_signal': sr.get('cross_signal', 'FLAT'),
            'h_label': sr.get('h_label', 'MIXED'),
            'h_direction': sr.get('h_direction', 'H_NEU'),
            'cross3_grade': sr.get('cross3_grade', 'UNKNOWN'),
            'cross3_combo': sr.get('cross3_combo', ''),
            'cross3_n': sr.get('cross3_n'),
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
    print("FCAS Daily Scanner v4.0")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)
    
    # Run scan
    print("\n[1/4] Running qimen scan...")
    result = run_qimen_scan()
    
    # Format output
    print("[2/4] Formatting output...")
    output = format_output(result)
    print(output)

    # Save history
    print("[3/4] Saving history...")
    save_history(result)

    # Push to Telegram
    print("[4/4] Pushing to Telegram...")
    send_telegram(output)
    
    print("\n[Done]")


if __name__ == "__main__":
    main()
