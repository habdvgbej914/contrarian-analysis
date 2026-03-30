"""
Contrarian Opportunity Analysis System v0.2
MCP Server Implementation
逆向机会分析系统 MCP服务器

Core upgrade: Integrated structural analysis engine based on
64-configuration binary system with lifecycle positioning.
"""

import os
import json
from datetime import datetime
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "analysis_history.json")
DEEP_HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deep_analysis_history.json")

app = FastMCP("contrarian-analysis-server")

FIVE_PHASES = ["origin", "visibility", "growth", "constraint", "foundation"]

CRITERIA = {
    "c1": {
        "layer": "environment", "label_en": "Trend Alignment", "label_zh": "趋势方向",
        "question_en": "Is this domain aligned or misaligned with the era's macro trend?",
        "question_zh": "这个领域和时代趋势是顺还是逆？",
        "positive": "aligned", "negative": "misaligned",
        "phase_prompts": {
            "origin": "Is the fundamental problem becoming more urgent or less relevant?",
            "visibility": "Current level of public attention and capital interest.",
            "growth": "Are new application scenarios extending or contracting?",
            "constraint": "Policy, tech bottlenecks, standards: tightening or loosening?",
            "foundation": "Maturity of talent, supply chains, supporting industries."
        }
    },
    "c2": {
        "layer": "environment", "label_en": "Energy State", "label_zh": "能量状态",
        "question_en": "Is this domain currently accumulating or dissipating energy?",
        "question_zh": "这个领域当下是在积蓄还是在消散？",
        "positive": "accumulating", "negative": "dissipating",
        "phase_prompts": {
            "origin": "Is core technology or capability being deepened or lost?",
            "visibility": "Are people quietly building, or retreating?",
            "growth": "Are new entrants and research increasing or decreasing?",
            "constraint": "Is industry consensus forming, or becoming chaotic?",
            "foundation": "Are capital, talent, resources flowing in or out?"
        }
    },
    "c3": {
        "layer": "participant", "label_en": "Internal Harmony", "label_zh": "内部协调",
        "question_en": "Is the system internally coordinated and functioning smoothly?",
        "question_zh": "系统内部各要素之间是否协调运转？",
        "positive": "harmonized", "negative": "dissonant",
        "phase_prompts": {
            "origin": "Are the core components working together toward the same purpose?",
            "visibility": "Is internal coordination visible or are cracks showing?",
            "growth": "Is internal integration deepening or fragmenting?",
            "constraint": "Are internal frictions manageable or destabilizing?",
            "foundation": "Is the organizational/structural foundation coherent?"
        }
    },
    "c4": {
        "layer": "participant", "label_en": "Personal Sustainability", "label_zh": "个人持续力",
        "question_en": "Can you sustain through the dormancy period?",
        "question_zh": "你自己能不能撑过蛰伏周期？",
        "positive": "can sustain", "negative": "cannot sustain",
        "phase_prompts": {
            "origin": "Can your motivation sustain you through zero return?",
            "visibility": "How much attention and resources can you mobilize?",
            "growth": "Are your skills developing or stagnating?",
            "constraint": "What are your stop-loss lines?",
            "foundation": "How long can your finances and support sustain you?"
        }
    },
    "c5": {
        "layer": "foundation", "label_en": "Ecosystem Support", "label_zh": "生态支撑",
        "question_en": "Is the surrounding ecosystem supporting or rejecting this?",
        "question_zh": "所处的生态系统是支撑还是排斥？",
        "positive": "supporting", "negative": "rejecting",
        "phase_prompts": {
            "origin": "Does this exist because the ecosystem naturally needs it, or is it artificially imposed?",
            "visibility": "Is the ecosystem visibly nurturing this, or is it indifferent/hostile?",
            "growth": "Are surrounding industries, communities, and systems growing alongside this?",
            "constraint": "Are ecosystem forces (regulation, society, nature) protecting or threatening this?",
            "foundation": "Are the resources this depends on (people, materials, environment) naturally available?"
        }
    },
    "c6": {
        "layer": "foundation", "label_en": "Foundation Depth", "label_zh": "根基深浅",
        "question_en": "Is the foundation deep or shallow?",
        "question_zh": "底层根基是深厚还是浅薄？",
        "positive": "deep", "negative": "shallow",
        "phase_prompts": {
            "origin": "How much structural capacity exists to support long-term development?",
            "visibility": "How long has this foundation been accumulating — years, decades, or just months?",
            "growth": "Are the roots spreading deeper and wider, or staying at the surface?",
            "constraint": "What natural barriers exist that protect this foundation from being easily replicated?",
            "foundation": "How deeply embedded is this in existing systems, knowledge, and infrastructure?"
        }
    }
}

LAYER_SYNTHESIS = {
    "environment": {
        "label": "Momentum / 势", "criteria": ["c1", "c2"],
        "interpretations": {
            (1, 1): "Strongest momentum. Trend aligned and energy accumulating.",
            (1, 0): "Momentum weakening. Trend aligned but energy dissipating.",
            (0, 1): "Counter-trend but energy accumulating. Potential contrarian opportunity.",
            (0, 0): "Not worth entering. Counter-trend and dissipating."
        }
    },
    "participant": {
        "label": "Feasibility / 可行性", "criteria": ["c3", "c4"],
        "interpretations": {
            (1, 1): "Strong execution. Internal harmony and personal sustainability both present.",
            (1, 0): "Harmonized but fragile. Internal coordination present but cannot sustain long-term.",
            (0, 1): "Can endure but internally dissonant. Structural friction despite personal capacity.",
            (0, 0): "Weak execution. Internal dissonance and cannot sustain."
        }
    },
    "foundation": {
        "label": "Substance / 质", "criteria": ["c5", "c6"],
        "interpretations": {
            (1, 1): "Most stable. Ecosystem supports and foundation runs deep. Enduring advantage.",
            (1, 0): "Ecosystem supports but foundation is shallow. Vulnerable to disruption.",
            (0, 1): "Deep foundation but ecosystem is hostile. High risk, timing dependent.",
            (0, 0): "No ecosystem support and no foundation depth. Not viable."
        }
    }
}

