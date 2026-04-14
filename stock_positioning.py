"""
stock_positioning.py — 10标的个性化天时定位配置

每个标的通过上市日期的四柱干支，在奇门局中定位到特定宫位。
日干定位看天盘（天盘属动=当下状态），月干定位看地盘（地盘属静=内在根基）。

原文依据：
- "推人年命，以局内年干为主" — 用本命干在局中定位
- "日为己身" — 日干是本体
- "年为父母，月为兄弟，日为己身，时为妻子" — 四柱四层
- "地盘属静，天盘属动。以动合静，则吉凶生焉"
- 甲遁六仪：甲子→戊, 甲戌→己, 甲申→庚, 甲午→辛, 甲辰→壬, 甲寅→癸

撞干解决：
- 日干相同 → 一个保留天盘，另一个改用月干
- 月干与其他标的有效干相同 → 改为在地盘上定位（同干天地盘落宫不同）
- (干, 盘) 组合保证10标的全部唯一
"""

from fcas_engine_v2 import (
    TIANGAN_NAMES, GONG_WUXING, STAR_WUXING, GATE_WUXING, GATE_JIXIONG,
    shengke, calc_wangshuai, tg_wuxing,
    REL_WOKE, REL_SHENGWO, REL_KEWO, REL_WOSHENG, REL_BIHE,
    WS_WANG, WS_XIANG, WS_QIU, WS_SI,
)

# Reverse lookup: Chinese stem name → internal index
_STEM_NAME_TO_IDX = {v: k for k, v in TIANGAN_NAMES.items()}

# ============================================================
# Scoring constants — named to make the logic auditable
# ============================================================
# Star score deltas (per 九星吉凶 table + wangshuai modifier)
_STAR_DAJI_HQ   = 3   # 大吉星 旺相
_STAR_DAJI_LQ   = 1   # 大吉星 休囚
_STAR_XIAOJI_HQ = 2   # 小吉星 旺相
_STAR_XIAOJI_LQ = 1   # 小吉星 休囚
_STAR_DAXIONG_HQ   = -3  # 大凶星 旺相（力强则凶重）
_STAR_DAXIONG_LQ   =  0  # 大凶星 休囚（力弱则不凶）
_STAR_XIAOXIONG_HQ = -2  # 小凶星 旺相
_STAR_XIAOXIONG_LQ =  0  # 小凶星 休囚

# Gate score deltas
_GATE_JI_HQ  = 3    # 吉门 旺相
_GATE_JI_LQ  = 1    # 吉门 休囚
_GATE_XIONG_HQ = -3  # 凶门 旺相
_GATE_XIONG_LQ =  0  # 凶门 休囚
_GATE_MENPO_ADJ = 2  # 门迫调整（宫克门 → 吉门减分 / 凶门加分）

# Heaven-ground stem interaction
_STEM_SHENGWO_BONUS = 1   # 地盘生天盘
_STEM_KEWO_PENALTY  = -1  # 地盘克天盘

# Palace-stem (本命干) relationship
_PAL_SHENGWO_BONUS  =  2  # 宫生干 = 得助
_PAL_KEWO_PENALTY   = -2  # 宫克干 = 受制
_PAL_WOSHENG_DRAIN  = -1  # 干生宫 = 泄气
_PAL_WOKE_DRAIN     = -1  # 干克宫 = 消耗

# Dual-plate weighting (primary plate = 60%, secondary = 40%)
_PRIMARY_WEIGHT   = 0.6
_SECONDARY_WEIGHT = 0.4

# Assessment thresholds
_FAVORABLE_THRESHOLD  =  5
_SLIGHT_FAV_THRESHOLD =  2
_SLIGHT_ADV_THRESHOLD = -2
_ADVERSE_THRESHOLD    = -5

# 伏吟 thresholds (stagnant state classification)
_FUYIN_JI_THRESHOLD   =  2
_FUYIN_XIONG_THRESHOLD = -2

# Star classification sets (index values from fcas_engine_v2)
_STAR_DAJI    = {3, 4, 5}
_STAR_XIAOJI  = {2, 7}
_STAR_DAXIONG = {0, 1}
_STAR_XIAOXIONG = {8, 6}

# Palace opposition map for 反吟 detection
_DUIGONG = {1: 9, 9: 1, 2: 8, 8: 2, 3: 7, 7: 3, 4: 6, 6: 4}

# Positioning config
# stem: 在局中查找的天干
# plate: "heaven"=天盘(动/表面/当下), "ground"=地盘(静/内在/根基)
# source: 定位来源说明

