"""
FCAS 天时层 v6 回测验证
587周 × 8标的 × 天时层v6评估

使用方式:
    python3 tianshi_v6_backtest.py

前置条件:
    - fcas_engine_v2.py (修复版) 在同目录
    - data/json/ 目录下有8个标的的周度价格数据
    - assess_tianshi_v6.py 在同目录
"""

import json
import os
import sys
from datetime import datetime, timedelta
from collections import defaultdict

# 导入核心模块
from fcas_engine_v2 import paipan
from assess_tianshi_v6 import assess_stock_tianshi_v6, STOCK_CONFIG

# ============================================================
# 回测配置
# ============================================================

# 有weekly数据文件的标的
BACKTEST_STOCKS = [
    '000651.SZ',  # 格力电器 → gree_weekly.json
    '000063.SZ',  # 中兴通讯 → zte_weekly.json
    '000858.SZ',  # 五粮液 → wuliangye_weekly.json
    '600276.SH',  # 恒瑞医药 → hengrui_weekly.json
    '600036.SH',  # 招商银行 → cmb_weekly.json
    '601318.SH',  # 中国平安 → ping_an_weekly.json
    '601857.SH',  # 中国石油 → petrochina_weekly.json
    '601012.SH',  # 隆基绿能 → longi_weekly.json
]

# 股票代码 → 实际JSON文件名映射
STOCK_FILE_MAP = {
    '000651.SZ': 'gree_weekly.json',
    '000063.SZ': 'zte_weekly.json',
    '000858.SZ': 'wuliangye_weekly.json',
    '600276.SH': 'hengrui_weekly.json',
    '600036.SH': 'cmb_weekly.json',
    # '600547.SH': 无文件
    '601318.SH': 'ping_an_weekly.json',
    '601857.SH': 'petrochina_weekly.json',
    # '601899.SH': 无文件
    '601012.SH': 'longi_weekly.json',
}

# 回测时间范围（与人事层587周一致）
# 具体日期需要根据data/json/里的数据确定
DATA_DIR = 'data/json/'
RESULTS_FILE = 'tianshi_v6_backtest_results.json'

# ============================================================
# 数据加载
# ============================================================

def load_weekly_prices(stock_code):
    """
    加载标的的周度价格数据
    
    数据格式（从Wind xlsx转换的JSON）:
    [
        {"date": "2015-01-02", "close": 37.12, "weekly_return_pct": null, ...},
        ...
    ]
    
    返回: list of dict, sorted by date
    """
    filename = STOCK_FILE_MAP.get(stock_code)
    if not filename:
        print(f"  ⚠️ {stock_code} 没有文件名映射")
        return None
    
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        print(f"  ⚠️ 文件不存在: {path}")
        return None
    
    with open(path, 'r') as f:
        data = json.load(f)
    
    # 过滤掉close为None的条目
    data = [d for d in data if d.get('close') is not None]
    return sorted(data, key=lambda x: x['date'])


def calc_future_return(prices, start_date, weeks=1):
    """
    计算从start_date开始未来N周的收益率
    
    返回: float (收益率) 或 None
    """
    dates = [p['date'] for p in prices]
    
    if start_date not in dates:
        # 找最近的日期
        for d in dates:
            if d >= start_date:
                start_date = d
                break
        else:
            return None
    
    start_idx = dates.index(start_date)
    end_idx = start_idx + weeks
    
    if end_idx >= len(prices):
        return None
    
    start_price = prices[start_idx]['close']
    end_price = prices[end_idx]['close']
    
    if start_price == 0:
        return None
    
    return (end_price - start_price) / start_price


# ============================================================
# 排盘时间确定
# ============================================================

def get_paipan_time_for_week(week_date_str):
    """
    对于每一周的数据，确定排盘时间
    
    策略：取该周周一的开盘时间（北京时间09:30）
    这样排出的是"该周初"的奇门局，用于评估该周的天时状态
    
    返回: datetime (用于paipan的时间参数)
    """
    dt = datetime.strptime(week_date_str, '%Y-%m-%d')
    
    # 回退到周一（如果不是周一的话）
    weekday = dt.weekday()  # 0=Mon, 6=Sun
    monday = dt - timedelta(days=weekday)
    
    # 设定为北京时间09:30（取交易开盘时间）
    # paipan需要的是年月日时，我们用巳时（09-11点）
    return monday


