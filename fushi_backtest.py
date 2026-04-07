"""
FCAS 符使系统回测脚本
====================
将符使评估结果与已有的天时v6 + 人事层回测数据合并，
验证符使全局基调是否能增加预测力。

前提：
- fcas_engine_v2.py 可用（已修复的排盘引擎）
- tianshi_v6_backtest_results.json 可用（4592条天时v6结果）
- assess_fushi.py 可用

用法：
  cd ~/Desktop/自主项目/fcas
  python3 fushi_backtest.py
"""

import json
import os
from datetime import datetime, timedelta
from collections import defaultdict

# ============================================================
# 配置
# ============================================================

# 8个标的
STOCKS = [
    '000651.SZ', '000063.SZ', '000858.SZ', '600276.SH',
    '600036.SH', '600547.SH', '601318.SH', '601857.SH',
]

# 回测时间范围（与天时v6一致）
# 574周 × 8标的 = 4592条
# 需要从json结果中提取日期列表

# 数据目录
DATA_DIR = 'data/json'
TIANSHI_RESULTS = 'tianshi_v6_backtest_results.json'
OUTPUT_FILE = 'fushi_backtest_results.json'


def load_tianshi_results():
    """加载已有的天时v6回测结果"""
    if not os.path.exists(TIANSHI_RESULTS):
        print(f"[ERROR] {TIANSHI_RESULTS} 不存在")
        print("请先运行天时v6回测脚本生成结果文件")
        return None
    
    with open(TIANSHI_RESULTS, 'r') as f:
        data = json.load(f)
    
    print(f"[INFO] 加载天时v6结果: {len(data)} 条")
    return data


def extract_unique_dates(tianshi_data):
    """从天时v6结果中提取唯一日期列表"""
    dates = set()
    for record in tianshi_data:
        # 假设每条记录有 'date' 字段
        date_str = record.get('date', record.get('week_start', ''))
        if date_str:
            dates.add(date_str)
    
    dates = sorted(list(dates))
    print(f"[INFO] 提取到 {len(dates)} 个唯一日期")
    return dates


def run_fushi_backtest(dates):
    """
    对每个日期运行符使评估
    
    注意：符使是全局属性，同一日期的所有标的共享同一个评估结果
    """
    try:
        from fcas_engine_v2 import paipan
        from assess_fushi import assess_fushi
    except ImportError as e:
        print(f"[ERROR] 导入失败: {e}")
        print("请确保 fcas_engine_v2.py 和 assess_fushi.py 在当前目录")
        return None
    
    results = {}
    errors = 0
    
    for i, date_str in enumerate(dates):
        try:
            # 解析日期，使用周一10:00作为排盘时间
            # 因为FCAS用的是周频数据，每周一个局
            dt = datetime.strptime(date_str, '%Y-%m-%d')
            # 使用该周的周一 10:00 排盘（工作日开盘时间）
            # 如果date_str本身就是周一，直接用
            weekday = dt.weekday()  # 0=Monday
            if weekday != 0:
                # 调整到该周的周一
                dt = dt - timedelta(days=weekday)
            
            dt = dt.replace(hour=10, minute=0)
            
            ju = paipan(dt)
            result = assess_fushi(ju)
            
            results[date_str] = {
                'fushi_score': result['fushi_score'],
                'fushi_label': result['fushi_label'],
                'relation_type': result['relation']['type'],
                'relation_score': result['relation']['score'],
                'zhifu_star': result['zhifu_star'],
                'zhifu_palace': result['zhifu_palace'],
                'zhishi_gate': result['zhishi_gate'],
                'zhishi_palace': result['zhishi_palace'],
                'paipan_dt': dt.strftime('%Y-%m-%d %H:%M'),
            }
            
            if (i + 1) % 50 == 0:
                print(f"  进度: {i+1}/{len(dates)}")
                
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  [WARN] {date_str} 排盘失败: {e}")
    
    print(f"[INFO] 符使评估完成: {len(results)} 成功, {errors} 失败")
    return results