CROSS_LAYER = {
    ("strong", "solid"): "Best window. Competition may have started. Feasibility layer decisive.",
    ("strong", "hollow"): "Potential bubble. High heat but weak foundation. Extreme caution.",
    ("weak", "solid"): "Undervalued opportunity. Key question: when does momentum inflection arrive?",
    ("weak", "hollow"): "Not worth entering. No momentum, no substance, no foothold."
}

# ============================================================
# Structural Configuration Engine / 结构配置引擎
# ============================================================

_TRIGRAM_MAP = {
    (1,1,1): "qian", (0,0,0): "kun", (1,0,0): "zhen", (0,1,1): "xun",
    (0,1,0): "kan",  (1,0,1): "li",  (0,0,1): "gen",  (1,1,0): "dui",
}

_TRIGRAM_PROPS = {
    "qian": {"element": "metal",  "nature": "creative force"},
    "kun":  {"element": "earth",  "nature": "receptive capacity"},
    "zhen": {"element": "wood",   "nature": "initiating movement"},
    "xun":  {"element": "wood",   "nature": "penetrating influence"},
    "kan":  {"element": "water",  "nature": "adaptive flow"},
    "li":   {"element": "fire",   "nature": "clarity and illumination"},
    "gen":  {"element": "earth",  "nature": "stillness and consolidation"},
    "dui":  {"element": "metal",  "nature": "exchange and communication"},
}

_ELEMENT_GENERATES = {"wood": "fire", "fire": "earth", "earth": "metal", "metal": "water", "water": "wood"}
_ELEMENT_CONTROLS = {"wood": "earth", "fire": "metal", "earth": "water", "metal": "wood", "water": "fire"}

def _get_structural_relation(base_element, yao_element):
    if yao_element == base_element: return "peer_competitor"
    if yao_element == _ELEMENT_GENERATES[base_element]: return "derivative_output"
    if base_element == _ELEMENT_GENERATES[yao_element]: return "upstream_support"
    if yao_element == _ELEMENT_CONTROLS[base_element]: return "accessible_resource"
    if base_element == _ELEMENT_CONTROLS[yao_element]: return "external_pressure"
    return "unknown"

_RELATION_LABELS = {
    "peer_competitor": "Peer Competitor / 同类竞争者",
    "derivative_output": "Derivative Output / 衍生产出",
    "upstream_support": "Upstream Support / 上游支撑",
    "accessible_resource": "Accessible Resource / 可获取资源",
    "external_pressure": "External Pressure / 外部压力",
    "unknown": "Unknown"
}

# ============================================================
# Three-Layer Judgment Engine / 三层判断引擎
# Based on Xiao Ji's method from "论扶抑" in 五行大义:
# Layer 1: 扶抑 (Support vs Suppress direction)
# Layer 2: 有气无气 (Vital vs Depleted lifecycle)
# Layer 3: 合德 vs 刑克 (Harmony vs Conflict modifier)
# ============================================================

# Layer 1: 扶抑 direction
# 母得子为扶 (my child supports me), 子遇母为抑 (my parent suppresses me)
def _get_fu_yi(base_element, yao_element):
    """Determine support/suppress direction between palace element and yao element"""
    if yao_element == base_element:
        return "peer"       # 比和 - same element
    if yao_element == _ELEMENT_GENERATES[base_element]:
        return "support"    # 扶 - child supports parent
    if base_element == _ELEMENT_GENERATES[yao_element]:
        return "suppress"   # 抑 - parent suppresses child
    if yao_element == _ELEMENT_CONTROLS[base_element]:
        return "resource"   # 我克 - I control it (妻财)
    if base_element == _ELEMENT_CONTROLS[yao_element]:
        return "pressure"   # 克我 - it controls me (官鬼)
    return "peer"

# Layer 2: 有气无气 (from lifecycle stage)
_VITAL_STAGES = {"launch", "volatility", "standards", "acceleration", "dominance"}
_DEPLETED_STAGES = {"deceleration", "structural_issues", "loss_of_momentum", "transformation"}
_NASCENT_STAGES = {"conception", "incubation", "nurturing"}

def _get_qi_state(lifecycle_id):
    """Determine vitality from lifecycle stage"""
    if lifecycle_id in _VITAL_STAGES: return "vital"
    if lifecycle_id in _DEPLETED_STAGES: return "depleted"
    if lifecycle_id in _NASCENT_STAGES: return "nascent"
    return "nascent"

# Layer 3: 合德 vs 刑克 (branch relationships)
_LIUHE = {"yin":"hai","hai":"yin","mao":"xu","xu":"mao","chen":"you","you":"chen",
          "si":"shen","shen":"si","wu":"wei","wei":"wu","zi":"chou","chou":"zi"}
_XING = {"zi":"mao","mao":"zi","chou":"xu","xu":"wei","wei":"chou",
         "yin":"si","si":"shen","shen":"yin","chen":"chen","wu":"wu","you":"you","hai":"hai"}
_CHONG = {"zi":"wu","wu":"zi","chou":"wei","wei":"chou","yin":"shen","shen":"yin",
          "mao":"you","you":"mao","chen":"xu","xu":"chen","si":"hai","hai":"si"}
