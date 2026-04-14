"""
Legacy FCAS compatibility layer.

This module restores the subset of the original `contrarian_analysis_mcp.py`
API that the historical backtest scripts still import:

- `CRITERIA`
- `detect_mislocation()`
- `run_analysis()`
- `_analyze_intent()`

It is intentionally standalone and does not expose MCP tools.
"""

from __future__ import annotations

from datetime import datetime

CRITERIA = {
    "c1": {
        "layer": "environment",
        "label_en": "Trend Alignment",
        "label_zh": "趋势方向",
        "question_en": "Is this domain aligned or misaligned with the era's macro trend?",
        "question_zh": "这个领域和时代趋势是顺还是逆？",
        "positive": "aligned",
        "negative": "misaligned",
    },
    "c2": {
        "layer": "environment",
        "label_en": "Energy State",
        "label_zh": "能量状态",
        "question_en": "Is this domain currently accumulating or dissipating energy?",
        "question_zh": "这个领域当下是在积蓄还是在消散？",
        "positive": "accumulating",
        "negative": "dissipating",
    },
    "c3": {
        "layer": "participant",
        "label_en": "Internal Harmony",
        "label_zh": "内部协调",
        "question_en": "Is the system internally coordinated and functioning smoothly?",
        "question_zh": "系统内部各要素之间是否协调运转？",
        "positive": "harmonized",
        "negative": "dissonant",
    },
    "c4": {
        "layer": "participant",
        "label_en": "Personal Sustainability",
        "label_zh": "个人持续力",
        "question_en": "Can you sustain through the dormancy period?",
        "question_zh": "你自己能不能撑过蛰伏周期？",
        "positive": "can sustain",
        "negative": "cannot sustain",
    },
    "c5": {
        "layer": "foundation",
        "label_en": "Ecosystem Support",
        "label_zh": "生态支撑",
        "question_en": "Is the surrounding ecosystem supporting or rejecting this?",
        "question_zh": "所处的生态系统是支撑还是排斥？",
        "positive": "supporting",
        "negative": "rejecting",
    },
    "c6": {
        "layer": "foundation",
        "label_en": "Foundation Depth",
        "label_zh": "根基深浅",
        "question_en": "Is the foundation deep or shallow?",
        "question_zh": "底层根基是深厚还是浅薄？",
        "positive": "deep",
        "negative": "shallow",
    },
}

LAYER_SYNTHESIS = {
    "environment": {
        "label": "Momentum / 势",
        "criteria": ["c1", "c2"],
        "interpretations": {
            (1, 1): "Strongest momentum. Trend aligned and energy accumulating.",
            (1, 0): "Momentum weakening. Trend aligned but energy dissipating.",
            (0, 1): "Counter-trend but energy accumulating. Potential emerging opportunity.",
            (0, 0): "Not worth entering. Counter-trend and dissipating.",
        },
    },
    "participant": {
        "label": "Feasibility / 可行性",
        "criteria": ["c3", "c4"],
        "interpretations": {
            (1, 1): "Strong execution. Internal harmony and personal sustainability both present.",
            (1, 0): "Harmonized but fragile. Internal coordination present but cannot sustain long-term.",
            (0, 1): "Can endure but internally dissonant. Structural friction despite personal capacity.",
            (0, 0): "Weak execution. Internal dissonance and cannot sustain.",
        },
    },
    "foundation": {
        "label": "Substance / 质",
        "criteria": ["c5", "c6"],
        "interpretations": {
            (1, 1): "Most stable. Ecosystem supports and foundation runs deep. Enduring advantage.",
            (1, 0): "Ecosystem supports but foundation is shallow. Vulnerable to disruption.",
            (0, 1): "Deep foundation but ecosystem is hostile. High risk, timing dependent.",
            (0, 0): "No ecosystem support and no foundation depth. Not viable.",
        },
    },
}

CROSS_LAYER = {
    ("strong", "solid"): "Best window. Competition may have started. Feasibility layer decisive.",
    ("strong", "hollow"): "Potential bubble. High heat but weak foundation. Extreme caution.",
    ("weak", "solid"): "Undervalued opportunity. Key question: when does momentum inflection arrive?",
    ("weak", "hollow"): "Not worth entering. No momentum, no substance, no foothold.",
}

