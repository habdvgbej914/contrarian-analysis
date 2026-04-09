"""
FCAS core engine (Force Configuration Analysis System)
气象分析系统核心引擎

Provides:
- Binary encoding tables (encoding)
- Qimen paipan engine (排盘引擎)
- Geju pattern matching (格局判断)
- Three-layer judgment bridge (萧吉三层判断)
- Yingqi timing derivation (应期推导)

This module is the single source of truth for structural analysis logic.
MCP exposure lives in `fcas_mcp.py`.
"""

import os
import json
import math
from datetime import datetime, timedelta
try:
    import ephem
    HAS_EPHEM = True
except ImportError:
    HAS_EPHEM = False, timedelta



# ============================================================================
# SECTION 1: BINARY ENCODING TABLES
# ============================================================================

# ============================================================
# Layer 1: 五行 Wuxing (3 bits)
# ============================================================
WX_MU = 0b000    # 木 Wood
WX_HUO = 0b001   # 火 Fire
WX_TU = 0b010    # 土 Earth
WX_JIN = 0b011   # 金 Metal
WX_SHUI = 0b100  # 水 Water

WUXING_NAMES = {WX_MU: "木", WX_HUO: "火", WX_TU: "土", WX_JIN: "金", WX_SHUI: "水"}

# ============================================================
# Layer 2: 十天干 Tiangan (4 bits = yinyang(1) + wuxing(3))
# ============================================================
TG_JIA  = 0b1000  # 甲 阳木 8
TG_YI   = 0b0000  # 乙 阴木 0
TG_BING = 0b1001  # 丙 阳火 9
TG_DING = 0b0001  # 丁 阴火 1
TG_WU   = 0b1010  # 戊 阳土 10
TG_JI   = 0b0010  # 己 阴土 2
TG_GENG = 0b1011  # 庚 阳金 11
TG_XIN  = 0b0011  # 辛 阴金 3
TG_REN  = 0b1100  # 壬 阳水 12
TG_GUI  = 0b0100  # 癸 阴水 4

# Ordered list for iteration (甲乙丙丁戊己庚辛壬癸)
TIANGAN_ORDER = [TG_JIA, TG_YI, TG_BING, TG_DING, TG_WU, TG_JI, TG_GENG, TG_XIN, TG_REN, TG_GUI]
TIANGAN_NAMES = {
    TG_JIA: "甲", TG_YI: "乙", TG_BING: "丙", TG_DING: "丁", TG_WU: "戊",
    TG_JI: "己", TG_GENG: "庚", TG_XIN: "辛", TG_REN: "壬", TG_GUI: "癸"
}
# Index-based lookup (0=甲, 1=乙, ... 9=癸)
TIANGAN_BY_INDEX = {i: tg for i, tg in enumerate(TIANGAN_ORDER)}
INDEX_BY_TIANGAN = {tg: i for i, tg in enumerate(TIANGAN_ORDER)}

def tg_wuxing(tg):
    """Get wuxing of a tiangan"""
    return tg & 0b0111

def tg_yinyang(tg):
    """1=阳, 0=阴"""
    return (tg >> 3) & 1

# ============================================================
# Layer 3: 十二地支 Dizhi (4 bits, ordinal 0-11)
# ============================================================
DZ_ZI   = 0   # 子
DZ_CHOU = 1   # 丑
DZ_YIN  = 2   # 寅
DZ_MAO  = 3   # 卯
DZ_CHEN = 4   # 辰
DZ_SI   = 5   # 巳
DZ_WU   = 6   # 午
DZ_WEI  = 7   # 未
DZ_SHEN = 8   # 申
DZ_YOU  = 9   # 酉
DZ_XU   = 10  # 戌
DZ_HAI  = 11  # 亥

DIZHI_NAMES = {
    0: "子", 1: "丑", 2: "寅", 3: "卯", 4: "辰", 5: "巳",
    6: "午", 7: "未", 8: "申", 9: "酉", 10: "戌", 11: "亥"
}

# 地支→五行
DIZHI_WUXING = {
    DZ_ZI: WX_SHUI, DZ_CHOU: WX_TU, DZ_YIN: WX_MU, DZ_MAO: WX_MU,
    DZ_CHEN: WX_TU, DZ_SI: WX_HUO, DZ_WU: WX_HUO, DZ_WEI: WX_TU,
    DZ_SHEN: WX_JIN, DZ_YOU: WX_JIN, DZ_XU: WX_TU, DZ_HAI: WX_SHUI
}

# ============================================================
# Layer 4: 九星 Jiuxing (4 bits, 0-8)
# ============================================================
STAR_PENG  = 0  # 天蓬 水 坎1
STAR_RUI   = 1  # 天芮 土 坤2
STAR_CHONG = 2  # 天冲 木 震3
STAR_FU    = 3  # 天辅 木 巽4
STAR_QIN   = 4  # 天禽 土 中5
STAR_XIN   = 5  # 天心 金 乾6
STAR_ZHU   = 6  # 天柱 金 兑7
STAR_REN   = 7  # 天任 土 艮8
STAR_YING  = 8  # 天英 火 离9

STAR_NAMES = {
    0: "天蓬", 1: "天芮", 2: "天冲", 3: "天辅", 4: "天禽",
    5: "天心", 6: "天柱", 7: "天任", 8: "天英"
}

STAR_WUXING = {
    STAR_PENG: WX_SHUI, STAR_RUI: WX_TU, STAR_CHONG: WX_MU,
    STAR_FU: WX_MU, STAR_QIN: WX_TU, STAR_XIN: WX_JIN,
    STAR_ZHU: WX_JIN, STAR_REN: WX_TU, STAR_YING: WX_HUO
}

# 九星本位宫 (star -> palace number 1-9)
STAR_HOME_PALACE = {
    STAR_PENG: 1, STAR_RUI: 2, STAR_CHONG: 3, STAR_FU: 4, STAR_QIN: 5,
    STAR_XIN: 6, STAR_ZHU: 7, STAR_REN: 8, STAR_YING: 9
}

# ============================================================
# Layer 5: 八门 Bamen (3 bits, 0-7)
# ============================================================
GATE_XIU   = 0  # 休门 水 坎1
GATE_SHENG = 1  # 生门 土 艮8
GATE_SHANG = 2  # 伤门 木 震3
GATE_DU    = 3  # 杜门 木 巽4
GATE_JING  = 4  # 景门 火 离9
GATE_SI    = 5  # 死门 土 坤2
GATE_JING2 = 6  # 惊门 金 兑7
GATE_KAI   = 7  # 开门 金 乾6

GATE_NAMES = {
    0: "休门", 1: "生门", 2: "伤门", 3: "杜门",
    4: "景门", 5: "死门", 6: "惊门", 7: "开门"
}

GATE_WUXING = {
    GATE_XIU: WX_SHUI, GATE_SHENG: WX_TU, GATE_SHANG: WX_MU,
    GATE_DU: WX_MU, GATE_JING: WX_HUO, GATE_SI: WX_TU,
    GATE_JING2: WX_JIN, GATE_KAI: WX_JIN
}

# 八门本位宫 (gate -> palace number 1-9)
GATE_HOME_PALACE = {
    GATE_XIU: 1, GATE_SHENG: 8, GATE_SHANG: 3, GATE_DU: 4,
    GATE_JING: 9, GATE_SI: 2, GATE_JING2: 7, GATE_KAI: 6
}

# 吉凶: 1=吉, 0=凶, -1=中平
GATE_JIXIONG = {
    GATE_XIU: 1, GATE_SHENG: 1, GATE_KAI: 1,   # 三吉门
    GATE_SI: 0, GATE_JING2: 0, GATE_SHANG: 0,   # 三凶门
    GATE_DU: -1, GATE_JING: -1                    # 中平
}

# ============================================================
# Layer 6: 八神 Bashen (3 bits, 0-7)
# ============================================================
DEITY_ZHIFU   = 0  # 直符
DEITY_TENGSHE = 1  # 腾蛇
DEITY_TAIYIN  = 2  # 太阴
DEITY_LIUHE   = 3  # 六合
DEITY_GOUCHEN = 4  # 勾陈
DEITY_ZHUQUE  = 5  # 朱雀
DEITY_JIUDI   = 6  # 九地
DEITY_JIUTIAN = 7  # 九天

DEITY_NAMES = {
    0: "直符", 1: "腾蛇", 2: "太阴", 3: "六合",
    4: "勾陈", 5: "朱雀", 6: "九地", 7: "九天"
}

# 阳遁八神顺序 (直符起，顺布)
DEITY_ORDER_YANG = [DEITY_ZHIFU, DEITY_TENGSHE, DEITY_TAIYIN, DEITY_LIUHE,
                     DEITY_GOUCHEN, DEITY_ZHUQUE, DEITY_JIUDI, DEITY_JIUTIAN]
# 阴遁八神顺序
DEITY_ORDER_YIN  = [DEITY_ZHIFU, DEITY_JIUTIAN, DEITY_JIUDI, DEITY_ZHUQUE,
                     DEITY_GOUCHEN, DEITY_LIUHE, DEITY_TAIYIN, DEITY_TENGSHE]

# ============================================================
# Layer 7: 九宫 Jiugong (palace number 1-9)
# ============================================================
GONG_WUXING = {
    1: WX_SHUI,  # 坎
    2: WX_TU,    # 坤
    3: WX_MU,    # 震
    4: WX_MU,    # 巽
    5: WX_TU,    # 中
    6: WX_JIN,   # 乾
    7: WX_JIN,   # 兑
    8: WX_TU,    # 艮
    9: WX_HUO    # 离
}

GONG_GUA_NAMES = {1: "坎", 2: "坤", 3: "震", 4: "巽", 5: "中", 6: "乾", 7: "兑", 8: "艮", 9: "离"}

# 洛书九宫飞布顺序 (从1宫起顺飞)
LOSHU_ORDER = [1, 2, 3, 4, 5, 6, 7, 8, 9]
# 洛书飞星顺序: 1→2→3→4→5→6→7→8→9 (但实际飞布按洛书轨迹)
# 洛书轨迹: 中→乾→兑→艮→离→坎→坤→震→巽 即 5→6→7→8→9→1→2→3→4
LOSHU_FLY_ORDER = [5, 6, 7, 8, 9, 1, 2, 3, 4]

# 九宫对宫 (六冲位)
GONG_CHONG = {1: 9, 9: 1, 2: 8, 8: 2, 3: 7, 7: 3, 4: 6, 6: 4, 5: 5}

# 九宫→八卦三爻二进制 (初爻→三爻, 从下往上读)
# 按FCAS确认: 111=乾 110=巽 101=离 100=艮 011=兑 010=坎 001=震 000=坤
GONG_TO_TRIGRAM = {
    1: 0b010,  # 坎
    2: 0b000,  # 坤
    3: 0b001,  # 震
    4: 0b110,  # 巽
    5: 0b000,  # 中(寄坤)
    6: 0b111,  # 乾
    7: 0b011,  # 兑
    8: 0b100,  # 艮
    9: 0b101   # 离
}

# ============================================================
# 纳音五行表 (Nayin — 60-stem resonance wuxing)
# Key: (tiangan_idx, dizhi_idx) per TIANGAN_NAMES/DIZHI encoding
# Value: (wuxing_idx, name_str)
# 依据: 《三命通会》纳音六十甲子表
# ============================================================
# TIANGAN_IDX: 8=甲,0=乙,9=丙,1=丁,10=戊,2=己,11=庚,3=辛,12=壬,4=癸
# DIZHI_IDX:   0=子,1=丑,2=寅,3=卯,4=辰,5=巳,6=午,7=未,8=申,9=酉,10=戌,11=亥
_NAYIN: dict = {
    # 甲子乙丑 海中金
    (8, 0): (3, '海中金'),  (0, 1): (3, '海中金'),
    # 丙寅丁卯 炉中火
    (9, 2): (1, '炉中火'),  (1, 3): (1, '炉中火'),
    # 戊辰己巳 大林木
    (10, 4): (0, '大林木'), (2, 5): (0, '大林木'),
    # 庚午辛未 路旁土
    (11, 6): (2, '路旁土'), (3, 7): (2, '路旁土'),
    # 壬申癸酉 剑锋金
    (12, 8): (3, '剑锋金'), (4, 9): (3, '剑锋金'),
    # 甲戌乙亥 山头火
    (8, 10): (1, '山头火'), (0, 11): (1, '山头火'),
    # 丙子丁丑 涧下水
    (9, 0): (4, '涧下水'),  (1, 1): (4, '涧下水'),
    # 戊寅己卯 城头土
    (10, 2): (2, '城头土'), (2, 3): (2, '城头土'),
    # 庚辰辛巳 白蜡金
    (11, 4): (3, '白蜡金'), (3, 5): (3, '白蜡金'),
    # 壬午癸未 杨柳木
    (12, 6): (0, '杨柳木'), (4, 7): (0, '杨柳木'),
    # 甲申乙酉 泉中水
    (8, 8): (4, '泉中水'),  (0, 9): (4, '泉中水'),
    # 丙戌丁亥 屋上土
    (9, 10): (2, '屋上土'), (1, 11): (2, '屋上土'),
    # 戊子己丑 霹雳火
    (10, 0): (1, '霹雳火'), (2, 1): (1, '霹雳火'),
    # 庚寅辛卯 松柏木
    (11, 2): (0, '松柏木'), (3, 3): (0, '松柏木'),
    # 壬辰癸巳 长流水
    (12, 4): (4, '长流水'), (4, 5): (4, '长流水'),
    # 甲午乙未 砂中金
    (8, 6): (3, '砂中金'),  (0, 7): (3, '砂中金'),
    # 丙申丁酉 山下火
    (9, 8): (1, '山下火'),  (1, 9): (1, '山下火'),
    # 戊戌己亥 平地木
    (10, 10): (0, '平地木'), (2, 11): (0, '平地木'),
    # 庚子辛丑 壁上土
    (11, 0): (2, '壁上土'), (3, 1): (2, '壁上土'),
    # 壬寅癸卯 金箔金
    (12, 2): (3, '金箔金'), (4, 3): (3, '金箔金'),
    # 甲辰乙巳 覆灯火
    (8, 4): (1, '覆灯火'),  (0, 5): (1, '覆灯火'),
    # 丙午丁未 天河水
    (9, 6): (4, '天河水'),  (1, 7): (4, '天河水'),
    # 戊申己酉 大驿土
    (10, 8): (2, '大驿土'), (2, 9): (2, '大驿土'),
    # 庚戌辛亥 钗钏金
    (11, 10): (3, '钗钏金'), (3, 11): (3, '钗钏金'),
    # 壬子癸丑 桑柘木
    (12, 0): (0, '桑柘木'), (4, 1): (0, '桑柘木'),
    # 甲寅乙卯 大溪水
    (8, 2): (4, '大溪水'),  (0, 3): (4, '大溪水'),
    # 丙辰丁巳 沙中土
    (9, 4): (2, '沙中土'),  (1, 5): (2, '沙中土'),
    # 戊午己未 天上火
    (10, 6): (1, '天上火'), (2, 7): (1, '天上火'),
    # 庚申辛酉 石榴木
    (11, 8): (0, '石榴木'), (3, 9): (0, '石榴木'),
    # 壬戌癸亥 大海水
    (12, 10): (4, '大海水'), (4, 11): (4, '大海水'),
}

def get_nayin(tg_idx: int, dz_idx: int):
    """获取天干地支组合的纳音五行。返回 (wuxing_idx, name) 或 None。"""
    return _NAYIN.get((tg_idx, dz_idx))


# ============================================================
# Relation Tables: 生克
# ============================================================
# 关系编码
REL_BIHE   = 0b000  # 比和 A=B
REL_WOSHENG = 0b001  # 我生 A生B (泄)
REL_WOKE   = 0b010  # 我克 A克B (耗)
REL_SHENGWO = 0b011  # 生我 B生A (助)
REL_KEWO   = 0b100  # 克我 B克A (制)

REL_NAMES = {0: "比和", 1: "我生", 2: "我克", 3: "生我", 4: "克我"}

def shengke(a_wx, b_wx):
    """五行生克关系: a对b的关系
    
    相生序: 木(0)→火(1)→土(2)→金(3)→水(4)→木(0)
    diff = (b - a) % 5
    diff=0: 比和, diff=1: 我生, diff=2: 我克
    diff=3: 克我 (b克a, e.g. 木看金: (3-0)%5=3, 金克木)
    diff=4: 生我 (b生a, e.g. 金看土: (2-3)%5=4, 土生金)
    """
    diff = (b_wx - a_wx) % 5
    # Map diff to relation constant
    DIFF_TO_REL = {
        0: REL_BIHE,     # 比和
        1: REL_WOSHENG,  # 我生
        2: REL_WOKE,     # 我克
        3: REL_KEWO,     # 克我 (NOT 生我!)
        4: REL_SHENGWO,  # 生我 (NOT 克我!)
    }
    return DIFF_TO_REL[diff]

# ============================================================
# Relation Tables: 六合
# ============================================================
LIUHE_PAIRS = {
    (DZ_ZI, DZ_CHOU): WX_TU,
    (DZ_YIN, DZ_HAI): WX_MU,
    (DZ_MAO, DZ_XU): WX_HUO,
    (DZ_CHEN, DZ_YOU): WX_JIN,
    (DZ_SI, DZ_SHEN): WX_SHUI,
    (DZ_WU, DZ_WEI): WX_TU,  # 一说火
}

def liuhe(a, b):
    """Check if two dizhi form 六合. Returns (True, hua_wuxing) or (False, None)"""
    pair = (min(a, b), max(a, b))
    # Need to check both orderings since some pairs aren't min/max ordered
    for (x, y), wx in LIUHE_PAIRS.items():
        if (a == x and b == y) or (a == y and b == x):
            return True, wx
    return False, None

