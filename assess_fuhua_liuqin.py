"""
assess_fuhua_liuqin.py - 符化六亲评估模块
=============================================

原文依据:
- 《御定奇门宝鉴》卷六: "生我之干为父母，我生之干为子息。比肩即是兄弟，
  克我官禄并疾。我克妻位及财。"
- 《执棋者》符化六亲技法: 以有效干五行为"我"，在盘中定位六亲星/宫
- 《股市预测方法大全》第13章: "妻财为用神(实质)+世爻为副神(名称)"

FCAS映射:
- 妻财(我克者) = 利润/收益/标的价值 → 核心用神
- 官鬼(克我者) = 监管/风险/外部压力 → 忌神
- 子孙(我生者) = 福神/生财之源 → 元神(生用神)
- 父母(生我者) = 成本/消息面/辛苦之神 → 仇神(克子孙)
- 兄弟(同我者) = 竞争/分财/同业 → 鼠神(克妻财)

核心设计:
- 每个标的有效干五行不同 → 同一盘中8标的的六亲落宫各不相同
- 这是per-stock区分的结构性来源，理论区分度高于符使(全局共享)
"""

# ============================================================
# 第一部分: 五行与天干映射表
# ============================================================

# 引擎整数索引→天干字符串转换 (兼容fcas_engine_v2的编码)
# 从引擎探测结果: {8:'甲', 0:'乙', 9:'丙', 1:'丁', 10:'戊', 2:'己', 11:'庚', 3:'辛', 12:'壬', 4:'癸'}
TIANGAN_IDX_TO_STR = {
    8: '甲', 0: '乙', 9: '丙', 1: '丁', 10: '戊',
    2: '己', 11: '庚', 3: '辛', 12: '壬', 4: '癸',
}

# 天干五行 (原文依据: 通用术数基础)
TIANGAN_WUXING = {
    '甲': '木', '乙': '木',
    '丙': '火', '丁': '火',
    '戊': '土', '己': '土',
    '庚': '金', '辛': '金',
    '壬': '水', '癸': '水',
}

# 五行生克关系 (原文依据: 《执棋者》核心原则层 "五行相生/相克")
WUXING_SHENG = {'木': '火', '火': '土', '土': '金', '金': '水', '水': '木'}  # A生B
WUXING_KE = {'木': '土', '土': '水', '水': '火', '火': '金', '金': '木'}      # A克B
WUXING_SHENG_WO = {'木': '水', '火': '木', '土': '火', '金': '土', '水': '金'}  # 生A者
WUXING_KE_WO = {'木': '金', '火': '水', '土': '木', '金': '火', '水': '土'}    # 克A者

# 宫位五行 (原文依据: 《执棋者》核心原则层)
PALACE_WUXING = {
    1: '水',  # 坎
    2: '土',  # 坤
    3: '木',  # 震
    4: '木',  # 巽
    5: '土',  # 中
    6: '金',  # 乾
    7: '金',  # 兑
    8: '土',  # 艮
    9: '火',  # 离
}

# 九星五行 (原文依据: 《宝鉴》卷二 九星所主)
STAR_WUXING = {
    0: '水',  # 天蓬 (坎水)
    1: '土',  # 天芮 (坤土)
    2: '木',  # 天冲 (震木)
    3: '木',  # 天辅 (巽木)
    4: '土',  # 天禽 (中土)
    5: '金',  # 天心 (乾金)
    6: '金',  # 天柱 (兑金)
    7: '土',  # 天任 (艮土)
    8: '火',  # 天英 (离火)
}

# 八门五行 (原文依据: 《执棋者》核心原则层)
GATE_WUXING = {
    0: '水',  # 休门
    1: '土',  # 生门
    2: '木',  # 伤门
    3: '木',  # 杜门
    4: '火',  # 景门
    5: '土',  # 死门
    6: '金',  # 惊门
    7: '金',  # 开门
}

# 八门吉凶属性 (原文依据: 《宝鉴》"释二吉四凶" + 生门开门休门为三吉门)
GATE_NATURE = {
    0: 'ji',    # 休门 - 吉
    1: 'ji',    # 生门 - 吉
    2: 'xiong', # 伤门 - 凶
    3: 'xiong', # 杜门 - 凶
    4: 'xiong', # 景门 - 凶(中性偏凶)
    5: 'xiong', # 死门 - 凶
    6: 'xiong', # 惊门 - 凶
    7: 'ji',    # 开门 - 吉
}