_TRIGRAM_MAP = {
    (1, 1, 1): "qian",
    (0, 0, 0): "kun",
    (1, 0, 0): "zhen",
    (0, 1, 1): "xun",
    (0, 1, 0): "kan",
    (1, 0, 1): "li",
    (0, 0, 1): "gen",
    (1, 1, 0): "dui",
}

_TRIGRAM_PROPS = {
    "qian": {"element": "metal", "nature": "creative force"},
    "kun": {"element": "earth", "nature": "receptive capacity"},
    "zhen": {"element": "wood", "nature": "initiating movement"},
    "xun": {"element": "wood", "nature": "penetrating influence"},
    "kan": {"element": "water", "nature": "adaptive flow"},
    "li": {"element": "fire", "nature": "clarity and illumination"},
    "gen": {"element": "earth", "nature": "stillness and consolidation"},
    "dui": {"element": "metal", "nature": "exchange and communication"},
}

_ELEMENT_GENERATES = {
    "wood": "fire",
    "fire": "earth",
    "earth": "metal",
    "metal": "water",
    "water": "wood",
}
_ELEMENT_CONTROLS = {
    "wood": "earth",
    "fire": "metal",
    "earth": "water",
    "metal": "wood",
    "water": "fire",
}

_RELATION_LABELS = {
    "peer_competitor": "Peer Competitor / 同类竞争者",
    "derivative_output": "Derivative Output / 衍生产出",
    "upstream_support": "Upstream Support / 上游支撑",
    "accessible_resource": "Accessible Resource / 可获取资源",
    "external_pressure": "External Pressure / 外部压力",
    "unknown": "Unknown",
}

_VITAL_STAGES = {"launch", "volatility", "standards", "acceleration", "dominance"}
_DEPLETED_STAGES = {"deceleration", "structural_issues", "loss_of_momentum", "transformation"}
_NASCENT_STAGES = {"conception", "incubation", "nurturing"}

_LIUHE = {
    "yin": "hai",
    "hai": "yin",
    "mao": "xu",
    "xu": "mao",
    "chen": "you",
    "you": "chen",
    "si": "shen",
    "shen": "si",
    "wu": "wei",
    "wei": "wu",
    "zi": "chou",
    "chou": "zi",
}
_XING = {
    "zi": "mao",
    "mao": "zi",
    "chou": "xu",
    "xu": "wei",
    "wei": "chou",
    "yin": "si",
    "si": "shen",
    "shen": "yin",
    "chen": "chen",
    "wu": "wu",
    "you": "you",
    "hai": "hai",
}
_CHONG = {
    "zi": "wu",
    "wu": "zi",
    "chou": "wei",
    "wei": "chou",
    "yin": "shen",
    "shen": "yin",
    "mao": "you",
    "you": "mao",
    "chen": "xu",
    "xu": "chen",
    "si": "hai",
    "hai": "si",
}
_HAI_HARM = {
    "xu": "you",
    "you": "xu",
    "hai": "shen",
    "shen": "hai",
    "zi": "wei",
    "wei": "zi",
    "chou": "wu",
    "wu": "chou",
    "yin": "si",
    "si": "yin",
    "mao": "chen",
    "chen": "mao",
}

_JUDGMENT_LABELS = {
    "strongly_favorable": "Strongly Favorable / 强势有利",
    "favorable": "Favorable / 有利",
    "favorable_with_tension": "Favorable with Tension / 有利但有阻力",
    "latent_potential": "Latent Potential / 潜力待发",
    "weak_positive": "Weak Positive / 弱势有利",
    "unstable": "Unstable / 不稳定",
    "emerging": "Emerging / 正在成形",
    "restrained_but_safe": "Restrained but Safe / 受限但安全",
    "adverse": "Adverse / 不利",
    "strongly_adverse": "Strongly Adverse / 强势不利",
    "dormant": "Dormant / 休眠",
    "depleted_negative": "Depleted / 枯竭",
    "critically_adverse": "Critically Adverse / 极度不利",
    "suppressed": "Suppressed / 被压制",
    "stable": "Stable / 稳定",
    "stagnant": "Stagnant / 停滞",
    "transitional": "Transitional / 过渡中",
}