# ============================================================
# 主回测函数
# ============================================================

def run_backtest():
    """
    运行587周×8标的的天时层v6回测
    """
    print("=" * 70)
    print("  FCAS 天时层 v6 回测验证")
    print("  587周 × 8标的")
    print("=" * 70)
    print()
    
    # 加载所有标的的价格数据
    all_prices = {}
    for code in BACKTEST_STOCKS:
        prices = load_weekly_prices(code)
        if prices:
            all_prices[code] = prices
            print(f"  ✅ {code}: {len(prices)}周数据 ({prices[0]['date']} ~ {prices[-1]['date']})")
        else:
            print(f"  ❌ {code}: 数据缺失")
    
    if not all_prices:
        print("\n❌ 没有任何价格数据，无法回测")
        return
    
    # 确定回测时间范围（取所有标的的交集）
    all_dates = None
    for code, prices in all_prices.items():
        dates = set(p['date'] for p in prices)
        if all_dates is None:
            all_dates = dates
        else:
            all_dates &= dates
    
    all_dates = sorted(all_dates)
    
    # 预留未来1周和13周的空间
    if len(all_dates) < 14:
        print("\n❌ 数据不足14周，无法回测")
        return
    
    backtest_dates = all_dates[:-13]  # 留出13周给未来收益计算
    print(f"\n  回测时间范围: {backtest_dates[0]} ~ {backtest_dates[-1]}")
    print(f"  共 {len(backtest_dates)} 周")
    print()
    
    # ── 回测循环 ──
    results = []
    label_counts = defaultdict(int)
    label_returns_1w = defaultdict(list)
    label_returns_13w = defaultdict(list)
    
    total = len(backtest_dates) * len(all_prices)
    done = 0
    
    for week_date in backtest_dates:
        # 排盘
        monday = get_paipan_time_for_week(week_date)
        
        try:
            # paipan()接受datetime对象
            pan_dt = datetime(monday.year, monday.month, monday.day, 9, 30)
            pan = paipan(pan_dt)
            # assess_stock_tianshi_v6会自动将QimenJu转为字典
        except Exception as e:
            print(f"  ⚠️ 排盘失败 {week_date}: {e}")
            done += len(all_prices)
            continue
        
        # 对每个标的评估
        for code, prices in all_prices.items():
            done += 1
            
            try:
                assessment = assess_stock_tianshi_v6(pan, code)
                label = assessment['label']
            except Exception as e:
                label = 'ERROR'
                assessment = {'label': 'ERROR', 'combined_score': 0, 'reasoning': str(e)}
            
            # 计算未来收益
            ret_1w = calc_future_return(prices, week_date, weeks=1)
            ret_13w = calc_future_return(prices, week_date, weeks=13)
            
            result = {
                'date': week_date,
                'stock_code': code,
                'label': label,
                'score': assessment.get('combined_score', 0),
                'same_palace': assessment.get('same_palace', False),
                'fuyin_fanyin': assessment.get('fuyin_fanyin'),
                'return_1w': ret_1w,
                'return_13w': ret_13w,
            }
            results.append(result)
            
            # 统计
            label_counts[label] += 1
            if ret_1w is not None:
                label_returns_1w[label].append(ret_1w)
            if ret_13w is not None:
                label_returns_13w[label].append(ret_13w)
            
            # 进度显示
            if done % 500 == 0:
                pct = done / total * 100
                print(f"  进度: {done}/{total} ({pct:.1f}%) - 当前: {week_date} {code}")
    
    # ── 保存结果 ──
    with open(RESULTS_FILE, 'w') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 结果已保存: {RESULTS_FILE} ({len(results)}条)")
    
    # ── 统计分析 ──
    print("\n" + "=" * 70)
    print("  回测统计结果")
    print("=" * 70)
    
    # 信号分布
    print("\n📊 信号分布:")
    total_signals = sum(label_counts.values())
    for label in ['FAVORABLE', 'PARTIAL_GOOD', 'NEUTRAL', 'PARTIAL_BAD', 'UNFAVORABLE', 'STAGNANT', 'VOLATILE', 'ERROR']:
        count = label_counts.get(label, 0)
        pct = count / total_signals * 100 if total_signals > 0 else 0
        print(f"  {label:16s}: {count:5d} ({pct:5.1f}%)")
    
    # 各标签的未来收益
    print("\n📈 各标签平均收益率:")
    print(f"  {'Label':16s} | {'1W Avg':>8s} | {'1W Med':>8s} | {'13W Avg':>8s} | {'13W Med':>8s} | {'N':>6s}")
    print(f"  {'-'*16}-+-{'-'*8}-+-{'-'*8}-+-{'-'*8}-+-{'-'*8}-+-{'-'*6}")
    
    for label in ['FAVORABLE', 'PARTIAL_GOOD', 'NEUTRAL', 'PARTIAL_BAD', 'UNFAVORABLE', 'STAGNANT', 'VOLATILE']:
        r1w = label_returns_1w.get(label, [])
        r13w = label_returns_13w.get(label, [])
        
        avg_1w = sum(r1w) / len(r1w) * 100 if r1w else 0
        med_1w = sorted(r1w)[len(r1w)//2] * 100 if r1w else 0
        avg_13w = sum(r13w) / len(r13w) * 100 if r13w else 0
        med_13w = sorted(r13w)[len(r13w)//2] * 100 if r13w else 0
        n = len(r1w)
        
        print(f"  {label:16s} | {avg_1w:+7.2f}% | {med_1w:+7.2f}% | {avg_13w:+7.2f}% | {med_13w:+7.2f}% | {n:6d}")
    
    # SPREAD 计算（FAVORABLE vs UNFAVORABLE）
    fav_1w = label_returns_1w.get('FAVORABLE', []) + label_returns_1w.get('PARTIAL_GOOD', [])
    unfav_1w = label_returns_1w.get('UNFAVORABLE', []) + label_returns_1w.get('PARTIAL_BAD', [])
    
    if fav_1w and unfav_1w:
        spread_1w = (sum(fav_1w)/len(fav_1w) - sum(unfav_1w)/len(unfav_1w)) * 100
        print(f"\n  1W SPREAD (FAV+PG vs UNFAV+PB): {spread_1w:+.2f}%")
    
    fav_13w = label_returns_13w.get('FAVORABLE', []) + label_returns_13w.get('PARTIAL_GOOD', [])
    unfav_13w = label_returns_13w.get('UNFAVORABLE', []) + label_returns_13w.get('PARTIAL_BAD', [])
    
    if fav_13w and unfav_13w:
        spread_13w = (sum(fav_13w)/len(fav_13w) - sum(unfav_13w)/len(unfav_13w)) * 100
        print(f"  13W SPREAD (FAV+PG vs UNFAV+PB): {spread_13w:+.2f}%")
    
    # 统计显著性检验（简化版：t-test）
    print("\n📐 统计检验:")
    try:
        from scipy import stats
        
        if fav_1w and unfav_1w:
            t_stat, p_value = stats.ttest_ind(fav_1w, unfav_1w)
            sig = "✅ 显著" if p_value < 0.05 else "❌ 不显著"
            print(f"  1W t-test: t={t_stat:.3f}, p={p_value:.4f} {sig}")
        
        if fav_13w and unfav_13w:
            t_stat, p_value = stats.ttest_ind(fav_13w, unfav_13w)
            sig = "✅ 显著" if p_value < 0.05 else "❌ 不显著"
            print(f"  13W t-test: t={t_stat:.3f}, p={p_value:.4f} {sig}")
    except ImportError:
        print("  (scipy未安装，跳过统计检验)")
    
    print("\n✅ 回测完成")
    return results


if __name__ == '__main__':
    run_backtest()