_HAI_HARM = {"xu":"you","you":"xu","hai":"shen","shen":"hai","zi":"wei","wei":"zi",
             "chou":"wu","wu":"chou","yin":"si","si":"yin","mao":"chen","chen":"mao"}

def _check_branch_relations(branch, other_branches):
    """Check harmony/conflict relations between a branch and other active branches"""
    relations = set()
    for ob in other_branches:
        if _LIUHE.get(branch) == ob: relations.add("harmony")
        if _XING.get(branch) == ob: relations.add("consumption")
        if _CHONG.get(branch) == ob: relations.add("opposition")
        if _HAI_HARM.get(branch) == ob: relations.add("hidden_damage")
    if not relations: relations.add("neutral")
    return list(relations)

# Three-layer integration
def _three_layer_judgment(fu_yi, qi_state, relations):
    """
    Combine three layers per Xiao Ji's method:
    "扶者吉，抑者凶。生王之时则为有气，死没之时则是无气。
     若遇合德，虽抑非害。若逢刑克，为凶更重之。"
    """
    base = {"support":"positive","suppress":"negative","peer":"neutral",
            "resource":"positive","pressure":"negative"}.get(fu_yi, "neutral")
    qi = {"vital":"strong","depleted":"weak","nascent":"moderate"}.get(qi_state, "moderate")
    has_harmony = "harmony" in relations
    has_conflict = any(r in relations for r in ["consumption","opposition","hidden_damage"])

    if base == "positive":
        if qi == "strong":
            if has_harmony: return "strongly_favorable"
            if has_conflict: return "favorable_with_tension"
            return "favorable"
        elif qi == "weak":
            if has_harmony: return "latent_potential"
            if has_conflict: return "unstable"
            return "weak_positive"
        else:
            return "emerging"
    elif base == "negative":
        if qi == "strong":
            if has_harmony: return "restrained_but_safe"
            if has_conflict: return "strongly_adverse"
            return "adverse"
        elif qi == "weak":
            if has_harmony: return "dormant"
            if has_conflict: return "critically_adverse"
            return "depleted_negative"
        else:
            return "suppressed"
    else:
        if qi == "strong": return "stable"
        elif qi == "weak": return "stagnant"
        else: return "transitional"

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

_BRANCH_ORDER = ["zi","chou","yin","mao","chen","si","wu","wei","shen","you","xu","hai"]
_BRANCH_ELEMENT = {
    "zi": "water", "chou": "earth", "yin": "wood", "mao": "wood",
    "chen": "earth", "si": "fire", "wu": "fire", "wei": "earth",
    "shen": "metal", "you": "metal", "xu": "earth", "hai": "water",
}

_TRIGRAM_BRANCHES = {
    "qian": {"inner": ["zi","yin","chen"],   "outer": ["wu","shen","xu"]},
    "kun":  {"inner": ["wei","si","mao"],     "outer": ["chou","hai","you"]},
    "zhen": {"inner": ["zi","yin","chen"],    "outer": ["wu","shen","xu"]},
    "xun":  {"inner": ["chou","hai","you"],   "outer": ["wei","si","mao"]},
    "kan":  {"inner": ["yin","chen","wu"],     "outer": ["shen","xu","zi"]},
    "li":   {"inner": ["mao","chou","hai"],   "outer": ["you","wei","si"]},
    "gen":  {"inner": ["chen","wu","shen"],    "outer": ["xu","zi","yin"]},
    "dui":  {"inner": ["si","mao","chou"],    "outer": ["hai","you","wei"]},
}

_LIFECYCLE_START = {"wood": "hai", "fire": "yin", "metal": "si", "water": "shen", "earth": "yin"}

_LIFECYCLE_STAGES = [
    {"id": "conception",        "label": "Conception / 概念酝酿",         "energy": "dormant"},
    {"id": "incubation",        "label": "Incubation / 早期孵化",         "energy": "dormant"},
    {"id": "nurturing",         "label": "Nurturing / 资源培育",          "energy": "growing"},
    {"id": "launch",            "label": "Launch / 正式启动",             "energy": "growing"},
    {"id": "volatility",        "label": "Initial Volatility / 初期波动", "energy": "unstable"},
    {"id": "standards",         "label": "Establishing Standards / 建立规范", "energy": "stabilizing"},
    {"id": "acceleration",      "label": "Rapid Growth / 快速成长",       "energy": "strong"},
    {"id": "dominance",         "label": "Market Dominance / 市场主导",   "energy": "peak"},
    {"id": "deceleration",      "label": "Growth Slowing / 增长放缓",     "energy": "declining"},
    {"id": "structural_issues", "label": "Structural Issues / 结构性问题", "energy": "declining"},
    {"id": "loss_of_momentum",  "label": "Loss of Momentum / 失去动力",   "energy": "depleted"},
    {"id": "transformation",    "label": "Transformation / 沉淀转化",     "energy": "dormant"},
]

def _get_lifecycle_stage(element, branch):
    start = _BRANCH_ORDER.index(_LIFECYCLE_START[element])
    conception_idx = (start - 3) % 12
    current = _BRANCH_ORDER.index(branch)
    return _LIFECYCLE_STAGES[(current - conception_idx) % 12]