_BRANCH_ORDER = ["zi", "chou", "yin", "mao", "chen", "si", "wu", "wei", "shen", "you", "xu", "hai"]
_BRANCH_ELEMENT = {
    "zi": "water",
    "chou": "earth",
    "yin": "wood",
    "mao": "wood",
    "chen": "earth",
    "si": "fire",
    "wu": "fire",
    "wei": "earth",
    "shen": "metal",
    "you": "metal",
    "xu": "earth",
    "hai": "water",
}

_TRIGRAM_BRANCHES = {
    "qian": {"inner": ["zi", "yin", "chen"], "outer": ["wu", "shen", "xu"]},
    "kun": {"inner": ["wei", "si", "mao"], "outer": ["chou", "hai", "you"]},
    "zhen": {"inner": ["zi", "yin", "chen"], "outer": ["wu", "shen", "xu"]},
    "xun": {"inner": ["chou", "hai", "you"], "outer": ["wei", "si", "mao"]},
    "kan": {"inner": ["yin", "chen", "wu"], "outer": ["shen", "xu", "zi"]},
    "li": {"inner": ["mao", "chou", "hai"], "outer": ["you", "wei", "si"]},
    "gen": {"inner": ["chen", "wu", "shen"], "outer": ["xu", "zi", "yin"]},
    "dui": {"inner": ["si", "mao", "chou"], "outer": ["hai", "you", "wei"]},
}

_LIFECYCLE_START = {"wood": "hai", "fire": "yin", "metal": "si", "water": "shen", "earth": "yin"}
_LIFECYCLE_STAGES = [
    {"id": "conception", "label": "Conception / 概念酝酿", "energy": "dormant"},
    {"id": "incubation", "label": "Incubation / 早期孵化", "energy": "dormant"},
    {"id": "nurturing", "label": "Nurturing / 资源培育", "energy": "growing"},
    {"id": "launch", "label": "Launch / 正式启动", "energy": "growing"},
    {"id": "volatility", "label": "Initial Volatility / 初期波动", "energy": "unstable"},
    {"id": "standards", "label": "Establishing Standards / 建立规范", "energy": "stabilizing"},
    {"id": "acceleration", "label": "Rapid Growth / 快速成长", "energy": "strong"},
    {"id": "dominance", "label": "Market Dominance / 市场主导", "energy": "peak"},
    {"id": "deceleration", "label": "Growth Slowing / 增长放缓", "energy": "declining"},
    {"id": "structural_issues", "label": "Structural Issues / 结构性问题", "energy": "declining"},
    {"id": "loss_of_momentum", "label": "Loss of Momentum / 失去动力", "energy": "depleted"},
    {"id": "transformation", "label": "Transformation / 沉淀转化", "energy": "dormant"},
]