STOCK_POSITIONING = {
    "000651.SZ": {
        "name": "格力电器",
        "ipo_date": "1996-11-18",
        "stem": "己",
        "plate": "heaven",
        "source": "日干",
    },
    "000063.SZ": {
        "name": "中兴通讯",
        "ipo_date": "1997-11-18",
        "stem": "戊",
        "plate": "heaven",
        "source": "日干(甲子遁戊)",
    },
    "000858.SZ": {
        "name": "五粮液",
        "ipo_date": "1998-04-27",
        "stem": "壬",
        "plate": "heaven",
        "source": "日干(甲辰遁壬)",
    },
    "600276.SH": {
        "name": "恒瑞医药",
        "ipo_date": "2000-10-18",
        "stem": "乙",
        "plate": "ground",
        "source": "月干→地盘(日干己撞格力,月干乙撞紫金天盘→改地盘)",
    },
    "600036.SH": {
        "name": "招商银行",
        "ipo_date": "2002-04-09",
        "stem": "丁",
        "plate": "heaven",
        "source": "日干",
    },
    "600547.SH": {
        "name": "山东黄金",
        "ipo_date": "2003-08-28",
        "stem": "癸",
        "plate": "heaven",
        "source": "日干",
    },
    "601318.SH": {
        "name": "中国平安",
        "ipo_date": "2007-03-01",
        "stem": "辛",
        "plate": "heaven",
        "source": "日干(甲午遁辛)",
    },
    "601857.SH": {
        "name": "中国石油",
        "ipo_date": "2007-11-05",
        "stem": "庚",
        "plate": "heaven",
        "source": "月干(日干癸撞山东黄金)",
    },
    "601899.SH": {
        "name": "紫金矿业",
        "ipo_date": "2008-04-25",
        "stem": "乙",
        "plate": "heaven",
        "source": "日干",
    },
    "601012.SH": {
        "name": "隆基绿能",
        "ipo_date": "2012-04-11",
        "stem": "癸",
        "plate": "ground",
        "source": "月干→地盘(日干壬撞五粮液,月干癸撞山东黄金天盘→改地盘)",
    },
}


def find_stock_palace(ju, stock_code):
    """Find the palace for a stock in the given qimen ju.

    Returns (palace_number, plate_name) or (None, None).
    """
    cfg = STOCK_POSITIONING.get(stock_code)
    if cfg is None:
        return None, None

    stem_idx = _STEM_NAME_TO_IDX.get(cfg["stem"])
    if stem_idx is None:
        return None, None

    plate = ju.heaven if cfg["plate"] == "heaven" else ju.ground

    for p in range(1, 10):
        if plate.get(p) == stem_idx:
            return p, cfg["plate"]

    return None, None