def merge_and_analyze(tianshi_data, fushi_results):
    """
    合并天时v6结果和符使评估结果，分析符使是否增加预测力
    """
    # 统计容器
    stats = defaultdict(lambda: {'count': 0, 'ret_1w': [], 'ret_13w': []})
    
    merged = []
    no_fushi = 0
    
    for record in tianshi_data:
        date_str = record.get('date', record.get('week_start', ''))
        
        fushi = fushi_results.get(date_str)
        if not fushi:
            no_fushi += 1
            continue
        
        # 合并
        tianshi_label = record.get('label', record.get('tianshi_label', 'UNKNOWN'))
        ret_1w = record.get('ret_1w', record.get('return_1w'))
        ret_13w = record.get('ret_13w', record.get('return_13w'))
        
        if ret_1w is None:
            continue
        
        fushi_label = fushi['fushi_label']
        
        # 记录
        merged_record = {
            'date': date_str,
            'stock': record.get('stock', record.get('ticker', '')),
            'tianshi_label': tianshi_label,
            'fushi_label': fushi_label,
            'fushi_score': fushi['fushi_score'],
            'ret_1w': ret_1w,
            'ret_13w': ret_13w,
        }
        merged.append(merged_record)
        
        # 分组统计
        # 1. 纯符使分组
        key_fushi = f"FUSHI_{fushi_label}"
        stats[key_fushi]['count'] += 1
        stats[key_fushi]['ret_1w'].append(ret_1w)
        if ret_13w is not None:
            stats[key_fushi]['ret_13w'].append(ret_13w)
        
        # 2. 天时×符使交叉分组
        key_cross = f"T_{tianshi_label}_x_FS_{fushi_label}"
        stats[key_cross]['count'] += 1
        stats[key_cross]['ret_1w'].append(ret_1w)
        if ret_13w is not None:
            stats[key_cross]['ret_13w'].append(ret_13w)
    
    if no_fushi > 0:
        print(f"[WARN] {no_fushi} 条天时记录无对应符使结果（日期不匹配）")
    
    print(f"[INFO] 合并成功: {len(merged)} 条")
    
    return merged, stats


def print_stats(stats):
    """打印统计结果"""
    print()
    print("=" * 80)
    print("符使系统回测统计结果")
    print("=" * 80)
    
    # 先打印纯符使分组
    print()
    print("--- 纯符使分组 ---")
    print(f"{'类别':<30} {'N':>6} {'1W Avg':>10} {'13W Avg':>10}")
    print("-" * 60)
    
    fushi_keys = sorted([k for k in stats if k.startswith('FUSHI_')])
    for key in fushi_keys:
        s = stats[key]
        n = s['count']
        avg_1w = sum(s['ret_1w']) / n * 100 if n > 0 else 0
        avg_13w = sum(s['ret_13w']) / len(s['ret_13w']) * 100 if s['ret_13w'] else float('nan')
        print(f"{key:<30} {n:>6} {avg_1w:>+9.2f}% {avg_13w:>+9.2f}%")
    
    # 符使SPREAD
    supp = stats.get('FUSHI_SUPPORTIVE', {'ret_1w': [], 'ret_13w': []})
    host = stats.get('FUSHI_HOSTILE', {'ret_1w': [], 'ret_13w': []})
    if supp['ret_1w'] and host['ret_1w']:
        spread_1w = (sum(supp['ret_1w'])/len(supp['ret_1w']) - sum(host['ret_1w'])/len(host['ret_1w'])) * 100
        print(f"\n1W SPREAD (SUPPORTIVE - HOSTILE): {spread_1w:+.2f}%")
    if supp['ret_13w'] and host['ret_13w']:
        spread_13w = (sum(supp['ret_13w'])/len(supp['ret_13w']) - sum(host['ret_13w'])/len(host['ret_13w'])) * 100
        print(f"13W SPREAD (SUPPORTIVE - HOSTILE): {spread_13w:+.2f}%")
    
    # 打印天时×符使交叉
    print()
    print("--- 天时×符使交叉分组 ---")
    print(f"{'类别':<45} {'N':>6} {'1W Avg':>10} {'13W Avg':>10}")
    print("-" * 75)
    
    cross_keys = sorted([k for k in stats if k.startswith('T_')])
    for key in cross_keys:
        s = stats[key]
        n = s['count']
        if n < 5:  # 样本太小不显示
            continue
        avg_1w = sum(s['ret_1w']) / n * 100 if n > 0 else 0
        avg_13w = sum(s['ret_13w']) / len(s['ret_13w']) * 100 if s['ret_13w'] else float('nan')
        print(f"{key:<45} {n:>6} {avg_1w:>+9.2f}% {avg_13w:>+9.2f}%")
    
    # 关键对比：同为天时FAV时，符使SUPPORTIVE vs HOSTILE
    key_fav_supp = 'T_FAVORABLE_x_FS_SUPPORTIVE'
    key_fav_host = 'T_FAVORABLE_x_FS_HOSTILE'
    key_fav_neut = 'T_FAVORABLE_x_FS_NEUTRAL'
    
    print()
    print("--- 关键对比：天时FAVORABLE内的符使调节效果 ---")
    for k in [key_fav_supp, key_fav_neut, key_fav_host]:
        if k in stats and stats[k]['count'] >= 3:
            s = stats[k]
            n = s['count']
            avg_1w = sum(s['ret_1w']) / n * 100
            avg_13w = sum(s['ret_13w']) / len(s['ret_13w']) * 100 if s['ret_13w'] else float('nan')
            print(f"  {k}: N={n}, 1W={avg_1w:+.2f}%, 13W={avg_13w:+.2f}%")
        else:
            print(f"  {k}: 样本不足")