_CONFIG_NAMES = {
    ("qian", "qian"): {"name": "Full Momentum", "zh": "全势运行"},
    ("qian", "dui"): {"name": "Strategic Engagement", "zh": "战略介入"},
    ("qian", "li"): {"name": "Aligned Vision", "zh": "愿景一致"},
    ("qian", "zhen"): {"name": "Authentic Action", "zh": "真实行动"},
    ("qian", "xun"): {"name": "Encounter", "zh": "偶遇机会"},
    ("qian", "kan"): {"name": "Strategic Contention", "zh": "战略博弈"},
    ("qian", "gen"): {"name": "Strategic Retreat", "zh": "战略撤退"},
    ("qian", "kun"): {"name": "Structural Deadlock", "zh": "结构性僵局"},
    ("dui", "qian"): {"name": "Decisive Breakthrough", "zh": "果断突破"},
    ("dui", "dui"): {"name": "Open Exchange", "zh": "开放交流"},
    ("dui", "li"): {"name": "Systemic Reform", "zh": "系统性改革"},
    ("dui", "zhen"): {"name": "Adaptive Following", "zh": "顺势而为"},
    ("dui", "xun"): {"name": "Critical Mass", "zh": "临界规模"},
    ("dui", "kan"): {"name": "Resource Constraint", "zh": "资源受限"},
    ("dui", "gen"): {"name": "Mutual Benefit", "zh": "互利共赢"},
    ("dui", "kun"): {"name": "Convergence", "zh": "集聚整合"},
    ("li", "qian"): {"name": "Abundant Capacity", "zh": "产能充沛"},
    ("li", "dui"): {"name": "Divergent Views", "zh": "分歧对立"},
    ("li", "li"): {"name": "Clear Visibility", "zh": "高度透明"},
    ("li", "zhen"): {"name": "Active Integration", "zh": "主动整合"},
    ("li", "xun"): {"name": "Iterative Refinement", "zh": "迭代优化"},
    ("li", "kan"): {"name": "Incomplete Transition", "zh": "转型未竟"},
    ("li", "gen"): {"name": "Exploratory Phase", "zh": "探索阶段"},
    ("li", "kun"): {"name": "Emerging Visibility", "zh": "崭露头角"},
    ("zhen", "qian"): {"name": "Powerful Expansion", "zh": "强势扩张"},
    ("zhen", "dui"): {"name": "Premature Commitment", "zh": "过早承诺"},
    ("zhen", "li"): {"name": "Amplified Impact", "zh": "放大效应"},
    ("zhen", "zhen"): {"name": "Rapid Initiation", "zh": "快速启动"},
    ("zhen", "xun"): {"name": "Sustained Persistence", "zh": "持续坚持"},
    ("zhen", "kan"): {"name": "Problem Resolution", "zh": "问题化解"},
    ("zhen", "gen"): {"name": "Minor Correction", "zh": "小幅修正"},
    ("zhen", "kun"): {"name": "Prepared Positioning", "zh": "提前布局"},
    ("xun", "qian"): {"name": "Early Accumulation", "zh": "早期积累"},
    ("xun", "dui"): {"name": "Deep Trust", "zh": "深度信任"},
    ("xun", "li"): {"name": "Internal Alignment", "zh": "内部协同"},
    ("xun", "zhen"): {"name": "Value Enhancement", "zh": "价值提升"},
    ("xun", "xun"): {"name": "Gradual Penetration", "zh": "渐进渗透"},
    ("xun", "kan"): {"name": "Dispersion", "zh": "分散化解"},
    ("xun", "gen"): {"name": "Steady Progress", "zh": "稳步推进"},
    ("xun", "kun"): {"name": "Wide Observation", "zh": "广泛观察"},
    ("kan", "qian"): {"name": "Patient Waiting", "zh": "耐心等待"},
    ("kan", "dui"): {"name": "Disciplined Boundaries", "zh": "有序约束"},
    ("kan", "li"): {"name": "Completed Transition", "zh": "转型完成"},
    ("kan", "zhen"): {"name": "Difficult Beginning", "zh": "艰难起步"},
    ("kan", "xun"): {"name": "Deep Infrastructure", "zh": "深层基建"},
    ("kan", "kan"): {"name": "Repeated Challenge", "zh": "持续考验"},
    ("kan", "gen"): {"name": "Blocked Path", "zh": "路径受阻"},
    ("kan", "kun"): {"name": "Close Alliance", "zh": "紧密结盟"},
    ("gen", "qian"): {"name": "Major Reserves", "zh": "重大储备"},
    ("gen", "dui"): {"name": "Strategic Sacrifice", "zh": "战略取舍"},
    ("gen", "li"): {"name": "Surface Polish", "zh": "表面包装"},
    ("gen", "zhen"): {"name": "Foundational Nourishment", "zh": "基础滋养"},
    ("gen", "xun"): {"name": "Legacy Restructuring", "zh": "遗产重组"},
    ("gen", "kan"): {"name": "Early Education", "zh": "启蒙培育"},
    ("gen", "gen"): {"name": "Consolidation", "zh": "巩固沉淀"},
    ("gen", "kun"): {"name": "Stripping Away", "zh": "剥离清退"},
    ("kun", "qian"): {"name": "Fundamental Transformation", "zh": "根本性转变"},
    ("kun", "dui"): {"name": "Approaching Threshold", "zh": "临近阈值"},
    ("kun", "li"): {"name": "Hidden Potential", "zh": "隐藏潜力"},
    ("kun", "zhen"): {"name": "Return to Origin", "zh": "回归本源"},
    ("kun", "xun"): {"name": "Rising Trajectory", "zh": "上升轨道"},
    ("kun", "kan"): {"name": "Organized Mobilization", "zh": "有序动员"},
    ("kun", "gen"): {"name": "Humble Foundation", "zh": "低调筑基"},
    ("kun", "kun"): {"name": "Full Receptivity", "zh": "全面承接"},
}

