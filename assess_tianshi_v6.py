"""
FCAS 天时层 v6 评估函数
直接定位（find_stock_palace）+ 遁法定位 结合版

依据：
- 《执棋者》遁法四步流程 + 详细分析格式
- 《御定奇门宝鉴》格局吉凶判断
- 排盘引擎 fcas_engine_v2.py (已修复 2026-04-06)

使用方式：
    from fcas_engine_v2 import paipan
    from assess_tianshi_v6 import assess_stock_tianshi_v6, print_assessment
    from datetime import datetime
    ju = paipan(datetime(2026, 4, 6, 17, 0))
    result = assess_stock_tianshi_v6(ju, '000651.SZ')
    print_assessment(result)
"""

# ============================================================
# QimenJu → 内部字典 适配层
# ============================================================
# fcas_engine_v2.paipan() 返回 QimenJu 对象，属性用数字编码
# 本模块内部用中文字符串，这里做转换

# 引擎编码 → 中文字符串 映射表
_TIANGAN_DECODE = {8:'甲', 0:'乙', 9:'丙', 1:'丁', 10:'戊', 2:'己', 11:'庚', 3:'辛', 12:'壬', 4:'癸'}
_STAR_DECODE = {0:'天蓬', 1:'天芮', 2:'天冲', 3:'天辅', 4:'天禽', 5:'天心', 6:'天柱', 7:'天任', 8:'天英'}
_GATE_DECODE = {0:'休门', 1:'生门', 2:'伤门', 3:'杜门', 4:'景门', 5:'死门', 6:'惊门', 7:'开门'}
_DEITY_DECODE_YANG = {0:'值符', 1:'腾蛇', 2:'太阴', 3:'六合', 4:'勾陈', 5:'朱雀', 6:'九地', 7:'九天'}
_DEITY_DECODE_YIN = {0:'值符', 1:'腾蛇', 2:'太阴', 3:'六合', 4:'白虎', 5:'玄武', 6:'九地', 7:'九天'}
_DIZHI_DECODE = {0:'子', 1:'丑', 2:'寅', 3:'卯', 4:'辰', 5:'巳', 6:'午', 7:'未', 8:'申', 9:'酉', 10:'戌', 11:'亥'}


def _convert_qimenju_to_dict(ju):
    """
    将 QimenJu 对象转换为本模块内部使用的字典格式
    
    QimenJu属性：
        ju.heaven[gong] = tiangan编码 (天盘干)
        ju.ground[gong] = tiangan编码 (地盘干)
        ju.stars[gong]  = star编码 (九星)
        ju.gates[gong]  = gate编码 (八门，中5宫无门)
        ju.deities[gong]= deity编码 (八神，中5宫无神)
        ju.is_yangdun   = bool
        ju.ju_number    = int
        ju.month_branch = int (月支编码，巽4=辰月? 实际是地支索引)
        ju.day_gz       = (gan编码, zhi编码)
        ju.hour_gz      = (gan编码, zhi编码)
        ju.kongwang     = (zhi编码, zhi编码)
        ju.zhifu_star   = star编码
        ju.zhishi_gate  = gate编码
    """
    # 选择八神解码表（阳遁用勾陈朱雀，阴遁用白虎玄武）
    # 注意：引擎里阳遁阴遁的八神顺序可能不同，但DEITY_NAMES是统一的
    # 实际引擎用 勾陈=4, 朱雀=5 不区分阴阳，这里统一处理
    deity_decode = _DEITY_DECODE_YANG  # 引擎编码统一
    
    # 月支：引擎的month_branch可能是宫号或地支编码
    # 从实际输出看 month_branch=4，对应巽4宫
    # 但我们需要的是月支的地支名（如"卯"），用于旺衰计算
    # month_branch=4 在清明节气→辰月，地支=辰
    # 实际上需要从月柱获取，如果有month_gz的话
    # 先用宫号映射到地支作为近似
    _gong_to_month_zhi = {
        1: '子', 2: '丑', 3: '卯', 4: '辰',  # 注意：巽4对应辰巳，取辰
        6: '戌', 7: '酉', 8: '丑', 9: '午',
    }
    
    # 更准确的方式：从month_gz获取月支
    month_zhi_str = '辰'  # 默认
    if hasattr(ju, 'month_gz') and ju.month_gz:
        _, mz = ju.month_gz
        month_zhi_str = _DIZHI_DECODE.get(mz, '辰')
    elif hasattr(ju, 'month_branch'):
        month_zhi_str = _gong_to_month_zhi.get(ju.month_branch, '辰')
    
    # 日干日支
    day_gan_str = _TIANGAN_DECODE.get(ju.day_gz[0], '?') if ju.day_gz else '?'
    day_zhi_str = _DIZHI_DECODE.get(ju.day_gz[1], '?') if ju.day_gz else '?'
    hour_gan_str = _TIANGAN_DECODE.get(ju.hour_gz[0], '?') if ju.hour_gz else '?'
    hour_zhi_str = _DIZHI_DECODE.get(ju.hour_gz[1], '?') if ju.hour_gz else '?'
    
    # 空亡（地支编码→地支名）
    kongwang_list = []
    if ju.kongwang:
        for kw in ju.kongwang:
            kw_str = _DIZHI_DECODE.get(kw, '')
            if kw_str:
                kongwang_list.append(kw_str)
    
    # 构建宫位字典
    palaces = {}
    for gong in [1, 2, 3, 4, 6, 7, 8, 9]:
        p = {
            'tianpan_gan': _TIANGAN_DECODE.get(ju.heaven.get(gong), '?'),
            'dipan_gan': _TIANGAN_DECODE.get(ju.ground.get(gong), '?'),
            'star': _STAR_DECODE.get(ju.stars.get(gong), '?'),
        }
        # 八门：中5宫无门
        gate_code = ju.gates.get(gong)
        p['door'] = _GATE_DECODE.get(gate_code, '') if gate_code is not None else ''
        
        # 八神：中5宫无神
        deity_code = ju.deities.get(gong)
        p['shen'] = deity_decode.get(deity_code, '') if deity_code is not None else ''
        
        palaces[gong] = p
    
    # 中5宫
    zhonggong_tianpan = _TIANGAN_DECODE.get(ju.heaven.get(5), '?')
    zhonggong_dipan = _TIANGAN_DECODE.get(ju.ground.get(5), '?')
    
    return {
        'ju_type': 'yang' if ju.is_yangdun else 'yin',
        'ju_num': ju.ju_number,
        'month_zhi': month_zhi_str,
        'day_gan': day_gan_str,
        'day_zhi': day_zhi_str,
        'hour_gan': hour_gan_str,
        'hour_zhi': hour_zhi_str,
        'zhifu_star': _STAR_DECODE.get(ju.zhifu_star, '?'),
        'zhishi_door': _GATE_DECODE.get(ju.zhishi_gate, '?'),
        'kongwang': kongwang_list,
        'palaces': palaces,
        'zhonggong_tianpan_gan': zhonggong_tianpan,
        'zhonggong_dipan_gan': zhonggong_dipan,
    }


