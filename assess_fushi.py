"""
FCAS 符使系统评估模块 v2 (Fu-Shi System Assessment)
====================================================
全局天时修正因子 — 基于值符宫与值使门宫的五行关系

回测验证结论（574周×8标的=4592条，2026-04-07确认）：
- S2(值符星吉凶旺衰) + S3(值使门吉凶旺衰) 三层打分无效
  → 凶门5/8=62.5%导致系统性偏负，HOSTILE组反而跑赢SUPPORTIVE
- S1(符使宫五行关系) 独立有效：
  → 使克符: 独立正alpha（FAV下+2.84%, NON_FAV下+0.58%）
  → 符克使: 独立负alpha（FAV下-1.02%, NON_FAV下-0.00%）
  → 符生使/使生符: 弱正效应
  → 符使比和: 弱负效应（样本少）
- FAV天时对所有关系有放大效应（beta放大器）

原文依据：
- 刘文元《奇门启悟》：最喜值符宫生扶值使宫或比和
- 回测修正："克则动"——使克符(趋势冲击现状)短期爆发力最强，
  符克使(现状压制趋势)短期最弱。克制≠凶，要看方向。

操作规则（回测验证）：
  1. 任何天时 + 使克符 → 增强买入信号
  2. FAVORABLE + 符克使 → 显著回避（陷阱信号）
  3. FAVORABLE + 生/和  → 正常持有

引擎编码：
  PALACE: 1=坎 2=坤 3=震 4=巽 5=中 6=乾 7=兑 8=艮 9=离
"""

# ============================================================
# 宫位五行
# ============================================================

PALACE_NAMES = {
    1: '坎', 2: '坤', 3: '震', 4: '巽',
    5: '中', 6: '乾', 7: '兑', 8: '艮', 9: '离',
}

PALACE_WUXING = {
    1: '水', 2: '土', 3: '木', 4: '木',
    5: '土', 6: '金', 7: '金', 8: '土', 9: '火',
}

# ============================================================
# 五行生克
# ============================================================

SHENG_CYCLE = {'木': '火', '火': '土', '土': '金', '金': '水', '水': '木'}
KE_CYCLE = {'木': '土', '土': '水', '水': '火', '火': '金', '金': '木'}


def wuxing_relation(wx_a, wx_b):
    """A对B的五行关系"""
    if wx_a == wx_b:
        return 'bi'
    if SHENG_CYCLE.get(wx_a) == wx_b:
        return 'sheng'
    if KE_CYCLE.get(wx_a) == wx_b:
        return 'ke'
    if SHENG_CYCLE.get(wx_b) == wx_a:
        return 'bei_sheng'
    if KE_CYCLE.get(wx_b) == wx_a:
        return 'bei_ke'
    return 'unknown'


# ============================================================
# 符使关系类型 → 信号修正
# ============================================================

# 回测验证的信号效应（1W平均超额收益）
# 使克符: +0.58% (NON_FAV), +2.84% (FAV) — 独立正alpha
# 符克使: -0.00% (NON_FAV), -1.02% (FAV) — 独立负alpha
# 符生使: +0.34% (NON_FAV), +1.60% (FAV) — 弱正
# 使生符: +0.16% (NON_FAV), +1.60% (FAV) — 弱正
# 符使比和: -0.22% (NON_FAV), -1.02% (FAV) — 弱负（样本极少）

FUSHI_SIGNAL = {
    '使克符': 'BOOST',     # 趋势冲击现状，能量剧烈流动，短期爆发
    '符生使': 'MILD_PLUS', # 现状滋养趋势，温和正向
    '使生符': 'MILD_PLUS', # 趋势反哺现状，温和正向
    '符使比和': 'NEUTRAL',  # 同步，无明显方向（样本少，保守处理）
    '符克使': 'DAMPEN',    # 现状压制趋势，好天时下是陷阱
}

# 信号修正规则（与天时标签交互）
# 返回的modifier可用于调整天时标签的置信度
INTERACTION_RULES = {
    # (tianshi_label, fushi_signal) → modifier
    ('FAVORABLE', 'BOOST'):     'STRONG_FAVORABLE',  # FAV+使克符=强买
    ('FAVORABLE', 'MILD_PLUS'): 'FAVORABLE',          # 维持
    ('FAVORABLE', 'NEUTRAL'):   'FAVORABLE',          # 维持
    ('FAVORABLE', 'DAMPEN'):    'FAVORABLE_TRAPPED',  # FAV+符克使=陷阱
    
    ('PARTIAL_GOOD', 'BOOST'):  'PARTIAL_GOOD_PLUS',
    ('PARTIAL_GOOD', 'DAMPEN'): 'NEUTRAL',            # 降级
    
    ('NEUTRAL', 'BOOST'):       'PARTIAL_GOOD',       # 升级
    ('NEUTRAL', 'DAMPEN'):      'NEUTRAL',            # 维持
    
    ('PARTIAL_BAD', 'BOOST'):   'NEUTRAL',            # 升级
    ('PARTIAL_BAD', 'DAMPEN'):  'PARTIAL_BAD',        # 维持
    
    ('UNFAVORABLE', 'BOOST'):   'PARTIAL_BAD',        # 克则动，减轻
    ('UNFAVORABLE', 'DAMPEN'):  'UNFAVORABLE',        # 维持
}