# 九星吉凶属性
STAR_NATURE = {
    0: 'xiong', # 天蓬 - 凶
    1: 'xiong', # 天芮 - 凶
    2: 'ji',    # 天冲 - 吉
    3: 'ji',    # 天辅 - 吉
    4: 'ji',    # 天禽 - 吉(中)
    5: 'ji',    # 天心 - 吉
    6: 'xiong', # 天柱 - 凶
    7: 'ji',    # 天任 - 吉
    8: 'xiong', # 天英 - 凶(中性偏凶)
}

# 八神吉凶
DEITY_NATURE = {
    0: 'ji',    # 值符 - 吉
    1: 'xiong', # 腾蛇 - 凶
    2: 'ji',    # 太阴 - 吉
    3: 'ji',    # 六合 - 吉
    4: 'xiong', # 白虎 - 凶(勾陈位)
    5: 'xiong', # 朱雀 - 凶(玄武位)
    6: 'ji',    # 九地 - 吉(中性)
    7: 'ji',    # 九天 - 吉(中性)
}

# 月令旺衰 (原文依据: 《宝鉴》卷五 "水旺于冬、相于春...")
# 地支→月份: 寅=1月, 卯=2月, ... 丑=12月
# 月支→五行旺衰: 旺(+2), 相(+1), 休(0), 囚(-1), 废/死(-2)
MONTH_BRANCH_SEASON = {
    '寅': '春', '卯': '春', '辰': '春',  # 实际辰为四季，简化处理
    '巳': '夏', '午': '夏', '未': '夏',
    '申': '秋', '酉': '秋', '戌': '秋',
    '亥': '冬', '子': '冬', '丑': '冬',
}

# 五行在四季的旺衰值 (原文依据: 《宝鉴》卷五)
# 旺=2, 相=1, 休=0, 囚=-1, 废/死=-2
WUXING_SEASONAL_STRENGTH = {
    '木': {'春': 2, '夏': 1, '四季': 0, '秋': -1, '冬': -2},
    '火': {'春': 1, '夏': 2, '四季': -1, '秋': -2, '冬': 0},  # 废→冬休
    '土': {'春': -1, '夏': 0, '四季': 2, '秋': 1, '冬': -2},  # 废→冬
    '金': {'春': 0, '夏': -1, '四季': -2, '秋': 2, '冬': 1},  # 废→四季
    '水': {'春': -2, '夏': 0, '四季': -1, '秋': 0, '冬': 2},  # 修正
}

# 四季月 (辰戌丑未)
SIJI_BRANCHES = {'辰', '戌', '丑', '未'}

# 六甲遁干表 (原文依据: 通用术数)
LIUJIA_DUN = {
    '甲子': '戊', '甲戌': '己', '甲申': '庚',
    '甲午': '辛', '甲辰': '壬', '甲寅': '癸',
}


# ============================================================
# 第二部分: 标的信息 (与stock_positioning.py一致)
# ============================================================

STOCK_INFO = {
    '000651.SZ': {'name': '格力电器', 'ipo_day_gz': '己未', 'effective_gan': '己'},
    '000063.SZ': {'name': '中兴通讯', 'ipo_day_gz': '甲子', 'effective_gan': '戊'},
    '000858.SZ': {'name': '五粮液',   'ipo_day_gz': '甲辰', 'effective_gan': '壬'},
    '600276.SH': {'name': '恒瑞医药', 'ipo_day_gz': '己酉', 'effective_gan': '己'},
    '600036.SH': {'name': '招商银行', 'ipo_day_gz': '丁未', 'effective_gan': '丁'},
    '600547.SH': {'name': '山东黄金', 'ipo_day_gz': '癸酉', 'effective_gan': '癸'},
    '601318.SH': {'name': '中国平安', 'ipo_day_gz': '甲午', 'effective_gan': '辛'},
    '601857.SH': {'name': '中国石油', 'ipo_day_gz': '癸卯', 'effective_gan': '癸', 'liuqin_exclude': True},
    '601899.SH': {'name': '紫金矿业', 'ipo_day_gz': '乙未', 'effective_gan': '乙'},
    '601012.SH': {'name': '隆基绿能', 'ipo_day_gz': '壬寅', 'effective_gan': '壬'},
    '688256.SH': {'name': '寒武纪',   'ipo_day_gz': '甲子', 'effective_gan': '戊'},
    '601138.SH': {'name': '工业富联', 'ipo_day_gz': '辛未', 'effective_gan': '辛'},
}


# ============================================================
# 第三部分: 核心函数
# ============================================================

def get_wuxing(gan):
    """获取天干的五行"""
    return TIANGAN_WUXING.get(gan)