# ============================================================
# 10标的 IPO日柱 + 定位配置
# ============================================================

STOCK_CONFIG = {
    '000651.SZ': {  # 格力电器
        'name': '格力电器',
        'ipo_ganzhi': '己未',  # IPO日柱
        'effective_gan': '己',  # 有效干
        'pan_layer': 'tianpan',  # 在哪个盘找：天盘
        # 旬首和遁干由find_xun()动态计算，不再硬编码
    },
    '000063.SZ': {  # 中兴通讯
        'name': '中兴通讯',
        'ipo_ganzhi': '甲子',
        'effective_gan': '戊',  # 甲子遁戊
        'pan_layer': 'tianpan',
    },
    '000858.SZ': {  # 五粮液
        'name': '五粮液',
        'ipo_ganzhi': '甲辰',
        'effective_gan': '壬',  # 甲辰遁壬
        'pan_layer': 'tianpan',
    },
    '600276.SH': {  # 恒瑞医药
        'name': '恒瑞医药',
        'ipo_ganzhi': '己酉',
        'effective_gan': '乙',  # 月干
        'pan_layer': 'dipan',   # 地盘
    },
    '600036.SH': {  # 招商银行
        'name': '招商银行',
        'ipo_ganzhi': '丁未',
        'effective_gan': '丁',
        'pan_layer': 'tianpan',
    },
    '600547.SH': {  # 山东黄金
        'name': '山东黄金',
        'ipo_ganzhi': '癸酉',
        'effective_gan': '癸',
        'pan_layer': 'tianpan',
    },
    '601318.SH': {  # 中国平安
        'name': '中国平安',
        'ipo_ganzhi': '甲午',
        'effective_gan': '辛',  # 甲午遁辛
        'pan_layer': 'tianpan',
    },
    '601857.SH': {  # 中国石油
        'name': '中国石油',
        'ipo_ganzhi': '癸卯',
        'effective_gan': '庚',  # 月干
        'pan_layer': 'tianpan',
    },
    '601899.SH': {  # 紫金矿业
        'name': '紫金矿业',
        'ipo_ganzhi': '乙未',
        'effective_gan': '乙',
        'pan_layer': 'tianpan',
    },
    '601012.SH': {  # 隆基绿能
        'name': '隆基绿能',
        'ipo_ganzhi': '壬寅',
        'effective_gan': '癸',  # 月干
        'pan_layer': 'dipan',
    },
}

# ============================================================
# 五行、生克、旺衰 基础数据
# ============================================================

WUXING = {
    '甲': '木', '乙': '木', '丙': '火', '丁': '火', '戊': '土',
    '己': '土', '庚': '金', '辛': '金', '壬': '水', '癸': '水',
}