def _pn(num):
    return PALACE_NAMES.get(num, f'?{num}')


# ============================================================
# 主评估函数
# ============================================================

def assess_fushi(ju):
    """
    符使系统评估 v2 — 只输出S1关系类型和信号

    输入: QimenJu 实例
    输出: dict {
        'relation_type': str,     # 使克符/符克使/符生使/使生符/符使比和
        'fushi_signal': str,      # BOOST/MILD_PLUS/NEUTRAL/DAMPEN
        'zhifu_palace': int,
        'zhishi_palace': int,
        'detail': str,            # 可读描述
    }
    """
    zf_p = ju.zhifu_palace
    zs_p = ju.zhishi_palace
    zf_wx = PALACE_WUXING.get(zf_p)
    zs_wx = PALACE_WUXING.get(zs_p)

    if not zf_wx or not zs_wx:
        return {
            'relation_type': 'unknown',
            'fushi_signal': 'NEUTRAL',
            'zhifu_palace': zf_p,
            'zhishi_palace': zs_p,
            'detail': '无法判断符使宫位五行',
        }

    rel = wuxing_relation(zf_wx, zs_wx)

    # 映射到中文关系名
    REL_NAMES = {
        'sheng': '符生使',
        'ke': '符克使',
        'bi': '符使比和',
        'bei_sheng': '使生符',
        'bei_ke': '使克符',
    }
    
    REL_DETAILS = {
        'sheng':     f'值符宫({_pn(zf_p)}/{zf_wx})生值使宫({_pn(zs_p)}/{zs_wx})，现状滋养趋势',
        'ke':        f'值符宫({_pn(zf_p)}/{zf_wx})克值使宫({_pn(zs_p)}/{zs_wx})，现状压制趋势',
        'bi':        f'值符宫({_pn(zf_p)}/{zf_wx})与值使宫({_pn(zs_p)}/{zs_wx})比和',
        'bei_sheng': f'值使宫({_pn(zs_p)}/{zs_wx})生值符宫({_pn(zf_p)}/{zf_wx})，趋势反哺现状',
        'bei_ke':    f'值使宫({_pn(zs_p)}/{zs_wx})克值符宫({_pn(zf_p)}/{zf_wx})，趋势冲击现状，克则动',
    }

    relation_type = REL_NAMES.get(rel, 'unknown')
    signal = FUSHI_SIGNAL.get(relation_type, 'NEUTRAL')
    detail = REL_DETAILS.get(rel, '未知关系')

    return {
        'relation_type': relation_type,
        'fushi_signal': signal,
        'zhifu_palace': zf_p,
        'zhishi_palace': zs_p,
        'detail': f'{detail} → {signal}',
    }


def apply_fushi_modifier(tianshi_label, fushi_signal):
    """
    将符使信号应用到天时标签上，返回修正后的标签

    输入:
        tianshi_label: str  — 天时v6的标签 (FAVORABLE, PARTIAL_GOOD, etc.)
        fushi_signal: str   — 符使信号 (BOOST, MILD_PLUS, NEUTRAL, DAMPEN)
    输出:
        str — 修正后的标签

    用法:
        fushi = assess_fushi(ju)
        modified_label = apply_fushi_modifier(tianshi_label, fushi['fushi_signal'])
    """
    key = (tianshi_label, fushi_signal)
    modified = INTERACTION_RULES.get(key)
    
    if modified:
        return modified
    
    # 未定义的组合（STAGNANT/VOLATILE等特殊标签不受符使影响）
    return tianshi_label


# ============================================================
# 批量（回测/扫描用）
# ============================================================

def assess_fushi_batch(ju_list):
    """输入: [(date_str, QimenJu), ...] → [(date_str, result), ...]"""
    return [(d, assess_fushi(ju)) for d, ju in ju_list]


# ============================================================
# 测试
# ============================================================

if __name__ == '__main__':
    print("FCAS 符使系统评估模块 v2")
    print("=" * 50)
    print()
    print("变更：去掉无效的S2/S3三层打分，只保留S1关系类型")
    print()
    print("测试:")
    print("  from datetime import datetime")
    print("  from fcas_engine_v2 import paipan")
    print("  from assess_fushi import assess_fushi, apply_fushi_modifier")
    print()
    print("  ju = paipan(datetime(2025, 4, 7, 10, 0))")
    print("  r = assess_fushi(ju)")
    print("  print(r['relation_type'], r['fushi_signal'])")
    print("  print(r['detail'])")
    print()
    print("  # 与天时标签交互")
    print("  modified = apply_fushi_modifier('FAVORABLE', r['fushi_signal'])")
    print("  print(f'FAVORABLE + {r[\"fushi_signal\"]} → {modified}')")
    print()
    print("信号含义:")
    print("  BOOST     = 使克符，趋势冲击现状，短期爆发（+2.84% FAV, +0.58% NON_FAV）")
    print("  MILD_PLUS = 符生使/使生符，温和正向（+1.60% FAV）")
    print("  NEUTRAL   = 符使比和，无方向")
    print("  DAMPEN    = 符克使，现状压制趋势（-1.02% FAV，陷阱信号）")