def get_liuqin_map(my_gan):
    """
    根据"我"的天干，返回六亲对应的五行

    原文依据: 《宝鉴》卷六
    "生我之干为父母，我生之干为子息。比肩即是兄弟，
     克我官禄并疾。我克妻位及财。"

    Returns:
        dict: {
            '妻财': wuxing,   # 我克者
            '官鬼': wuxing,   # 克我者
            '父母': wuxing,   # 生我者
            '子孙': wuxing,   # 我生者
            '兄弟': wuxing,   # 同我者
        }
    """
    my_wx = get_wuxing(my_gan)
    if not my_wx:
        return None

    return {
        '妻财': WUXING_KE[my_wx],       # 我克者
        '官鬼': WUXING_KE_WO[my_wx],    # 克我者
        '父母': WUXING_SHENG_WO[my_wx], # 生我者
        '子孙': WUXING_SHENG[my_wx],    # 我生者
        '兄弟': my_wx,                  # 同我者
    }


# 天干阴阳属性
TIANGAN_YINYANG = {
    '甲': '阳', '乙': '阴',
    '丙': '阳', '丁': '阴',
    '戊': '阳', '己': '阴',
    '庚': '阳', '辛': '阴',
    '壬': '阳', '癸': '阴',
}


def get_liuqin_gans(my_gan):
    """
    根据"我"的天干，返回六亲对应的具体天干（含正偏区分）

    原文依据:
    - 《执棋者》核心原则层: "结合阴阳属性(与'我'同性为偏，异性为正)"
    - 《刘文元奇门启悟》: "正财为妻子，偏财为情人"

    FCAS映射:
    - 正财(异性我克): 主要收益来源 → 权重更高
    - 偏财(同性我克): 次要/投机收益 → 权重稍低

    Returns:
        dict: {
            '正财': gan,     # 异性我克 (主要收益)
            '偏财': gan,     # 同性我克 (次要收益)
            '正官': gan,     # 异性克我 (正面监管)
            '偏官': gan,     # 同性克我 (攻击性压力)
            '正印': gan,     # 异性生我 (正面支撑)
            '偏印': gan,     # 同性生我
            '食神': gan,     # 同性我生 (稳定产出)
            '伤官': gan,     # 异性我生 (创新但不稳定)
            '比肩': gan,     # 同性同我 (同质竞争)
            '劫财': gan,     # 异性同我 (抢夺资源)
        }
    """
    my_wx = get_wuxing(my_gan)
    my_yy = TIANGAN_YINYANG.get(my_gan)
    if not my_wx or not my_yy:
        return None

    result = {}
    # 我克者(妻财): 正财=异性, 偏财=同性
    qc_wx = WUXING_KE[my_wx]
    for g, w in TIANGAN_WUXING.items():
        if w == qc_wx:
            if TIANGAN_YINYANG[g] != my_yy:
                result['正财'] = g
            else:
                result['偏财'] = g

    # 克我者(官鬼): 正官=异性, 偏官=同性
    gg_wx = WUXING_KE_WO[my_wx]
    for g, w in TIANGAN_WUXING.items():
        if w == gg_wx:
            if TIANGAN_YINYANG[g] != my_yy:
                result['正官'] = g
            else:
                result['偏官'] = g

    # 生我者(父母): 正印=异性, 偏印=同性
    fm_wx = WUXING_SHENG_WO[my_wx]
    for g, w in TIANGAN_WUXING.items():
        if w == fm_wx:
            if TIANGAN_YINYANG[g] != my_yy:
                result['正印'] = g
            else:
                result['偏印'] = g

    # 我生者(子孙): 食神=同性, 伤官=异性
    zs_wx = WUXING_SHENG[my_wx]
    for g, w in TIANGAN_WUXING.items():
        if w == zs_wx:
            if TIANGAN_YINYANG[g] == my_yy:
                result['食神'] = g
            else:
                result['伤官'] = g

    # 同我者(兄弟): 比肩=同性, 劫财=异性
    for g, w in TIANGAN_WUXING.items():
        if w == my_wx and g != my_gan:
            if TIANGAN_YINYANG[g] == my_yy:
                result['比肩'] = g
            else:
                result['劫财'] = g

    return result


def find_gan_in_pan(ju, target_wuxing, exclude_gan=None):
    """
    在奇门盘天盘中找到所有属于指定五行的天干及其落宫

    Args:
        ju: QimenJu实例
        target_wuxing: 目标五行 (如 '土')
        exclude_gan: 排除的天干 (如有效干本身，避免自身入选)

    Returns:
        list of dict: [{'gan': '戊', 'palace': 2, 'palace_wx': '土', ...}, ...]
    """
    results = []
    heaven = ju.heaven  # 天盘干: {palace_id: gan_index_or_str}

    for palace_id, gan_raw in heaven.items():
        if palace_id == 5:
            continue  # 中宫跳过(天禽寄宫)

        # 兼容整数索引和字符串天干
        if isinstance(gan_raw, int):
            gan = TIANGAN_IDX_TO_STR.get(gan_raw)
        else:
            gan = gan_raw

        if not gan:
            continue

        gan_wx = get_wuxing(gan)
        if gan_wx == target_wuxing:
            if exclude_gan and gan == exclude_gan:
                continue
            results.append({
                'gan': gan,
                'palace': palace_id,
                'palace_wx': PALACE_WUXING[palace_id],
            })

    return results