GONG_WUXING = {
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

GONG_NAME = {
    1: '坎', 2: '坤', 3: '震', 4: '巽', 5: '中', 6: '乾', 7: '兑', 8: '艮', 9: '离'
}

# 九星五行
STAR_WUXING = {
    '天蓬': '水', '天芮': '土', '天冲': '木', '天辅': '木',
    '天禽': '土', '天心': '金', '天柱': '金', '天任': '土', '天英': '火',
}

# 九星吉凶属性
STAR_JIXI = {
    '天蓬': '凶', '天芮': '凶', '天冲': '吉', '天辅': '吉',
    '天禽': '吉', '天心': '吉', '天柱': '凶', '天任': '吉', '天英': '凶',
}

# 八门五行
DOOR_WUXING = {
    '开门': '金', '休门': '水', '生门': '土', '伤门': '木',
    '杜门': '木', '景门': '火', '死门': '土', '惊门': '金',
}

# 八门吉凶属性
DOOR_JIXI = {
    '开门': '吉', '休门': '吉', '生门': '吉', '伤门': '凶',
    '杜门': '凶', '景门': '凶', '死门': '凶', '惊门': '凶',
}

# 八神（转盘八神）
SHEN_ATTR = {
    '值符': '吉', '腾蛇': '凶', '太阴': '吉', '六合': '吉',
    '白虎': '凶', '玄武': '凶', '九地': '吉', '九天': '吉',
    # 勾陈/朱雀 阴遁用
    '勾陈': '凶', '朱雀': '凶',
}

# 五行生克关系
def shengke(a, b):
    """返回 a 对 b 的关系: 'sheng'(a生b), 'ke'(a克b), 'bei_sheng'(a被b生=泄), 'bei_ke'(a被b克), 'tongwu'(比和)"""
    sheng_chain = ['木', '火', '土', '金', '水']
    if a == b:
        return 'tongwu'
    ia = sheng_chain.index(a)
    ib = sheng_chain.index(b)
    if sheng_chain[(ia + 1) % 5] == b:
        return 'sheng'  # a生b
    if sheng_chain[(ia + 2) % 5] == b:
        return 'ke'  # a克b
    if sheng_chain[(ib + 1) % 5] == a:
        return 'bei_sheng'  # b生a → a泄气于b → 实际是a被b泄
    # 剩下就是 b克a
    return 'bei_ke'


# 月份对应旺相休囚死（简化版：按当令五行）
# 节气月→当令五行
def get_danglin_wuxing(month_zhi):
    """根据月支获取当令五行"""
    month_to_wuxing = {
        '寅': '木', '卯': '木',
        '巳': '火', '午': '火',
        '申': '金', '酉': '金',
        '亥': '水', '子': '水',
        '辰': '土', '未': '土', '戌': '土', '丑': '土',
    }
    return month_to_wuxing.get(month_zhi, '土')


def calc_wangshuai(target_wuxing, danglin_wuxing):
    """
    计算旺衰状态
    返回: '旺'(同五行), '相'(当令生我), '休'(我生当令), '囚'(克我者当令), '死'(我克者当令)
    """
    if target_wuxing == danglin_wuxing:
        return '旺'
    rel = shengke(danglin_wuxing, target_wuxing)
    if rel == 'sheng':
        return '相'  # 当令生我 → 我相
    elif rel == 'bei_sheng':
        return '休'  # 我生当令 → 我休
    elif rel == 'ke':
        return '囚'  # 当令克我 → 我囚
    elif rel == 'bei_ke':
        return '死'  # 我克当令 → 我死
    return '旺'  # 比和


# ============================================================
# 六十甲子序 + 旬首查找
# ============================================================

TIANGAN = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸']
DIZHI = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥']

# 生成六十甲子序列
JIAZI_60 = [TIANGAN[i % 10] + DIZHI[i % 12] for i in range(60)]

# 六甲旬首 → 遁干映射
XUN_TO_DUNGAN = {
    '甲子': '戊', '甲戌': '己', '甲申': '庚',
    '甲午': '辛', '甲辰': '壬', '甲寅': '癸',
}

# 查找干支所在旬首
def find_xun(ganzhi):
    """找到干支所在的旬首"""
    idx = JIAZI_60.index(ganzhi)
    xun_start = (idx // 10) * 10
    return JIAZI_60[xun_start]


def find_xun_dungan(ganzhi):
    """找到干支所在旬的遁干"""
    xun = find_xun(ganzhi)
    return XUN_TO_DUNGAN[xun]


# ============================================================
# 模块A：直接定位 — 找有效干在天盘/地盘的落宫
# ============================================================

def find_stock_palace_direct(pan, stock_code):
    """
    直接定位：在排盘结果中找有效干所在的宫位
    
    pan: paipan()的输出字典，结构：
        pan['palaces'][gong_num] = {
            'tianpan_gan': '...',  # 天盘天干
            'dipan_gan': '...',    # 地盘天干
            'star': '...',         # 九星
            'door': '...',         # 八门
            'shen': '...',         # 八神
            'angang': '...',       # 暗干（如果有）
        }
        pan['ju_type']: 'yang' / 'yin'  # 阳遁/阴遁
        pan['ju_num']: int              # 局数
        pan['month_zhi']: str           # 月支
        pan['hour_gan']: str            # 时干
        pan['hour_zhi']: str            # 时支
        pan['day_gan']: str             # 日干
        pan['day_zhi']: str             # 日支
        pan['zhifu_star']: str          # 值符星
        pan['zhishi_door']: str         # 值使门
    
    返回: {'gong': int, 'method': 'direct', 'detail': str} 或 None
    """
    config = STOCK_CONFIG.get(stock_code)
    if not config:
        return None
    
    eff_gan = config['effective_gan']
    layer = config['pan_layer']  # 'tianpan' or 'dipan'
    
    # 第一轮：按配置的盘层查找
    for gong_num in [1, 2, 3, 4, 6, 7, 8, 9]:  # 跳过中5宫
        palace = pan['palaces'][gong_num]
        if layer == 'tianpan' and palace.get('tianpan_gan') == eff_gan:
            return {
                'gong': gong_num,
                'method': 'direct',
                'layer': layer,
                'detail': f"有效干[{eff_gan}]在天盘落{GONG_NAME[gong_num]}{gong_num}宫"
            }
        elif layer == 'dipan' and palace.get('dipan_gan') == eff_gan:
            return {
                'gong': gong_num,
                'method': 'direct',
                'layer': layer,
                'detail': f"有效干[{eff_gan}]在地盘落{GONG_NAME[gong_num]}{gong_num}宫"
            }
    
    # 第二轮fallback：如果配置盘层找不到，尝试另一个盘层
    fallback_layer = 'dipan' if layer == 'tianpan' else 'tianpan'
    fallback_key = 'dipan_gan' if fallback_layer == 'dipan' else 'tianpan_gan'
    for gong_num in [1, 2, 3, 4, 6, 7, 8, 9]:
        palace = pan['palaces'][gong_num]
        if palace.get(fallback_key) == eff_gan:
            return {
                'gong': gong_num,
                'method': 'direct_fallback',
                'layer': fallback_layer,
                'detail': f"有效干[{eff_gan}]在{fallback_layer}(fallback)落{GONG_NAME[gong_num]}{gong_num}宫"
            }
    
    # 如果在8宫都没找到，检查中5宫寄宫
    # 中5宫天禽寄宫：阳遁寄坤2，阴遁寄艮8
    if pan.get('zhonggong_tianpan_gan') == eff_gan or pan.get('zhonggong_dipan_gan') == eff_gan:
        ji_gong = 2 if pan.get('ju_type') == 'yang' else 8
        return {
            'gong': ji_gong,
            'method': 'direct_zhonggong',
            'layer': layer,
            'detail': f"有效干[{eff_gan}]在中5宫，寄{GONG_NAME[ji_gong]}{ji_gong}宫"
        }
    
    return None


# ============================================================
# 模块B：遁法定位 — 用IPO日柱游宫飞布
# ============================================================

def dunfa_locate(pan, stock_code):
    """
    遁法定位：以IPO日柱为目标干支，通过"找旬首→定起点→游宫飞布→定位宫位"
    
    《执棋者》遁法四步：
    步骤1：定目标干支 = IPO日柱（如格力=己未）
    步骤2：找旬首起点 = IPO日柱所在旬的遁干在地盘的宫位
    步骤3：游宫飞布 = 阳遁顺飞(1→2→3...9→1), 阴遁逆飞(9→8→7...1→9)
    步骤4：定位到IPO日柱落的宫位
    
    宫位数字对应：坎1、坤2、震3、巽4、中5、乾6、兑7、艮8、离9
    """
    config = STOCK_CONFIG.get(stock_code)
    if not config:
        return None
    
    ipo_ganzhi = config['ipo_ganzhi']
    
    # 步骤1：目标干支
    target_idx = JIAZI_60.index(ipo_ganzhi)
    
    # 步骤2：找旬首和遁干
    xun = find_xun(ipo_ganzhi)
    dungan = XUN_TO_DUNGAN[xun]
    xun_idx = JIAZI_60.index(xun)
    
    # 在盘局中找地盘上遁干所在宫位
    start_gong = None
    for gong_num in [1, 2, 3, 4, 5, 6, 7, 8, 9]:
        if gong_num == 5:
            # 中5宫的地盘干需要特殊处理
            if pan.get('zhonggong_dipan_gan') == dungan:
                start_gong = 5
                break
        else:
            if pan['palaces'][gong_num].get('dipan_gan') == dungan:
                start_gong = gong_num
                break
    
    if start_gong is None:
        return None
    
    # 步骤3：游宫飞布
    # 从旬首到目标干支的距离（在六十甲子中的偏移量）
    offset = target_idx - xun_idx  # 0-9 之间
    
    is_yang = pan.get('ju_type') == 'yang'
    
    # 宫位数按1-9循环（包含5）
    # 阳遁：顺飞 1→2→3→4→5→6→7→8→9→1...
    # 阴遁：逆飞 9→8→7→6→5→4→3→2→1→9...
    current_gong = start_gong
    for step in range(offset):
        if is_yang:
            current_gong += 1
            if current_gong > 9:
                current_gong = 1
        else:
            current_gong -= 1
            if current_gong < 1:
                current_gong = 9
    
    # 如果落在中5宫，需要寄宫
    final_gong = current_gong
    if final_gong == 5:
        final_gong = 2 if is_yang else 8  # 阳寄坤，阴寄艮
    
    direction = '顺' if is_yang else '逆'
    return {
        'gong': final_gong,
        'raw_gong': current_gong,  # 游宫原始结果（可能是5）
        'method': 'dunfa',
        'ipo_ganzhi': ipo_ganzhi,
        'xun': xun,
        'dungan': dungan,
        'start_gong': start_gong,
        'offset': offset,
        'direction': direction,
        'detail': f"遁法：{ipo_ganzhi}在{xun}旬，地盘{dungan}起{GONG_NAME.get(start_gong, '中')}{start_gong}宫，"
                  f"{'阳' if is_yang else '阴'}遁{direction}飞{offset}步，落{GONG_NAME.get(final_gong, '中')}{final_gong}宫"
    }


# ============================================================
# 宫位评估：基于《执棋者》详细分析格式
# ============================================================

def evaluate_palace(pan, gong_num, stock_code, month_zhi, ju=None, all_geju=None):
    """
    对指定宫位进行《执棋者》格式的详细评估
    
    《执棋者》核心原则：
    1. 特殊格局具有颠覆性力量，解释力超过一般星门旺衰（"大象与特例的辩证"）
    2. 能量视角：分析谁在什么环境中受何种力量以何种方式影响
    3. 九星双层旺衰：时令旺衰（显性）vs 落宫旺衰（隐性）
    4. 分析主体不参与十干克应（"用神仅作为被形容的对象"）
    
    评估架构：
    Layer 0: 特殊格局检查（颠覆性，直接决定吉凶基调）
    Layer 1: 落宫环境对有效干的影响（宫生克干 = 环境对"我"的态度）
    Layer 2: 九星内核（性质 + 双层旺衰）
    Layer 3: 八门行为（表现 + 门迫检查）  
    Layer 4: 八神特质
    Layer 5: 空亡检查
    
    参数:
        pan: 转换后的字典
        gong_num: 宫号
        stock_code: 标的代码
        month_zhi: 月支
        ju: QimenJu对象（可选，用于调用引擎格局函数）
        all_geju: evaluate_all_geju()的结果（可选，避免重复计算）
    
    返回: dict with 'score', 'details', etc.
    """
    config = STOCK_CONFIG.get(stock_code)
    eff_gan = config['effective_gan']
    eff_wuxing = WUXING[eff_gan]
    danglin = get_danglin_wuxing(month_zhi)
    
    palace = pan['palaces'][gong_num]
    gong_wx = GONG_WUXING[gong_num]
    
    score = 0.0
    details = []
    has_special = False  # 是否有颠覆性特殊格局
    
    # ══════════════════════════════════════════════════════
    # Layer 0: 特殊格局检查（颠覆性力量）
    # 《执棋者》："特殊格局具有颠覆性力量...其解释力往往超过
    #  一般的星门旺衰和普通十干克应"
    # ══════════════════════════════════════════════════════
    
    # 从引擎格局结果中筛选该宫的格局
    palace_geju = []
    if all_geju:
        palace_geju = [g for g in all_geju if g.palace == gong_num]
    
    # 分类：重/极格局 vs 轻/中格局
    major_ji = [g for g in palace_geju if g.jixiong == 1 and g.severity >= 2]
    major_xiong = [g for g in palace_geju if g.jixiong == 0 and g.severity >= 2]
    minor_ji = [g for g in palace_geju if g.jixiong == 1 and g.severity < 2]
    minor_xiong = [g for g in palace_geju if g.jixiong == 0 and g.severity < 2]
    
    if major_ji or major_xiong:
        has_special = True
        # 颠覆性格局：severity 2=重(±3分), 3=极(±4分)
        for g in major_ji:
            pts = g.severity + 1  # severity2→3, severity3→4
            score += pts
            details.append(f"L0:【{g.name}】吉{['轻','中','重','极'][g.severity]}(+{pts}) {g.description}")
        for g in major_xiong:
            pts = g.severity + 1
            score -= pts
            details.append(f"L0:【{g.name}】凶{['轻','中','重','极'][g.severity]}(-{pts}) {g.description}")
    
    # 轻/中格局：正常权重
    for g in minor_ji:
        pts = g.severity + 1  # severity0→1, severity1→2
        score += pts
        details.append(f"L0:{g.name} 吉{['轻','中'][g.severity]}(+{pts})")
    for g in minor_xiong:
        pts = g.severity + 1
        score -= pts
        details.append(f"L0:{g.name} 凶{['轻','中'][g.severity]}(-{pts})")
    
    # jixiong=-1 的中性格局：不计分，但记录
    neutral_geju = [g for g in palace_geju if g.jixiong == -1]
    for g in neutral_geju:
        details.append(f"L0:{g.name} 中性(0)")
    
    # ══════════════════════════════════════════════════════
    # Layer 1: 落宫环境对有效干的影响
    # 《执棋者》详细分析格式："落宫：分析落宫判断其所处的环境/处境/氛围"
    # 能量视角：宫生干=环境滋养我，宫克干=环境压制我
    # ══════════════════════════════════════════════════════
    
    rel = shengke(gong_wx, eff_wuxing)
    if rel == 'sheng':
        score += 2
        details.append(f"L1:宫生干(+2) {GONG_NAME[gong_num]}{gong_wx}生{eff_gan}{eff_wuxing}=环境滋养")
    elif rel == 'tongwu':
        score += 1
        details.append(f"L1:宫干比和(+1) 环境同气")
    elif rel == 'bei_sheng':
        score -= 1  # 干生宫=我泄气于环境
        details.append(f"L1:干泄宫(-1) {eff_gan}生{gong_wx}=被环境消耗")
    elif rel == 'ke':
        score -= 2
        details.append(f"L1:宫克干(-2) {gong_wx}克{eff_wuxing}=环境压制")
    elif rel == 'bei_ke':
        score += 0  # 干克宫=我对抗环境，耗气但主动
        details.append(f"L1:干克宫(0) {eff_wuxing}克{gong_wx}=对抗消耗")
    
    # ══════════════════════════════════════════════════════
    # Layer 2: 九星（内核/性质）+ 双层旺衰
    # 《执棋者》："九星判断其性格/内心/事物的核心/内核的性质"
    # "从九星的时令旺衰（当下/显性状态）与落宫旺衰力量（长久角度/隐性状态）
    #  两个层面分别分析"
    # ══════════════════════════════════════════════════════
    
    star = palace.get('star', '')
    if star and star != '?':
        star_wx = STAR_WUXING.get(star, '')
        star_ji = STAR_JIXI.get(star, '')
        
        # 时令旺衰（显性/当下）
        ws_shiling = calc_wangshuai(star_wx, danglin) if star_wx else '休'
        # 落宫旺衰（隐性/长久）
        ws_luogong = calc_wangshuai(star_wx, gong_wx) if star_wx else '休'
        
        positive_ws = {'旺', '相'}
        sl_pos = ws_shiling in positive_ws
        lg_pos = ws_luogong in positive_ws
        
        if star_ji == '吉':
            if sl_pos and lg_pos:
                score += 3  # 吉星双旺=内核强健且持久
                details.append(f"L2:{star}吉星双旺(+3) 时令{ws_shiling}+宫{ws_luogong}")
            elif sl_pos:
                score += 2  # 吉星时令旺=当下有力但长期受限
                details.append(f"L2:{star}吉星时旺宫弱(+2) 时令{ws_shiling}+宫{ws_luogong}")
            elif lg_pos:
                score += 1  # 吉星落宫旺=基础好但当下受压
                details.append(f"L2:{star}吉星时弱宫旺(+1) 时令{ws_shiling}+宫{ws_luogong}")
            else:
                score += 0  # 吉星双弱=有吉名无实力
                details.append(f"L2:{star}吉星双弱(0) 时令{ws_shiling}+宫{ws_luogong}")
        else:
            # 凶星：《宝鉴》"大凶无气交为小"
            if sl_pos and lg_pos:
                score -= 3  # 凶星双旺=凶力极强
                details.append(f"L2:{star}凶星双旺(-3) 时令{ws_shiling}+宫{ws_luogong}")
            elif sl_pos:
                score -= 2
                details.append(f"L2:{star}凶星时旺(-2) 时令{ws_shiling}+宫{ws_luogong}")
            elif lg_pos:
                score -= 1
                details.append(f"L2:{star}凶星宫旺(-1) 时令{ws_shiling}+宫{ws_luogong}")
            else:
                score -= 0  # 凶星双弱=凶力消散
                details.append(f"L2:{star}凶星双弱(0) 时令{ws_shiling}+宫{ws_luogong}")
    
    # ══════════════════════════════════════════════════════
    # Layer 3: 八门（行为/表现）+ 门迫
    # 《执棋者》："八门判断其表现形式/行为/事物的显性特征"
    # 门迫 = 宫五行克门五行 = 行为受环境压制
    # ══════════════════════════════════════════════════════
    
    door = palace.get('door', '')
    if door and door != '?':
        door_wx = DOOR_WUXING.get(door, '')
        door_ji = DOOR_JIXI.get(door, '')
        
        # 门的时令旺衰
        ws_door = calc_wangshuai(door_wx, danglin) if door_wx else '休'
        door_pos = ws_door in {'旺', '相'}
        
        # 门迫检查（宫克门）
        is_menpo = False
        if door_wx:
            door_gong_rel = shengke(gong_wx, door_wx)
            is_menpo = (door_gong_rel == 'ke')
        
        if door_ji == '吉':
            if is_menpo:
                # 《宝鉴》"吉门被迫吉不就"
                score -= 1
                details.append(f"L3:{door}吉门被迫(-1) {gong_wx}克{door_wx}=吉不就")
            elif door_pos:
                score += 2
                details.append(f"L3:{door}吉门旺(+2) {ws_door}")
            else:
                score += 1
                details.append(f"L3:{door}吉门{ws_door}(+1)")
        else:
            if is_menpo:
                # 《宝鉴》"凶门被迫凶不起"
                score += 1
                details.append(f"L3:{door}凶门被迫(+1) {gong_wx}克{door_wx}=凶不起")
            elif door_pos:
                score -= 2
                details.append(f"L3:{door}凶门旺(-2) {ws_door}")
            else:
                score -= 1  # 凶门弱=凶力减轻但仍存
                details.append(f"L3:{door}凶门{ws_door}(-1)")
    
    # ══════════════════════════════════════════════════════
    # Layer 4: 八神特质
    # 《执棋者》："八神判断其特征/状态/神态/特质/属性"
    # ══════════════════════════════════════════════════════
    
    shen = palace.get('shen', '')
    if shen and shen != '?':
        shen_ji = SHEN_ATTR.get(shen, '')
        if shen_ji == '吉':
            score += 1
            details.append(f"L4:{shen}吉神(+1)")
        elif shen_ji == '凶':
            score -= 1
            details.append(f"L4:{shen}凶神(-1)")
    
    # ══════════════════════════════════════════════════════
    # Layer 5: 空亡检查
    # 《执棋者》："空亡核心表示不稳定、信心的缺失、结果的延迟"
    # "绝不可简单断为没有"
    # 空亡但得月令生助 → 假空，力量不灭
    # ══════════════════════════════════════════════════════
    
    kongwang = pan.get('kongwang', [])
    # 宫位对应地支（简化版）
    _gong_dizhi = {
        1: ['子'], 2: ['丑', '未'], 3: ['卯'], 4: ['辰', '巳'],
        6: ['戌', '亥'], 7: ['酉'], 8: ['丑', '寅'], 9: ['午']
    }
    is_kongwang = False
    if kongwang:
        gong_zhi_list = _gong_dizhi.get(gong_num, [])
        for kw in kongwang:
            if kw in gong_zhi_list:
                is_kongwang = True
                # 检查假空：得月令生助
                kw_wx_map = {'子':'水','丑':'土','寅':'木','卯':'木','辰':'土',
                             '巳':'火','午':'火','未':'土','申':'金','酉':'金','戌':'土','亥':'水'}
                kw_wx = kw_wx_map.get(kw, '')
                if kw_wx:
                    kw_ws = calc_wangshuai(kw_wx, danglin)
                    if kw_ws in ('旺', '相'):
                        details.append(f"L5:空亡但{kw_ws}=假空(0) {kw}空得月令助")
                        # 假空不扣分
                    else:
                        score -= 2  # 真空亡=不稳定
                        details.append(f"L5:空亡(-2) {kw}空且{kw_ws}")
                break
    if not is_kongwang:
        details.append(f"L5:不空亡")
    
    # ══════════════════════════════════════════════════════
    # 综合：如果有颠覆性特殊格局，其他层的贡献被压缩
    # ══════════════════════════════════════════════════════
    # 不额外处理——特殊格局的分值本身就大(±3/±4)，自然主导总分
    
    return {
        'score': score,
        'details': details,
        'gong': gong_num,
        'gong_name': GONG_NAME[gong_num],
        'star': palace.get('star', ''),
        'door': palace.get('door', ''),
        'shen': palace.get('shen', ''),
        'tianpan_gan': palace.get('tianpan_gan', ''),
        'dipan_gan': palace.get('dipan_gan', ''),
        'has_special_geju': has_special,
        'geju_count': len(palace_geju),
    }


# ============================================================
# 伏吟/反吟 全局检查
# ============================================================

def check_fuyin_fanyin(pan):
    """
    检查全局是否伏吟或反吟
    
    伏吟：九星回到本宫（天蓬在坎1，天芮在坤2...）
    反吟：九星到对宫（天蓬在离9，天芮在艮8...）
    
    返回: 'fuyin', 'fanyin', None
    """
    star_bengong = {
        '天蓬': 1, '天芮': 2, '天冲': 3, '天辅': 4,
        '天禽': 5, '天心': 6, '天柱': 7, '天任': 8, '天英': 9,
    }
    
    duigong = {1: 9, 2: 8, 3: 7, 4: 6, 6: 4, 7: 3, 8: 2, 9: 1}
    
    fuyin_count = 0
    fanyin_count = 0
    
    for gong_num in [1, 2, 3, 4, 6, 7, 8, 9]:
        star = pan['palaces'][gong_num].get('star', '')
        if star in star_bengong:
            if star_bengong[star] == gong_num:
                fuyin_count += 1
            elif duigong.get(star_bengong[star]) == gong_num:
                fanyin_count += 1
    
    # 伏吟/反吟需要多数星满足条件（>= 6）
    if fuyin_count >= 6:
        return 'fuyin'
    if fanyin_count >= 6:
        return 'fanyin'
    return None


# ============================================================
# 主函数：天时层v6评估
# ============================================================

def assess_stock_tianshi_v6(pan_or_ju, stock_code):
    """
    天时层v6评估主函数
    
    双维度定位 + 多维度评估 → 综合标签
    
    参数:
        pan_or_ju: paipan()输出的QimenJu对象，或已转换的字典
        stock_code: 标的代码（如'000651.SZ'）
    
    返回:
        {
            'label': str,           # FAVORABLE/PARTIAL_GOOD/NEUTRAL/PARTIAL_BAD/UNFAVORABLE/STAGNANT/VOLATILE
            'direct_palace': dict,   # 直接定位结果
            'dunfa_palace': dict,    # 遁法定位结果
            'direct_eval': dict,     # 直接定位宫的评估
            'dunfa_eval': dict,      # 遁法定位宫的评估
            'combined_score': float, # 综合得分
            'fuyin_fanyin': str,     # 伏吟/反吟状态
            'reasoning': str,        # 推理过程
        }
    """
    # 自动检测输入类型：QimenJu对象 → 转换为字典
    # 同时保留原始ju对象用于调用引擎格局函数
    ju = None  # 原始QimenJu对象
    if not isinstance(pan_or_ju, dict):
        ju = pan_or_ju
        pan = _convert_qimenju_to_dict(pan_or_ju)
    else:
        pan = pan_or_ju
    
    config = STOCK_CONFIG.get(stock_code)
    if not config:
        return {'label': 'NEUTRAL', 'reasoning': f'未知标的: {stock_code}'}
    
    month_zhi = pan.get('month_zhi', '子')
    
    # ── 调用引擎格局函数（一次性计算所有格局，多标的共享）──
    all_geju = None
    if ju is not None:
        try:
            from fcas_engine_v2 import evaluate_all_geju
            all_geju = evaluate_all_geju(ju)
        except Exception:
            all_geju = None
    
    # ── 直接定位 ──
    direct_result = find_stock_palace_direct(pan, stock_code)
    
    # ── 遁法定位 ──
    dunfa_result = dunfa_locate(pan, stock_code)
    
    # ── 评估各落宫（传入ju和all_geju）──
    direct_eval = None
    dunfa_eval = None
    
    if direct_result:
        direct_eval = evaluate_palace(pan, direct_result['gong'], stock_code, month_zhi, ju=ju, all_geju=all_geju)
    
    if dunfa_result:
        dunfa_eval = evaluate_palace(pan, dunfa_result['gong'], stock_code, month_zhi, ju=ju, all_geju=all_geju)
    
    # ── 伏吟/反吟检查 ──
    fy = check_fuyin_fanyin(pan)
    
    # ── 综合评分 ──
    # 权重：直接定位 = 当下状态（权重0.6），遁法 = 时空结构（权重0.4）
    # 依据：直接定位反映有效干在当前局中的即时位置，遁法反映标的的"命盘"在此局的结构映射
    
    direct_score = direct_eval['score'] if direct_eval else 0
    dunfa_score = dunfa_eval['score'] if dunfa_eval else 0
    
    # 如果两个方法定位到同一宫，权重合并（信号强化）
    same_palace = (direct_result and dunfa_result and 
                   direct_result['gong'] == dunfa_result['gong'])
    
    if same_palace:
        # 同宫强化：取该宫评分 * 1.2（避免重复计分，但信号加强）
        combined_score = direct_score * 1.2
    elif direct_eval and dunfa_eval:
        combined_score = direct_score * 0.6 + dunfa_score * 0.4
    elif direct_eval:
        combined_score = direct_score * 0.8  # 只有直接定位，降低信心
    elif dunfa_eval:
        combined_score = dunfa_score * 0.6  # 只有遁法，信心更低
    else:
        combined_score = 0
    
    # ── 伏吟/反吟修正 ──
    if fy == 'fuyin':
        label = 'STAGNANT'
        reasoning_suffix = "全局伏吟→停滞"
    elif fy == 'fanyin':
        label = 'VOLATILE'
        reasoning_suffix = "全局反吟→动荡"
    else:
        reasoning_suffix = ""
    
    # ── 分数 → 标签映射 ──
    # 新评分范围约 -15 ~ +15（特殊格局±4，环境±2，星±3，门±2，神±1，空亡±2）
    if fy not in ('fuyin', 'fanyin'):
        if combined_score >= 5:
            label = 'FAVORABLE'
        elif combined_score >= 2:
            label = 'PARTIAL_GOOD'
        elif combined_score >= -2:
            label = 'NEUTRAL'
        elif combined_score >= -5:
            label = 'PARTIAL_BAD'
        else:
            label = 'UNFAVORABLE'
    
    # ── 构建推理过程 ──
    reasoning_parts = []
    reasoning_parts.append(f"标的: {config['name']}({stock_code})")
    reasoning_parts.append(f"有效干: {config['effective_gan']}, 盘层: {config['pan_layer']}")
    
    if direct_result:
        reasoning_parts.append(f"直接定位: {direct_result['detail']}")
        if direct_eval:
            reasoning_parts.append(f"  直接宫评分: {direct_score} ({'; '.join(direct_eval['details'])})")
    else:
        reasoning_parts.append("直接定位: 未找到有效干落宫")
    
    if dunfa_result:
        reasoning_parts.append(f"遁法定位: {dunfa_result['detail']}")
        if dunfa_eval:
            reasoning_parts.append(f"  遁法宫评分: {dunfa_score} ({'; '.join(dunfa_eval['details'])})")
    else:
        reasoning_parts.append("遁法定位: 定位失败")
    
    if same_palace:
        reasoning_parts.append(f"⚡ 双法同宫强化: {GONG_NAME[direct_result['gong']]}宫")
    
    if reasoning_suffix:
        reasoning_parts.append(reasoning_suffix)
    
    reasoning_parts.append(f"综合得分: {combined_score:.2f} → {label}")
    
    return {
        'label': label,
        'stock_code': stock_code,
        'stock_name': config['name'],
        'direct_palace': direct_result,
        'dunfa_palace': dunfa_result,
        'direct_eval': direct_eval,
        'dunfa_eval': dunfa_eval,
        'combined_score': round(combined_score, 2),
        'same_palace': same_palace,
        'fuyin_fanyin': fy,
        'reasoning': '\n'.join(reasoning_parts),
    }


# ============================================================
# 批量评估：一次排盘评估所有标的
# ============================================================

def assess_all_stocks_tianshi_v6(pan):
    """
    对所有10个标的进行天时层v6评估
    
    返回: {stock_code: assessment_result, ...}
    """
    results = {}
    for stock_code in STOCK_CONFIG:
        results[stock_code] = assess_stock_tianshi_v6(pan, stock_code)
    return results


# ============================================================
# 测试/验证用：打印评估结果
# ============================================================

def print_assessment(result):
    """打印单个标的的评估结果"""
    print(f"\n{'='*60}")
    print(f"  {result.get('stock_name', '?')} ({result.get('stock_code', '?')})")
    print(f"  天时标签: {result['label']}")
    print(f"  综合得分: {result['combined_score']}")
    if result.get('same_palace'):
        print(f"  ⚡ 双法同宫!")
    if result.get('fuyin_fanyin'):
        print(f"  ⚠️ {result['fuyin_fanyin']}")
    print(f"{'='*60}")
    print(result.get('reasoning', ''))
    print()


# ============================================================
# CLI 入口（测试用）
# ============================================================

if __name__ == '__main__':
    print("天时层v6评估模块已加载")
    print(f"已配置 {len(STOCK_CONFIG)} 个标的:")
    for code, cfg in STOCK_CONFIG.items():
        print(f"  {code} {cfg['name']}: 有效干={cfg['effective_gan']}, 日柱={cfg['ipo_ganzhi']}, 盘={cfg['pan_layer']}")
    print()
    print("使用方式:")
    print("  from assess_tianshi_v6 import assess_stock_tianshi_v6")
    print("  result = assess_stock_tianshi_v6(pan, '000651.SZ')")
    print("  print_assessment(result)")