# ============================================================
# Relation Tables: 六冲
# ============================================================
def liuchong(a, b):
    """Check if two dizhi form 六冲"""
    return abs(a - b) == 6

# ============================================================
# Relation Tables: 三刑
# ============================================================
XING_NONE = 0
XING_WULI = 1     # 无礼之刑
XING_SHISHI = 2   # 恃势之刑
XING_SHIEN = 3    # 恃恩之刑
XING_ZIXING = 4   # 自刑

XING_NAMES = {0: "无刑", 1: "无礼之刑", 2: "恃势之刑", 3: "恃恩之刑", 4: "自刑"}

# Directed xing relationships
SANXING_TABLE = {
    (DZ_ZI, DZ_MAO): XING_WULI, (DZ_MAO, DZ_ZI): XING_WULI,
    (DZ_YIN, DZ_SI): XING_SHISHI, (DZ_SI, DZ_SHEN): XING_SHISHI, (DZ_SHEN, DZ_YIN): XING_SHISHI,
    (DZ_CHOU, DZ_XU): XING_SHIEN, (DZ_XU, DZ_WEI): XING_SHIEN, (DZ_WEI, DZ_CHOU): XING_SHIEN,
    (DZ_WU, DZ_WU): XING_ZIXING, (DZ_CHEN, DZ_CHEN): XING_ZIXING,
    (DZ_YOU, DZ_YOU): XING_ZIXING, (DZ_HAI, DZ_HAI): XING_ZIXING,
}

def sanxing(a, b):
    """Check three punishments"""
    return SANXING_TABLE.get((a, b), XING_NONE)

# ============================================================
# Relation Tables: 三合局
# ============================================================
SANHE_GROUPS = {
    WX_SHUI: (DZ_SHEN, DZ_ZI, DZ_CHEN),   # 申子辰 水局
    WX_MU:   (DZ_HAI, DZ_MAO, DZ_WEI),     # 亥卯未 木局
    WX_HUO:  (DZ_YIN, DZ_WU, DZ_XU),       # 寅午戌 火局
    WX_JIN:  (DZ_SI, DZ_YOU, DZ_CHOU),      # 巳酉丑 金局
}

# ============================================================
# Relation Tables: 五行墓位
# ============================================================
WUXING_MU_DIZHI = {
    WX_MU: DZ_WEI,    # 木墓未 → 坤2
    WX_HUO: DZ_XU,    # 火墓戌 → 乾6
    WX_TU: DZ_CHEN,   # 土墓辰 → 巽4
    WX_JIN: DZ_CHOU,  # 金墓丑 → 艮8
    WX_SHUI: DZ_CHEN, # 水墓辰 → 巽4
}

WUXING_MU_GONG = {
    WX_MU: 2,   # 坤
    WX_HUO: 6,  # 乾
    WX_TU: 4,   # 巽
    WX_JIN: 8,  # 艮
    WX_SHUI: 4, # 巽
}

# 阴阳土分墓
TG_MU_SPECIAL = {
    TG_WU: DZ_XU,    # 戊(阳土)墓戌
    TG_JI: DZ_CHOU,  # 己(阴土)墓丑
}

# ============================================================
# Relation Tables: 十二长生
# ============================================================
STAGE_SHOUQI   = 0   # 受气/概念酝酿
STAGE_TAI      = 1   # 胎/早期孵化
STAGE_YANG     = 2   # 养/资源培育
STAGE_CHANGSHENG = 3 # 长生/正式启动
STAGE_MUYU     = 4   # 沐浴/初期波动
STAGE_GUANDAI  = 5   # 冠带/建立规范
STAGE_LINGUAN  = 6   # 临官/快速成长
STAGE_DIWANG   = 7   # 帝旺/市场主导
STAGE_SHUAI    = 8   # 衰/增长放缓
STAGE_BING     = 9   # 病/结构性问题
STAGE_SIWANG   = 10  # 死/失去动力
STAGE_MU       = 11  # 墓/沉淀转化

STAGE_NAMES = {
    0: "受气", 1: "胎", 2: "养", 3: "长生", 4: "沐浴", 5: "冠带",
    6: "临官", 7: "帝旺", 8: "衰", 9: "病", 10: "死", 11: "墓"
}
STAGE_BIZ_NAMES = {
    0: "概念酝酿", 1: "早期孵化", 2: "资源培育", 3: "正式启动",
    4: "初期波动", 5: "建立规范", 6: "快速成长", 7: "市场主导",
    8: "增长放缓", 9: "结构性问题", 10: "失去动力", 11: "沉淀转化"
}

# 各五行长生地支 (per 萧吉《五行大义》)
CHANGSHENG_START = {
    WX_MU:   DZ_HAI,   # 木长生亥
    WX_HUO:  DZ_YIN,   # 火长生寅
    WX_JIN:  DZ_SI,    # 金长生巳
    WX_SHUI: DZ_SHEN,  # 水长生申
    WX_TU:   DZ_MAO,   # 土长生卯 (萧吉: 生于卯)
}

def calc_changsheng(wuxing, dizhi):
    """Calculate 十二长生 stage for given wuxing at given dizhi"""
    start = CHANGSHENG_START[wuxing]
    offset = (dizhi - start + 12) % 12
    # offset 0 = 长生(3), 1 = 沐浴(4), ... so stage = (offset + 3) % 12
    return (offset + 3) % 12

# ============================================================
# Relation Tables: 旺衰 (旺相休囚死)
# ============================================================
WS_WANG = 0  # 旺
WS_XIANG = 1 # 相
WS_XIU = 2   # 休
WS_QIU = 3   # 囚
WS_SI = 4    # 死/废

WS_NAMES = {0: "旺", 1: "相", 2: "休", 3: "囚", 4: "死"}

# Season from month branch
def get_season(month_branch):
    """Returns season wuxing from month dizhi"""
    if month_branch in (DZ_YIN, DZ_MAO):
        return WX_MU      # 春
    elif month_branch in (DZ_SI, DZ_WU):
        return WX_HUO     # 夏
    elif month_branch in (DZ_SHEN, DZ_YOU):
        return WX_JIN     # 秋
    elif month_branch in (DZ_HAI, DZ_ZI):
        return WX_SHUI    # 冬
    else:  # 辰戌丑未
        return WX_TU      # 四季

def calc_wangshuai(wuxing, month_branch):
    """Calculate 旺衰 status. Returns WS_* constant.
    
    Per《宝鉴》: 春天木旺火相水休金囚土死
    Rules (from perspective of the 当令/旺 element = season_wx):
    - 当令者旺: wuxing == season → 旺
    - 我生者相: season generates wuxing → 相 (season生wuxing)
    - 生我者休: wuxing generates season → 休 (wuxing生season)  
    - 我克者囚: season conquers wuxing → 囚 (season克wuxing)
    - 克我者死: wuxing conquers season → 死 (wuxing克season)
    
    Using shengke(season, wuxing):
    - BIHE → 旺
    - WOSHENG (season生wuxing) → 相
    - SHENGWO (wuxing生season) → 休
    - WOKE (season克wuxing) → 囚   ← "我克者囚"
    - KEWO (wuxing克season) → 死   ← "克我者死"
    
    Wait - KEWO means "b克a", i.e. wuxing克season. That means wuxing is
    the one conquering the season. Per "克我者死", this means wuxing is the
    one that CONQUERS the 旺 element, so it should be 死? No!
    
    Let me re-derive with a concrete example:
    春=木(0). shengke(木0, 金3) = ?
    From 木's view of 金: 金克木, so 金 is the conquerer of 木.
    Per "克我者死": the one that conquers 旺(木) is 死.
    So 金 should be 死? But 原文 says 金=囚!
    
    原文: "春天木旺火相水休金囚土死"
    - 木=旺(当令)
    - 火=相(木生火, 当令者所生)
    - 水=休(水生木, 生当令者)
    - 金=囚(金克木...但原文说金囚)
    - 土=死(木克土, 当令者所克...但原文说土死)
    
    Hmm wait. 原文说的"我克者囚"的"我"是谁？
    不是当令者！是被判断的那个元素自己。
    "我克者囚" = 如果我(被判断元素)所克的是当令者，则我为囚。
    "克我者死" = 如果克我(被判断元素)的是当令者，则我为死。
    
    金(被判断): 金克木(当令)? 不对，是木不克金。金→水→木? 不是。
    Actually 金克木 YES! 金克木是对的。
    所以"我(金)克者"= 我克的对象 = 金克木。金所克的是当令者木。
    → "我克者囚" → 金=囚 ✓
    
    土(被判断): 谁克土？木克土。木是当令者。
    → "克我者死" → 克土的是当令者木 → 土=死 ✓
    
    So the correct mapping from the JUDGED element's perspective:
    shengke(wuxing_被判断, season_当令):
    - BIHE → 旺
    - WOSHENG (被判断生当令) → 休 ("生我者休" 这里"我"=当令,"生我"=被判断生当令)
    - WOKE (被判断克当令) → 囚 ("我克者囚" 这里"我"=被判断)
    - SHENGWO (当令生被判断) → 相 ("我生者相" 这里"我"=当令,"我生"=当令生被判断)
    - KEWO (当令克被判断) → 死 ("克我者死" 这里"我"=被判断,"克我"=当令克被判断)
    
    So I should use shengke(wuxing, season) NOT shengke(season, wuxing)!
    """
    season_wx = get_season(month_branch)
    rel = shengke(wuxing, season_wx)
    
    mapping = {
        REL_BIHE: WS_WANG,      # 同类=旺
        REL_WOSHENG: WS_XIU,    # 我(被判断)生当令=休 (生我者休，此"我"=当令)
        REL_WOKE: WS_QIU,       # 我(被判断)克当令=囚 (我克者囚)
        REL_SHENGWO: WS_XIANG,  # 当令生我(被判断)=相 (我生者相，此"我"=当令)
        REL_KEWO: WS_SI,        # 当令克我(被判断)=死 (克我者死)
    }
    return mapping[rel]

# ============================================================
# Relation Tables: 旬空 Xunkong
# ============================================================
# 六甲旬首: 甲子(0), 甲戌(1), 甲申(2), 甲午(3), 甲辰(4), 甲寅(5)
# Each xun head's dizhi index
XUN_HEAD_DIZHI = [DZ_ZI, DZ_XU, DZ_SHEN, DZ_WU, DZ_CHEN, DZ_YIN]

def get_xunkong(xun_index):
    """Get the two kongwang dizhi for a given xun (0-5)"""
    start = XUN_HEAD_DIZHI[xun_index]
    k1 = (start + 10) % 12
    k2 = (start + 11) % 12
    return (k1, k2)

# For quick reference:
# 甲子旬空: 戌亥  甲戌旬空: 申酉  甲申旬空: 午未
# 甲午旬空: 辰巳  甲辰旬空: 寅卯  甲寅旬空: 子丑

def get_xun_from_ganzhi(tg_idx, dz):
    """Given tiangan index (0-9) and dizhi (0-11), find which xun it belongs to.
    Returns xun index 0-5."""
    # The 60 jiazi cycle: stem index = i % 10, branch = i % 12
    # Given tg_idx and dz, find i such that i%10==tg_idx and i%12==dz
    # Then xun = i // 10
    for i in range(60):
        if i % 10 == tg_idx and i % 12 == dz:
            return i // 10
    return 0

# ============================================================
# 六仪遁甲: which stem hides which jiazi
# ============================================================
# 甲子遁戊, 甲戌遁己, 甲申遁庚, 甲午遁辛, 甲辰遁壬, 甲寅遁癸
JIAZI_DUN = {
    0: TG_WU,   # 甲子→戊
    1: TG_JI,   # 甲戌→己
    2: TG_GENG, # 甲申→庚
    3: TG_XIN,  # 甲午→辛
    4: TG_REN,  # 甲辰→壬
    5: TG_GUI,  # 甲寅→癸
}

# Reverse: which liuyi reveals which jiazi
DUN_TO_JIAZI = {v: k for k, v in JIAZI_DUN.items()}

# 六仪顺序 (for ground plate layout)
LIUYI_ORDER = [TG_WU, TG_JI, TG_GENG, TG_XIN, TG_REN, TG_GUI]
# 三奇逆序 (for ground plate layout)  
SANQI_ORDER = [TG_DING, TG_BING, TG_YI]

# Complete stem order for Yangdun: 戊己庚辛壬癸丁丙乙 (六仪顺布，三奇逆布)
YANG_STEM_ORDER = [TG_WU, TG_JI, TG_GENG, TG_XIN, TG_REN, TG_GUI, TG_DING, TG_BING, TG_YI]
# For Yindun: 六仪逆布，三奇顺布
YIN_STEM_ORDER = [TG_WU, TG_JI, TG_GENG, TG_XIN, TG_REN, TG_GUI, TG_DING, TG_BING, TG_YI]
# Note: the ORDER is the same, but the DIRECTION of placement differs

# ============================================================
# 宫位飞布顺序 (for star/gate rotation)
# ============================================================
# 九宫顺行 (排除中5): 1→8→3→4→9→2→7→6 (洛书顺序跳过5)
PALACE_FLY_FORWARD = [1, 8, 3, 4, 9, 2, 7, 6]
# 九宫逆行: reverse
PALACE_FLY_BACKWARD = [1, 6, 7, 2, 9, 4, 3, 8]


# ============================================================================
# SECTION 2: QIMEN PAIPAN ENGINE
# ============================================================================

# ============================================================
# 干支历 (Ganzhi Calendar) - Sexagenary cycle calculations
# ============================================================

# Reference point: 甲子日 = a known date
# 2000-01-07 (Friday) is 甲子日 in the sexagenary cycle
# We use this as epoch for day pillar calculation
EPOCH_DATE = datetime(2000, 1, 7)
EPOCH_DAY_GZ = 0  # 甲子 = index 0 in 60-cycle

def ganzhi_index(tg_idx, dz):
    """Convert tiangan index (0-9) and dizhi (0-11) to 60-jiazi index (0-59)"""
    # Find i such that i%10 == tg_idx and i%12 == dz
    for i in range(60):
        if i % 10 == tg_idx and i % 12 == dz:
            return i
    return -1

def ganzhi_from_index(idx):
    """Convert 60-jiazi index to (tiangan_index, dizhi)"""
    return (idx % 10, idx % 12)

def get_day_ganzhi(dt):
    """Get day pillar ganzhi from datetime. Returns (tg_index, dz)"""
    delta = (dt - EPOCH_DATE).days
    idx = (EPOCH_DAY_GZ + delta) % 60
    return ganzhi_from_index(idx)