def find_specific_gan_in_pan(ju, target_gan):
    """
    在奇门盘天盘中精确查找指定天干的落宫

    这是per-stock区分的关键：同五行但不同天干（戊vs己）落在不同宫位

    Args:
        ju: QimenJu实例
        target_gan: 目标天干字符串 (如 '壬')

    Returns:
        list of dict: [{'gan': '壬', 'palace': 3, 'palace_wx': '木', ...}, ...]
    """
    results = []
    heaven = ju.heaven

    for palace_id, gan_raw in heaven.items():
        if palace_id == 5:
            continue

        if isinstance(gan_raw, int):
            gan = TIANGAN_IDX_TO_STR.get(gan_raw)
        else:
            gan = gan_raw

        if gan == target_gan:
            results.append({
                'gan': gan,
                'palace': palace_id,
                'palace_wx': PALACE_WUXING[palace_id],
            })

    return results


def get_seasonal_strength(wuxing, month_branch):
    """
    获取五行在当前月令的旺衰值

    原文依据: 《宝鉴》卷五
    "水旺于冬、相于春、休于夏、囚于四季、废于秋"等

    Returns:
        int: 旺=2, 相=1, 休=0, 囚=-1, 废=-2
    """
    if month_branch in SIJI_BRANCHES:
        season = '四季'
    else:
        season = MONTH_BRANCH_SEASON.get(month_branch, '春')

    return WUXING_SEASONAL_STRENGTH.get(wuxing, {}).get(season, 0)


def check_kongwang(palace_id, kongwang_palaces):
    """检查宫位是否空亡"""
    return palace_id in kongwang_palaces


def shengke_relation(a_wx, b_wx):
    """
    判断A对B的五行关系

    Returns:
        str: 'sheng'=A生B, 'ke'=A克B, 'bi'=比和,
             'xie'=A泄于B(B生A→A被泄), 'shou_ke'=A受B克(B克A)
    """
    if a_wx == b_wx:
        return 'bi'
    if WUXING_SHENG.get(a_wx) == b_wx:
        return 'sheng'  # A生B
    if WUXING_KE.get(a_wx) == b_wx:
        return 'ke'     # A克B
    if WUXING_SHENG.get(b_wx) == a_wx:
        return 'xie'    # B生A，A被泄
    if WUXING_KE.get(b_wx) == a_wx:
        return 'shou_ke'  # B克A，A受克
    return 'unknown'