def assess_stock_tianshi(ju, stock_code, all_geju):
    """Full per-stock tianshi assessment.

    1. Find stock's palace via day/month stem on heaven/ground plate
    2. Also find the SAME stem on the OTHER plate (for dual-layer assessment)
    3. Check fuyin (same palace) / fanyin (opposite palace)
    4. Score both palaces, combine with weights

    Per原文:
    - 天盘=动=表面/当下 (primary for heaven-plate stocks)
    - 地盘=静=内在/根基 (primary for ground-plate stocks)
    - 同宫=伏吟: "只宜收敛货财，养威畜锐，不利出兵"
    - 对宫=反吟: "主中途反覆，事出意外"
    """
    cfg = STOCK_POSITIONING.get(stock_code)
    if cfg is None:
        return "NEUTRAL", 0, {}

    stem_idx = _STEM_NAME_TO_IDX.get(cfg["stem"])

    # Find stem on both plates
    tp = None  # tianpan (heaven) palace
    gp = None  # dipan (ground) palace
    for p in range(1, 10):
        if ju.heaven.get(p) == stem_idx:
            tp = p
        if ju.ground.get(p) == stem_idx:
            gp = p

    def _score_palace(palace):
        if palace is None:
            return 0
        month_br = ju.month_branch
        star = ju.stars.get(palace)
        # 中宫寄坤: P5 has no gate, use P2's gate
        gate = ju.gates.get(palace) if palace != 5 else ju.gates.get(2)
        gong_wx = GONG_WUXING.get(palace)
        h_stem = ju.heaven.get(palace)
        g_stem = ju.ground.get(palace)
        score = 0

        # Star quality with wangshuai
        if star is not None:
            sw = STAR_WUXING.get(star)
            ws = calc_wangshuai(sw, month_br) if sw else None
            hq = ws in (WS_WANG, WS_XIANG) if ws is not None else False
            if star in _STAR_DAJI:
                score += _STAR_DAJI_HQ if hq else _STAR_DAJI_LQ
            elif star in _STAR_XIAOJI:
                score += _STAR_XIAOJI_HQ if hq else _STAR_XIAOJI_LQ
            elif star in _STAR_DAXIONG:
                score += _STAR_DAXIONG_HQ if hq else _STAR_DAXIONG_LQ
            elif star in _STAR_XIAOXIONG:
                score += _STAR_XIAOXIONG_HQ if hq else _STAR_XIAOXIONG_LQ

        # Gate quality with wangshuai + menpo (门迫)
        if gate is not None:
            gj = GATE_JIXIONG.get(gate, -1)
            gw = GATE_WUXING.get(gate)
            gws = calc_wangshuai(gw, month_br) if gw else None
            ghq = gws in (WS_WANG, WS_XIANG) if gws is not None else False
            if gj == 1:
                score += _GATE_JI_HQ if ghq else _GATE_JI_LQ
            elif gj == 0:
                score += _GATE_XIONG_HQ if ghq else _GATE_XIONG_LQ
            # 门迫: 宫克门 → 吉门受制 / 凶门反减
            if gong_wx and gw and shengke(gong_wx, gw) == REL_WOKE:
                if gj == 1:
                    score -= _GATE_MENPO_ADJ
                elif gj == 0:
                    score += _GATE_MENPO_ADJ

        # Local geju patterns
        local = [g for g in all_geju if g.palace == palace]
        score += sum(g.severity + 1 for g in local if g.jixiong == 1)
        score -= sum(g.severity + 1 for g in local if g.jixiong == 0)

        # Heaven-ground stem interaction
        if h_stem is not None and g_stem is not None:
            rel = shengke(tg_wuxing(g_stem), tg_wuxing(h_stem))
            if rel == REL_SHENGWO:
                score += _STEM_SHENGWO_BONUS
            elif rel == REL_KEWO:
                score += _STEM_KEWO_PENALTY

        # Palace-stem (本命干) relationship — "落宫旺相则吉，休囚则凶"
        stem_wx = tg_wuxing(stem_idx)
        if gong_wx is not None and stem_wx is not None:
            pal_rel = shengke(stem_wx, gong_wx)
            if pal_rel == REL_SHENGWO:    # 宫生干 = 得助
                score += _PAL_SHENGWO_BONUS
            elif pal_rel == REL_KEWO:     # 宫克干 = 受制
                score += _PAL_KEWO_PENALTY
            elif pal_rel == REL_WOSHENG:  # 干生宫 = 泄气
                score += _PAL_WOSHENG_DRAIN
            elif pal_rel == REL_WOKE:     # 干克宫 = 消耗
                score += _PAL_WOKE_DRAIN
            # 比和 = 0, no change

        return score

    # Check fuyin (同宫) / fanyin (对宫)
    if tp is not None and gp is not None:
        if tp == gp:
            # 伏吟
            palace_score = _score_palace(tp)
            if palace_score >= _FUYIN_JI_THRESHOLD:
                return "STAGNANT_JI", palace_score, {"tp": tp, "gp": gp, "special": "伏吟"}
            elif palace_score <= _FUYIN_XIONG_THRESHOLD:
                return "STAGNANT_XIONG", palace_score, {"tp": tp, "gp": gp, "special": "伏吟"}
            else:
                return "STAGNANT", palace_score, {"tp": tp, "gp": gp, "special": "伏吟"}

        if _DUIGONG.get(tp) == gp:
            # 反吟
            tp_score = _score_palace(tp)
            gp_score = _score_palace(gp)
            combined = tp_score * _PRIMARY_WEIGHT + gp_score * _SECONDARY_WEIGHT
            return "VOLATILE", round(combined, 1), {"tp": tp, "gp": gp, "special": "反吟"}

    # Normal: primary plate has higher weight
    tp_score = _score_palace(tp) if tp else 0
    gp_score = _score_palace(gp) if gp else 0

    if cfg["plate"] == "heaven":
        # 天盘定位的标的: 天盘权重高
        combined = tp_score * _PRIMARY_WEIGHT + gp_score * _SECONDARY_WEIGHT
    else:
        # 地盘定位的标的: 地盘权重高
        combined = gp_score * _PRIMARY_WEIGHT + tp_score * _SECONDARY_WEIGHT

    combined = round(combined, 1)

    if combined >= _FAVORABLE_THRESHOLD:
        assessment = "FAVORABLE"
    elif combined >= _SLIGHT_FAV_THRESHOLD:
        assessment = "SLIGHT_FAV"
    elif combined <= _ADVERSE_THRESHOLD:
        assessment = "ADVERSE"
    elif combined <= _SLIGHT_ADV_THRESHOLD:
        assessment = "SLIGHT_ADV"
    else:
        assessment = "NEUTRAL"

    return assessment, combined, {"tp": tp, "gp": gp, "special": None}