_CONFIG_NAMES = {
    ("qian","qian"): {"name": "Full Momentum", "zh": "全势运行"},
    ("qian","dui"):  {"name": "Strategic Engagement", "zh": "战略介入"},
    ("qian","li"):   {"name": "Aligned Vision", "zh": "愿景一致"},
    ("qian","zhen"): {"name": "Authentic Action", "zh": "真实行动"},
    ("qian","xun"):  {"name": "Encounter", "zh": "偶遇机会"},
    ("qian","kan"):  {"name": "Strategic Contention", "zh": "战略博弈"},
    ("qian","gen"):  {"name": "Strategic Retreat", "zh": "战略撤退"},
    ("qian","kun"):  {"name": "Structural Deadlock", "zh": "结构性僵局"},
    ("dui","qian"):  {"name": "Decisive Breakthrough", "zh": "果断突破"},
    ("dui","dui"):   {"name": "Open Exchange", "zh": "开放交流"},
    ("dui","li"):    {"name": "Systemic Reform", "zh": "系统性改革"},
    ("dui","zhen"):  {"name": "Adaptive Following", "zh": "顺势而为"},
    ("dui","xun"):   {"name": "Critical Mass", "zh": "临界规模"},
    ("dui","kan"):   {"name": "Resource Constraint", "zh": "资源受限"},
    ("dui","gen"):   {"name": "Mutual Benefit", "zh": "互利共赢"},
    ("dui","kun"):   {"name": "Convergence", "zh": "集聚整合"},
    ("li","qian"):   {"name": "Abundant Capacity", "zh": "产能充沛"},
    ("li","dui"):    {"name": "Divergent Views", "zh": "分歧对立"},
    ("li","li"):     {"name": "Clear Visibility", "zh": "高度透明"},
    ("li","zhen"):   {"name": "Active Integration", "zh": "主动整合"},
    ("li","xun"):    {"name": "Iterative Refinement", "zh": "迭代优化"},
    ("li","kan"):    {"name": "Incomplete Transition", "zh": "转型未竟"},
    ("li","gen"):    {"name": "Exploratory Phase", "zh": "探索阶段"},
    ("li","kun"):    {"name": "Emerging Visibility", "zh": "崭露头角"},
    ("zhen","qian"): {"name": "Powerful Expansion", "zh": "强势扩张"},
    ("zhen","dui"):  {"name": "Premature Commitment", "zh": "过早承诺"},
    ("zhen","li"):   {"name": "Amplified Impact", "zh": "放大效应"},
    ("zhen","zhen"): {"name": "Rapid Initiation", "zh": "快速启动"},
    ("zhen","xun"):  {"name": "Sustained Persistence", "zh": "持续坚持"},
    ("zhen","kan"):  {"name": "Problem Resolution", "zh": "问题化解"},
    ("zhen","gen"):  {"name": "Minor Correction", "zh": "小幅修正"},
    ("zhen","kun"):  {"name": "Prepared Positioning", "zh": "提前布局"},
    ("xun","qian"):  {"name": "Early Accumulation", "zh": "早期积累"},
    ("xun","dui"):   {"name": "Deep Trust", "zh": "深度信任"},
    ("xun","li"):    {"name": "Internal Alignment", "zh": "内部协同"},
    ("xun","zhen"):  {"name": "Value Enhancement", "zh": "价值提升"},
    ("xun","xun"):   {"name": "Gradual Penetration", "zh": "渐进渗透"},
    ("xun","kan"):   {"name": "Dispersion", "zh": "分散化解"},
    ("xun","gen"):   {"name": "Steady Progress", "zh": "稳步推进"},
    ("xun","kun"):   {"name": "Wide Observation", "zh": "广泛观察"},
    ("kan","qian"):  {"name": "Patient Waiting", "zh": "耐心等待"},
    ("kan","dui"):   {"name": "Disciplined Boundaries", "zh": "有序约束"},
    ("kan","li"):    {"name": "Completed Transition", "zh": "转型完成"},
    ("kan","zhen"):  {"name": "Difficult Beginning", "zh": "艰难起步"},
    ("kan","xun"):   {"name": "Deep Infrastructure", "zh": "深层基建"},
    ("kan","kan"):   {"name": "Repeated Challenge", "zh": "持续考验"},
    ("kan","gen"):   {"name": "Blocked Path", "zh": "路径受阻"},
    ("kan","kun"):   {"name": "Close Alliance", "zh": "紧密结盟"},
    ("gen","qian"):  {"name": "Major Reserves", "zh": "重大储备"},
    ("gen","dui"):   {"name": "Strategic Sacrifice", "zh": "战略取舍"},
    ("gen","li"):    {"name": "Surface Polish", "zh": "表面包装"},
    ("gen","zhen"):  {"name": "Foundational Nourishment", "zh": "基础滋养"},
    ("gen","xun"):   {"name": "Legacy Restructuring", "zh": "遗产重组"},
    ("gen","kan"):   {"name": "Early Education", "zh": "启蒙培育"},
    ("gen","gen"):   {"name": "Consolidation", "zh": "巩固沉淀"},
    ("gen","kun"):   {"name": "Stripping Away", "zh": "剥离清退"},
    ("kun","qian"):  {"name": "Fundamental Transformation", "zh": "根本性转变"},
    ("kun","dui"):   {"name": "Approaching Threshold", "zh": "临近阈值"},
    ("kun","li"):    {"name": "Hidden Potential", "zh": "隐藏潜力"},
    ("kun","zhen"):  {"name": "Return to Origin", "zh": "回归本源"},
    ("kun","xun"):   {"name": "Rising Trajectory", "zh": "上升轨道"},
    ("kun","kan"):   {"name": "Organized Mobilization", "zh": "有序动员"},
    ("kun","gen"):   {"name": "Humble Foundation", "zh": "低调筑基"},
    ("kun","kun"):   {"name": "Full Receptivity", "zh": "全面承接"},
}