_INTENT_MAP = {
    "seek_profit": {
        "target": "accessible_resource",
        "label": "Seek Profit / 求财",
        "helper": "derivative_output",
        "helper_logic": "Output generates resources",
        "threat": "peer_competitor",
        "threat_logic": "Competition drains resources",
    },
    "seek_position": {
        "target": "external_pressure",
        "label": "Seek Position / 求职求名",
        "helper": "accessible_resource",
        "helper_logic": "Resources attract authority",
        "threat": "derivative_output",
        "threat_logic": "Output disperses authority focus",
    },
    "seek_protection": {
        "target": "upstream_support",
        "label": "Seek Protection / 求庇护",
        "helper": "external_pressure",
        "helper_logic": "Authority reinforces support structures",
        "threat": "accessible_resource",
        "threat_logic": "Resource extraction weakens support",
    },
    "seek_output": {
        "target": "derivative_output",
        "label": "Seek Output / 求产出",
        "helper": "peer_competitor",
        "helper_logic": "Peer activity stimulates output",
        "threat": "upstream_support",
        "threat_logic": "Support structures constrain output",
    },
    "assess_competition": {
        "target": "peer_competitor",
        "label": "Assess Competition / 看竞争",
        "helper": "upstream_support",
        "helper_logic": "Support strengthens competitive position",
        "threat": "external_pressure",
        "threat_logic": "External pressure suppresses competitors",
    },
}


def _get_structural_relation(base_element: str, yao_element: str) -> str:
    if yao_element == base_element:
        return "peer_competitor"
    if yao_element == _ELEMENT_GENERATES[base_element]:
        return "derivative_output"
    if base_element == _ELEMENT_GENERATES[yao_element]:
        return "upstream_support"
    if yao_element == _ELEMENT_CONTROLS[base_element]:
        return "accessible_resource"
    if base_element == _ELEMENT_CONTROLS[yao_element]:
        return "external_pressure"
    return "unknown"


def _get_fu_yi(base_element: str, yao_element: str) -> str:
    if yao_element == base_element:
        return "peer"
    if yao_element == _ELEMENT_GENERATES[base_element]:
        return "support"
    if base_element == _ELEMENT_GENERATES[yao_element]:
        return "suppress"
    if yao_element == _ELEMENT_CONTROLS[base_element]:
        return "resource"
    if base_element == _ELEMENT_CONTROLS[yao_element]:
        return "pressure"
    return "peer"


def _get_qi_state(lifecycle_id: str) -> str:
    if lifecycle_id in _VITAL_STAGES:
        return "vital"
    if lifecycle_id in _DEPLETED_STAGES:
        return "depleted"
    if lifecycle_id in _NASCENT_STAGES:
        return "nascent"
    return "nascent"


def _check_branch_relations(branch: str, other_branches: list[str]) -> list[str]:
    relations = set()
    for other in other_branches:
        if _LIUHE.get(branch) == other:
            relations.add("harmony")
        if _XING.get(branch) == other:
            relations.add("consumption")
        if _CHONG.get(branch) == other:
            relations.add("opposition")
        if _HAI_HARM.get(branch) == other:
            relations.add("hidden_damage")
    if not relations:
        relations.add("neutral")
    return list(relations)


def _three_layer_judgment(fu_yi: str, qi_state: str, relations: list[str]) -> str:
    base = {
        "support": "positive",
        "suppress": "negative",
        "peer": "neutral",
        "resource": "positive",
        "pressure": "negative",
    }.get(fu_yi, "neutral")
    qi = {"vital": "strong", "depleted": "weak", "nascent": "moderate"}.get(qi_state, "moderate")
    has_harmony = "harmony" in relations
    has_conflict = any(rel in relations for rel in ("consumption", "opposition", "hidden_damage"))

    if base == "positive":
        if qi == "strong":
            if has_harmony:
                return "strongly_favorable"
            if has_conflict:
                return "favorable_with_tension"
            return "favorable"
        if qi == "weak":
            if has_harmony:
                return "latent_potential"
            if has_conflict:
                return "unstable"
            return "weak_positive"
        return "emerging"

    if base == "negative":
        if qi == "strong":
            if has_harmony:
                return "restrained_but_safe"
            if has_conflict:
                return "strongly_adverse"
            return "adverse"
        if qi == "weak":
            if has_harmony:
                return "dormant"
            if has_conflict:
                return "critically_adverse"
            return "depleted_negative"
        return "suppressed"

    if qi == "strong":
        return "stable"
    if qi == "weak":
        return "stagnant"
    return "transitional"