def evaluate_palace_quality(ju, palace_id, month_branch):
    """
    评估一个宫位的综合质量 (星门神+旺衰+环境)

    原文依据:
    - 《宝鉴》卷六 八门分论六亲吉凶
    - 《执棋者》详细分析格式: 落宫→八神→九星→八门→旺衰

    Returns:
        dict: {
            'score': float,
            'star': int, 'gate': int, 'deity': int,
            'star_nature': str, 'gate_nature': str, 'deity_nature': str,
            'star_strength': int, 'gate_strength': int,
            'palace_shengke_gan': str,
            'is_kongwang': bool,
            'details': str
        }
    """
    score = 0.0
    details = []

    star = ju.stars.get(palace_id)
    gate = ju.gates.get(palace_id)
    deity = ju.deities.get(palace_id)
    heaven_gan_raw = ju.heaven.get(palace_id)
    ground_gan_raw = ju.ground.get(palace_id)
    # 兼容整数索引和字符串
    heaven_gan = TIANGAN_IDX_TO_STR.get(heaven_gan_raw, heaven_gan_raw) if isinstance(heaven_gan_raw, int) else heaven_gan_raw
    ground_gan = TIANGAN_IDX_TO_STR.get(ground_gan_raw, ground_gan_raw) if isinstance(ground_gan_raw, int) else ground_gan_raw
    p_wx = PALACE_WUXING[palace_id]

    # --- D1: 九星吉凶 + 旺衰 ---
    star_wx = STAR_WUXING.get(star, '土')
    star_nat = STAR_NATURE.get(star, 'xiong')
    star_seasonal = get_seasonal_strength(star_wx, month_branch)

    if star_nat == 'ji':
        score += 1.0
        if star_seasonal >= 1:  # 旺相
            score += 0.5
            details.append(f"星吉旺+1.5")
        else:
            details.append(f"星吉+1.0")
    else:
        # 凶星：如果休囚→凶性减弱 (原文: 凶星休囚→吉)
        if star_seasonal <= -1:
            score += 0.5  # 凶星休囚，凶不起
            details.append(f"凶星休囚→减凶+0.5")
        else:
            score -= 1.0
            details.append(f"星凶-1.0")

    # --- D2: 八门吉凶 + 旺衰 ---
    gate_wx = GATE_WUXING.get(gate, '土')
    gate_nat = GATE_NATURE.get(gate, 'xiong')
    gate_seasonal = get_seasonal_strength(gate_wx, month_branch)

    # 门迫检查: 宫克门 (原文: "吉门被迫吉不就，凶门被迫凶不起")
    # 门迫: 宫克门 (原文: 《宝鉴》"宫克门，门克宫，皆不吉")
    # shengke_relation(p_wx, gate_wx): p对gate的关系, 'ke'=A克B
    gate_forced = (shengke_relation(p_wx, gate_wx) == 'ke')  # 宫克门=门迫

    if gate_nat == 'ji':
        if gate_forced:
            score += 0.0  # 吉门被迫，吉不就
            details.append(f"吉门被迫→0")
        elif gate_seasonal >= 1:
            score += 1.5
            details.append(f"吉门旺+1.5")
        else:
            score += 1.0
            details.append(f"吉门+1.0")
    else:
        if gate_forced:
            score += 0.5  # 凶门被迫，凶不起
            details.append(f"凶门被迫→减凶+0.5")
        elif gate_seasonal <= -1:
            score += 0.0  # 凶门休囚，中性
            details.append(f"凶门休囚→0")
        else:
            score -= 1.0
            details.append(f"门凶-1.0")

    # --- D3: 八神 ---
    deity_nat = DEITY_NATURE.get(deity, 'xiong')
    if deity_nat == 'ji':
        score += 0.5
        details.append(f"神吉+0.5")
    else:
        score -= 0.5
        details.append(f"神凶-0.5")

    # --- D4: 落宫生克天盘干 ---
    if heaven_gan:
        hg_wx = get_wuxing(heaven_gan)
        rel = shengke_relation(p_wx, hg_wx)
        if rel == 'sheng':    # 宫生干=滋养
            score += 1.0
            details.append(f"宫生干+1.0")
        elif rel == 'shou_ke':  # 干克宫 (不明显，不计)
            pass
        elif rel == 'ke':     # 宫克干=压制
            score -= 1.0
            details.append(f"宫克干-1.0")

    # --- D5: 空亡检查 ---
    is_kw = False
    if hasattr(ju, 'kongwang'):
        kw = ju.kongwang
        # kongwang是地支列表，需要转换为宫位
        # 简化: 直接传入已计算的空亡宫位列表
        # 这里先标记，外部传入
        pass

    return {
        'score': score,
        'star': star,
        'gate': gate,
        'deity': deity,
        'star_nature': star_nat,
        'gate_nature': gate_nat,
        'deity_nature': deity_nat,
        'star_strength': star_seasonal,
        'gate_strength': gate_seasonal,
        'gate_forced': gate_forced,
        'heaven_gan': heaven_gan,
        'ground_gan': ground_gan,
        'details': '; '.join(details),
    }