def _find_palace(binary_str):
    bits = [int(b) for b in binary_str]
    palace_trigrams = [
        ("qian", (1,1,1)), ("zhen", (1,0,0)), ("kan", (0,1,0)), ("gen", (0,0,1)),
        ("kun", (0,0,0)), ("xun", (0,1,1)), ("li", (1,0,1)), ("dui", (1,1,0))
    ]
    def make_bin(lo, up):
        return f"{up[2]}{up[1]}{up[0]}{lo[2]}{lo[1]}{lo[0]}"
    def flip(b): return 1 - b
    labels = {1:"First Evolution",2:"Second Evolution",3:"Third Evolution",
              4:"Fourth Evolution",5:"Fifth Evolution",6:"Origin Configuration",
              7:"Transitional",8:"Return to Core"}
    for pn, p in palace_trigrams:
        b = list(p)
        if binary_str == make_bin(b, b): return pn, labels[6], 6
        l1=b.copy(); l1[0]=flip(l1[0])
        if binary_str == make_bin(l1, b): return pn, labels[1], 1
        l2=l1.copy(); l2[1]=flip(l2[1])
        if binary_str == make_bin(l2, b): return pn, labels[2], 2
        l3=l2.copy(); l3[2]=flip(l3[2])
        if binary_str == make_bin(l3, b): return pn, labels[3], 3
        u4=b.copy(); u4[0]=flip(u4[0])
        if binary_str == make_bin(l3, u4): return pn, labels[4], 4
        u5=u4.copy(); u5[1]=flip(u5[1])
        if binary_str == make_bin(l3, u5): return pn, labels[5], 5
        ut=u5.copy(); ut[0]=b[0]
        if binary_str == make_bin(l3, ut): return pn, labels[7], 7
        if binary_str == make_bin(b, ut): return pn, labels[8], 8
    return "unknown", "Unknown", 0

def analyze_configuration(binary_str):
    bits = [int(b) for b in binary_str]
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

    # First pass: collect all branch info
    all_positions = []
    for i in range(6):
        c_id = criteria_map[i]
        yao_bit = bits[5 - i]
        branch = lower_branches[i] if i < 3 else upper_branches[i - 3]
        branch_el = _BRANCH_ELEMENT[branch]
        relation = _get_structural_relation(palace_element, branch_el)
        lifecycle = _get_lifecycle_stage(palace_element, branch)
        all_positions.append({
            "position": i + 1, "criterion": c_id,
            "state": yao_bit, "state_label": "active" if yao_bit == 1 else "inactive",
            "branch": branch, "branch_element": branch_el,
            "structural_relation": relation,
            "relation_label": _RELATION_LABELS[relation],
            "lifecycle_stage": lifecycle["id"], "lifecycle_label": lifecycle["label"],
            "lifecycle_energy": lifecycle["energy"],
        })

    # Second pass: three-layer judgment for each position
    active_branches = [p["branch"] for p in all_positions if p["state"] == 1]
    from collections import Counter
    judgment_counts = Counter()

    for p in all_positions:
        fu_yi = _get_fu_yi(palace_element, p["branch_element"])
        qi_state = _get_qi_state(p["lifecycle_stage"])
        other_branches = [b for b in active_branches if b != p["branch"]]
        branch_rels = _check_branch_relations(p["branch"], other_branches)
        judgment = _three_layer_judgment(fu_yi, qi_state, branch_rels)

        p["direction"] = fu_yi
        p["vitality"] = qi_state
        p["branch_relations"] = branch_rels
        p["judgment"] = judgment
        p["judgment_label"] = _JUDGMENT_LABELS.get(judgment, judgment)

        if p["state"] == 1:
            judgment_counts[judgment] += 1

    # Overall assessment from active position judgments
    if not judgment_counts:
        overall_judgment = "depleted_negative"
    else:
        # Determine overall by most common judgment among active positions
        overall_judgment = judgment_counts.most_common(1)[0][0]

    return {
        "configuration_name": config["name"], "configuration_zh": config["zh"],
        "upper_nature": _TRIGRAM_PROPS[upper_tri]["nature"],
        "lower_nature": _TRIGRAM_PROPS[lower_tri]["nature"],
        "structural_family": _TRIGRAM_PROPS[palace]["nature"],
        "family_element": palace_element,
        "evolution_stage": evolution, "evolution_number": evolution_num,
        "positions": all_positions,
        "overall_judgment": overall_judgment,
        "overall_judgment_label": _JUDGMENT_LABELS.get(overall_judgment, overall_judgment),
        "judgment_distribution": dict(judgment_counts),
    }

# ============================================================
# Analysis Engine / 分析引擎
# ============================================================

def synthesize_layer(layer_name, criterion_states):
    layer = LAYER_SYNTHESIS[layer_name]
    c_ids = layer["criteria"]
    states = tuple(criterion_states[c] for c in c_ids)
    return {"layer": layer_name, "label": layer["label"],
            "states": dict(zip(c_ids, states)),
            "interpretation": layer["interpretations"].get(states, "Undetermined.")}

def generate_binary_code(states):
    return "".join(str(states.get(c, 0)) for c in ["c2", "c1", "c4", "c3", "c6", "c5"])

def detect_mislocation(criterion_states, layer_syntheses):
    env_sum = sum(layer_syntheses["environment"]["states"].values())
    found_sum = sum(layer_syntheses["foundation"]["states"].values())
    if found_sum >= 1 and env_sum == 0:
        return {"type": "form_without_flow", "description": "Established infrastructure but no market attention. Classic undervalued opportunity."}
    elif env_sum >= 1 and found_sum == 0:
        return {"type": "flow_without_form", "description": "Growing attention but no crystallized solution. Bubble risk."}
    elif env_sum >= 1 and found_sum >= 1:
        return {"type": "no_mislocation_positive", "description": "Both form and flow present. Mainstream opportunity."}
    else:
        return {"type": "no_mislocation_negative", "description": "Neither form nor flow. No substance, no momentum."}