def _get_lifecycle_stage(element: str, branch: str) -> dict[str, str]:
    start = _BRANCH_ORDER.index(_LIFECYCLE_START[element])
    conception_idx = (start - 3) % 12
    current_idx = _BRANCH_ORDER.index(branch)
    return _LIFECYCLE_STAGES[(current_idx - conception_idx) % 12]


def _find_palace(binary_str: str) -> tuple[str, str, int]:
    palace_trigrams = [
        ("qian", (1, 1, 1)),
        ("zhen", (1, 0, 0)),
        ("kan", (0, 1, 0)),
        ("gen", (0, 0, 1)),
        ("kun", (0, 0, 0)),
        ("xun", (0, 1, 1)),
        ("li", (1, 0, 1)),
        ("dui", (1, 1, 0)),
    ]
    labels = {
        1: "First Evolution",
        2: "Second Evolution",
        3: "Third Evolution",
        4: "Fourth Evolution",
        5: "Fifth Evolution",
        6: "Origin Configuration",
        7: "Transitional",
        8: "Return to Core",
    }

    def make_bin(lower: list[int], upper: list[int]) -> str:
        return f"{upper[2]}{upper[1]}{upper[0]}{lower[2]}{lower[1]}{lower[0]}"

    def flip(bit: int) -> int:
        return 1 - bit

    for palace_name, trigram in palace_trigrams:
        base = list(trigram)
        if binary_str == make_bin(base, base):
            return palace_name, labels[6], 6

        lower_1 = base.copy()
        lower_1[0] = flip(lower_1[0])
        if binary_str == make_bin(lower_1, base):
            return palace_name, labels[1], 1

        lower_2 = lower_1.copy()
        lower_2[1] = flip(lower_2[1])
        if binary_str == make_bin(lower_2, base):
            return palace_name, labels[2], 2

        lower_3 = lower_2.copy()
        lower_3[2] = flip(lower_3[2])
        if binary_str == make_bin(lower_3, base):
            return palace_name, labels[3], 3

        upper_4 = base.copy()
        upper_4[0] = flip(upper_4[0])
        if binary_str == make_bin(lower_3, upper_4):
            return palace_name, labels[4], 4

        upper_5 = upper_4.copy()
        upper_5[1] = flip(upper_5[1])
        if binary_str == make_bin(lower_3, upper_5):
            return palace_name, labels[5], 5

        upper_t = upper_5.copy()
        upper_t[0] = base[0]
        if binary_str == make_bin(lower_3, upper_t):
            return palace_name, labels[7], 7
        if binary_str == make_bin(base, upper_t):
            return palace_name, labels[8], 8

    return "unknown", "Unknown", 0