def assess_stock_liuqin(ju, stock_code, month_branch, kongwang_palaces=None):
    """
    核心函数: 对单个标的进行符化六亲评估

    逻辑:
    1. 以标的有效干五行为"我"
    2. 确定六亲(妻财/官鬼/子孙/父母/兄弟)对应的五行
    3. 在天盘找到对应的天干和落宫
    4. 重点评估:
       - 妻财(用神): 状态好→利润可期
       - 子孙(元神): 生用神，状态好→持续助力
       - 官鬼(忌神): 状态强→风险大
       - 兄弟(鼠神): 动则克财
    5. 综合打分

    原文依据:
    - 《股市预测方法大全》第13章: "妻财为用神(实质)"
    - "子孙为福神，为生用神之元神"
    - "兄弟为鼠神，专克妻财"
    - "官鬼为忧患之神"

    Returns:
        dict: {
            'stock_code': str,
            'effective_gan': str,
            'my_wuxing': str,
            'qicai': {...},      # 妻财信息
            'guangui': {...},    # 官鬼信息
            'zisun': {...},      # 子孙信息
            'fumu': {...},       # 父母信息
            'xiongdi': {...},    # 兄弟信息
            'total_score': float,
            'label': str,
            'reasoning': str,
        }
    """
    if kongwang_palaces is None:
        kongwang_palaces = set()

    info = STOCK_INFO.get(stock_code)
    if not info:
        return None
    if info.get('liuqin_exclude'):
        return None

    eff_gan = info['effective_gan']
    my_wx = get_wuxing(eff_gan)
    liuqin_map = get_liuqin_map(eff_gan)      # 五行级别(向后兼容)
    liuqin_gans = get_liuqin_gans(eff_gan)    # 精确天干级别(正偏区分)

    result = {
        'stock_code': stock_code,
        'stock_name': info['name'],
        'effective_gan': eff_gan,
        'my_wuxing': my_wx,
    }

    # ---- 用精确天干查找六亲在盘中的位置 ----
    # 关键改动: 用find_specific_gan_in_pan按天干精确匹配
    # 这样戊(土)和己(土)的正财/偏财落在不同宫位 → per-stock区分

    def _eval_gan(target_gan, lq_wx):
        """查找并评估指定天干在盘中的状态"""
        if not target_gan:
            return []
        hits = find_specific_gan_in_pan(ju, target_gan)
        evals = []
        for hit in hits:
            pal_eval = evaluate_palace_quality(ju, hit['palace'], month_branch)
            pal_eval['gan'] = hit['gan']
            pal_eval['palace'] = hit['palace']
            pal_eval['is_kongwang'] = hit['palace'] in kongwang_palaces
            if pal_eval['is_kongwang']:
                gan_seasonal = get_seasonal_strength(lq_wx, month_branch)
                if gan_seasonal >= 1:
                    pal_eval['kongwang_type'] = 'fake'
                    pal_eval['score'] -= 0.5
                else:
                    pal_eval['kongwang_type'] = 'real'
                    pal_eval['score'] -= 2.0
                    pal_eval['details'] += '; 真空亡-2.0'
            evals.append(pal_eval)
        return evals

    qc_wx = liuqin_map['妻财']
    gg_wx = liuqin_map['官鬼']
    zs_wx = liuqin_map['子孙']
    fm_wx = liuqin_map['父母']
    xd_wx = liuqin_map['兄弟']

    # 精确天干查找 (正偏分开)
    zhengcai_evals = _eval_gan(liuqin_gans.get('正财'), qc_wx)
    piancai_evals = _eval_gan(liuqin_gans.get('偏财'), qc_wx)
    zhengguan_evals = _eval_gan(liuqin_gans.get('正官'), gg_wx)
    pianguan_evals = _eval_gan(liuqin_gans.get('偏官'), gg_wx)
    shishen_evals = _eval_gan(liuqin_gans.get('食神'), zs_wx)
    shangguan_evals = _eval_gan(liuqin_gans.get('伤官'), zs_wx)
    zhengyin_evals = _eval_gan(liuqin_gans.get('正印'), fm_wx)
    pianyin_evals = _eval_gan(liuqin_gans.get('偏印'), fm_wx)
    bijian_evals = _eval_gan(liuqin_gans.get('比肩'), xd_wx)
    jiecai_evals = _eval_gan(liuqin_gans.get('劫财'), xd_wx)

    # 合并为六亲级别 (正偏合并，但保留区分信息)
    all_qc = zhengcai_evals + piancai_evals
    all_gg = zhengguan_evals + pianguan_evals
    all_zs = shishen_evals + shangguan_evals
    all_fm = zhengyin_evals + pianyin_evals
    all_xd = bijian_evals + jiecai_evals

    # ---- 综合打分 ----
    # v2修正 (基于4018条回测诊断, 2026-04-07):
    #
    # 原文依据修正:
    # 1. 官鬼: 原按"忌神"取反向(-1.0)，但诊断显示官鬼中度活跃(0~1.5)
    #    → 1W +0.521%，是最强单因子。原理: "克则动"(v10已验证)
    #    → 官鬼克我 = 外部力量推动标的运动 = 正向(适度时)
    #    → 改为: 正向权重×0.6，但加非线性衰减(过强则压制)
    #
    # 2. 父母: 原按"仇神克子孙"取反向(-0.5)，但诊断显示父母>2.5
    #    → 1W +0.496%，最强单因子。原文: 《股市预测方法大全》第13章
    #    "官鬼或父母动生用神或卦身，可能有利好消息或动作"
    #    → 父母 = 消息面/政策支撑，强旺 = 利好充足
    #    → 改为: 正向权重×0.5
    #
    # 3. 兄弟: 原按"鼠神克财"取反向(-0.8)，诊断显示兄弟不现
    #    → 1W -0.14%，唯一负值。兄弟在场 = 市场活跃度/流动性
    #    → 改为: 正向权重×0.3(存在即正向), 不现=-0.3(流动性缺失)
    #
    # 4. 妻财: 诊断显示妻财负分 → 1W +0.246%。"克则动"
    #    → 妻财受克 = 财在运动中 = 不一定凶
    #    → 维持正向但降低权重×1.0(原×1.5)，不现惩罚降为-1.0

    total = 0.0
    reasoning_parts = []

    # 妻财/用神 (核心，但权重从1.5降到1.0，减少过度主导)
    if zhengcai_evals:
        best = max(zhengcai_evals, key=lambda x: x['score'])
        sc = best['score'] * 1.0
        total += sc
        reasoning_parts.append(f"正财{best['gan']}落{best['palace']}宫({best['score']:.1f}×1.0={sc:.1f})")
        result['qicai'] = best
    elif piancai_evals:
        best = max(piancai_evals, key=lambda x: x['score'])
        sc = best['score'] * 0.7
        total += sc
        reasoning_parts.append(f"偏财{best['gan']}落{best['palace']}宫({best['score']:.1f}×0.7={sc:.1f})")
        result['qicai'] = best
    else:
        total -= 1.0  # 降低：不现从-2.0改为-1.0
        reasoning_parts.append("妻财不现-1.0")
        result['qicai'] = {'score': -1.0, 'details': '不现'}

    # 偏财补充(如果正财已存在)
    if zhengcai_evals and piancai_evals:
        best_pc = max(piancai_evals, key=lambda x: x['score'])
        if best_pc['score'] > 0:
            bonus = best_pc['score'] * 0.2
            total += bonus
            reasoning_parts.append(f"偏财补充+{bonus:.1f}")

    # 子孙/元神 (生用神之源，维持正向)
    if all_zs:
        best_zs = max(all_zs, key=lambda x: x['score'])
        zs_score = best_zs['score'] * 0.8
        total += zs_score
        reasoning_parts.append(f"子孙{best_zs['gan']}落{best_zs['palace']}宫({best_zs['score']:.1f}×0.8)")
        result['zisun'] = best_zs
    else:
        total -= 0.5
        reasoning_parts.append("子孙不现-0.5")
        result['zisun'] = {'score': -0.5, 'details': '不现'}

    # 官鬼 → 正向(克则动)，但非线性：中度最佳，过强衰减
    # 诊断: 官鬼0~1.5 → 1W +0.521% (最强)
    #        官鬼>1.5 → 效果减弱(压制过度)
    if all_gg:
        strongest_gg = max(all_gg, key=lambda x: x['score'])
        raw = strongest_gg['score']
        if raw <= 1.5:
            gg_impact = raw * 0.6  # 中度活跃→正向推动
        else:
            gg_impact = 1.5 * 0.6 + (raw - 1.5) * (-0.3)  # 过强→边际递减
        total += gg_impact
        reasoning_parts.append(f"官鬼{strongest_gg['gan']}落{strongest_gg['palace']}宫(raw={raw:.1f}→{gg_impact:+.1f})")
        result['guangui'] = strongest_gg
    else:
        total -= 0.3  # 官鬼不现=无外力推动=微负
        reasoning_parts.append("官鬼不现-0.3")
        result['guangui'] = {'score': 0.0, 'details': '不现'}

    # 兄弟 → 正向(存在=市场活跃度)
    # 诊断: 兄弟不现 → 1W -0.14% (唯一负值)
    if all_xd:
        strongest_xd = max(all_xd, key=lambda x: x['score'])
        xd_impact = strongest_xd['score'] * 0.3
        total += xd_impact
        reasoning_parts.append(f"兄弟{strongest_xd['gan']}落{strongest_xd['palace']}宫({strongest_xd['score']:.1f}×0.3)")
        result['xiongdi'] = strongest_xd
    else:
        total -= 0.3  # 不现=流动性缺失
        reasoning_parts.append("兄弟不现-0.3")
        result['xiongdi'] = {'score': 0.0, 'details': '不现'}

    # 父母 → 正向(消息面/政策支撑)
    # 诊断: 父母>2.5 → 1W +0.496% (最强单因子)
    if all_fm:
        strongest_fm = max(all_fm, key=lambda x: x['score'])
        fm_impact = strongest_fm['score'] * 0.5
        total += fm_impact
        reasoning_parts.append(f"父母{strongest_fm['gan']}落{strongest_fm['palace']}宫({strongest_fm['score']:.1f}×0.5)")
        result['fumu'] = strongest_fm
    else:
        result['fumu'] = {'score': 0.0, 'details': '不现'}

    # ---- 贪生忘克 (保留，但方向调整) ----
    # 兄弟和子孙同时强 → 连续生相，能量流畅
    if all_xd and all_zs:
        best_xd = max(all_xd, key=lambda x: x['score'])
        best_zs_s = max(all_zs, key=lambda x: x['score'])['score']
        if best_xd['score'] > 1.0 and best_zs_s > 1.0:
            correction = 0.3
            total += correction
            reasoning_parts.append(f"贪生忘克+{correction}")

    # ---- 标签 ----
    # v2阈值 (基于4018条分数分布校准, 2026-04-07):
    # 分数均值=+2.05, 中位数=+2.06, P10=+0.10, P90=+4.05
    # 13W效果: ≥5→+4.654%, [3,5)→+2.7%, [1,3)→+3.0%, [-1,0)→+1.381%(最差)
    # 设计: 以中位数为NEUTRAL中心, 极值两端拉开
    result['total_score'] = round(total, 2)
    result['reasoning'] = ' | '.join(reasoning_parts)

    if total >= 4.5:
        result['label'] = 'STRONGLY_FAVORABLE'  # ~P85+
    elif total >= 3.0:
        result['label'] = 'FAVORABLE'           # ~P60-P85
    elif total >= 1.5:
        result['label'] = 'PARTIAL_GOOD'        # ~P30-P60
    elif total >= 0.5:
        result['label'] = 'NEUTRAL'             # ~P15-P30
    elif total >= -0.5:
        result['label'] = 'PARTIAL_BAD'         # ~P5-P15
    else:
        result['label'] = 'UNFAVORABLE'          # ~P5-

    return result