def print_distribution(fushi_results):
    """打印符使标签分布"""
    dist = defaultdict(int)
    for date_str, result in fushi_results.items():
        dist[result['fushi_label']] += 1
    
    total = sum(dist.values())
    print()
    print("--- 符使标签分布 ---")
    for label in ['SUPPORTIVE', 'NEUTRAL', 'HOSTILE']:
        n = dist.get(label, 0)
        pct = n / total * 100 if total > 0 else 0
        print(f"  {label}: {n} ({pct:.1f}%)")
    print(f"  总计: {total} 个唯一日期")
    
    # 检查分布是否合理
    # 理论上NEUTRAL应该最多，如果SUPPORTIVE或HOSTILE占比过高说明阈值有问题
    neutral_pct = dist.get('NEUTRAL', 0) / total * 100 if total > 0 else 0
    if neutral_pct < 20:
        print(f"  [WARN] NEUTRAL占比仅{neutral_pct:.1f}%，阈值可能需要调整")
    elif neutral_pct > 70:
        print(f"  [WARN] NEUTRAL占比{neutral_pct:.1f}%过高，评估可能缺乏区分度")


# ============================================================
# 主流程
# ============================================================

def main():
    print("=" * 60)
    print("FCAS 符使系统回测")
    print("=" * 60)
    
    # 1. 加载天时v6结果
    tianshi_data = load_tianshi_results()
    if tianshi_data is None:
        return
    
    # 2. 提取唯一日期
    dates = extract_unique_dates(tianshi_data)
    if not dates:
        print("[ERROR] 未提取到日期")
        return
    
    # 3. 对每个日期运行符使评估
    print()
    print("[STEP] 运行符使评估...")
    fushi_results = run_fushi_backtest(dates)
    if fushi_results is None:
        return
    
    # 4. 打印分布
    print_distribution(fushi_results)
    
    # 5. 合并分析
    print()
    print("[STEP] 合并天时v6与符使结果...")
    merged, stats = merge_and_analyze(tianshi_data, fushi_results)
    
    # 6. 打印结果
    print_stats(stats)
    
    # 7. 保存结果
    output = {
        'fushi_by_date': fushi_results,
        'merged_count': len(merged),
        'stats_summary': {}
    }
    
    # 转换stats为可序列化格式
    for key, s in stats.items():
        n = s['count']
        output['stats_summary'][key] = {
            'count': n,
            'avg_1w': sum(s['ret_1w']) / n if n > 0 else None,
            'avg_13w': sum(s['ret_13w']) / len(s['ret_13w']) if s['ret_13w'] else None,
        }
    
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n[DONE] 结果已保存到 {OUTPUT_FILE}")
    print()
    print("下一步:")
    print("  1. 检查符使标签分布是否合理（NEUTRAL应在30-60%）")
    print("  2. 检查SUPPORTIVE vs HOSTILE的SPREAD是否正向")
    print("  3. 检查天时FAV内符使的调节效果是否单调")
    print("  4. 如果效果不好，考虑调整阈值或移除此模块")


if __name__ == '__main__':
    main()
