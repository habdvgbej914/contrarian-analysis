"""
FCAS MCP server entrypoint.

This module re-exports the standalone engine from `fcas_engine_v2.py`
for compatibility and adds only the FastMCP tool wrappers.
"""

from datetime import datetime

from mcp.server.fastmcp import FastMCP

from fcas_engine_v2 import *  # noqa: F401,F403


app = FastMCP("fcas-server")


@app.tool()
def fcas_paipan(year: int, month: int, day: int, hour: int, minute: int = 0) -> str:
    """排盘: 给定时间，生成完整奇门局。"""
    dt = datetime(year, month, day, hour, minute)
    ju = paipan(dt)
    hex_info = ju.get_hexagram_binary()

    lines = []
    lines.append(f"奇门局: {'阳' if ju.is_yangdun else '阴'}遁{ju.ju_number}局")
    lines.append(f"节气: {ju.term_name} | 三元: {['上', '中', '下'][ju.sanyuan]}元")
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
    lines.append(
        f"C2={hex_info['C2']} C1={hex_info['C1']} C4={hex_info['C4']} "
        f"C3={hex_info['C3']} C6={hex_info['C6']} C5={hex_info['C5']}"
    )
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


@app.tool()
def fcas_analyze(year: int, month: int, day: int, hour: int, minute: int = 0) -> str:
    """完整FCAS分析: 排盘+格局判断+三层判断+应期推导。"""
    dt = datetime(year, month, day, hour, minute)
    result = analyze(dt)

    lines = []
    js = result["ju_summary"]
    lines.append(f"=== FCAS分析: {result['datetime']} ===")
    lines.append(f"奇门局: {js['type']} | {js['term']} {js['sanyuan']}")
    lines.append(f"日柱: {js['day_pillar']} | 时柱: {js['hour_pillar']} | 空亡: {js['kongwang']}")
    hx = result["hexagram"]
    lines.append(f"\nFCAS Binary: {hx['binary_str']}")

    geju_list = result["geju"]
    ji = [g for g in geju_list if g.jixiong == 1]
    xiong = [g for g in geju_list if g.jixiong == 0]
    lines.append(f"\n格局: 吉{len(ji)}条 凶{len(xiong)}条")
    for g in ji:
        lines.append(f"  [吉] {g.name}: {g.description}")
    for g in xiong:
        lines.append(f"  [凶] {g.name}: {g.description}")

    a = result["assessment"]
    lines.append(f"\n萧吉三层判断:")
    lines.append(f"  卦宫: {a['palace']}({a['palace_wuxing']})")
    sy = a["shi_yao"]
    lines.append(f"  世爻: 第{sy['position']}爻 {sy['dizhi']}({sy['wuxing']}) [{sy['liuqin']}]")
    lines.append(f"  生命阶段: {sy['changsheng']}({sy['changsheng_biz']}) | 旺衰: {sy['wangshuai']}")
    lines.append(
        f"  L1扶抑: {a['layer1_fuyi']} | "
        f"L2有气: {a['layer2_qi']} | "
        f"L3修正: {a['layer3_modifier']}"
    )
    lines.append(f"  >>> {a['final_assessment']}")

    lines.append("\n爻位:")
    for y in a["all_yaos"]:
        yy = "阳" if y["yinyang"] else "阴"
        lines.append(
            f"  {y['pos']}爻({y['criterion']}): "
            f"{yy} {y['dizhi']}({y['wuxing']}) [{y['liuqin']}|{y['liuqin_biz']}]"
        )

    yq = result["yingqi"]
    if yq:
        lines.append("\n应期条件:")
        for c in yq:
            dz_n = DIZHI_NAMES.get(c.dizhi_value, "?")
            pri = ["核心", "重要", "参考"][c.priority]
            lines.append(f"  [{pri}] {c.cond_type}: {dz_n} — {c.description}")

    return "\n".join(lines)


@app.tool()
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
            sv = ["轻", "中", "重", "极"][g.severity]
            lines.append(f"  [{sv}] {g.name} / {g.name_biz} ({p_name}宫): {g.description}")
    if xiong:
        lines.append("\n凶格:")
        for g in xiong:
            p_name = GONG_GUA_NAMES.get(g.palace, "全局") if g.palace else "全局"
            sv = ["轻", "中", "重", "极"][g.severity]
            lines.append(f"  [{sv}] {g.name} / {g.name_biz} ({p_name}宫): {g.description}")
    return "\n".join(lines)


@app.tool()
def fcas_yingqi(year: int, month: int, day: int, hour: int, minute: int = 0) -> str:
    """应期推导: 返回当前状态的时间条件集合。"""
    dt = datetime(year, month, day, hour, minute)
    result = analyze(dt)
    yq = result["yingqi"]

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
    app.run()