def get_hour_ganzhi(day_tg_idx, hour):
    """Get hour pillar ganzhi.
    day_tg_idx: day tiangan index (0-9)
    hour: 0-23
    
    时辰 dizhi:
    23:00-01:00 子(0), 01:00-03:00 丑(1), ... 21:00-23:00 亥(11)
    
    时干 follows 五鼠遁元 rule:
    甲己日起甲子时, 乙庚日起丙子时, 丙辛日起戊子时, 丁壬日起庚子时, 戊癸日起壬子时
    """
    # Hour to shichen dizhi
    if hour == 23:
        shichen_dz = 0  # 子时 (late)
    else:
        shichen_dz = ((hour + 1) // 2) % 12
    
    # 五鼠遁元: day stem determines starting hour stem
    # 甲(0)/己(5)→甲子, 乙(1)/庚(6)→丙子, 丙(2)/辛(7)→戊子, 丁(3)/壬(8)→庚子, 戊(4)/癸(9)→壬子
    day_group = day_tg_idx % 5
    start_tg_idx = (day_group * 2) % 10  # 0→0, 1→2, 2→4, 3→6, 4→8
    
    hour_tg_idx = (start_tg_idx + shichen_dz) % 10
    return (hour_tg_idx, shichen_dz)

def get_shichen(hour):
    """Convert hour (0-23) to shichen dizhi (0-11)"""
    if hour == 23:
        return 0
    return ((hour + 1) // 2) % 12

# ============================================================
# 节气 (Solar Terms) - Simplified calculation
# ============================================================

# For a production system, you'd use astronomical calculations or a lookup table.
# Here we use a simplified approximation for 2026.

# 2026 solar terms (approximate dates, London time)
SOLAR_TERMS_2026 = {
    # (month, day): (term_index, term_name)
    # term_index per our encoding: 冬至=0, 小寒=1, ..., 大雪=23
    (1, 5): (1, "小寒"), (1, 20): (2, "大寒"),
    (2, 4): (3, "立春"), (2, 18): (4, "雨水"),
    (3, 5): (5, "惊蛰"), (3, 20): (6, "春分"),
    (4, 4): (7, "清明"), (4, 20): (8, "谷雨"),
    (5, 5): (9, "立夏"), (5, 21): (10, "小满"),
    (6, 5): (11, "芒种"), (6, 21): (12, "夏至"),
    (7, 7): (13, "小暑"), (7, 22): (14, "大暑"),
    (8, 7): (15, "立秋"), (8, 23): (16, "处暑"),
    (9, 7): (17, "白露"), (9, 22): (18, "秋分"),
    (10, 8): (19, "寒露"), (10, 23): (20, "霜降"),
    (11, 7): (21, "立冬"), (11, 22): (22, "小雪"),
    (12, 7): (23, "大雪"), (12, 21): (0, "冬至"),
}

def _solar_longitude(dt):
    """计算太阳黄经（度）"""
    if not HAS_EPHEM:
        return 0
    sun = ephem.Sun()
    obs = ephem.Observer()
    obs.date = dt.strftime('%Y/%m/%d %H:%M:%S')
    sun.compute(obs)
    import math
    # 使用地心视黄经（不是日心黄经hlong）
    eq = ephem.Equatorial(sun.ra, sun.dec, epoch=obs.date)
    ec = ephem.Ecliptic(eq)
    return math.degrees(float(ec.lon))

def _find_jieqi_time(year, target_lon, est_month):
    """二分法查找节气精确时间"""
    if not HAS_EPHEM:
        return None
    import math
    est = datetime(year, est_month, 15)
    lo = est - timedelta(days=35)
    hi = est + timedelta(days=35)
    for _ in range(60):
        mid = lo + (hi - lo) / 2
        lon = _solar_longitude(mid)
        diff = (lon - target_lon + 180) % 360 - 180
        if abs(diff) < 0.0001:
            return mid
        if diff > 0:
            hi = mid
        else:
            lo = mid
    return lo + (hi - lo) / 2

# 节气名称和黄经度数
_JIEQI_NAMES = [
    "冬至","小寒","大寒","立春","雨水","惊蛰",
    "春分","清明","谷雨","立夏","小满","芒种",
    "夏至","小暑","大暑","立秋","处暑","白露",
    "秋分","寒露","霜降","立冬","小雪","大雪"
]

def _get_all_jieqi(year):
    """获取某年前后所有节气"""
    results = []
    for y in [year-1, year, year+1]:
        for i, name in enumerate(_JIEQI_NAMES):
            target_lon = (270 + i * 15) % 360
            # 估算月份
            if name == "冬至": est_m = 12
            elif name in ("小寒","大寒"): est_m = 1
            elif name in ("立春","雨水"): est_m = 2
            elif name in ("惊蛰","春分"): est_m = 3
            elif name in ("清明","谷雨"): est_m = 4
            elif name in ("立夏","小满"): est_m = 5
            elif name in ("芒种","夏至"): est_m = 6
            elif name in ("小暑","大暑"): est_m = 7
            elif name in ("立秋","处暑"): est_m = 8
            elif name in ("白露","秋分"): est_m = 9
            elif name in ("寒露","霜降"): est_m = 10
            elif name in ("立冬","小雪"): est_m = 11
            else: est_m = 12
            
            jq_dt = _find_jieqi_time(y, target_lon, est_m)
            if jq_dt:
                results.append((jq_dt, i, name))
    results.sort(key=lambda x: x[0])
    return results

def get_current_term(dt):
    """Get the current solar term for any date.
    Returns (term_index, term_name, is_yangdun)
    
    Fixed: 使用ephem天文算法计算精确节气，支持任意年份。
    """
    if HAS_EPHEM:
        all_jq = _get_all_jieqi(dt.year)
        current = all_jq[0]
        for jq_dt, idx, name in all_jq:
            if jq_dt <= dt:
                current = (jq_dt, idx, name)
            else:
                break
        _, term_idx, term_name = current
    else:
        # Fallback to 2026 hardcoded table
        terms_sorted = []
        terms_sorted.append((datetime(2025, 12, 22), 0, "冬至"))
        for (m, d), (idx, name) in sorted(SOLAR_TERMS_2026.items()):
            terms_sorted.append((datetime(2026, m, d), idx, name))
        current_term = terms_sorted[0]
        for term_dt, idx, name in terms_sorted:
            if term_dt <= dt:
                current_term = (term_dt, idx, name)
            else:
                break
        _, term_idx, term_name = current_term
    
    is_yangdun = term_idx < 12
    return term_idx, term_name, is_yangdun

# ============================================================
# 局数 (Ju Number) Determination
# ============================================================

# 节气→局数映射
# 阳遁: 冬至/小寒/大寒→1/2/3局(上中下元), 立春/雨水/惊蛰→8/5/2(上中下), etc.
# 按《宝鉴》: 冬至甲子起坎(1), 小寒大寒随之; 立春甲子起艮(8), 雨水惊蛰随之

YANGDUN_JU = {
    # term_index: (上元局数, 中元局数, 下元局数)
    0: (1, 7, 4),   # 冬至
    1: (2, 8, 5),   # 小寒
    2: (3, 9, 6),   # 大寒
    3: (8, 5, 2),   # 立春
    4: (9, 6, 3),   # 雨水
    5: (1, 7, 4),   # 惊蛰
    6: (3, 9, 6),   # 春分
    7: (4, 1, 7),   # 清明
    8: (5, 2, 8),   # 谷雨
    9: (4, 1, 7),   # 立夏
    10: (5, 2, 8),  # 小满
    11: (6, 3, 9),  # 芒种
}

YINDUN_JU = {
    12: (9, 3, 6),  # 夏至
    13: (8, 2, 5),  # 小暑
    14: (7, 1, 4),  # 大暑
    15: (2, 5, 8),  # 立秋
    16: (1, 4, 7),  # 处暑
    17: (9, 3, 6),  # 白露
    18: (7, 1, 4),  # 秋分
    19: (6, 9, 3),  # 寒露
    20: (5, 8, 2),  # 霜降
    21: (6, 9, 3),  # 立冬
    22: (5, 8, 2),  # 小雪
    23: (4, 7, 1),  # 大雪
}

def get_sanyuan(day_tg_idx, day_dz):
    """Determine 三元 (upper/middle/lower) from day pillar.
    
    Per《宝鉴》: 符头为甲己之日。
    符头地支: 子午卯酉→上元, 寅申巳亥→中元, 辰戌丑未→下元
    """
    # Find the fuutou (符头): the most recent 甲 or 己 day
    # 甲=0, 己=5 in tg_idx
    # The current day's tg_idx tells us how far we are from the last 甲/己 day
    if day_tg_idx >= 5:
        days_since_futou = day_tg_idx - 5
        futou_tg = 5  # 己
    else:
        days_since_futou = day_tg_idx
        futou_tg = 0  # 甲
    
    # 符头地支 = day_dz - days_since_futou (mod 12)
    futou_dz = (day_dz - days_since_futou) % 12
    
    if futou_dz in (DZ_ZI, DZ_WU, DZ_MAO, DZ_YOU):
        return 0  # 上元
    elif futou_dz in (DZ_YIN, DZ_SHEN, DZ_SI, DZ_HAI):
        return 1  # 中元
    else:  # 辰戌丑未
        return 2  # 下元

def get_ju_number(term_idx, sanyuan, is_yangdun):
    """Get the ju number (1-9) from term and sanyuan"""
    if is_yangdun:
        return YANGDUN_JU[term_idx][sanyuan]
    else:
        return YINDUN_JU[term_idx][sanyuan]

# ============================================================
# 地盘布局 (Ground Plate Layout)
# ============================================================

def layout_ground_plate(ju_number, is_yangdun):
    """Layout the ground plate stems.
    
    Per《宝鉴》:
    阳遁: 甲子戊起于局数对应宫, 六仪顺布(宫号递增), 三奇逆布(丁丙乙按宫号递增紧跟)
    阴遁: 甲子戊起于局数对应宫, 六仪逆布(宫号递减), 三奇顺布(丁丙乙按宫号递减紧跟)
    
    《宝鉴》阳遁一局example: 戊坎1→己坤2→庚震3→辛巽4→壬中5→癸乾6→丁兑7→丙艮8→乙离9
    → 顺序就是宫号 1,2,3,4,5,6,7,8,9
    
    《宝鉴》阴遁九局example: 戊离9→己艮8→庚兑7→辛乾6→壬中5→癸巽4→丁震3→丙坤2→乙坎1
    → 逆序就是宫号 9,8,7,6,5,4,3,2,1
    
    Returns dict: {palace_number: stem}
    """
    # Sequential palace order: 1,2,3,4,5,6,7,8,9
    PALACE_SEQ = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    
    # 9 stems in order: 戊己庚辛壬癸丁丙乙
    stems = YANG_STEM_ORDER  # [戊, 己, 庚, 辛, 壬, 癸, 丁, 丙, 乙]
    
    ground = {}
    start_idx = PALACE_SEQ.index(ju_number)  # Where 戊 starts
    
    for i, stem in enumerate(stems):
        if is_yangdun:
            palace_idx = (start_idx + i) % 9
        else:
            palace_idx = (start_idx - i) % 9
        palace = PALACE_SEQ[palace_idx]
        ground[palace] = stem
    
    return ground

# ============================================================
# 天盘布局 (Heaven Plate - Stars and Stems rotation)
# ============================================================

def get_xun_head_for_hour(hour_tg_idx, hour_dz):
    """Find which 六甲旬首 the current hour belongs to.
    Returns xun index (0-5)."""
    return get_xun_from_ganzhi(hour_tg_idx, hour_dz)

def layout_heaven_plate(ground, xun_index, is_yangdun):
    """Layout the heaven plate by rotating stems based on 直符加时干.
    
    直符 follows the hour stem:
    1. Find 旬首 (which 甲 the hour belongs to)
    2. 旬首遁于某仪 → that 仪 is on ground plate at some palace → that's 直符's home
    3. 直符 flies to the palace where the hour stem sits on the ground plate
    4. All other stems rotate accordingly
    
    Returns dict: {palace_number: stem}
    """
    # Step 1: Find the 六仪 that hides this xun's 甲
    dun_stem = JIAZI_DUN[xun_index]
    
    # Step 2: Find where that stem is on the ground plate
    zhifu_home = None
    for palace, stem in ground.items():
        if stem == dun_stem and palace != 5:  # Skip center
            zhifu_home = palace
            break
    
    if zhifu_home is None:
        zhifu_home = 1  # Fallback
    
    # Step 3: Find where the hour stem is on the ground plate
    # The hour stem = the time stem from the tiangan of the hour
    # But actually, 直符加时干 means: 直符 goes to the palace where
    # the hour's 天干 sits on the ground plate
    # 
    # Wait - re-reading《宝鉴》: "看天上直符，原在何宫，取其随时干所到之宫"
    # Meaning: find which ground palace has the hour stem, 直符 goes there
    
    # For the hour stem, we need to find which of the 9 stems it matches
    # Hour stem is one of the 10 tiangan; on the ground plate we only have 9 (excl 甲)
    # If hour stem is 甲, it's hidden - use the corresponding 六仪
    
    return _rotate_stems(ground, zhifu_home, is_yangdun)

def _rotate_stems(ground, zhifu_home, is_yangdun):
    """Rotate all stems: 直符's home stem goes to hour stem's palace position.
    For simplicity in this version, we compute based on the offset."""
    # The heaven plate is the ground plate rotated so that
    # the stem at zhifu_home moves to the hour stem's palace
    # For now, return ground as-is (to be refined with actual rotation)
    # This is a simplified version - full rotation requires knowing the hour stem palace
    return dict(ground)

# ============================================================
# 九星排布 (Star Layout)
# ============================================================

def layout_stars(zhifu_star, zhifu_palace, is_yangdun):
    """Layout 9 stars. 直符星 goes to zhifu_palace, others follow in order.
    
    Stars rotate in the same direction as the 遁 type:
    阳遁顺行, 阴遁逆行 (in palace fly order)
    """
    stars = {}
    
    # 直符星's home palace index in fly order
    home_idx = PALACE_FLY_FORWARD.index(STAR_HOME_PALACE[zhifu_star])
    # Target palace index
    target_idx = PALACE_FLY_FORWARD.index(zhifu_palace) if zhifu_palace in PALACE_FLY_FORWARD else 0
    # Offset
    offset = target_idx - home_idx
    
    # All 8 stars (excluding 天禽 which stays in center/寄坤)
    movable_stars = [s for s in range(9) if s != STAR_QIN]
    
    for star in movable_stars:
        star_home_idx = PALACE_FLY_FORWARD.index(STAR_HOME_PALACE[star])
        new_idx = (star_home_idx + offset) % 8
        new_palace = PALACE_FLY_FORWARD[new_idx]
        stars[new_palace] = star
    
    # 天禽寄坤
    if 2 in stars:
        pass  # 天禽 shares with whatever is in palace 2
    stars[5] = STAR_QIN  # Mark center
    
    return stars

# ============================================================
# 八门排布 (Gate Layout)  
# ============================================================

def layout_gates(zhishi_gate, zhishi_palace, is_yangdun):
    """Layout 8 gates. 直使门 goes to zhishi_palace, others follow.
    
    直使加时支: 直使 follows the hour branch to its palace.
    """
    gates = {}
    
    home_idx = PALACE_FLY_FORWARD.index(GATE_HOME_PALACE[zhishi_gate])
    target_idx = PALACE_FLY_FORWARD.index(zhishi_palace) if zhishi_palace in PALACE_FLY_FORWARD else 0
    offset = target_idx - home_idx
    
    for gate in range(8):
        gate_home_idx = PALACE_FLY_FORWARD.index(GATE_HOME_PALACE[gate])
        new_idx = (gate_home_idx + offset) % 8
        new_palace = PALACE_FLY_FORWARD[new_idx]
        gates[new_palace] = gate
    
    return gates

# ============================================================
# 八神排布 (Deity Layout)
# ============================================================

def layout_deities(zhifu_palace, is_yangdun):
    """Layout 8 deities. 直符 goes to zhifu_palace, others follow in order.
    阳遁顺布, 阴遁逆布.
    """
    deities = {}
    order = DEITY_ORDER_YANG if is_yangdun else DEITY_ORDER_YIN
    
    start_idx = PALACE_FLY_FORWARD.index(zhifu_palace) if zhifu_palace in PALACE_FLY_FORWARD else 0
    
    for i, deity in enumerate(order):
        if is_yangdun:
            palace_idx = (start_idx + i) % 8
        else:
            palace_idx = (start_idx - i) % 8
        palace = PALACE_FLY_FORWARD[palace_idx]
        deities[palace] = deity
    
    return deities

# ============================================================
# 完整排盘 (Complete Paipan)
# ============================================================

class QimenJu:
    """Complete Qimen ju data structure"""
    
    def __init__(self):
        # Metadata
        self.is_yangdun = True
        self.ju_number = 1
        self.term_idx = 0
        self.term_name = ""
        self.sanyuan = 0  # 0=上, 1=中, 2=下
        
        # Four pillars
        self.year_gz = (0, 0)    # (tg_idx, dz)
        self.month_gz = (0, 0)
        self.day_gz = (0, 0)
        self.hour_gz = (0, 0)
        
        # Xun
        self.xun_index = 0
        self.kongwang = (0, 0)
        
        # Plates
        self.ground = {}      # palace -> stem
        self.heaven = {}      # palace -> stem  
        self.stars = {}       # palace -> star
        self.gates = {}       # palace -> gate
        self.deities = {}     # palace -> deity
        
        # Duty
        self.zhifu_star = 0
        self.zhifu_palace = 1
        self.zhishi_gate = 0
        self.zhishi_palace = 1
        
        # Derived
        self.month_branch = 0  # For 旺衰 calculation
    
    def display(self):
        """Pretty print the ju"""
        print("=" * 60)
        print(f"奇门局: {'阳' if self.is_yangdun else '阴'}遁{self.ju_number}局")
        print(f"节气: {self.term_name} | 三元: {['上','中','下'][self.sanyuan]}元")
        
        day_tg = TIANGAN_NAMES[TIANGAN_BY_INDEX[self.day_gz[0]]]
        day_dz = DIZHI_NAMES[self.day_gz[1]]
        hour_tg = TIANGAN_NAMES[TIANGAN_BY_INDEX[self.hour_gz[0]]]
        hour_dz = DIZHI_NAMES[self.hour_gz[1]]
        print(f"日柱: {day_tg}{day_dz} | 时柱: {hour_tg}{hour_dz}")
        
        k1, k2 = self.kongwang
        print(f"旬首: 甲{DIZHI_NAMES[XUN_HEAD_DIZHI[self.xun_index]]}旬 | 空亡: {DIZHI_NAMES[k1]}{DIZHI_NAMES[k2]}")
        
        print(f"直符: {STAR_NAMES[self.zhifu_star]}(落{GONG_GUA_NAMES[self.zhifu_palace]}宫)")
        print(f"直使: {GATE_NAMES[self.zhishi_gate]}(落{GONG_GUA_NAMES[self.zhishi_palace]}宫)")
        
        print("-" * 60)
        print(f"{'宫':>4} {'地盘':>4} {'天盘':>4} {'九星':>6} {'八门':>6} {'八神':>6}")
        print("-" * 60)
        
        for p in [4, 9, 2, 3, 5, 7, 8, 1, 6]:  # 九宫格顺序
            g_stem = self.ground.get(p)
            h_stem = self.heaven.get(p)
            star = self.stars.get(p)
            gate = self.gates.get(p)
            deity = self.deities.get(p)
            
            g_name = TIANGAN_NAMES.get(g_stem, "  ") if g_stem is not None else "  "
            h_name = TIANGAN_NAMES.get(h_stem, "  ") if h_stem is not None else "  "
            s_name = STAR_NAMES.get(star, "    ") if star is not None else "    "
            gt_name = GATE_NAMES.get(gate, "    ") if gate is not None else "    "
            d_name = DEITY_NAMES.get(deity, "    ") if deity is not None else "    "
            
            print(f"{GONG_GUA_NAMES[p]:>4} {g_name:>4} {h_name:>4} {s_name:>6} {gt_name:>6} {d_name:>6}")
        
        print("=" * 60)
    
    def get_hexagram_binary(self):
        """Extract the FCAS 6-bit hexagram from this ju.
        
        Per design: upper trigram from 直符星's home gua,
                    lower trigram from 直符落宫's gua.
        Returns 6-bit integer and breakdown.
        """
        upper = GONG_TO_TRIGRAM[STAR_HOME_PALACE[self.zhifu_star]]
        lower = GONG_TO_TRIGRAM[self.zhifu_palace]
        
        hexagram = (upper << 3) | lower
        
        # Decode to C1-C6
        c5 = hexagram & 1          # 初爻 (LSB)
        c6 = (hexagram >> 1) & 1   # 二爻
        c3 = (hexagram >> 2) & 1   # 三爻
        c4 = (hexagram >> 3) & 1   # 四爻
        c1 = (hexagram >> 4) & 1   # 五爻
        c2 = (hexagram >> 5) & 1   # 上爻 (MSB)
        
        return {
            'binary': hexagram,
            'binary_str': f"{hexagram:06b}",
            'upper_trigram': upper,
            'lower_trigram': lower,
            'C1': c1, 'C2': c2, 'C3': c3, 'C4': c4, 'C5': c5, 'C6': c6
        }


def paipan(dt):
    """Main entry point: given a datetime, produce a complete QimenJu.
    
    Args:
        dt: datetime object (assumed to be in the local timezone relevant for calculation)
    
    Returns:
        QimenJu instance
    """
    ju = QimenJu()
    
    # === Step 1: Determine 节气 and 阴阳遁 ===
    term_idx, term_name, is_yangdun = get_current_term(dt)
    ju.term_idx = term_idx
    ju.term_name = term_name
    ju.is_yangdun = is_yangdun

    # === Step 2: Day pillar ===
    day_tg_idx, day_dz = get_day_ganzhi(dt)
    ju.day_gz = (day_tg_idx, day_dz)

    # === Step 3: Hour pillar ===
    hour_tg_idx, hour_dz = get_hour_ganzhi(day_tg_idx, dt.hour)
    ju.hour_gz = (hour_tg_idx, hour_dz)

    # === Step 4: 三元 and 局数（含超神检测）===
    # 超神: 符头落在上一节气周期内 → 沿用上一节气的局数
    # 依据《宝鉴》: 超神接气置闰法
    sanyuan = get_sanyuan(day_tg_idx, day_dz)
    ju.sanyuan = sanyuan

    # 计算符头日期
    _days_since_futou = day_tg_idx - 5 if day_tg_idx >= 5 else day_tg_idx
    _futou_dt = dt - timedelta(days=_days_since_futou)

    # 找当前节气起始日（向前扫描，用午夜时刻保持日期一致性）
    # 注: 节气时刻在日内，用午夜确保同一天统一归属
    _dt_midnight = datetime(dt.year, dt.month, dt.day)
    _term_start = _dt_midnight
    for _back in range(1, 25):
        _check = _dt_midnight - timedelta(days=_back)
        _ct, _, _ = get_current_term(_check)
        if _ct != term_idx:
            _term_start = _dt_midnight - timedelta(days=_back - 1)
            break

    _chaoshen = _futou_dt.date() < _term_start.date()
    ju.chaoshen = _chaoshen

    if _chaoshen:
        # 超神: 使用上一节气的 term_idx / is_yangdun
        _prev_day = _term_start - timedelta(days=1)
        _prev_term_idx, _prev_name, _prev_yangdun = get_current_term(_prev_day)
        _prev_tg, _prev_dz = get_day_ganzhi(_prev_day)
        _prev_sy = get_sanyuan(_prev_tg, _prev_dz)
        ju.ju_number = get_ju_number(_prev_term_idx, _prev_sy, _prev_yangdun)
        # 注: 阴阳遁跟节气走，超神时局数用上一节气，但阴阳遁也随之
        ju.is_yangdun = _prev_yangdun
        ju.term_idx = _prev_term_idx
        ju.term_name = _prev_name + '(超神)'
    else:
        ju.ju_number = get_ju_number(term_idx, sanyuan, is_yangdun)
    
    # === Step 5: 旬首 and 空亡 ===
    # 空亡/旬首 display uses the DAY's xun; heaven-plate mechanics use the HOUR's xun
    day_xun_index = get_xun_from_ganzhi(day_tg_idx, day_dz)
    xun_index = get_xun_from_ganzhi(hour_tg_idx, hour_dz)
    ju.xun_index = day_xun_index   # for display and 空亡
    ju.kongwang = get_xunkong(day_xun_index)
    
    # === Step 6: Month branch (for 旺衰) ===
    # Simplified: use the term to approximate month branch
    # 立春后=寅月, 惊蛰后=卯月, etc.
    month_branches = {
        3: DZ_YIN, 4: DZ_YIN, 5: DZ_MAO, 6: DZ_MAO,
        7: DZ_CHEN, 8: DZ_CHEN, 9: DZ_SI, 10: DZ_SI,
        11: DZ_WU, 12: DZ_WU, 13: DZ_WEI, 14: DZ_WEI,
        15: DZ_SHEN, 16: DZ_SHEN, 17: DZ_YOU, 18: DZ_YOU,
        19: DZ_XU, 20: DZ_XU, 21: DZ_HAI, 22: DZ_HAI,
        23: DZ_ZI, 0: DZ_ZI, 1: DZ_CHOU, 2: DZ_CHOU,
    }
    ju.month_branch = month_branches.get(term_idx, DZ_YIN)
    
    # === Step 7: Ground plate ===
    ju.ground = layout_ground_plate(ju.ju_number, is_yangdun)
    
    # === Step 8: Find 直符 and 直使 ===
    # 旬首所遁之仪在地盘的宫 → 该宫的星=直符, 该宫的门=直使
    dun_stem = JIAZI_DUN[xun_index]

    # 天禽寄宫: 阳遁寄坤2宫, 阴遁寄艮8宫
    # 依据《刘文元奇门启悟》: "阳遁寄坤2宫，阴遁寄艮8宫之法，是符合易理的。"
    # 《宝鉴》: "阳遁阴遁，俱寄坤宫。一本：阳遁寄坤，阴遁寄艮。"
    tianqin_host = 2 if is_yangdun else 8
    ju.tianqin_host = tianqin_host  # expose for downstream use

    zhifu_home = None
    for palace, stem in ju.ground.items():
        if stem == dun_stem:
            if palace == 5:
                # 中5宫 → 天禽寄宫（阳遁坤2，阴遁艮8）
                zhifu_home = tianqin_host
            else:
                zhifu_home = palace
            break
    if zhifu_home is None:
        zhifu_home = tianqin_host  # Fallback

    # 直符星 = home palace's star
    for star, home_p in STAR_HOME_PALACE.items():
        if home_p == zhifu_home:
            ju.zhifu_star = star
            break

    # 直使门 = home palace's gate
    for gate, home_p in GATE_HOME_PALACE.items():
        if home_p == zhifu_home:
            ju.zhishi_gate = gate
            break

    # === Step 9: 直符加时干 - determine where 直符 flies to ===
    # Find the palace where the hour stem sits on the ground plate
    hour_stem = TIANGAN_BY_INDEX[hour_tg_idx]

    # If hour stem is 甲, use the corresponding 六仪
    if hour_stem == TG_JIA:
        hour_stem = dun_stem

    zhifu_target = None
    for palace, stem in ju.ground.items():
        if stem == hour_stem:
            if palace == 5:
                zhifu_target = tianqin_host  # 动态寄宫
            else:
                zhifu_target = palace
            break
    if zhifu_target is None:
        zhifu_target = tianqin_host  # Fallback

    ju.zhifu_palace = zhifu_target

    # === Step 10: 直使加时支 ===
    # 直使 follows the hour branch
    # Per《宝鉴》: "直使随时支转宫"
    # offset = number of time stems from 旬首 to current hour
    # This equals (hour_dz - xun_head_dz + 12) % 12
    # But gates rotate through 9 palaces (including center), not 12
    # The offset counts how many shichen have passed, and the gate
    # moves that many palaces forward (阳遁) or backward (阴遁)
    xun_head_dz = XUN_HEAD_DIZHI[xun_index]
    offset = (hour_dz - xun_head_dz + 12) % 12

    PALACE_SEQ = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    zhishi_home = GATE_HOME_PALACE[ju.zhishi_gate]
    zhishi_home_idx = PALACE_SEQ.index(zhishi_home)

    if is_yangdun:
        zhishi_target_idx = (zhishi_home_idx + offset) % 9
    else:
        zhishi_target_idx = (zhishi_home_idx - offset) % 9

    ju.zhishi_palace = PALACE_SEQ[zhishi_target_idx]

    # === Step 11: Layout stars (外环旋转, 天禽寄宫动态) ===
    # 转盘法: 九星按外环[1,8,3,4,9,2,7,6]整体旋转
    RING = PALACE_FLY_FORWARD  # [1, 8, 3, 4, 9, 2, 7, 6]

    # 值符星原位和目标位在外环的索引（中5宫用动态寄宫替代）
    zhifu_home_ring = tianqin_host if zhifu_home == 5 else zhifu_home
    zhifu_target_ring = tianqin_host if zhifu_target == 5 else zhifu_target

    from_idx = RING.index(zhifu_home_ring)
    to_idx = RING.index(zhifu_target_ring)
    star_steps = (to_idx - from_idx) % 8

    star_layout = {}
    for star in range(9):
        if star == STAR_QIN:
            continue  # 天禽固定寄宫
        home_p = STAR_HOME_PALACE[star]
        home_ring = tianqin_host if home_p == 5 else home_p
        ring_idx = RING.index(home_ring)
        new_ring_idx = (ring_idx + star_steps) % 8
        new_palace = RING[new_ring_idx]
        star_layout[new_palace] = star
    star_layout[5] = STAR_QIN  # 天禽标记在中5宫（实际落宫见tianqin_host）
    ju.stars = star_layout
    
    # === Step 12: Layout heaven plate stems (FIXED: 星带地盘干走) ===
    # 天盘天干 = 移到该宫的星所携带的原位地盘干
    # 天禽在中5宫，其天干来自动态寄宫的地盘干
    heaven = {}
    for new_palace, star in star_layout.items():
        if star == STAR_QIN:
            heaven[5] = ju.ground.get(5, ju.ground.get(tianqin_host))
            continue
        star_home = STAR_HOME_PALACE[star]
        heaven[new_palace] = ju.ground[star_home]
    ju.heaven = heaven
    
    # === Step 13: Layout gates (FIXED v2: 值使加时支) ===
    # 八门旋转步数 ≠ 九星步数
    # 八门步数 = 值使门从本位到zhishi_palace在外环上的偏移量
    # 值使目标宫zhishi_palace已在Step 10中通过"值使加时支"正确计算
    gate_layout = {}
    
    # 计算八门旋转步数
    zhishi_home_gate = GATE_HOME_PALACE[ju.zhishi_gate]
    zhishi_home_ring = 2 if zhishi_home_gate == 5 else zhishi_home_gate
    zhishi_target_ring = 2 if ju.zhishi_palace == 5 else ju.zhishi_palace
    
    gate_from_idx = RING.index(zhishi_home_ring)
    gate_to_idx = RING.index(zhishi_target_ring)
    gate_steps = (gate_to_idx - gate_from_idx) % 8
    
    for gate in range(8):
        home_p = GATE_HOME_PALACE[gate]
        home_ring = 2 if home_p == 5 else home_p
        if home_ring not in RING:
            continue
        ring_idx = RING.index(home_ring)
        new_ring_idx = (ring_idx + gate_steps) % 8  # 用八门自己的步数
        new_palace = RING[new_ring_idx]
        gate_layout[new_palace] = gate
    ju.gates = gate_layout
    
    # === Step 14: Layout deities (FIXED: 外环旋转) ===
    # 八神: 值符落宫起，阳遁顺时针，阴遁逆时针
    deity_layout = {}
    order = DEITY_ORDER_YANG if is_yangdun else DEITY_ORDER_YIN
    
    zhifu_p = ju.zhifu_palace
    if zhifu_p == 5:
        zhifu_p = 2
    start_idx_d = RING.index(zhifu_p)
    
    for i, deity in enumerate(order):
        if is_yangdun:
            ring_idx = (start_idx_d + i) % 8
        else:
            ring_idx = (start_idx_d - i) % 8
        palace = RING[ring_idx]
        deity_layout[palace] = deity
    ju.deities = deity_layout
    
    return ju


# ============================================================
# Verification helper
# ============================================================

def verify_with_known(dt, expected_desc=""):
    """Run paipan and display results for verification"""
    print(f"\n排盘时间: {dt.strftime('%Y-%m-%d %H:%M')} ({expected_desc})")
    ju = paipan(dt)
    ju.display()
    
    hex_info = ju.get_hexagram_binary()
    print(f"\nFCAS二进制: {hex_info['binary_str']}")
    print(f"C2={hex_info['C2']} C1={hex_info['C1']} C4={hex_info['C4']} C3={hex_info['C3']} C6={hex_info['C6']} C5={hex_info['C5']}")
    
    # Decode trigrams
    upper_names = {v: k for k, v in GONG_TO_TRIGRAM.items()}
    lower_names = {v: k for k, v in GONG_TO_TRIGRAM.items()}
    upper_gong = None
    lower_gong = None
    for gong, tri in GONG_TO_TRIGRAM.items():
        if tri == hex_info['upper_trigram'] and upper_gong is None:
            upper_gong = gong
        if tri == hex_info['lower_trigram'] and lower_gong is None:
            lower_gong = gong
    
    print(f"上卦: {GONG_GUA_NAMES.get(upper_gong, '?')}({hex_info['upper_trigram']:03b})")
    print(f"下卦: {GONG_GUA_NAMES.get(lower_gong, '?')}({hex_info['lower_trigram']:03b})")
    
    return ju


# ============================================================================
# SECTION 3: GEJU PATTERN MATCHING
# ============================================================================

# ============================================================
# Geju result structure
# ============================================================

class GejuResult:
    def __init__(self, name, name_biz, jixiong, severity, palace, description):
        self.name = name          # 格局名 (traditional)
        self.name_biz = name_biz  # 商业语言名
        self.jixiong = jixiong    # 1=吉, 0=凶
        self.severity = severity  # 0=轻, 1=中, 2=重, 3=极
        self.palace = palace      # 发生在哪个宫 (or None for global)
        self.description = description
    
    def __repr__(self):
        jx = "吉" if self.jixiong else "凶"
        sv = ["轻","中","重","极"][self.severity]
        p = f"({GONG_GUA_NAMES.get(self.palace, '全局')}宫)" if self.palace else "(全局)"
        return f"[{jx}{sv}] {self.name} / {self.name_biz} {p}: {self.description}"


# ============================================================
# 天干加临格局 (Stem Overlay Patterns)
# Per《宝鉴》卷二 "六仪加十干诸格" & 卷五 凶格/吉格章节
# ============================================================

def evaluate_stem_overlays(ju):
    """Check all heaven-over-ground stem combinations for known patterns.
    
    Complete 100-entry table per《宝鉴》卷二"混合百神"chapter.
    Key: (heaven_stem, ground_stem) → (name, name_biz, jixiong, severity, description)
    
    Returns list of GejuResult.
    """
    # Full lookup table: (天盘干, 地盘干) → geju definition
    # jixiong: 1=吉, 0=凶, -1=context-dependent
    # severity: 0=轻, 1=中, 2=重
    STEM_OVERLAY_TABLE = {
        # === 六甲(戊)加十干 ===
        (TG_WU, TG_WU): ("青龙出地", "Dragon Emerges", 1, 1, "喜信必来，门合则美"),
        (TG_WU, TG_YI): ("青龙入云", "Dragon Enters Cloud", 1, 1, "利阴私和合"),
        (TG_WU, TG_BING): ("青龙返首", "Dragon Returns", 1, 2, "凡事亨通，兼得长久"),
        (TG_WU, TG_DING): ("青龙耀明", "Dragon Shines", 1, 1, "宜谒贵人，改官迁职"),
        (TG_WU, TG_JI): ("青龙合灵", "Dragon Joins Spirit", 1, 1, "吉星主财，吉门事成"),
        (TG_WU, TG_GENG): ("青龙符格", "Dragon Blocked", 0, 1, "起咎成凶，宜静默"),
        (TG_WU, TG_XIN): ("青龙失惊", "Dragon Startled", 0, 0, "门合万事从心，凶星财利亡倾"),
        (TG_WU, TG_REN): ("青龙网罗", "Dragon Ensnared", 0, 1, "阴人灾祸，诡谲不和"),
        (TG_WU, TG_GUI): ("青龙华盖", "Dragon Canopy", -1, 0, "门合吉星永无灾害，伤死门凶"),
        # === 六乙加十干 ===
        (TG_YI, TG_WU): ("日入地户", "Sun Enters Earth Gate", -1, 0, "宜隐伏藏形"),
        (TG_YI, TG_YI): ("日奇伏刑", "Sun Wonder Hidden", 0, 0, "贵人问主失名"),
        (TG_YI, TG_BING): ("奇仪顺格", "Wonder Aligned", 1, 1, "吉星授官迁职"),
        (TG_YI, TG_DING): ("奇仪相佐", "Wonders Assist", 1, 1, "利见贵人，财禄丰盛"),
        (TG_YI, TG_JI): ("日奇入墓", "Sun Wonder Entombed", 0, 1, "暗昧不明，百事不成"),
        (TG_YI, TG_GENG): ("日奇被刑", "Sun Wonder Punished", 0, 1, "门中虽吉，事多缠绵"),
        (TG_YI, TG_XIN): ("青龙逃走", "Dragon Flees", 0, 1, "木受金克，破财遗失"),
        (TG_YI, TG_REN): ("日奇入地", "Sun Enters Ground", -1, 0, "阴暗晦滞"),
        (TG_YI, TG_GUI): ("日奇华盖", "Sun Wonder Canopy", -1, 0, "隐遁吉，出行不利"),
        # === 六丙加十干 ===
        (TG_BING, TG_WU): ("飞鸟跌穴", "Phoenix Landing", 1, 2, "主客皆利，出战远行吉"),
        (TG_BING, TG_YI): ("日月并行", "Sun Moon Together", 1, 1, "公谋私事皆利"),
        (TG_BING, TG_BING): ("月奇悖格", "Moon Wonder Conflict", 0, 0, "文书逼迫，破耗遗失"),
        (TG_BING, TG_DING): ("月奇朱雀", "Moon Sparrow", -1, 0, "有文书口舌事"),
        (TG_BING, TG_JI): ("火悖地户", "Fire Conflicts Gate", 0, 0, "文书阻塞"),
        (TG_BING, TG_GENG): ("荧入太白", "Fire Into Metal", 0, 2, "速战可胜，迟则反受害"),
        (TG_BING, TG_XIN): ("月奇受制", "Moon Controlled", 0, 1, "谋事不成"),
        (TG_BING, TG_REN): ("火入天罗", "Fire Into Net", 0, 1, "壬水克丙火，百事不利"),
        (TG_BING, TG_GUI): ("月奇华盖", "Moon Wonder Canopy", -1, 0, "隐遁吉，余事不利"),
        # === 六丁加十干 ===
        (TG_DING, TG_WU): ("阴阳化气", "Yin-Yang Synthesis", 1, 2, "利为百事"),
        (TG_DING, TG_YI): ("龙凤呈祥", "Dragon-Phoenix Auspice", 1, 2, "利为百事"),
        (TG_DING, TG_BING): ("星月相会", "Star Moon Meet", 1, 1, "贵人指引"),
        (TG_DING, TG_DING): ("星奇入太阴", "Star in Taiyin", 1, 0, "文书阴私事吉"),
        (TG_DING, TG_JI): ("火入勾陈", "Fire Enters Hook", 0, 0, "事涉嫌疑"),
        (TG_DING, TG_GENG): ("星奇受制", "Star Controlled", 0, 1, "庚金克丁火，文书口舌"),
        (TG_DING, TG_XIN): ("朱雀入狱", "Sparrow Jailed", 0, 1, "罪人自陷"),
        (TG_DING, TG_REN): ("星奇入地", "Star Enters Ground", -1, 0, "丁壬虽合，然为淫合"),
        (TG_DING, TG_GUI): ("朱雀投江", "Sparrow Falls River", 0, 1, "火入水，文书牵连口舌"),
        # === 六己加十干 ===
        (TG_JI, TG_WU): ("明堂从禄", "Hall Follows Fortune", 1, 0, "吉事增福"),
        (TG_JI, TG_YI): ("地户逢星", "Gate Meets Star", 1, 0, "利阴私和合"),
        (TG_JI, TG_BING): ("地户埋光", "Gate Buries Light", 0, 0, "丙火入坤墓"),
        (TG_JI, TG_DING): ("明堂贪生", "Hall Seeks Life", 1, 0, "利见贵人"),
        (TG_JI, TG_JI): ("明堂重逢", "Hall Reunites", -1, 0, "地户重合"),
        (TG_JI, TG_GENG): ("明堂伏杀", "Hall Hidden Kill", 0, 1, "金克木，凶险"),
        (TG_JI, TG_XIN): ("天庭得势", "Court Gains Power", -1, 0, "宜谋略"),
        (TG_JI, TG_REN): ("明堂被刑", "Hall Punished", 0, 0, "刑害之事"),
        (TG_JI, TG_GUI): ("明堂华盖", "Hall Canopy", -1, 0, "地户遇合"),
        # === 六庚加十干 ===
        (TG_GENG, TG_WU): ("太白入甲", "Metal Enters Shield", 0, 2, "庚克甲，下克上臣逆君"),
        (TG_GENG, TG_YI): ("太白贪合", "Metal Seeks Union", -1, 0, "乙庚合，为客不利"),
        (TG_GENG, TG_BING): ("太白入荧", "Metal Invades Fire", 0, 2, "贼兵即来偷营劫寨"),
        (TG_GENG, TG_DING): ("太白受制", "Metal Controlled", -1, 0, "丁火制庚金"),
        (TG_GENG, TG_JI): ("刑格", "Punishment Block", 0, 2, "主刑伤破败，车破马倒"),
        (TG_GENG, TG_GENG): ("太白重刑", "Double Metal Punishment", 0, 2, "战则两败俱伤"),
        (TG_GENG, TG_XIN): ("太白重锋", "Double Metal Edge", 0, 1, "白虎出林"),
        (TG_GENG, TG_REN): ("小格", "Minor Block", 0, 1, "行路迷程不能前进"),
        (TG_GENG, TG_GUI): ("大格", "Major Block", 0, 1, "阻塞不通"),
        # === 六辛加十干 ===
        (TG_XIN, TG_WU): ("天庭入狱", "Court Enters Prison", 0, 0, "凶星不吉"),
        (TG_XIN, TG_YI): ("白虎猖狂", "Tiger Rampant", 0, 2, "金克木，凡事皆凶"),
        (TG_XIN, TG_BING): ("天庭坐明", "Court Sits Bright", -1, 0, "丙火制辛金"),
        (TG_XIN, TG_DING): ("天庭得奇", "Court Gets Wonder", 1, 0, "丁火炼辛金成器"),
        (TG_XIN, TG_JI): ("天庭入墓", "Court Entombed", 0, 1, "辛金入己土墓"),
        (TG_XIN, TG_GENG): ("白虎出力", "Tiger Exerts", 0, 1, "官非争讼"),
        (TG_XIN, TG_XIN): ("天庭伏宫", "Court Hidden", 0, 0, "自刑不利"),
        (TG_XIN, TG_REN): ("天庭受刑", "Court Punished", 0, 0, "凶"),
        (TG_XIN, TG_GUI): ("天庭网罗", "Court Ensnared", 0, 0, "不吉"),
        # === 六壬加十干 ===
        (TG_REN, TG_WU): ("天牢入甲", "Prison Enters Shield", 0, 0, "壬水入戊土墓"),
        (TG_REN, TG_YI): ("天牢逢星", "Prison Meets Star", -1, 0, "宜阴私"),
        (TG_REN, TG_BING): ("天牢克火", "Prison Conquers Fire", 0, 1, "壬水克丙火"),
        (TG_REN, TG_DING): ("天牢合朱", "Prison Joins Sparrow", -1, 0, "壬丁合，阴私事"),
        (TG_REN, TG_JI): ("天牢入地", "Prison Enters Earth", -1, 0, "土克水，晦暗"),
        (TG_REN, TG_GENG): ("太白退位", "Metal Retreats", 0, 0, "庚壬不利"),
        (TG_REN, TG_XIN): ("天牢华盖", "Prison Canopy", -1, 0, "宜隐遁"),
        (TG_REN, TG_REN): ("天牢重锁", "Double Prison", 0, 1, "百事不利"),
        (TG_REN, TG_GUI): ("天牢地网", "Prison Ground Net", 0, 1, "上下皆水，凶"),
        # === 六癸加十干 ===
        (TG_GUI, TG_WU): ("天藏入甲", "Vault Enters Shield", -1, 0, "隐伏"),
        (TG_GUI, TG_YI): ("天藏逢星", "Vault Meets Star", -1, 0, "宜阴私暗事"),
        (TG_GUI, TG_BING): ("天藏克火", "Vault Conquers Fire", 0, 0, "癸水克丙火"),
        (TG_GUI, TG_DING): ("腾蛇夭矫", "Serpent Writhes", 0, 1, "行路迷程，万事伤嗟"),
        (TG_GUI, TG_JI): ("天藏入地", "Vault Enters Earth", 0, 0, "己土制癸水"),
        (TG_GUI, TG_GENG): ("天藏白虎", "Vault Tiger", 0, 1, "凶险"),
        (TG_GUI, TG_XIN): ("天藏入狱", "Vault Enters Prison", 0, 0, "不利"),
        (TG_GUI, TG_REN): ("天藏地网", "Vault Ground Net", 0, 0, "幽暗"),
        (TG_GUI, TG_GUI): ("华盖重逢", "Double Canopy", 0, 0, "阴暗不明"),
    }
    
    results = []
    
    for palace in range(1, 10):
        h_stem = ju.heaven.get(palace)
        g_stem = ju.ground.get(palace)
        if h_stem is None or g_stem is None:
            continue
        
        key = (h_stem, g_stem)
        if key in STEM_OVERLAY_TABLE:
            name, name_biz, jixiong, severity, desc = STEM_OVERLAY_TABLE[key]
            
            # Context-dependent (-1): resolve based on gate/star at this palace
            if jixiong == -1:
                gate = ju.gates.get(palace)
                if gate is not None and GATE_JIXIONG.get(gate, 0) == 1:
                    jixiong = 1  # 吉门同宫 → 吉
                else:
                    jixiong = 0  # 否则偏凶
            
            results.append(GejuResult(name, name_biz, jixiong, severity, palace, desc))
    
    return results


# ============================================================
# 三奇入墓 (Three Wonders Enter Tomb)
# Per《宝鉴》: "奇仪入墓，谓入于墓库之宫"
# ============================================================

def evaluate_qiru_mu(ju):
    """Check if any of the three qi (乙丙丁) have entered their tomb palace."""
    results = []
    
    for palace in range(1, 10):
        h_stem = ju.heaven.get(palace)
        if h_stem is None:
            continue
        
        # 乙奇入墓: 乙(木)到坤2宫 (木墓未，未在坤)
        if h_stem == TG_YI and palace == 2:
            results.append(GejuResult(
                "乙奇入墓", "Wood Wonder Entombed",
                0, 2, palace,
                "乙木入坤宫，木墓未，消威退喜"
            ))
        
        # 丙奇入墓: 丙(火)到乾6宫 (火墓戌，戌在乾)
        if h_stem == TG_BING and palace == 6:
            results.append(GejuResult(
                "丙奇入墓", "Fire Wonder Entombed",
                0, 2, palace,
                "丙火入乾宫，火墓戌，百无一成"
            ))
        
        # 丁奇入墓: 丁(火)到艮8宫 (阴火墓丑，丑在艮)
        if h_stem == TG_DING and palace == 8:
            results.append(GejuResult(
                "丁奇入墓", "Star Wonder Entombed",
                0, 2, palace,
                "丁火入艮宫，阴火墓丑，百事不顺"
            ))
    
    return results


# ============================================================
# 时干入墓 (Hour Stem Enters Tomb)
# Per《宝鉴》: 戊戌、壬辰、丙戌、癸未、丁丑、己丑
# ============================================================

def evaluate_shigan_rumu(ju):
    """Check if the hour stem has entered its tomb."""
    results = []
    hour_tg_idx = ju.hour_gz[0]
    hour_stem = TIANGAN_BY_INDEX[hour_tg_idx]
    hour_dz = ju.hour_gz[1]
    
    # Per《宝鉴》specific combinations
    rumu_pairs = [
        (TG_WU, DZ_XU),   # 戊戌
        (TG_REN, DZ_CHEN), # 壬辰
        (TG_BING, DZ_XU),  # 丙戌
        (TG_GUI, DZ_WEI),  # 癸未
        (TG_DING, DZ_CHOU),# 丁丑
        (TG_JI, DZ_CHOU),  # 己丑
    ]
    
    for tg, dz in rumu_pairs:
        if hour_stem == tg and hour_dz == dz:
            results.append(GejuResult(
                "时干入墓", "Hour Stem Entombed",
                0, 1, None,
                f"{TIANGAN_NAMES[tg]}{DIZHI_NAMES[dz]}时干入墓，事多晦滞"
            ))
    
    return results


# ============================================================
# 五不遇时 (Five Inauspicious Hours)
# Per《宝鉴》: "时干克日干，阳干克阳干，阴干克阴干"
# ============================================================

def evaluate_wubuyushi(ju):
    """Check if the hour stem conquers the day stem (same yin/yang polarity)."""
    results = []
    day_stem = TIANGAN_BY_INDEX[ju.day_gz[0]]
    hour_stem = TIANGAN_BY_INDEX[ju.hour_gz[0]]
    
    # Check: hour克day, same yinyang
    day_wx = tg_wuxing(day_stem)
    hour_wx = tg_wuxing(hour_stem)
    day_yy = tg_yinyang(day_stem)
    hour_yy = tg_yinyang(hour_stem)
    
    rel = shengke(hour_wx, day_wx)
    if rel == REL_WOKE and day_yy == hour_yy:
        results.append(GejuResult(
            "五不遇时", "Inauspicious Hour",
            0, 2, None,
            f"时干{TIANGAN_NAMES[hour_stem]}克日干{TIANGAN_NAMES[day_stem]}，同{'阳' if day_yy else '阴'}，百事皆凶"
        ))
    
    return results


# ============================================================
# 六仪击刑 (Six Ceremonies Strike Punishment)
# Per《宝鉴》: 旬首宫位与时支构成三刑
# ============================================================

def evaluate_liuyi_jixing(ju):
    """Check if the current 六甲旬首 triggers 三刑."""
    results = []
    
    # Per《宝鉴》specific mapping:
    # 甲子直符宫加三，时加卯 → 子卯刑 (无礼)
    # 甲戌直符宫加二，时加未 → 丑戌未刑 (恃恩)  
    # 甲申直符宫加八，时加寅 → 巳申寅刑 (恃势)
    # 甲午直符宫加九，时加午 → 午自刑
    # 甲辰直符宫加四，时加辰 → 辰自刑
    # 甲寅直符宫加四，时加巳 → 寅巳刑 (恃势)
    
    xun = ju.xun_index
    hour_dz = ju.hour_gz[1]
    xun_dz = XUN_HEAD_DIZHI[xun]
    
    xing_type = sanxing(xun_dz, hour_dz)
    if xing_type != XING_NONE:
        results.append(GejuResult(
            "六仪击刑", "Ceremony Strikes Punishment",
            0, 2, None,
            f"甲{DIZHI_NAMES[xun_dz]}旬，时支{DIZHI_NAMES[hour_dz]}，{XING_NAMES[xing_type]}，事事皆凶"
        ))
    
    return results


# ============================================================
# 门迫 (Gate Oppression)
# Per《宝鉴》: "吉门被迫吉不就，凶门被迫凶不起"
# 门迫 = 宫的五行克门的五行
# ============================================================

def evaluate_menpo(ju):
    """Check for gate oppression in each palace."""
    results = []
    
    for palace in range(1, 10):
        gate = ju.gates.get(palace)
        if gate is None:
            continue
        
        gong_wx = GONG_WUXING[palace]
        gate_wx = GATE_WUXING[gate]
        
        rel = shengke(gong_wx, gate_wx)
        if rel == REL_WOKE:  # 宫克门
            is_ji_gate = GATE_JIXIONG[gate] == 1
            if is_ji_gate:
                desc = f"{GATE_NAMES[gate]}(吉)被{GONG_GUA_NAMES[palace]}宫克，吉不就"
            else:
                desc = f"{GATE_NAMES[gate]}(凶)被{GONG_GUA_NAMES[palace]}宫克，凶不起"
            
            results.append(GejuResult(
                "门迫", "Gate Oppressed",
                0 if is_ji_gate else 1,  # 吉门被迫=凶, 凶门被迫=反吉
                0, palace,
                desc
            ))
    
    return results


# ============================================================
# 伏吟 / 反吟 (Hidden/Reversed Chanting)
# ============================================================

def evaluate_fuyin_fanyin(ju):
    """Check for 伏吟 (stems in home position) and 反吟 (stems in opposite position)."""
    results = []
    
    fuyin_count = 0
    fanyin_count = 0
    
    for palace in range(1, 10):
        h_stem = ju.heaven.get(palace)
        g_stem = ju.ground.get(palace)
        if h_stem is None or g_stem is None:
            continue
        
        # 伏吟: 天盘干与地盘干相同
        if h_stem == g_stem:
            fuyin_count += 1
        
        # 反吟: 天盘干在地盘的对宫
        opposite = GONG_CHONG.get(palace)
        if opposite and ju.ground.get(opposite) == h_stem:
            fanyin_count += 1
    
    if fuyin_count >= 7:  # Most palaces have same stem = 伏吟局
        results.append(GejuResult(
            "伏吟", "Stagnation Pattern",
            0, 2, None,
            "天地两盘相同，宜收敛固守，不利出击"
        ))
    
    if fanyin_count >= 7:  # Most palaces have opposite stem = 反吟局
        results.append(GejuResult(
            "反吟", "Reversal Pattern",
            0, 2, None,
            "天地两盘对冲，主反覆不定，事出意外"
        ))
    
    return results


# ============================================================
# 天网四张 (Heaven's Net)
# Per《宝鉴》: "六癸所临之方"
# ============================================================

def evaluate_tianwang(ju):
    """Check for 天网四张 - palace where 癸 sits on heaven plate."""
    results = []
    
    for palace in range(1, 10):
        h_stem = ju.heaven.get(palace)
        if h_stem == TG_GUI:
            results.append(GejuResult(
                "天网四张", "Heaven's Net Spread",
                0, 1, palace,
                f"六癸临{GONG_GUA_NAMES[palace]}宫，不能前进，进亦无遇"
            ))
    
    return results


# ============================================================
# 三奇得使 (Three Wonders Get Envoy)
# Per《宝鉴》: 三奇所在宫得直使之吉门
# ============================================================

def evaluate_sanqi_deshi(ju):
    """Check if any of the three qi (乙丙丁) shares a palace with a favorable gate."""
    results = []
    ji_gates = {GATE_KAI, GATE_XIU, GATE_SHENG}  # 三吉门
    
    for palace in range(1, 10):
        h_stem = ju.heaven.get(palace)
        gate = ju.gates.get(palace)
        
        if h_stem in (TG_YI, TG_BING, TG_DING) and gate in ji_gates:
            qi_name = TIANGAN_NAMES[h_stem]
            gate_name = GATE_NAMES[gate]
            results.append(GejuResult(
                "三奇得使", "Wonder Meets Envoy",
                1, 2, palace,
                f"{qi_name}奇逢{gate_name}，利谋为获利，出兵遣将"
            ))
    
    return results


# ============================================================
# 奇门会合 (Wonder-Gate Convergence)
# Per《宝鉴》: "乙丙丁三奇，与开休生三吉门会合之方，乃奇门第一要格"
# ============================================================

def evaluate_qimen_huihe(ju):
    """Check for the supreme pattern: qi + favorable gate in same palace."""
    # This overlaps with sanqi_deshi but is specifically the top-tier pattern
    # Already captured above; we don't double-count
    return []


# ============================================================
# 九遁 (Nine Concealment Patterns)
# ============================================================

def evaluate_jiudun(ju):
    """Check for the nine concealment patterns."""
    results = []
    
    for palace in range(1, 10):
        h_stem = ju.heaven.get(palace)
        gate = ju.gates.get(palace)
        g_stem = ju.ground.get(palace)
        deity = ju.deities.get(palace)
        
        if h_stem is None:
            continue
        
        # 天遁: 天盘生门+丙+地盘丁宫
        if gate == GATE_SHENG and h_stem == TG_BING and g_stem == TG_DING:
            results.append(GejuResult(
                "天遁", "Heaven Concealment",
                1, 2, palace,
                "生门+丙奇+丁，虽是美格然出行不宜用"
            ))
        
        # 地遁: 天盘开门+乙+地盘己宫
        if gate == GATE_KAI and h_stem == TG_YI and g_stem == TG_JI:
            results.append(GejuResult(
                "地遁", "Earth Concealment",
                1, 2, palace,
                "开门+乙奇+己，百事皆利"
            ))
        
        # 人遁: 天盘休门+丁+太阴
        if gate == GATE_XIU and h_stem == TG_DING and deity == DEITY_TAIYIN:
            results.append(GejuResult(
                "人遁", "Human Concealment",
                1, 2, palace,
                "休门+丁奇+太阴，利阴私和合"
            ))
        
        # 神遁: 天盘生门+丙+九天
        if gate == GATE_SHENG and h_stem == TG_BING and deity == DEITY_JIUTIAN:
            results.append(GejuResult(
                "神遁", "Spirit Concealment",
                1, 2, palace,
                "生门+丙奇+九天"
            ))
        
        # 鬼遁: 天盘杜门+乙+九地
        if gate == GATE_DU and h_stem == TG_YI and deity == DEITY_JIUDI:
            results.append(GejuResult(
                "鬼遁", "Ghost Concealment",
                1, 2, palace,
                "杜门+乙奇+九地"
            ))
    
    return results


# ============================================================
# 空亡状态检查
# ============================================================

def evaluate_kongwang(ju):
    """Check which palaces have stems that fall on 空亡 branches."""
    results = []
    k1, k2 = ju.kongwang
    
    # Check if 直符 star's palace has kongwang
    # More precisely: check if the 六仪 on the heaven plate
    # corresponds to a 甲 whose branch is in kongwang
    for palace in range(1, 10):
        h_stem = ju.heaven.get(palace)
        if h_stem is None:
            continue
        
        # If this stem is a 六仪, find which 甲 it hides
        if h_stem in DUN_TO_JIAZI:
            jiazi_idx = DUN_TO_JIAZI[h_stem]
            jiazi_dz = XUN_HEAD_DIZHI[jiazi_idx]
            # No, that's the 旬首 branch, not the hidden 甲's branch
            # The 六仪 itself carries a specific ganzhi in the 60-jiazi cycle
            # For kongwang check: we check if the PALACE's ground stem's
            # associated branch falls in kongwang
            # Actually, kongwang applies to the hour's xun - the two branches
            # that are empty in this xun. Any yao/star/element with those
            # branches is considered 空亡.
            pass
    
    # For FCAS purposes, we note kongwang as a global state
    # Individual yao-level kongwang is checked during bridge computation
    return results


# ============================================================
# 旺衰修正 (Seasonal Strength Modifier)
# Per《宝鉴》: "凡奇仪星门，逢时旺相有气，百事皆吉；休囚无气，百事皆凶"
# ============================================================

def evaluate_wangshuai_modifier(ju):
    """Check overall 旺衰 status for key elements."""
    results = []
    month_br = ju.month_branch
    
    # Check 直符星 旺衰
    star_wx = STAR_WUXING[ju.zhifu_star]
    star_ws = calc_wangshuai(star_wx, month_br)
    
    if star_ws in (WS_WANG, WS_XIANG):
        results.append(GejuResult(
            "直符有气", "Commanding Star Vital",
            1, 1, None,
            f"直符{STAR_NAMES[ju.zhifu_star]}({WUXING_NAMES[star_wx]})在{DIZHI_NAMES[month_br]}月{WS_NAMES[star_ws]}，有气"
        ))
    elif star_ws in (WS_QIU, WS_SI):
        results.append(GejuResult(
            "直符无气", "Commanding Star Depleted",
            0, 1, None,
            f"直符{STAR_NAMES[ju.zhifu_star]}({WUXING_NAMES[star_wx]})在{DIZHI_NAMES[month_br]}月{WS_NAMES[star_ws]}，无气"
        ))
    
    # Check 直使门 旺衰
    gate_wx = GATE_WUXING[ju.zhishi_gate]
    gate_ws = calc_wangshuai(gate_wx, month_br)
    
    if gate_ws in (WS_QIU, WS_SI):
        results.append(GejuResult(
            "直使无气", "Commanding Gate Depleted",
            0, 0, None,
            f"直使{GATE_NAMES[ju.zhishi_gate]}({WUXING_NAMES[gate_wx]})在{DIZHI_NAMES[month_br]}月{WS_NAMES[gate_ws]}"
        ))
    
    return results


# ============================================================
# 玉女守门 (Jade Lady Guards Gate)
# Per《宝鉴》: 直使之门加于六丁之上
# ============================================================

def evaluate_yunv_shoumen(ju):
    """Check if 直使 gate lands on a palace where 丁 is on ground plate."""
    results = []
    
    zhishi_palace = ju.zhishi_palace
    g_stem = ju.ground.get(zhishi_palace)
    
    if g_stem == TG_DING:
        results.append(GejuResult(
            "玉女守门", "Jade Lady Guards Gate",
            1, 1, zhishi_palace,
            "利阴私和合，有酒食宴会之乐"
        ))
    
    return results


# ============================================================
# Master evaluation function
# ============================================================

def evaluate_all_geju(ju):
    """Run all geju pattern checks and return combined results.
    
    Also applies the《宝鉴》correction principles:
    1. "吉门被迫吉不就，凶门被迫凶不起" (handled in menpo)
    2. "大凶无气交为小，小凶有气亦丁宁" (severity adjustment)
    3. 旺衰 as overall modifier
    """
    all_results = []
    
    # Run all evaluators
    all_results.extend(evaluate_stem_overlays(ju))
    all_results.extend(evaluate_qiru_mu(ju))
    all_results.extend(evaluate_shigan_rumu(ju))
    all_results.extend(evaluate_wubuyushi(ju))
    all_results.extend(evaluate_liuyi_jixing(ju))
    all_results.extend(evaluate_menpo(ju))
    all_results.extend(evaluate_fuyin_fanyin(ju))
    all_results.extend(evaluate_tianwang(ju))
    all_results.extend(evaluate_sanqi_deshi(ju))
    all_results.extend(evaluate_jiudun(ju))
    all_results.extend(evaluate_yunv_shoumen(ju))
    all_results.extend(evaluate_wangshuai_modifier(ju))
    
    # Apply severity adjustment based on 旺衰
    # "大凶无气交为小" - severe xiong patterns lose severity when weak
    # "小凶有气亦丁宁" - minor xiong patterns gain severity when strong
    month_br = ju.month_branch
    for r in all_results:
        if r.palace and r.jixiong == 0:  # Xiong pattern with specific palace
            # Check if the relevant element has qi
            h_stem = ju.heaven.get(r.palace)
            if h_stem:
                stem_wx = tg_wuxing(h_stem)
                ws = calc_wangshuai(stem_wx, month_br)
                if ws in (WS_QIU, WS_SI) and r.severity >= 2:
                    r.severity -= 1  # 大凶无气交为小
                    r.description += " [无气减轻]"
                elif ws in (WS_WANG, WS_XIANG) and r.severity <= 1:
                    r.severity += 1  # 小凶有气亦丁宁
                    r.description += " [有气加重]"
    
    return all_results


def summarize_geju(results):
    """Produce a summary of geju analysis."""
    ji_results = [r for r in results if r.jixiong == 1]
    xiong_results = [r for r in results if r.jixiong == 0]
    
    print(f"\n格局分析: 共{len(results)}条 (吉{len(ji_results)}条, 凶{len(xiong_results)}条)")
    print("-" * 60)
    
    if ji_results:
        print("\n吉格:")
        for r in ji_results:
            print(f"  {r}")
    
    if xiong_results:
        print("\n凶格:")
        for r in xiong_results:
            print(f"  {r}")
    
    # Overall assessment
    if not results:
        overall = "平"
    elif not xiong_results:
        max_sev = max(r.severity for r in ji_results)
        overall = "大吉" if max_sev >= 2 else "小吉"
    elif not ji_results:
        max_sev = max(r.severity for r in xiong_results)
        overall = "大凶" if max_sev >= 2 else "小凶"
    else:
        ji_weight = sum(r.severity + 1 for r in ji_results)
        xiong_weight = sum(r.severity + 1 for r in xiong_results)
        if ji_weight > xiong_weight * 1.5:
            overall = "吉中有凶"
        elif xiong_weight > ji_weight * 1.5:
            overall = "凶中有吉"
        else:
            overall = "吉凶混杂"
    
    print(f"\n综合: {overall}")
    return overall


# ============================================================================
# SECTION 4: YINGQI TIMING DERIVATION
# ============================================================================

# ============================================================
# Timing condition types
# ============================================================

class TimingCondition:
    """A single timing condition for yingqi."""
    
    def __init__(self, cond_type, dizhi_value, description, priority):
        self.cond_type = cond_type      # Type of condition
        self.dizhi_value = dizhi_value  # The dizhi that triggers this condition
        self.description = description
        self.priority = priority        # 0=primary, 1=secondary, 2=tertiary
    
    def __repr__(self):
        dz_name = DIZHI_NAMES.get(self.dizhi_value, "?") if self.dizhi_value is not None else "?"
        return f"[P{self.priority}] {self.cond_type}: {dz_name} — {self.description}"


# ============================================================
# Core yingqi derivation
# ============================================================

def derive_yingqi(shi_yao, palace_wuxing, kongwang, month_branch):
    """Derive timing conditions from 世爻 state.
    
    Per《宝鉴》:
    - "物之败坏，当在世爻空破败绝之时"
    - "须看何时提出世下所伏之父母爻，及何旬空去其世爻"
    - "又须合内外两卦之数，以定其年分日子之多少"
    
    Args:
        shi_yao: dict with 'dizhi', 'wuxing' keys
        palace_wuxing: int, the palace's wuxing
        kongwang: tuple of 2 dizhi values
        month_branch: current month dizhi
    
    Returns:
        list of TimingCondition
    """
    conditions = []
    shi_dz = shi_yao['dizhi']
    shi_wx = shi_yao['wuxing']
    k1, k2 = kongwang
    
    # === Condition 1: 空亡 ===
    # If 世爻 branch is in 旬空, it needs to be "filled" or "clashed" to activate
    if shi_dz == k1 or shi_dz == k2:
        # 出空/填实: when the kongwang branch is actually present (valued day/hour)
        conditions.append(TimingCondition(
            "填实出空", shi_dz,
            f"世爻{DIZHI_NAMES[shi_dz]}在旬空中，逢{DIZHI_NAMES[shi_dz]}日/时填实",
            0
        ))
        # 冲空: clash the empty branch to activate
        chong_dz = (shi_dz + 6) % 12
        conditions.append(TimingCondition(
            "冲空", chong_dz,
            f"逢{DIZHI_NAMES[chong_dz]}冲{DIZHI_NAMES[shi_dz]}空亡，激活世爻",
            0
        ))
    
    # === Condition 2: 入墓 ===
    # If 世爻's wuxing is entombed at its current position
    mu_dz = WUXING_MU_DIZHI[shi_wx]
    stage = calc_changsheng(shi_wx, shi_dz)
    if stage == STAGE_MU:
        # 世爻 itself is at 墓 stage → needs 冲墓 to release
        chong_mu = (mu_dz + 6) % 12
        conditions.append(TimingCondition(
            "冲墓", chong_mu,
            f"世爻{WUXING_NAMES[shi_wx]}入墓于{DIZHI_NAMES[mu_dz]}，逢{DIZHI_NAMES[chong_mu]}冲开",
            0
        ))
    
    # === Condition 3: 旺衰 — 得生旺之时应 ===
    ws = calc_wangshuai(shi_wx, month_branch)
    if ws in (WS_QIU, WS_SI):
        # 世爻休囚无气 → wait for 生旺 season
        sheng_dz = CHANGSHENG_START[shi_wx]
        wang_dz = (sheng_dz + 4) % 12  # 帝旺 = 长生 + 4 steps
        conditions.append(TimingCondition(
            "待生旺", sheng_dz,
            f"世爻{WUXING_NAMES[shi_wx]}当前{WS_NAMES[ws]}，待{DIZHI_NAMES[sheng_dz]}月/日长生",
            1
        ))
        conditions.append(TimingCondition(
            "待帝旺", wang_dz,
            f"或待{DIZHI_NAMES[wang_dz]}月/日帝旺",
            1
        ))
    elif ws in (WS_WANG, WS_XIANG):
        # 世爻旺相有气 → current period is active, check 衰败 timing
        shuai_dz = (CHANGSHENG_START[shi_wx] + 5) % 12  # 衰 = 长生+5
        conditions.append(TimingCondition(
            "防衰", shuai_dz,
            f"世爻当前{WS_NAMES[ws]}有气，{DIZHI_NAMES[shuai_dz]}月/日起转衰",
            2
        ))
    
    # === Condition 4: 败绝位 — 应避开 ===
    # 绝 = 长生前一位 (即 受气前一位 = 墓后一位? No)
    # 十二长生序: 受气→胎→养→长生→沐浴→...→墓
    # 绝位 = 受气的前一位 = 从长生往回数4位
    # Actually: 受气(0)的对应地支 = 长生地支-3 (mod 12)
    # 败位 = 沐浴位 (长生后一位)
    jue_dz = (CHANGSHENG_START[shi_wx] - 3 + 12) % 12  # 受气-1 in dizhi = 绝
    # Actually let me just compute directly:
    # 绝 stage = 受气前一位。In the 12-stage cycle, there's no explicit "绝"
    # In traditional systems: after 墓 is 绝, then 胎...
    # So: 长生=3, ..., 墓=11, then cycle: 0=受气 is sometimes called 绝's next
    # Traditional order: ...死(10)→墓(11)→绝(= position after 墓 = 0 in our encoding)
    # Wait, our encoding: 受气=0, 胎=1, 养=2, 长生=3, ...
    # The traditional full 12: 长生→沐浴→冠带→临官→帝旺→衰→病→死→墓→绝→胎→养
    # So 绝 is between 墓 and 胎. In our encoding this maps to... 
    # Our encoding starts at 受气(0) where traditional starts at 长生.
    # 受气 IS 绝 in some traditions. Let me use: 绝 = 受气 position = stage 0
    
    # Find dizhi where shi_wx has stage 0 (受气/绝)
    # calc_changsheng(shi_wx, dz) == 0 when dz = ?
    # (dz - start + 12)%12 + 3)%12 == 0
    # means (dz - start + 12)%12 == 9
    # dz = (start + 9) % 12
    jue_dz = (CHANGSHENG_START[shi_wx] + 9) % 12
    bai_dz = (CHANGSHENG_START[shi_wx] + 1) % 12  # 沐浴=败
    
    conditions.append(TimingCondition(
        "避绝", jue_dz,
        f"逢{DIZHI_NAMES[jue_dz]}为{WUXING_NAMES[shi_wx]}绝位，宜避",
        2
    ))
    conditions.append(TimingCondition(
        "避败", bai_dz,
        f"逢{DIZHI_NAMES[bai_dz]}为{WUXING_NAMES[shi_wx]}沐浴败位，不稳",
        2
    ))
    
    # === Condition 5: 六合 — 绊住 ===
    # If 世爻 branch is in a 六合 pair with something, it may be held back
    he_found, he_wx = liuhe(shi_dz, shi_dz)  # Self-check doesn't make sense
    # Check all possible合 partners
    for partner_dz in range(12):
        if partner_dz == shi_dz:
            continue
        is_he, he_wx = liuhe(shi_dz, partner_dz)
        if is_he:
            # 世爻 can be "held" by this合
            chong_partner = (partner_dz + 6) % 12
            conditions.append(TimingCondition(
                "合绊/冲开", chong_partner,
                f"世爻{DIZHI_NAMES[shi_dz]}与{DIZHI_NAMES[partner_dz]}合，逢{DIZHI_NAMES[chong_partner]}冲开",
                1
            ))
            break  # Only one合 partner exists
    
    # === Condition 6: 冲起 — 世爻被冲激活 ===
    shi_chong = (shi_dz + 6) % 12
    if shi_dz != k1 and shi_dz != k2:  # Not already in kongwang
        conditions.append(TimingCondition(
            "冲起", shi_chong,
            f"逢{DIZHI_NAMES[shi_chong]}冲{DIZHI_NAMES[shi_dz]}，激发变动",
            1
        ))
    
    return conditions


def display_yingqi(conditions):
    """Pretty-print timing conditions."""
    print(f"\n应期推导: {len(conditions)}个条件")
    print("-" * 60)
    
    primary = [c for c in conditions if c.priority == 0]
    secondary = [c for c in conditions if c.priority == 1]
    tertiary = [c for c in conditions if c.priority == 2]
    
    if primary:
        print("\n核心条件 (必须满足):")
        for c in primary:
            print(f"  {c}")
    
    if secondary:
        print("\n重要条件 (影响时机):")
        for c in secondary:
            print(f"  {c}")
    
    if tertiary:
        print("\n参考条件 (辅助判断):")
        for c in tertiary:
            print(f"  {c}")


# ============================================================
# Integration with bridge
# ============================================================

def yingqi_from_assessment(assessment, kongwang, month_branch):
    """Extract yingqi from a bridge assessment result.
    
    Args:
        assessment: dict from three_layer_judgment()
        kongwang: tuple of 2 kongwang dizhi
        month_branch: current month dizhi
    """
    shi_info = assessment['shi_yao']
    
    # Reconstruct shi_yao dict with numeric values
    # Need to reverse-lookup dizhi name to value
    dz_reverse = {v: k for k, v in DIZHI_NAMES.items()}
    wx_reverse = {v: k for k, v in WUXING_NAMES.items()}
    
    shi_yao = {
        'dizhi': dz_reverse[shi_info['dizhi']],
        'wuxing': wx_reverse[shi_info['wuxing']],
    }
    
    palace_wx = wx_reverse[assessment['palace_wuxing']]
    
    return derive_yingqi(shi_yao, palace_wx, kongwang, month_branch)


# ============================================================================
# SECTION 5: BRIDGE (QIMEN → FCAS SIX-YAO SYSTEM)
# ============================================================================

# ============================================================
# 京房八宫 (Jingfang Eight Palace) lookup
# Maps each of the 64 hexagrams to its palace
# ============================================================

# 八宫: each hexagram belongs to one of the 8 palace trigrams
# The palace determines the hexagram's base wuxing
# Palace assignment follows Jingfang's sequence:
#   本卦→一世→二世→三世→四世→五世→游魂→归魂

def _build_jingfang_table():
    """Build the complete 64-hexagram to palace mapping per Jingfang.
    
    For each palace (upper trigram), the 8 hexagrams are generated by:
    1. 本卦: upper=palace, lower=palace (pure hexagram)
    2. 一世: flip yao 1 (初爻)
    3. 二世: flip yao 1,2
    4. 三世: flip yao 1,2,3
    5. 四世: flip yao 1,2,3,4
    6. 五世: flip yao 1,2,3,4,5
    7. 游魂: un-flip yao 4 (restore yao 4 from 五世)
    8. 归魂: lower=palace trigram (restore lower to match upper)
    """
    table = {}  # hexagram_binary -> (palace_trigram, shi_position, palace_name)
    
    palace_trigrams = [
        (0b111, "乾", WX_JIN),
        (0b010, "坎", WX_SHUI),
        (0b100, "艮", WX_TU),
        (0b001, "震", WX_MU),
        (0b110, "巽", WX_MU),
        (0b101, "离", WX_HUO),
        (0b000, "坤", WX_TU),
        (0b011, "兑", WX_JIN),
    ]
    
    for palace_tri, palace_name, palace_wx in palace_trigrams:
        # 本卦
        ben = (palace_tri << 3) | palace_tri
        table[ben] = (palace_tri, 6, palace_name, palace_wx)  # 世在上爻(6)
        
        # Generate the 7 变卦 by progressive flipping
        current = ben
        
        # 一世到五世: flip from 初爻 upward
        shi_positions = [1, 2, 3, 4, 5]  # 世爻位置
        for i, shi in enumerate(shi_positions):
            bit_to_flip = i  # bit 0=初爻, 1=二爻, ...
            current = current ^ (1 << bit_to_flip)
            table[current] = (palace_tri, shi, palace_name, palace_wx)
        
        # 游魂(六世): from 五世, restore 四爻 (bit 3)
        youhun = current ^ (1 << 3)  
        table[youhun] = (palace_tri, 4, palace_name, palace_wx)  # 世在四爻
        
        # 归魂: upper stays as palace, lower restores to palace
        guihun = (palace_tri << 3) | (youhun & 0b111)
        # Actually 归魂 = upper keeps palace trigram, lower = palace trigram
        # Wait - 归魂 should have the same LOWER trigram as the palace
        # but the UPPER trigram may differ. Let me reconsider.
        # 
        # Actually per Jingfang:
        # 归魂: from 游魂, flip the lower trigram back to palace trigram
        guihun = (youhun & 0b111000) | palace_tri
        table[guihun] = (palace_tri, 3, palace_name, palace_wx)  # 世在三爻
    
    return table

JINGFANG_TABLE = _build_jingfang_table()


def get_palace_info(hexagram_binary):
    """Get the Jingfang palace info for a 6-bit hexagram.
    Returns (palace_trigram, shi_yao_position, palace_name, palace_wuxing)"""
    info = JINGFANG_TABLE.get(hexagram_binary)
    if info is None:
        # Fallback: derive from upper trigram
        upper = (hexagram_binary >> 3) & 0b111
        for tri, name, wx in [(0b111,"乾",WX_JIN),(0b010,"坎",WX_SHUI),
                               (0b100,"艮",WX_TU),(0b001,"震",WX_MU),
                               (0b110,"巽",WX_MU),(0b101,"离",WX_HUO),
                               (0b000,"坤",WX_TU),(0b011,"兑",WX_JIN)]:
            if upper == tri:
                return (tri, 6, name, wx)
        return (0, 6, "?", WX_TU)
    return info


# ============================================================
# 纳甲 (Najia) - assign tiangan and dizhi to each yao
# ============================================================

# Per Jingfang najia rules:
# 乾卦纳甲壬, 坤卦纳乙癸
# 上卦纳: 乾甲壬, 坎戊, 艮丙, 震庚, 巽辛, 离己, 坤乙癸, 兑丁
# 下卦纳: 同上但乾用甲(非壬)

NAJIA_TIANGAN = {
    # trigram: (lower_tg_idx, upper_tg_idx)
    0b111: (0, 8),  # 乾: 下甲上壬
    0b010: (4, 4),  # 坎: 戊
    0b100: (2, 2),  # 艮: 丙
    0b001: (6, 6),  # 震: 庚
    0b110: (3, 3),  # 巽: 辛
    0b101: (5, 5),  # 离: 己
    0b000: (1, 9),  # 坤: 下乙上癸
    0b011: (1, 1),  # 兑: 丁 — wait, should be 丁(3)
}
# Fix: 兑纳丁
NAJIA_TIANGAN[0b011] = (3, 3)

# 纳支 rules per trigram:
# 乾(阳): 子寅辰 (下卦), 午申戌 (上卦) — 阳支顺行
# 坎(阳): 寅辰午, 申戌子
# 艮(阳): 辰午申, 戌子寅
# 震(阳): 子寅辰, 午申戌
# 巽(阴): 丑亥酉 (下卦), 未巳卯 (上卦) — 阴支逆行
# 离(阴): 卯丑亥, 酉未巳
# 坤(阴): 未巳卯, 丑亥酉
# 兑(阴): 巳卯丑, 亥酉未

NAJIA_DIZHI = {
    # trigram: [yao1, yao2, yao3, yao4, yao5, yao6] dizhi values
    0b111: [DZ_ZI, DZ_YIN, DZ_CHEN, DZ_WU, DZ_SHEN, DZ_XU],      # 乾
    0b010: [DZ_YIN, DZ_CHEN, DZ_WU, DZ_SHEN, DZ_XU, DZ_ZI],      # 坎
    0b100: [DZ_CHEN, DZ_WU, DZ_SHEN, DZ_XU, DZ_ZI, DZ_YIN],      # 艮
    0b001: [DZ_ZI, DZ_YIN, DZ_CHEN, DZ_WU, DZ_SHEN, DZ_XU],      # 震
    0b110: [DZ_CHOU, DZ_HAI, DZ_YOU, DZ_WEI, DZ_SI, DZ_MAO],     # 巽
    0b101: [DZ_MAO, DZ_CHOU, DZ_HAI, DZ_YOU, DZ_WEI, DZ_SI],     # 离
    0b000: [DZ_WEI, DZ_SI, DZ_MAO, DZ_CHOU, DZ_HAI, DZ_YOU],     # 坤
    0b011: [DZ_SI, DZ_MAO, DZ_CHOU, DZ_HAI, DZ_YOU, DZ_WEI],     # 兑
}

def get_najia(hexagram_binary):
    """Get the full najia for a hexagram.
    Returns list of 6 dicts, one per yao (index 0=初爻, 5=上爻).
    Each dict: {position, dizhi, wuxing, tiangan_idx}
    """
    upper_tri = (hexagram_binary >> 3) & 0b111
    lower_tri = hexagram_binary & 0b111
    
    yaos = []
    
    # Lower trigram (初爻, 二爻, 三爻)
    lower_dz = NAJIA_DIZHI[lower_tri][:3]
    lower_tg = NAJIA_TIANGAN[lower_tri][0]
    
    for i in range(3):
        dz = lower_dz[i]
        yaos.append({
            'position': i + 1,  # 1=初爻, 2=二爻, 3=三爻
            'dizhi': dz,
            'wuxing': DIZHI_WUXING[dz],
            'tiangan_idx': lower_tg,
        })
    
    # Upper trigram (四爻, 五爻, 上爻)
    upper_dz = NAJIA_DIZHI[upper_tri][3:]
    upper_tg = NAJIA_TIANGAN[upper_tri][1]
    
    for i in range(3):
        dz = upper_dz[i]
        yaos.append({
            'position': i + 4,  # 4=四爻, 5=五爻, 6=上爻
            'dizhi': dz,
            'wuxing': DIZHI_WUXING[dz],
            'tiangan_idx': upper_tg,
        })
    
    return yaos


# ============================================================
# 六亲 (Six Relations) assignment
# ============================================================

LIUQIN_NAMES = {
    REL_BIHE: ("兄弟", "Peer Competitor"),
    REL_WOSHENG: ("子孙", "Derivative Output"),
    REL_WOKE: ("妻财", "Accessible Resource"),
    REL_SHENGWO: ("父母", "Upstream Support"),
    REL_KEWO: ("官鬼", "External Pressure"),
}

def assign_liuqin(yaos, palace_wuxing):
    """Assign 六亲 to each yao based on palace wuxing."""
    for yao in yaos:
        rel = shengke(palace_wuxing, yao['wuxing'])
        yao['liuqin'] = rel
        yao['liuqin_name'] = LIUQIN_NAMES[rel][0]
        yao['liuqin_biz'] = LIUQIN_NAMES[rel][1]
    return yaos


# ============================================================
# 萧吉三层判断法 (Xiao Ji Three-Layer Judgment)
# ============================================================

def three_layer_judgment(ju, hexagram_binary, geju_results):
    """Apply Xiao Ji's three-layer judgment method.
    
    Layer 1: 扶抑 (Support/Suppress) — palace wx vs shi yao wx
    Layer 2: 有气无气 (Vital/Depleted) — shi yao 十二长生 + 旺衰
    Layer 3: 合德/刑克 (Harmony/Conflict) — geju patterns as modifier
    
    Returns assessment dict.
    """
    # Get palace info
    palace_tri, shi_pos, palace_name, palace_wx = get_palace_info(hexagram_binary)
    
    # Get najia
    yaos = get_najia(hexagram_binary)
    yaos = assign_liuqin(yaos, palace_wx)
    
    # Find 世爻
    shi_yao = yaos[shi_pos - 1]  # shi_pos is 1-indexed
    ying_pos = ((shi_pos - 1) + 3) % 6 + 1  # 应爻 is 3 positions away
    ying_yao = yaos[ying_pos - 1]
    
    # === Layer 1: 扶抑 ===
    fuyi_rel = shengke(palace_wx, shi_yao['wuxing'])
    
    FUYI_MAP = {
        REL_BIHE: "NEUTRAL",       # 比和 — 同类
        REL_WOSHENG: "SUPPORTIVE", # 宫生世=扶 (母得子=扶)
        REL_SHENGWO: "SUPPRESSED", # 世生宫=泄 (子遇母=抑)
        REL_WOKE: "PRESSURED",     # 宫克世=制 (外力压制主体)
        REL_KEWO: "CONSUMING",     # 世克宫=耗 (主体消耗根基)
    }
    fuyi = FUYI_MAP[fuyi_rel]
    
    # === Layer 2: 有气无气 ===
    # Per《宝鉴》: "凡奇、仪、星、门，逢时旺相有气，百事皆吉；休囚无气，百事皆凶"
    # Must check THREE elements: 世爻 + 直符星 + 直使门
    
    shi_changsheng = calc_changsheng(shi_yao['wuxing'], shi_yao['dizhi'])
    shi_wangshuai = calc_wangshuai(shi_yao['wuxing'], ju.month_branch)
    
    youqi_stages = {STAGE_CHANGSHENG, STAGE_GUANDAI, STAGE_LINGUAN, STAGE_DIWANG}
    wuqi_stages = {STAGE_SHUAI, STAGE_BING, STAGE_SIWANG, STAGE_MU}
    
    # 世爻 qi
    if shi_changsheng in youqi_stages and shi_wangshuai in (WS_WANG, WS_XIANG):
        shi_qi = 2  # strong qi
    elif shi_changsheng in wuqi_stages and shi_wangshuai in (WS_QIU, WS_SI):
        shi_qi = -2  # no qi
    elif shi_wangshuai in (WS_WANG, WS_XIANG):
        shi_qi = 1  # timely but weak
    elif shi_wangshuai in (WS_QIU, WS_SI):
        shi_qi = -1  # untimely
    else:
        shi_qi = 0
    
    # 直符星 qi — "凡星逢时旺相有气"
    star_wx = STAR_WUXING[ju.zhifu_star]
    star_ws = calc_wangshuai(star_wx, ju.month_branch)
    if star_ws in (WS_WANG, WS_XIANG):
        star_qi = 1
    elif star_ws in (WS_QIU, WS_SI):
        star_qi = -1
    else:
        star_qi = 0
    
    # 直使门 qi — "凡门逢时旺相有气"
    gate_wx = GATE_WUXING[ju.zhishi_gate]
    gate_ws = calc_wangshuai(gate_wx, ju.month_branch)
    if gate_ws in (WS_WANG, WS_XIANG):
        gate_qi = 1
    elif gate_ws in (WS_QIU, WS_SI):
        gate_qi = -1
    else:
        gate_qi = 0
    
    # Composite qi: weighted sum (世爻 weight=2, star=1, gate=1)
    total_qi = shi_qi + star_qi + gate_qi
    
    if total_qi >= 3:
        qi_status = "HAS_QI"           # 三者皆旺
    elif total_qi >= 1:
        qi_status = "WEAK_QI_BUT_TIMELY"  # 整体偏旺
    elif total_qi <= -3:
        qi_status = "NO_QI"            # 三者皆囚
    elif total_qi <= -1:
        qi_status = "WEAK_QI_UNTIMELY"   # 整体偏囚
    else:
        qi_status = "WEAK_QI"          # 中性
    
    # === Layer 3: 合德/刑克 ===
    # Per《宝鉴》: "大凶无气交为小" — xiong patterns with no qi lose force
    # Per《宝鉴》: "吉星旺相万举万全，若遇休囚劝君不必进前程" — ji patterns need qi
    ji_geju = [g for g in geju_results if g.jixiong == 1]
    xiong_geju = [g for g in geju_results if g.jixiong == 0]
    
    # Apply yuqi (余气) correction to weights
    # When overall qi is weak/depleted: xiong patterns lose force ("凶不起")
    # When overall qi is strong: xiong patterns gain force ("有气亦丁宁")
    # When overall qi is weak: ji patterns also lose force ("劝君不必进前程")
    if total_qi <= -2:
        # 整体无气: 凶力大减，吉力也减
        xiong_weight_mult = 0.3   # 凶不起
        ji_weight_mult = 0.5      # 吉也不就
    elif total_qi <= -1:
        xiong_weight_mult = 0.6
        ji_weight_mult = 0.7
    elif total_qi >= 2:
        # 整体有气: 吉力加强，凶力也加强
        xiong_weight_mult = 1.3   # 有气丁宁
        ji_weight_mult = 1.3      # 旺相万举万全
    elif total_qi >= 1:
        xiong_weight_mult = 1.1
        ji_weight_mult = 1.1
    else:
        xiong_weight_mult = 1.0
        ji_weight_mult = 1.0
    
    ji_w = sum((g.severity + 1) * ji_weight_mult for g in ji_geju) if ji_geju else 0
    xi_w = sum((g.severity + 1) * xiong_weight_mult for g in xiong_geju) if xiong_geju else 0
    
    if ji_geju and not xiong_geju:
        modifier = "HEDE"       # 合德
    elif xiong_geju and not ji_geju:
        # Key fix: if xiong patterns have no qi, they can't form true XINGKE
        if xiong_weight_mult < 0.5:
            modifier = "MIXED_XIONG"  # 凶无气→降为mixed而非纯刑克
        else:
            modifier = "XINGKE"     # 刑克
    elif ji_geju and xiong_geju:
        modifier = "MIXED_JI" if ji_w > xi_w else "MIXED_XIONG"
    else:
        modifier = "NONE"
    
    # === Synthesis ===
    # Apply 萧吉 correction rules
    # "若遇合德，虽抑非害" → suppress + hede = downgrade severity
    # "若逢刑克，为凶更重" → adverse + xingke = upgrade severity
    
    if fuyi == "SUPPORTIVE":
        base = "FAVORABLE"
    elif fuyi == "NEUTRAL":
        base = "NEUTRAL"
    elif fuyi == "SUPPRESSED":
        base = "ADVERSE" if modifier != "HEDE" else "MITIGATED"
    elif fuyi == "PRESSURED":
        base = "ADVERSE"
    elif fuyi == "CONSUMING":
        base = "DRAINING"
    else:
        base = "NEUTRAL"
    
    # Cross L1 base with L3 modifier
    if base == "FAVORABLE":
        if modifier == "HEDE":
            final = "STRONGLY_FAVORABLE"
        elif modifier == "XINGKE":
            final = "FAVORABLE_WITH_RISK"
        elif modifier in ("MIXED_XIONG",):
            final = "FAVORABLE_WITH_CAUTION"
        else:
            final = "FAVORABLE"
    elif base == "NEUTRAL":
        if modifier == "HEDE":
            final = "FAVORABLE"
        elif modifier == "XINGKE":
            final = "ADVERSE"
        elif modifier == "MIXED_XIONG":
            final = "NEUTRAL_LEANING_ADVERSE"
        elif modifier == "MIXED_JI":
            final = "NEUTRAL_LEANING_FAVORABLE"
        else:
            final = "NEUTRAL"
    elif base == "ADVERSE":
        if modifier == "HEDE":
            final = "ADVERSE_MITIGATED"
        elif modifier == "XINGKE":
            final = "STRONGLY_ADVERSE"
        elif modifier == "MIXED_JI":
            final = "ADVERSE_WITH_OPENING"
        else:
            final = "ADVERSE"
    elif base == "DRAINING":
        if modifier in ("HEDE", "MIXED_JI"):
            final = "DRAINING_MITIGATED"
        elif modifier in ("XINGKE", "MIXED_XIONG"):
            final = "DRAINING_COMPOUNDED"
        else:
            final = "DRAINING"
    elif base == "MITIGATED":
        final = "MITIGATED"
    else:
        final = base
    
    # L2 Qi modifier — adjusts severity
    if "NO_QI" in qi_status:
        if "FAVORABLE" in final:
            final = final.replace("FAVORABLE", "WEAKLY_FAVORABLE")
        elif "ADVERSE" not in final and "DRAINING" not in final:
            final += "_DEPLETED"
    elif qi_status == "HAS_QI":
        if "ADVERSE" in final:
            final = final.replace("ADVERSE", "ACTIVELY_ADVERSE")
        elif "DRAINING" in final:
            final = final.replace("DRAINING", "ACTIVELY_DRAINING")
    
    # === 门迫修正 (Gate Oppression Correction) ===
    # Per《宝鉴》: "吉门被迫吉不就，凶门被迫凶不起"
    # Check if 直使门 (the commanding gate = action direction) is oppressed
    # 直使门 is the most important single gate — it represents the primary action channel
    zhishi_palace = ju.zhishi_palace
    zhishi_gate = ju.zhishi_gate
    zhishi_gong_wx = GONG_WUXING.get(zhishi_palace)
    zhishi_gate_wx = GATE_WUXING.get(zhishi_gate)
    zhishi_menpo = False
    
    if zhishi_gong_wx is not None and zhishi_gate_wx is not None:
        if shengke(zhishi_gong_wx, zhishi_gate_wx) == REL_WOKE:  # 宫克门=门迫
            zhishi_menpo = True
            is_ji_gate = GATE_JIXIONG.get(zhishi_gate, 0) == 1
            
            if is_ji_gate:
                # 吉门被迫→吉不就: favorable assessments get downgraded
                if "STRONGLY_FAVORABLE" in final:
                    final = "FAVORABLE_WITH_CAUTION"
                elif final == "FAVORABLE":
                    final = "NEUTRAL_LEANING_FAVORABLE"
                elif "FAVORABLE" in final and "WEAKLY" not in final:
                    final = final.replace("FAVORABLE", "WEAKLY_FAVORABLE")
            else:
                # 凶门被迫→凶不起: adverse assessments get mitigated
                if "STRONGLY_ADVERSE" in final or "ACTIVELY_ADVERSE" in final:
                    final = "ADVERSE_MITIGATED"
                elif final == "ADVERSE":
                    final = "ADVERSE_MITIGATED"
                elif "COMPOUNDED" in final:
                    final = final.replace("COMPOUNDED", "MITIGATED")
    
    return {
        'hexagram_binary': f"{hexagram_binary:06b}",
        'palace': palace_name,
        'palace_wuxing': WUXING_NAMES[palace_wx],
        'shi_yao': {
            'position': shi_pos,
            'dizhi': DIZHI_NAMES[shi_yao['dizhi']],
            'wuxing': WUXING_NAMES[shi_yao['wuxing']],
            'liuqin': shi_yao['liuqin_name'],
            'changsheng': STAGE_NAMES[shi_changsheng],
            'changsheng_biz': STAGE_BIZ_NAMES[shi_changsheng],
            'wangshuai': WS_NAMES[shi_wangshuai],
        },
        'ying_yao': {
            'position': ying_pos,
            'dizhi': DIZHI_NAMES[ying_yao['dizhi']],
            'liuqin': ying_yao['liuqin_name'],
        },
        'layer1_fuyi': fuyi,
        'layer2_qi': qi_status,
        'layer3_modifier': modifier,
        'final_assessment': final,
        'all_yaos': [
            {
                'pos': y['position'],
                'criterion': ['C5','C6','C3','C4','C1','C2'][y['position']-1],
                'yinyang': (hexagram_binary >> (y['position']-1)) & 1,
                'dizhi': DIZHI_NAMES[y['dizhi']],
                'wuxing': WUXING_NAMES[y['wuxing']],
                'liuqin': y['liuqin_name'],
                'liuqin_biz': y['liuqin_biz'],
            }
            for y in yaos
        ],
    }


# ============================================================
# Complete FCAS analysis pipeline
# ============================================================

def analyze(dt):
    """Run the complete FCAS analysis for a given datetime.
    
    Returns complete analysis dict.
    """
    
    # Step 1: Paipan
    ju = paipan(dt)
    
    # Step 2: Extract hexagram
    hex_info = ju.get_hexagram_binary()
    hexagram = hex_info['binary']
    
    # Step 3: Geju evaluation
    geju_results = evaluate_all_geju(ju)
    
    # Step 4: Three-layer judgment
    assessment = three_layer_judgment(ju, hexagram, geju_results)
    
    # Step 5: Yingqi derivation
    yingqi_conditions = yingqi_from_assessment(assessment, ju.kongwang, ju.month_branch)
    
    return {
        'datetime': dt.strftime('%Y-%m-%d %H:%M'),
        'ju_summary': {
            'type': f"{'阳' if ju.is_yangdun else '阴'}遁{ju.ju_number}局",
            'term': ju.term_name,
            'sanyuan': ['上','中','下'][ju.sanyuan] + '元',
            'day_pillar': f"{TIANGAN_NAMES[TIANGAN_BY_INDEX[ju.day_gz[0]]]}{DIZHI_NAMES[ju.day_gz[1]]}",
            'hour_pillar': f"{TIANGAN_NAMES[TIANGAN_BY_INDEX[ju.hour_gz[0]]]}{DIZHI_NAMES[ju.hour_gz[1]]}",
            'kongwang': f"{DIZHI_NAMES[ju.kongwang[0]]}{DIZHI_NAMES[ju.kongwang[1]]}",
        },
        'hexagram': hex_info,
        'geju': geju_results,
        'assessment': assessment,
        'yingqi': yingqi_conditions,
        'ju': ju,  # Keep reference for detailed inspection
    }


def display_analysis(result):
    """Pretty-print a complete analysis."""
    
    print("=" * 70)
    print(f"FCAS 完整分析: {result['datetime']}")
    print("=" * 70)
    
    # Ju summary
    js = result['ju_summary']
    print(f"\n奇门局: {js['type']} | {js['term']} {js['sanyuan']}")
    print(f"日柱: {js['day_pillar']} | 时柱: {js['hour_pillar']} | 空亡: {js['kongwang']}")
    
    # Display the ju
    result['ju'].display()
    
    # Hexagram
    hx = result['hexagram']
    print(f"\nFCAS Binary: {hx['binary_str']}")
    print(f"C2={hx['C2']} C1={hx['C1']} C4={hx['C4']} C3={hx['C3']} C6={hx['C6']} C5={hx['C5']}")
    
    # Geju
    summarize_geju(result['geju'])
    
    # Three-layer assessment
    a = result['assessment']
    print(f"\n{'='*70}")
    print(f"萧吉三层判断")
    print(f"{'='*70}")
    print(f"卦宫: {a['palace']}({a['palace_wuxing']})")
    sy = a['shi_yao']
    print(f"世爻: 第{sy['position']}爻 {sy['dizhi']}({sy['wuxing']}) [{sy['liuqin']}]")
    print(f"       生命阶段: {sy['changsheng']}({sy['changsheng_biz']}) | 旺衰: {sy['wangshuai']}")
    yy = a['ying_yao']
    print(f"应爻: 第{yy['position']}爻 {yy['dizhi']} [{yy['liuqin']}]")
    
    print(f"\n第一层(扶抑): {a['layer1_fuyi']}")
    print(f"第二层(有气无气): {a['layer2_qi']}")
    print(f"第三层(合德/刑克): {a['layer3_modifier']}")
    print(f"\n>>> 综合判断: {a['final_assessment']}")
    
    # Yao detail table
    print(f"\n爻位详情:")
    print(f"{'爻位':>4} {'标准':>4} {'阴阳':>4} {'地支':>4} {'五行':>4} {'六亲':>8} {'商业语言':>20}")
    for y in a['all_yaos']:
        yy_str = "阳" if y['yinyang'] else "阴"
        print(f"  {y['pos']:>2}   {y['criterion']:>4}   {yy_str:>2}   {y['dizhi']:>2}   {y['wuxing']:>2}   {y['liuqin']:>6}   {y['liuqin_biz']:>18}")
    
    # Yingqi
    if 'yingqi' in result:
        display_yingqi(result['yingqi'])


# ============================================================================
# SECTION 6: MCP TOOL DEFINITIONS
# ============================================================================

def fcas_paipan(year: int, month: int, day: int, hour: int, minute: int = 0) -> str:
    """排盘: 给定时间，生成完整奇门局。"""
    dt = datetime(year, month, day, hour, minute)
    ju = paipan(dt)
    hex_info = ju.get_hexagram_binary()
    
    lines = []
    lines.append(f"奇门局: {'阳' if ju.is_yangdun else '阴'}遁{ju.ju_number}局")
    lines.append(f"节气: {ju.term_name} | 三元: {['上','中','下'][ju.sanyuan]}元")
    day_tg = TIANGAN_NAMES[TIANGAN_BY_INDEX[ju.day_gz[0]]]
    day_dz = DIZHI_NAMES[ju.day_gz[1]]
    hour_tg = TIANGAN_NAMES[TIANGAN_BY_INDEX[ju.hour_gz[0]]]
    hour_dz = DIZHI_NAMES[ju.hour_gz[1]]
    lines.append(f"日柱: {day_tg}{day_dz} | 时柱: {hour_tg}{hour_dz}")
    k1, k2 = ju.kongwang
    lines.append(f"旬首: 甲{DIZHI_NAMES[XUN_HEAD_DIZHI[ju.xun_index]]}旬 | 空亡: {DIZHI_NAMES[k1]}{DIZHI_NAMES[k2]}")
    lines.append(f"直符: {STAR_NAMES[ju.zhifu_star]}(落{GONG_GUA_NAMES[ju.zhifu_palace]}宫)")
    lines.append(f"直使: {GATE_NAMES[ju.zhishi_gate]}(落{GONG_GUA_NAMES[ju.zhishi_palace]}宫)")
    lines.append(f"\nFCAS Binary: {hex_info['binary_str']}")
    lines.append(f"C2={hex_info['C2']} C1={hex_info['C1']} C4={hex_info['C4']} C3={hex_info['C3']} C6={hex_info['C6']} C5={hex_info['C5']}")
    lines.append("\n宫位详情:")
    for p in [4, 9, 2, 3, 5, 7, 8, 1, 6]:
        g = ju.ground.get(p)
        h = ju.heaven.get(p)
        s = ju.stars.get(p)
        gt = ju.gates.get(p)
        d = ju.deities.get(p)
        g_n = TIANGAN_NAMES.get(g, " ") if g is not None else " "
        h_n = TIANGAN_NAMES.get(h, " ") if h is not None else " "
        s_n = STAR_NAMES.get(s, "  ") if s is not None else "  "
        gt_n = GATE_NAMES.get(gt, "  ") if gt is not None else "  "
        d_n = DEITY_NAMES.get(d, "  ") if d is not None else "  "
        lines.append(f"  {GONG_GUA_NAMES[p]} | 地:{g_n} 天:{h_n} | {s_n} | {gt_n} | {d_n}")
    return "\n".join(lines)


def fcas_analyze(year: int, month: int, day: int, hour: int, minute: int = 0) -> str:
    """完整FCAS分析: 排盘+格局判断+三层判断+应期推导。"""
    dt = datetime(year, month, day, hour, minute)
    result = analyze(dt)
    
    lines = []
    js = result['ju_summary']
    lines.append(f"=== FCAS分析: {result['datetime']} ===")
    lines.append(f"奇门局: {js['type']} | {js['term']} {js['sanyuan']}")
    lines.append(f"日柱: {js['day_pillar']} | 时柱: {js['hour_pillar']} | 空亡: {js['kongwang']}")
    hx = result['hexagram']
    lines.append(f"\nFCAS Binary: {hx['binary_str']}")
    
    geju_list = result['geju']
    ji = [g for g in geju_list if g.jixiong == 1]
    xiong = [g for g in geju_list if g.jixiong == 0]
    lines.append(f"\n格局: 吉{len(ji)}条 凶{len(xiong)}条")
    for g in ji:
        lines.append(f"  [吉] {g.name}: {g.description}")
    for g in xiong:
        lines.append(f"  [凶] {g.name}: {g.description}")
    
    a = result['assessment']
    lines.append(f"\n萧吉三层判断:")
    lines.append(f"  卦宫: {a['palace']}({a['palace_wuxing']})")
    sy = a['shi_yao']
    lines.append(f"  世爻: 第{sy['position']}爻 {sy['dizhi']}({sy['wuxing']}) [{sy['liuqin']}]")
    lines.append(f"  生命阶段: {sy['changsheng']}({sy['changsheng_biz']}) | 旺衰: {sy['wangshuai']}")
    lines.append(f"  L1扶抑: {a['layer1_fuyi']} | L2有气: {a['layer2_qi']} | L3修正: {a['layer3_modifier']}")
    lines.append(f"  >>> {a['final_assessment']}")
    
    lines.append(f"\n爻位:")
    for y in a['all_yaos']:
        yy = "阳" if y['yinyang'] else "阴"
        lines.append(f"  {y['pos']}爻({y['criterion']}): {yy} {y['dizhi']}({y['wuxing']}) [{y['liuqin']}|{y['liuqin_biz']}]")
    
    yq = result['yingqi']
    if yq:
        lines.append(f"\n应期条件:")
        for c in yq:
            dz_n = DIZHI_NAMES.get(c.dizhi_value, "?")
            pri = ["核心","重要","参考"][c.priority]
            lines.append(f"  [{pri}] {c.cond_type}: {dz_n} — {c.description}")
    
    return "\n".join(lines)


def fcas_geju(year: int, month: int, day: int, hour: int, minute: int = 0) -> str:
    """格局判断: 返回当前时刻的所有奇门格局(吉凶)。"""
    dt = datetime(year, month, day, hour, minute)
    ju = paipan(dt)
    results = evaluate_all_geju(ju)
    
    ji = [g for g in results if g.jixiong == 1]
    xiong = [g for g in results if g.jixiong == 0]
    lines = [f"格局分析: 共{len(results)}条 (吉{len(ji)} 凶{len(xiong)})"]
    if ji:
        lines.append("\n吉格:")
        for g in ji:
            p_name = GONG_GUA_NAMES.get(g.palace, "全局") if g.palace else "全局"
            sv = ["轻","中","重","极"][g.severity]
            lines.append(f"  [{sv}] {g.name} / {g.name_biz} ({p_name}宫): {g.description}")
    if xiong:
        lines.append("\n凶格:")
        for g in xiong:
            p_name = GONG_GUA_NAMES.get(g.palace, "全局") if g.palace else "全局"
            sv = ["轻","中","重","极"][g.severity]
            lines.append(f"  [{sv}] {g.name} / {g.name_biz} ({p_name}宫): {g.description}")
    return "\n".join(lines)


def fcas_yingqi(year: int, month: int, day: int, hour: int, minute: int = 0) -> str:
    """应期推导: 返回当前状态的时间条件集合。"""
    dt = datetime(year, month, day, hour, minute)
    result = analyze(dt)
    yq = result['yingqi']
    
    lines = [f"应期推导: {len(yq)}个条件"]
    primary = [c for c in yq if c.priority == 0]
    secondary = [c for c in yq if c.priority == 1]
    tertiary = [c for c in yq if c.priority == 2]
    if primary:
        lines.append("\n核心条件(必须满足):")
        for c in primary:
            lines.append(f"  {c.cond_type}: {DIZHI_NAMES.get(c.dizhi_value, '?')} — {c.description}")
    if secondary:
        lines.append("\n重要条件(影响时机):")
        for c in secondary:
            lines.append(f"  {c.cond_type}: {DIZHI_NAMES.get(c.dizhi_value, '?')} — {c.description}")
    if tertiary:
        lines.append("\n参考条件(辅助判断):")
        for c in tertiary:
            lines.append(f"  {c.cond_type}: {DIZHI_NAMES.get(c.dizhi_value, '?')} — {c.description}")
    return "\n".join(lines)


if __name__ == "__main__":
    result = analyze(datetime.now())
    display_analysis(result)