def assess_all_stocks_liuqin(ju, month_branch, kongwang_palaces=None, stock_codes=None):
    """
    批量评估所有标的的符化六亲状态

    Args:
        ju: QimenJu实例
        month_branch: 月支 (如 '卯')
        kongwang_palaces: 空亡宫位集合
        stock_codes: 要评估的标的列表，默认全部

    Returns:
        list of dict: 每个标的的评估结果
    """
    if stock_codes is None:
        stock_codes = list(STOCK_INFO.keys())

    results = []
    for code in stock_codes:
        r = assess_stock_liuqin(ju, code, month_branch, kongwang_palaces)
        if r:
            results.append(r)

    return results


# ============================================================
# 第四部分: 测试/示例
# ============================================================

if __name__ == '__main__':
    # 独立测试: 验证六亲映射逻辑
    print("=" * 60)
    print("符化六亲映射测试")
    print("=" * 60)

    test_cases = [
        ('己', '土'),  # 格力/恒瑞: 土克水=妻财, 木克土=官鬼
        ('戊', '土'),  # 中兴/寒武纪
        ('壬', '水'),  # 五粮液/隆基
        ('丁', '火'),  # 招商银行
        ('癸', '水'),  # 山东黄金/中石油
        ('辛', '金'),  # 中国平安/工业富联
        ('乙', '木'),  # 紫金矿业
    ]

    for gan, expected_wx in test_cases:
        lq = get_liuqin_map(gan)
        wx = get_wuxing(gan)
        assert wx == expected_wx, f"{gan} wuxing mismatch"
        print(f"\n{gan}({wx}):")
        print(f"  妻财(我克): {lq['妻财']}行 → 天干:{[k for k,v in TIANGAN_WUXING.items() if v==lq['妻财']]}")
        print(f"  官鬼(克我): {lq['官鬼']}行 → 天干:{[k for k,v in TIANGAN_WUXING.items() if v==lq['官鬼']]}")
        print(f"  子孙(我生): {lq['子孙']}行 → 天干:{[k for k,v in TIANGAN_WUXING.items() if v==lq['子孙']]}")
        print(f"  父母(生我): {lq['父母']}行 → 天干:{[k for k,v in TIANGAN_WUXING.items() if v==lq['父母']]}")
        print(f"  兄弟(同我): {lq['兄弟']}行 → 天干:{[k for k,v in TIANGAN_WUXING.items() if v==lq['兄弟']]}")

    # 验证: 不同标的在同一盘中的六亲不同
    print("\n" + "=" * 60)
    print("Per-stock区分验证: 不同有效干 → 不同妻财五行")
    print("=" * 60)
    seen = {}
    for code, info in STOCK_INFO.items():
        lq = get_liuqin_map(info['effective_gan'])
        qc_wx = lq['妻财']
        key = info['effective_gan']
        if key not in seen:
            seen[key] = []
        seen[key].append(info['name'])
        print(f"  {info['name']}({info['effective_gan']}/{get_wuxing(info['effective_gan'])}): 妻财={qc_wx}")

    # 统计区分度
    unique_qc = set()
    for code, info in STOCK_INFO.items():
        lq = get_liuqin_map(info['effective_gan'])
        unique_qc.add(lq['妻财'])
    print(f"\n  8标的中妻财五行种类: {len(unique_qc)} (越多区分度越高)")
    print(f"  五行: {unique_qc}")