def run_analysis(domain, criterion_states):
    layers = {n: synthesize_layer(n, criterion_states) for n in ["environment", "participant", "foundation"]}
    env_s = sum(layers["environment"]["states"].values())
    found_s = sum(layers["foundation"]["states"].values())
    momentum = "strong" if env_s >= 1 else "weak"
    substance = "solid" if found_s >= 1 else "hollow"
    cross = CROSS_LAYER.get((momentum, substance), "Undetermined.")
    mislocation = detect_mislocation(criterion_states, layers)
    code = generate_binary_code(criterion_states)
    config = analyze_configuration(code)
    return {
        "domain": domain, "binary_code": code, "timestamp": datetime.now().isoformat(),
        "configuration": config,
        "layers": {n: {"label": l["label"], "interpretation": l["interpretation"]} for n, l in layers.items()},
        "cross_layer": {"momentum": momentum, "substance": substance, "interpretation": cross},
        "mislocation": mislocation
    }

# ============================================================
# History
# ============================================================

def load_history():
    try:
        with open(HISTORY_FILE, "r") as f: return json.load(f)
    except: return []

def save_history(result):
    history = load_history()
    history.append({
        "domain": result["domain"], "binary_code": result["binary_code"],
        "configuration": result["configuration"]["configuration_name"],
        "configuration_zh": result["configuration"]["configuration_zh"],
        "judgment": result["configuration"]["overall_judgment"],
        "judgment_label": result["configuration"]["overall_judgment_label"],
        "mislocation": result["mislocation"]["type"],
        "momentum": result["cross_layer"]["momentum"],
        "substance": result["cross_layer"]["substance"],
        "timestamp": result["timestamp"]
    })
    with open(HISTORY_FILE, "w") as f: json.dump(history, f, ensure_ascii=False, indent=2)

def load_deep_history():
    try:
        with open(DEEP_HISTORY_FILE, "r") as f: return json.load(f)
    except: return []

def save_deep_history(record):
    history = load_deep_history()
    history.append(record)
    with open(DEEP_HISTORY_FILE, "w") as f: json.dump(history, f, ensure_ascii=False, indent=2)

# ============================================================
# MCP Tools
# ============================================================

@app.tool()
def get_framework_guide() -> str:
    """Get the complete analysis framework guide v0.2."""
    lines = ["CONTRARIAN OPPORTUNITY ANALYSIS FRAMEWORK v0.2", "=" * 50, "",
             "STRUCTURE: 6 Criteria × 5 Dimensions × 3 Layers",
             "64 configurations with lifecycle positioning", "",
             "LAYERS:", "  Environment (Momentum): C1 Trend + C2 Energy",
             "  Participant (Feasibility): C3 Incumbent + C4 Personal",
             "  Foundation (Substance): C5 Ecosystem + C6 Depth", "", "CRITERIA:"]
    for c_id in ["c1","c2","c3","c4","c5","c6"]:
        c = CRITERIA[c_id]
        lines.extend([f"\n[{c_id}] {c['label_en']} / {c['label_zh']}", f"  Q: {c['question_en']}",
                       f"  +: {c['positive']} | -: {c['negative']}", "  Dimensions:"])
        for ph, pr in c["phase_prompts"].items():
            lines.append(f"    {ph}: {pr}")
    lines.extend(["", "LIFECYCLE: Conception → Incubation → Nurturing → Launch → Volatility →",
                   "  Standards → Acceleration → Dominance → Deceleration →",
                   "  Structural Issues → Loss of Momentum → Transformation", "",
                   "OUTPUT: Business language only. No metaphysical terminology."])
    return "\n".join(lines)

@app.tool()
def quick_scan(domain: str, c1: int, c2: int, c3: int, c4: int, c5: int, c6: int) -> str:
    """Quick 6-bit scan with lifecycle. c3: 0=misaligned(contrarian positive), 1=matched."""
    states = {"c1": c1, "c2": c2, "c3": c3, "c4": c4, "c5": c5, "c6": c6}
    result = run_analysis(domain, states)
    save_history(result)
    config = result["configuration"]
    lines = [f"QUICK SCAN: {domain}",
             f"Binary: {result['binary_code']} | {config['configuration_name']} / {config['configuration_zh']}",
             f"Assessment: {config['overall_judgment_label']}",
             f"Evolution: {config['evolution_stage']}",
             f"Mislocation: {result['mislocation']['type']}", "", "Position Analysis:"]
    for p in config["positions"]:
        s = "+" if p["state"] == 1 else "-"
        lines.append(f"  [{s}] {p['criterion'].upper()}: {p['judgment_label']}")
        lines.append(f"      {p['relation_label']} @ {p['lifecycle_label']}")
    lines.extend(["", f"Form-Flow: {result['mislocation']['description']}"])
    return "\n".join(lines)