def analyze_configuration(binary_str: str) -> dict[str, object]:
    bits = [int(bit) for bit in binary_str]
    lower_bits = (bits[5], bits[4], bits[3])
    upper_bits = (bits[2], bits[1], bits[0])
    lower_tri = _TRIGRAM_MAP[lower_bits]
    upper_tri = _TRIGRAM_MAP[upper_bits]
    config = _CONFIG_NAMES.get((upper_tri, lower_tri), {"name": "Unknown", "zh": "未知"})
    palace, evolution, evolution_num = _find_palace(binary_str)
    palace_element = _TRIGRAM_PROPS[palace]["element"]
    lower_branches = _TRIGRAM_BRANCHES[lower_tri]["inner"]
    upper_branches = _TRIGRAM_BRANCHES[upper_tri]["outer"]
    criteria_map = ["c5", "c6", "c3", "c4", "c1", "c2"]

    all_positions: list[dict[str, object]] = []
    for idx in range(6):
        criterion = criteria_map[idx]
        state = bits[5 - idx]
        branch = lower_branches[idx] if idx < 3 else upper_branches[idx - 3]
        branch_element = _BRANCH_ELEMENT[branch]
        relation = _get_structural_relation(palace_element, branch_element)
        lifecycle = _get_lifecycle_stage(palace_element, branch)
        all_positions.append(
            {
                "position": idx + 1,
                "criterion": criterion,
                "state": state,
                "state_label": "active" if state == 1 else "inactive",
                "branch": branch,
                "branch_element": branch_element,
                "structural_relation": relation,
                "relation_label": _RELATION_LABELS[relation],
                "lifecycle_stage": lifecycle["id"],
                "lifecycle_label": lifecycle["label"],
                "lifecycle_energy": lifecycle["energy"],
            }
        )

    active_branches = [p["branch"] for p in all_positions if p["state"] == 1]
    judgment_counts: dict[str, int] = {}
    for position in all_positions:
        direction = _get_fu_yi(palace_element, position["branch_element"])
        vitality = _get_qi_state(position["lifecycle_stage"])
        other_branches = [branch for branch in active_branches if branch != position["branch"]]
        branch_relations = _check_branch_relations(position["branch"], other_branches)
        judgment = _three_layer_judgment(direction, vitality, branch_relations)

        position["direction"] = direction
        position["vitality"] = vitality
        position["branch_relations"] = branch_relations
        position["judgment"] = judgment
        position["judgment_label"] = _JUDGMENT_LABELS.get(judgment, judgment)

        if position["state"] == 1:
            judgment_counts[judgment] = judgment_counts.get(judgment, 0) + 1

    overall_judgment = "depleted_negative"
    if judgment_counts:
        overall_judgment = max(judgment_counts.items(), key=lambda item: item[1])[0]

    return {
        "configuration_name": config["name"],
        "configuration_zh": config["zh"],
        "upper_nature": _TRIGRAM_PROPS[upper_tri]["nature"],
        "lower_nature": _TRIGRAM_PROPS[lower_tri]["nature"],
        "structural_family": _TRIGRAM_PROPS[palace]["nature"],
        "family_element": palace_element,
        "evolution_stage": evolution,
        "evolution_number": evolution_num,
        "positions": all_positions,
        "overall_judgment": overall_judgment,
        "overall_judgment_label": _JUDGMENT_LABELS.get(overall_judgment, overall_judgment),
        "judgment_distribution": judgment_counts,
    }


def synthesize_layer(layer_name: str, criterion_states: dict[str, int]) -> dict[str, object]:
    layer = LAYER_SYNTHESIS[layer_name]
    criteria = layer["criteria"]
    states = tuple(criterion_states[c] for c in criteria)
    return {
        "layer": layer_name,
        "label": layer["label"],
        "states": dict(zip(criteria, states)),
        "interpretation": layer["interpretations"].get(states, "Undetermined."),
    }


def generate_binary_code(states: dict[str, int]) -> str:
    return "".join(str(states.get(criterion, 0)) for criterion in ["c2", "c1", "c4", "c3", "c6", "c5"])


def detect_mislocation(criterion_states: dict[str, int], layer_syntheses: dict[str, dict[str, object]]) -> dict[str, str]:
    env_sum = sum(layer_syntheses["environment"]["states"].values())
    foundation_sum = sum(layer_syntheses["foundation"]["states"].values())

    if foundation_sum >= 1 and env_sum == 0:
        return {
            "type": "form_without_flow",
            "description": "Established infrastructure but no market attention. Classic undervalued opportunity.",
        }
    if env_sum >= 1 and foundation_sum == 0:
        return {
            "type": "flow_without_form",
            "description": "Growing attention but no crystallized solution. Bubble risk.",
        }
    if env_sum >= 1 and foundation_sum >= 1:
        return {
            "type": "no_mislocation_positive",
            "description": "Both form and flow present. Mainstream opportunity.",
        }
    return {
        "type": "no_mislocation_negative",
        "description": "Neither form nor flow. No substance, no momentum.",
    }


def run_analysis(domain: str, criterion_states: dict[str, int]) -> dict[str, object]:
    layers = {
        name: synthesize_layer(name, criterion_states)
        for name in ("environment", "participant", "foundation")
    }
    env_strength = sum(layers["environment"]["states"].values())
    foundation_strength = sum(layers["foundation"]["states"].values())
    momentum = "strong" if env_strength >= 1 else "weak"
    substance = "solid" if foundation_strength >= 1 else "hollow"
    cross_interpretation = CROSS_LAYER.get((momentum, substance), "Undetermined.")
    mislocation = detect_mislocation(criterion_states, layers)
    binary_code = generate_binary_code(criterion_states)
    configuration = analyze_configuration(binary_code)

    return {
        "domain": domain,
        "binary_code": binary_code,
        "timestamp": datetime.now().isoformat(),
        "configuration": configuration,
        "layers": {
            name: {"label": layer["label"], "interpretation": layer["interpretation"]}
            for name, layer in layers.items()
        },
        "cross_layer": {
            "momentum": momentum,
            "substance": substance,
            "interpretation": cross_interpretation,
        },
        "mislocation": mislocation,
    }


