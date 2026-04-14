"""
FCAS 排盘引擎八门旋转修复补丁

问题：Step 13中八门旋转步数用了star_steps（九星步数），
      但八门应该用值使门自己的步数（值使加时支的偏移量）。

修复：用值使门从本位到zhishi_palace在外环上的偏移量作为八门旋转步数。

应用方法：
    在 fcas_engine_v2.py 中找到 Step 13 的代码块，替换为本文件中的修复版。
    
原始代码位置：大约第1258-1268行
原始代码：
    # === Step 13: Layout gates (FIXED: 外环旋转) ===
    # 八门也按外环旋转，步数与九星相同
    gate_layout = {}
    for gate in range(8):
        home_p = GATE_HOME_PALACE[gate]
        home_ring = 2 if home_p == 5 else home_p
        if home_ring not in RING:
            continue
        ring_idx = RING.index(home_ring)
        new_ring_idx = (ring_idx + star_steps) % 8  # 门和星转同样步数(简化版)
        new_palace = RING[new_ring_idx]
        gate_layout[new_palace] = gate
    ju.gates = gate_layout

替换为：
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
"""

# 验证脚本：对比修复前后八门位置是否不同
if __name__ == '__main__':
    from fcas_engine_v2 import paipan, GATE_NAMES, STAR_NAMES, GONG_GUA_NAMES
    from datetime import datetime
    
    # 测试多个时间点
    test_times = [
        datetime(2026, 4, 6, 17, 0),   # 今天
        datetime(2026, 4, 1, 9, 30),    # 回测起始
        datetime(2025, 6, 15, 10, 0),   # 去年夏天
        datetime(2024, 1, 26, 9, 30),   # 115w回测起始
        datetime(2020, 3, 23, 9, 30),   # COVID底
    ]
    
    for dt in test_times:
        ju = paipan(dt)
        print(f"\n{'='*50}")
        print(f"时间: {dt.strftime('%Y-%m-%d %H:%M')}")
        print(f"局: {'阳' if ju.is_yangdun else '阴'}遁{ju.ju_number}局")
        print(f"值符: {STAR_NAMES[ju.zhifu_star]}  值使: {GATE_NAMES[ju.zhishi_gate]}")
        print(f"值使目标宫: {GONG_GUA_NAMES[ju.zhishi_palace]}({ju.zhishi_palace})")
        print(f"值符目标宫: {GONG_GUA_NAMES[ju.zhifu_palace]}({ju.zhifu_palace})")
        
        # 显示当前八门布局
        print(f"\n当前八门布局(可能有偏差):")
        for gong in [1,2,3,4,6,7,8,9]:
            gate = ju.gates.get(gong, '?')
            star = ju.stars.get(gong, '?')
            gate_name = GATE_NAMES.get(gate, '?')
            star_name = STAR_NAMES.get(star, '?')
            print(f"  {GONG_GUA_NAMES[gong]}{gong}宫: {star_name} {gate_name}")
        
        # 计算星步数和门步数是否不同
        from fcas_engine_v2 import PALACE_FLY_FORWARD, GATE_HOME_PALACE, STAR_HOME_PALACE, STAR_QIN
        RING = PALACE_FLY_FORWARD
        
        # 星步数
        zhifu_home = STAR_HOME_PALACE[ju.zhifu_star]
        zhifu_home_r = 2 if zhifu_home == 5 else zhifu_home
        zhifu_target_r = 2 if ju.zhifu_palace == 5 else ju.zhifu_palace
        star_steps = (RING.index(zhifu_target_r) - RING.index(zhifu_home_r)) % 8
        
        # 门步数
        zhishi_home = GATE_HOME_PALACE[ju.zhishi_gate]
        zhishi_home_r = 2 if zhishi_home == 5 else zhishi_home
        zhishi_target_r = 2 if ju.zhishi_palace == 5 else ju.zhishi_palace
        gate_steps = (RING.index(zhishi_target_r) - RING.index(zhishi_home_r)) % 8
        
        diff = "⚠️ 不同!" if star_steps != gate_steps else "✅ 相同"
        print(f"\n  星步数={star_steps}, 门步数={gate_steps} {diff}")