@app.tool()
def deep_scan(domain: str,
    c1_judgment: bool, c1_origin: str, c1_visibility: str, c1_growth: str, c1_constraint: str, c1_foundation: str,
    c2_judgment: bool, c2_origin: str, c2_visibility: str, c2_growth: str, c2_constraint: str, c2_foundation: str,
    c3_judgment: bool, c3_origin: str, c3_visibility: str, c3_growth: str, c3_constraint: str, c3_foundation: str,
    c4_judgment: bool, c4_origin: str, c4_visibility: str, c4_growth: str, c4_constraint: str, c4_foundation: str,
    c5_judgment: bool, c5_origin: str, c5_visibility: str, c5_growth: str, c5_constraint: str, c5_foundation: str,
    c6_judgment: bool, c6_origin: str, c6_visibility: str, c6_growth: str, c6_constraint: str, c6_foundation: str
) -> str:
    """Deep 30-dimension scan with reasoning chain and lifecycle analysis."""
    states = {"c1": int(c1_judgment), "c2": int(c2_judgment),
              "c3": int(c3_judgment),
              "c4": int(c4_judgment), "c5": int(c5_judgment), "c6": int(c6_judgment)}
    params = locals()
    reasoning_chain = {}
    for c_id in ["c1","c2","c3","c4","c5","c6"]:
        c = CRITERIA[c_id]
        reasoning_chain[c_id] = {
            "criterion": f"{c['label_en']} / {c['label_zh']}", "question": c["question_en"],
            "judgment": states[c_id],
            "judgment_label": c["positive"] if states[c_id] == 1 else c["negative"],
            "dimensions": {ph: params[f"{c_id}_{ph}"] for ph in FIVE_PHASES}
        }
    result = run_analysis(domain, states)
    save_history(result)
    deep_record = {"domain": domain, "binary_code": result["binary_code"],
                   "timestamp": result["timestamp"], "configuration": result["configuration"],
                   "reasoning_chain": reasoning_chain, "layers": result["layers"],
                   "cross_layer": result["cross_layer"], "mislocation": result["mislocation"]}
    save_deep_history(deep_record)
    config = result["configuration"]
    lines = [f"DEEP CONTRARIAN ANALYSIS: {domain}", f"Binary Code: {result['binary_code']}",
             f"Configuration: {config['configuration_name']} / {config['configuration_zh']}",
             f"Structural Family: {config['structural_family']}",
             f"Evolution: {config['evolution_stage']}",
             f"Overall Assessment: {config['overall_judgment_label']}",
             f"{'=' * 50}", ""]
    for c_id in ["c1","c2","c3","c4","c5","c6"]:
        rc = reasoning_chain[c_id]
        pos = next(p for p in config["positions"] if p["criterion"] == c_id)
        s = "+" if rc["judgment"] == 1 else "-"
        lines.extend([f"[{c_id}] {rc['criterion']}", f"  State: [{s}] {rc['judgment_label']}",
                       f"  Assessment: {pos['judgment_label']}",
                       f"  Direction: {pos['direction']} | Vitality: {pos['vitality']} | Relations: {', '.join(pos['branch_relations'])}",
                       f"  Role: {pos['relation_label']} @ {pos['lifecycle_label']}"])
        for ph in FIVE_PHASES:
            lines.append(f"    {ph}: {rc['dimensions'][ph]}")
        lines.append("")
    lines.extend([f"{'─' * 50}", "LAYER SYNTHESIS:"])
    for n in ["environment","participant","foundation"]:
        l = result["layers"][n]; lines.append(f"  {l['label']}: {l['interpretation']}")
    cl = result["cross_layer"]
    lines.extend(["", f"CROSS-LAYER: Momentum={cl['momentum']} × Substance={cl['substance']}",
                   f"  {cl['interpretation']}"])
    ml = result["mislocation"]
    lines.extend(["", f"FORM-FLOW: {ml['type']}", f"  {ml['description']}",
                   "", f"{'=' * 50}", "Full analysis saved to deep_analysis_history.json"])
    return "\n".join(lines)

@app.tool()
def get_analysis_history() -> str:
    """View past analysis results."""
    history = load_history(); deep_history = load_deep_history()
    if not history and not deep_history: return "No analysis history yet."
    lines = ["ANALYSIS HISTORY", "=" * 40]
    if history:
        lines.append("\n--- Quick Scans ---")
        for i, h in enumerate(history):
            lines.extend([f"\n{i+1}. {h['domain']}",
                          f"   Code: {h['binary_code']} | {h.get('configuration','N/A')} / {h.get('configuration_zh','')}",
                          f"   Judgment: {h.get('judgment_label','N/A')} | Mislocation: {h['mislocation']}",
                          f"   Time: {h['timestamp']}"])
    if deep_history:
        lines.append(f"\n--- Deep Analyses ({len(deep_history)}) ---")
        for i, h in enumerate(deep_history):
            cfg = h.get('configuration', {})
            lines.extend([f"\n{i+1}. {h['domain']}", f"   Code: {h['binary_code']}",
                          f"   Config: {cfg.get('configuration_name','N/A')} / {cfg.get('configuration_zh','')}",
                          f"   Time: {h['timestamp']}"])
    return "\n".join(lines)


# ============================================================
# Intent Query System / 意图查询系统
# Based on six structural relations (六亲):
# User brings an intent → framework identifies which relation to examine
# → reports target state, helpers, threats, and guidance
# ============================================================