def _analyze_intent(config: dict[str, object], intent_key: str) -> dict[str, object]:
    intent = _INTENT_MAP[intent_key]
    positions = config["positions"]

    targets = [p for p in positions if p["structural_relation"] == intent["target"]]
    helpers = [p for p in positions if p["structural_relation"] == intent["helper"]]
    threats = [p for p in positions if p["structural_relation"] == intent["threat"]]

    active_targets = [p for p in targets if p["state"] == 1]
    active_helpers = [p for p in helpers if p["state"] == 1]
    active_threats = [p for p in threats if p["state"] == 1]

    target_present = bool(active_targets)
    helper_present = bool(active_helpers)
    threat_strong = any(p["vitality"] == "vital" for p in active_threats)
    target_vital = any(p["vitality"] in ("vital", "nascent") for p in active_targets)
    helper_vital = any(p["vitality"] in ("vital", "nascent") for p in active_helpers)

    if target_present and helper_present and not threat_strong:
        if target_vital and helper_vital:
            overall = "strongly_supported"
            guidance = "Conditions strongly support this intent. Target and helpers are both active and vital."
        elif target_vital or helper_vital:
            overall = "supported_with_resistance"
            guidance = "Conditions support this intent. One of target/helper is vital, providing a foundation to work from."
        else:
            overall = "supported_but_weak"
            guidance = "Target and helpers are both present but lack vitality. Opportunity exists but momentum is limited."
    elif target_present and helper_present and threat_strong:
        overall = "contested"
        guidance = "Target and helpers active, but strong threats are present. Proceed with caution and active risk management."
    elif target_present and not helper_present and not threat_strong:
        overall = "possible_but_unsupported"
        guidance = "Target exists but lacks helper support. Feasible but may require patience or external catalysts."
    elif target_present and not helper_present and threat_strong:
        overall = "challenged"
        guidance = "Target exists but faces strong threats without helper support. High risk."
    elif not target_present and helper_present:
        overall = "indirect_path"
        guidance = "Target not currently active, but helpers are present. Build through indirect approach — strengthen output to generate resources."
    elif not target_present and not helper_present and not threat_strong:
        overall = "dormant"
        guidance = "Neither target nor helpers are active, but no strong threats either. Conditions are dormant — wait for activation."
    elif not target_present and not helper_present and threat_strong:
        overall = "not_viable"
        guidance = "No target, no helpers, and active threats. Conditions do not support this intent."
    else:
        overall = "uncertain"
        guidance = "Mixed signals. Requires deeper analysis."

    return {
        "intent": intent["label"],
        "overall": overall,
        "guidance": guidance,
        "target": {
            "relation": intent["target"],
            "relation_label": _RELATION_LABELS[intent["target"]],
            "positions": [
                {
                    "criterion": p["criterion"],
                    "state": "active" if p["state"] == 1 else "inactive",
                    "judgment": p["judgment_label"],
                    "vitality": p["vitality"],
                    "direction": p["direction"],
                }
                for p in targets
            ],
        },
        "helper": {
            "relation": intent["helper"],
            "relation_label": _RELATION_LABELS[intent["helper"]],
            "logic": intent["helper_logic"],
            "positions": [
                {
                    "criterion": p["criterion"],
                    "state": "active" if p["state"] == 1 else "inactive",
                    "judgment": p["judgment_label"],
                    "vitality": p["vitality"],
                }
                for p in helpers
            ],
        },
        "threat": {
            "relation": intent["threat"],
            "relation_label": _RELATION_LABELS[intent["threat"]],
            "logic": intent["threat_logic"],
            "positions": [
                {
                    "criterion": p["criterion"],
                    "state": "active" if p["state"] == 1 else "inactive",
                    "judgment": p["judgment_label"],
                    "vitality": p["vitality"],
                }
                for p in threats
            ],
        },
    }


if __name__ == "__main__":
    sample = run_analysis(
        "compat_smoke",
        {"c1": 1, "c2": 1, "c3": 0, "c4": 1, "c5": 1, "c6": 0},
    )
    print(sample["binary_code"], sample["configuration"]["configuration_name"])
