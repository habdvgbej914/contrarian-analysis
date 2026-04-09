"""
assess_sanyuan.py — 三元递进分析 (FCAS v4.0)

原文依据（《执棋者》）:
- 元神宫: 值符星的固定本位宫（九星归位）
- 值符宫: 值符星在天盘的当前落宫（ju.zhifu_palace）
- 天乙宫: 时干在天盘的落宫
- 能量流转: 三宫间的五行生克关系

三宫顺序: 元神→值符→天乙
完全顺生（元生值、值生乙）→ FORWARD
有克 → BLOCKED
其余 → MIXED
"""

from fcas_engine_v2 import (
    STAR_HOME_PALACE, GONG_WUXING,
    shengke,
    REL_BIHE, REL_WOSHENG, REL_WOKE, REL_SHENGWO, REL_KEWO,
)

# 九星本位宫 (元神宫): star → home_palace
# 0=天蓬→1坎, 1=天芮→2坤, 2=天冲→3震, 3=天辅→4巽
# 4=天禽→5中(寄), 5=天心→6乾, 6=天柱→7兑, 7=天任→8艮, 8=天英→9离
YUANSHEN_PALACE = STAR_HOME_PALACE  # direct reuse


def _flow_label(rel: int) -> str:
    """将生克关系转为能量流标签（从A宫到B宫的视角）"""
    if rel == REL_WOSHENG:
        return 'sheng'   # A生B: 顺泄，能量流出
    elif rel == REL_SHENGWO:
        return 'sheng'   # B生A: 能量流入（对A有利）
    elif rel == REL_WOKE:
        return 'ke'      # A克B: 制约
    elif rel == REL_KEWO:
        return 'ke'      # B克A: 被制约
    else:
        return 'bi'      # 比和: 平


def assess_sanyuan(ju) -> dict:
    """
    计算三元递进分析。

    返回 dict:
        yuanshen_palace: int   元神宫（值符星本位）
        zhifu_palace:    int   值符宫（值符星当前落宫）
        tianyi_palace:   int   天乙宫（时干在天盘落宫）
        wx_yuan:         int   元神宫五行
        wx_zhifu:        int   值符宫五行
        wx_tianyi:       int   天乙宫五行
        flow_yuan_zf:    str   元神→值符关系 ('sheng'/'ke'/'bi')
        flow_zf_ty:      str   值符→天乙关系
        flow_yuan_ty:    str   元神→天乙关系
        overall:         str   'FORWARD'/'BLOCKED'/'MIXED'
    """
    # 元神宫: 值符星的本位
    yuanshen_p = YUANSHEN_PALACE.get(ju.zhifu_star, 1)
    # 天禽在中5宫，实际寄宫
    if yuanshen_p == 5:
        yuanshen_p = getattr(ju, 'tianqin_host', 2)

    # 值符宫
    zhifu_p = ju.zhifu_palace
    if zhifu_p == 5:
        zhifu_p = getattr(ju, 'tianqin_host', 2)

    # 天乙宫: 时干在天盘的落宫
    hour_tg = ju.hour_gz[0]
    tianyi_p = None
    for palace, stem in ju.heaven.items():
        if stem == hour_tg:
            tianyi_p = palace
            break
    if tianyi_p is None:
        tianyi_p = zhifu_p  # fallback: 与值符同宫
    if tianyi_p == 5:
        tianyi_p = getattr(ju, 'tianqin_host', 2)

    # 三宫五行
    wx_yuan  = GONG_WUXING.get(yuanshen_p, 0)
    wx_zhifu = GONG_WUXING.get(zhifu_p, 0)
    wx_tianyi = GONG_WUXING.get(tianyi_p, 0)

    # 五行关系（从A看B: shengke(A_wx, B_wx)）
    rel_yuan_zf  = shengke(wx_yuan, wx_zhifu)
    rel_zf_ty    = shengke(wx_zhifu, wx_tianyi)
    rel_yuan_ty  = shengke(wx_yuan, wx_tianyi)

    flow_yuan_zf = _flow_label(rel_yuan_zf)
    flow_zf_ty   = _flow_label(rel_zf_ty)
    flow_yuan_ty = _flow_label(rel_yuan_ty)

    # 总体判断
    # FORWARD: 元神生值符 且 值符生天乙（完全顺生链）
    if rel_yuan_zf == REL_WOSHENG and rel_zf_ty == REL_WOSHENG:
        overall = 'FORWARD'
    # BLOCKED: 有克制关系（任意一环有克）
    elif REL_WOKE in (rel_yuan_zf, rel_zf_ty, rel_yuan_ty) or \
         REL_KEWO in (rel_yuan_zf, rel_zf_ty, rel_yuan_ty):
        overall = 'BLOCKED'
    else:
        overall = 'MIXED'

    return {
        'yuanshen_palace': yuanshen_p,
        'zhifu_palace':    zhifu_p,
        'tianyi_palace':   tianyi_p,
        'wx_yuan':         wx_yuan,
        'wx_zhifu':        wx_zhifu,
        'wx_tianyi':       wx_tianyi,
        'flow_yuan_zf':    flow_yuan_zf,
        'flow_zf_ty':      flow_zf_ty,
        'flow_yuan_ty':    flow_yuan_ty,
        'overall':         overall,
    }