# Six-relation generation and control cycles
_RELATION_GENERATES = {
    "upstream_support": "peer_competitor",
    "peer_competitor": "derivative_output",
    "derivative_output": "accessible_resource",
    "accessible_resource": "external_pressure",
    "external_pressure": "upstream_support",
}
_RELATION_CONTROLS = {
    "peer_competitor": "accessible_resource",
    "accessible_resource": "upstream_support",
    "upstream_support": "derivative_output",
    "derivative_output": "external_pressure",
    "external_pressure": "peer_competitor",
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

def _analyze_intent(config, intent_key):
    """Analyze a configuration from the perspective of a specific intent"""
    intent = _INTENT_MAP[intent_key]
    positions = config["positions"]

    targets = [p for p in positions if p["structural_relation"] == intent["target"]]
    helpers = [p for p in positions if p["structural_relation"] == intent["helper"]]
    threats = [p for p in positions if p["structural_relation"] == intent["threat"]]

    # Target assessment: is it active (state=1)?
    active_targets = [t for t in targets if t["state"] == 1]
    target_present = len(active_targets) > 0
    target_vital = any(t["vitality"] in ("vital", "nascent") for t in active_targets)

    # Helper assessment: is it active?
    active_helpers = [h for h in helpers if h["state"] == 1]
    helper_present = len(active_helpers) > 0
    helper_vital = any(h["vitality"] in ("vital", "nascent") for h in active_helpers)

    # Threat assessment: is it active AND vital (strong enough to cause harm)?
    active_threats = [t for t in threats if t["state"] == 1]
    threat_strong = any(t["vitality"] == "vital" for t in active_threats)
    threat_present = len(active_threats) > 0

    # Generate guidance using layered logic:
    # Best case: target active + helper active + no strong threat
    # Worst case: no target + no helper
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
            "positions": [{
                "criterion": t["criterion"],
                "state": "active" if t["state"] == 1 else "inactive",
                "judgment": t["judgment_label"],
                "vitality": t["vitality"],
                "direction": t["direction"],
            } for t in targets]
        },
        "helper": {
            "relation": intent["helper"],
            "relation_label": _RELATION_LABELS[intent["helper"]],
            "logic": intent["helper_logic"],
            "positions": [{
                "criterion": h["criterion"],
                "state": "active" if h["state"] == 1 else "inactive",
                "judgment": h["judgment_label"],
                "vitality": h["vitality"],
            } for h in helpers]
        },
        "threat": {
            "relation": intent["threat"],
            "relation_label": _RELATION_LABELS[intent["threat"]],
            "logic": intent["threat_logic"],
            "positions": [{
                "criterion": t["criterion"],
                "state": "active" if t["state"] == 1 else "inactive",
                "judgment": t["judgment_label"],
                "vitality": t["vitality"],
            } for t in threats]
        },
    }


@app.tool()
def query_intent(domain: str, c1: int, c2: int, c3: int, c4: int, c5: int, c6: int,
                 intent: str) -> str:
    """Query a configuration with a specific intent.
    意图查询：带着目的分析配置。

    Args:
        domain: what is being analyzed
        c1-c6: binary judgments (1=positive, 0=negative)
        intent: one of 'seek_profit', 'seek_position', 'seek_protection', 'seek_output', 'assess_competition'
    """
    if intent not in _INTENT_MAP:
        return f"Unknown intent '{intent}'. Valid: {', '.join(_INTENT_MAP.keys())}"

    states = {"c1": c1, "c2": c2, "c3": c3, "c4": c4, "c5": c5, "c6": c6}
    result = run_analysis(domain, states)
    config = result["configuration"]
    intent_result = _analyze_intent(config, intent)

    lines = [
        f"INTENT QUERY: {domain}",
        f"Intent: {intent_result['intent']}",
        f"Config: {config['configuration_name']} / {config['configuration_zh']}",
        f"Binary: {result['binary_code']} | Evolution: {config['evolution_stage']}",
        f"{'=' * 50}",
        "",
        f"ASSESSMENT: {intent_result['overall'].upper().replace('_', ' ')}",
        f"  {intent_result['guidance']}",
        "",
        f"TARGET — {intent_result['target']['relation_label']}:",
    ]
    for p in intent_result['target']['positions']:
        lines.append(f"  [{p['state']}] {p['criterion'].upper()}: {p['judgment']} (vitality: {p['vitality']}, direction: {p['direction']})")

    lines.extend(["", f"HELPER — {intent_result['helper']['relation_label']}:",
                   f"  Logic: {intent_result['helper']['logic']}"])
    for p in intent_result['helper']['positions']:
        lines.append(f"  [{p['state']}] {p['criterion'].upper()}: {p['judgment']} (vitality: {p['vitality']})")

    lines.extend(["", f"THREAT — {intent_result['threat']['relation_label']}:",
                   f"  Logic: {intent_result['threat']['logic']}"])
    for p in intent_result['threat']['positions']:
        lines.append(f"  [{p['state']}] {p['criterion'].upper()}: {p['judgment']} (vitality: {p['vitality']})")

    # Mitigation advice if threats are active
    active_threats = [p for p in intent_result['threat']['positions'] if p['state'] == 'active']
    if active_threats:
        lines.extend(["", "MITIGATION:"])
        threat_rel = intent_result['threat']['relation']
        controller = [k for k, v in _RELATION_CONTROLS.items() if v == threat_rel]
        if controller:
            controller_label = _RELATION_LABELS.get(controller[0], controller[0])
            lines.append(f"  To reduce threat: strengthen {controller_label}")
            controller_positions = [p for p in config['positions'] if p['structural_relation'] == controller[0]]
            for cp in controller_positions:
                s = "active" if cp["state"] == 1 else "inactive"
                lines.append(f"    {cp['criterion'].upper()} [{s}]: {cp['judgment_label']}")

    return "\n".join(lines)


@app.prompt("analyze-opportunity")
def analyze_opportunity_prompt() -> str:
    return """You are using the Structural Analysis System v0.3.

Steps:
1. Call get_framework_guide to understand the 6 criteria and 5 dimensions
2. Research the domain the user wants to analyze
3. For each criterion, assess 5 dimensions, make binary judgment
4. Call quick_scan or deep_scan to get the structural configuration
5. Ask the user what their INTENT is (what do they want to achieve?)
6. Call query_intent with the same c1-c6 values and the user's intent
7. Present the guidance: what supports their intent, what threatens it, how to mitigate

INTENTS:
  seek_profit — looking for returns/resources
  seek_position — looking for career/authority/recognition
  seek_protection — looking for support/backing/safety
  seek_output — looking for innovation/growth/new products
  assess_competition — understanding competitive dynamics

ALL OUTPUT IN BUSINESS LANGUAGE. No metaphysical terminology."""

if __name__ == "__main__":
    app.run()