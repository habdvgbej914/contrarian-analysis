"""
FCAS Auto-Verifier v2.0
验证三层交叉信号的预测能力

核心设计:
- 主指标: 13W超额收益 (个股 vs CSI300基准)
- 信号: cross3_grade (三层联合评级)，不再用天时单层
- 数据源: data/json/*_weekly.json (本地Wind周频数据)
- 评级逻辑: STRONG★★/GOOD★→期望跑赢基准, WEAK/ADVERSE→期望跑输
- SPARSE/UNKNOWN/NEUTRAL→仅记录，不计入准确率

v1.0 → v2.0 改动:
- 放弃 yfinance (A股从海外基本不可用)
- 放弃单层 FAVORABLE/ADVERSE 判断 (天时无独立预测力)
- 改用三层交叉信号 cross3_grade
- 改用超额收益 vs 绝对收益 (更严格的基准对比)
- 1W仅作噪声参考，主验证为13W

Usage: python3 verify_predictions.py
"""

import os
import json
from datetime import datetime, timedelta

from fcas_utils import load_json_file, save_json_file, send_telegram

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR    = os.path.join(SCRIPT_DIR, 'data', 'json')
SCAN_HISTORY_FILE  = os.path.join(SCRIPT_DIR, 'daily_scan_history.json')
VERIFICATION_FILE  = os.path.join(SCRIPT_DIR, 'verification_results.json')

# ============================================================
# 股票代码 → 本地数据文件别名
# ============================================================
CODE_TO_ALIAS = {
    '000651.SZ': 'gree',
    '000063.SZ': 'zte',
    '000858.SZ': 'wuliangye',
    '600276.SH': 'hengrui',
    '600036.SH': 'cmb',
    '601318.SH': 'ping_an',
    '601857.SH': 'petrochina',
    '601012.SH': 'longi',
    '601899.SH': None,  # 无本地数据
    '600547.SH': None,  # 无本地数据
}

STOCK_NAMES = {
    '000651.SZ': '格力电器',
    '000063.SZ': '中兴通讯',
    '000858.SZ': '五粮液',
    '600276.SH': '恒瑞医药',
    '600036.SH': '招商银行',
    '601318.SH': '中国平安',
    '601857.SH': '中国石油',
    '601012.SH': '隆基绿能',
    '601899.SH': '紫金矿业',
    '600547.SH': '山东黄金',
}

# ============================================================
# cross3_grade → 方向期望
# OUTPERFORM: 期望跑赢基准 (超额 > 0)
# UNDERPERFORM: 期望跑输基准 (超额 ≤ 0)
# SKIP: 样本不足或未知，不计入准确率
# ============================================================
GRADE_DIRECTION = {
    'PRIME★★★': 'OUTPERFORM',
    'STRONG★★': 'OUTPERFORM',
    'GOOD★':    'OUTPERFORM',
    'MODERATE': 'OUTPERFORM',   # 温和正向，期望轻微跑赢
    'NEUTRAL':  'SKIP',
    'WEAK':     'UNDERPERFORM',
    'ADVERSE':  'UNDERPERFORM',
    'SPARSE':   'SKIP',
    'UNKNOWN':  'SKIP',
}

# 验证周期（以周为单位）
VERIFY_WEEKS = 13   # 主验证: 13周
NOISE_WEEKS  = 1    # 噪声参考: 1周

# 缓存
_PRICE_CACHE   = {}   # (alias, date_str) → close
_RETURNS_CACHE = {}   # alias → {date_str: weekly_return_pct}


# ============================================================
# 数据加载
# ============================================================

def _load_weekly(alias: str) -> list:
    path = os.path.join(DATA_DIR, f'{alias}_weekly.json')
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)


def _build_price_index(alias: str) -> dict:
    """返回 {date_str: close} 字典"""
    if alias in _PRICE_CACHE:
        return _PRICE_CACHE[alias]
    rows = _load_weekly(alias)
    idx = {r['date']: r['close'] for r in rows if r.get('close') is not None}
    _PRICE_CACHE[alias] = idx
    return idx


def _get_price_after(price_idx: dict, target_date_str: str) -> tuple:
    """
    获取 target_date_str 当天或之后最近的收盘价。
    返回 (actual_date_str, price) 或 (None, None)
    """
    dates = sorted(price_idx.keys())
    for d in dates:
        if d >= target_date_str:
            return d, price_idx[d]
    return None, None


def _get_price_on_or_before(price_idx: dict, target_date_str: str) -> tuple:
    """
    获取 target_date_str 当天或之前最近的收盘价。
    返回 (actual_date_str, price) 或 (None, None)
    """
    dates = sorted(price_idx.keys(), reverse=True)
    for d in dates:
        if d <= target_date_str:
            return d, price_idx[d]
    return None, None


def _calc_return(price_idx: dict, entry_date_str: str, weeks: int) -> float | None:
    """
    计算从 entry_date 起 N 周后的收益率。
    entry: 当天或之后最近的价格
    exit:  entry日期 + N周后，当天或之后最近的价格
    """
    entry_d, entry_p = _get_price_after(price_idx, entry_date_str)
    if entry_p is None:
        return None
    exit_date = (datetime.strptime(entry_d, '%Y-%m-%d') + timedelta(weeks=weeks)).strftime('%Y-%m-%d')
    exit_d, exit_p = _get_price_after(price_idx, exit_date)
    if exit_p is None:
        return None
    return round((exit_p - entry_p) / entry_p * 100, 4)


# CSI300 基准
_CSI300_IDX = None

def _get_csi300_index():
    global _CSI300_IDX
    if _CSI300_IDX is None:
        path = os.path.join(DATA_DIR, 'csi300_index.json')
        with open(path) as f:
            rows = json.load(f)
        _CSI300_IDX = {r['date']: r['close'] for r in rows if r.get('close') is not None}
    return _CSI300_IDX


# ============================================================
# 历史记录解析
# ============================================================

def load_history() -> list:
    return load_json_file(SCAN_HISTORY_FILE, [], label='Scan history', expected_type=list)


def flatten_history(history: list) -> list:
    """
    从 daily_scan_history 提取每条 (stock, date, cross3_grade, ...) 记录。
    只保留有 cross3_grade 字段的记录（v4.0+格式）。
    每股每天取最后一次扫描。
    """
    latest = {}
    for record in history:
        if not isinstance(record, dict):
            continue
        ts = record.get('timestamp', '')
        stocks = record.get('stocks', {})
        if not ts or not isinstance(stocks, dict):
            continue
        try:
            scan_date = datetime.strptime(ts.split()[0], '%Y-%m-%d').strftime('%Y-%m-%d')
        except ValueError:
            continue

        for code, data in stocks.items():
            if not isinstance(data, dict):
                continue
            grade = data.get('cross3_grade')
            if not grade:
                continue  # 跳过 v3.0 及更早的记录

            key = (code, scan_date)
            entry = {
                'stock_code':   code,
                'stock_name':   STOCK_NAMES.get(code, code),
                'scan_date':    scan_date,
                'scan_time':    ts,
                'ju':           record.get('ju', ''),
                'assessment':   data.get('assessment', ''),
                'h_label':      data.get('h_label', ''),
                'liuqin_label': data.get('liuqin_label', ''),
                'cross3_grade': grade,
                'cross3_combo': data.get('cross3_combo', ''),
                'cross3_n':     data.get('cross3_n'),
                'cross3_r13w':  None,  # backtest expected, looked up from CROSS_3LAYER
                'direction':    GRADE_DIRECTION.get(grade, 'SKIP'),
            }
            # 取最晚扫描（同一天多次）
            if key not in latest or ts > latest[key]['scan_time']:
                latest[key] = entry

    return sorted(latest.values(), key=lambda x: (x['scan_date'], x['stock_code']))


# ============================================================
# 验证执行
# ============================================================

def run_verification(flat_records: list, existing_records: list) -> tuple:
    """
    对每条记录检查13W（主）和1W（参考）是否到期，计算超额收益并评级。
    返回 (all_records, newly_verified)
    """
    today_str = datetime.now().strftime('%Y-%m-%d')
    csi300 = _get_csi300_index()

    # 现有记录索引
    ex_idx = {}
    for v in existing_records:
        k = (v['stock_code'], v['scan_date'])
        ex_idx[k] = v

    all_records = []
    newly_verified = []

    for r in flat_records:
        code   = r['stock_code']
        alias  = CODE_TO_ALIAS.get(code)
        key    = (code, r['scan_date'])

        # 合并已有验证数据
        existing = ex_idx.get(key, {})
        rec = dict(r)
        rec['verification'] = dict(existing.get('verification', {}))

        if alias is None:
            # 无本地数据：直接标记 NO_DATA
            for label, weeks in [('13w', VERIFY_WEEKS), ('1w', NOISE_WEEKS)]:
                if rec['verification'].get(f'{label}_grade') not in ('OUTPERFORM', 'UNDERPERFORM', 'SKIP_GRADE', 'CORRECT', 'WRONG'):
                    rec['verification'][f'{label}_grade'] = 'NO_DATA'
            all_records.append(rec)
            continue

        price_idx = _build_price_index(alias)

        for label, weeks in [('13w', VERIFY_WEEKS), ('1w', NOISE_WEEKS)]:
            grade_key = f'{label}_grade'

            # 已有终态，跳过
            if rec['verification'].get(grade_key) in ('OUTPERFORM', 'UNDERPERFORM', 'SKIP_GRADE', 'CORRECT', 'WRONG'):
                continue

            # 检查到期（scan_date + weeks 周 < today）
            maturity = (datetime.strptime(r['scan_date'], '%Y-%m-%d') + timedelta(weeks=weeks)).strftime('%Y-%m-%d')
            if maturity > today_str:
                continue

            # 计算个股收益率
            stock_ret = _calc_return(price_idx, r['scan_date'], weeks)
            # 计算CSI300收益率（基准）
            bench_ret = _calc_return(csi300, r['scan_date'], weeks)

            if stock_ret is None or bench_ret is None:
                rec['verification'][grade_key] = 'NO_DATA'
                continue

            excess = round(stock_ret - bench_ret, 4)
            direction = r['direction']

            if direction == 'SKIP':
                grade = 'SKIP_GRADE'
            elif direction == 'OUTPERFORM':
                grade = 'CORRECT' if excess > 0 else 'WRONG'
            else:  # UNDERPERFORM
                grade = 'CORRECT' if excess <= 0 else 'WRONG'

            rec['verification'][grade_key]          = grade
            rec['verification'][f'{label}_stock_ret']  = stock_ret
            rec['verification'][f'{label}_bench_ret']  = bench_ret
            rec['verification'][f'{label}_excess']     = excess
            rec['verification'][f'{label}_maturity']   = maturity

            if label == '13w' and grade in ('CORRECT', 'WRONG'):
                newly_verified.append({
                    'stock':      f"{r['stock_name']} ({code})",
                    'scan_date':  r['scan_date'],
                    'grade_label': r['cross3_grade'],
                    'combo':      r['cross3_combo'],
                    'direction':  direction,
                    'stock_ret':  stock_ret,
                    'bench_ret':  bench_ret,
                    'excess':     excess,
                    'grade':      grade,
                })

        all_records.append(rec)

    return all_records, newly_verified


# ============================================================
# 统计
# ============================================================

def compute_stats(all_records: list) -> dict:
    stats = {
        'total': len(all_records),
        'by_grade': {},
        'summary_13w': {'correct': 0, 'wrong': 0, 'skip': 0, 'no_data': 0, 'pending': 0, 'excess_vals': []},
        'summary_1w':  {'correct': 0, 'wrong': 0, 'skip': 0, 'no_data': 0, 'pending': 0, 'excess_vals': []},
    }

    for r in all_records:
        grade_label = r.get('cross3_grade', 'UNKNOWN')
        if grade_label not in stats['by_grade']:
            stats['by_grade'][grade_label] = {
                'n': 0, 'correct': 0, 'wrong': 0, 'skip': 0, 'excess_vals': []
            }
        stats['by_grade'][grade_label]['n'] += 1

        v = r.get('verification', {})
        for label, key in [('13w', 'summary_13w'), ('1w', 'summary_1w')]:
            g = v.get(f'{label}_grade')
            excess = v.get(f'{label}_excess')
            if g is None:
                stats[key]['pending'] += 1
            elif g == 'NO_DATA':
                stats[key]['no_data'] += 1
            elif g == 'SKIP_GRADE':
                stats[key]['skip'] += 1
                if label == '13w':
                    stats['by_grade'][grade_label]['skip'] += 1
            elif g == 'CORRECT':
                stats[key]['correct'] += 1
                if excess is not None:
                    stats[key]['excess_vals'].append(excess)
                if label == '13w':
                    stats['by_grade'][grade_label]['correct'] += 1
                    if excess is not None:
                        stats['by_grade'][grade_label]['excess_vals'].append(excess)
            elif g == 'WRONG':
                stats[key]['wrong'] += 1
                if excess is not None:
                    stats[key]['excess_vals'].append(excess)
                if label == '13w':
                    stats['by_grade'][grade_label]['wrong'] += 1
                    if excess is not None:
                        stats['by_grade'][grade_label]['excess_vals'].append(excess)

    return stats


def print_stats(stats: dict):
    s13 = stats['summary_13w']
    s1  = stats['summary_1w']

    print(f"\n{'=' * 60}")
    print('FCAS VERIFICATION v2.0 — 三层交叉信号准确率')
    print(f"{'=' * 60}")
    print(f"  总扫描记录: {stats['total']}")

    # 13W 主指标
    actionable = s13['correct'] + s13['wrong']
    print(f"\n  ── 13W 主指标 (超额收益 vs CSI300) ──")
    print(f"  可验证: {actionable} | SKIP: {s13['skip']} | NO_DATA: {s13['no_data']} | PENDING: {s13['pending']}")
    if actionable > 0:
        acc = s13['correct'] / actionable * 100
        avg_excess = sum(s13['excess_vals']) / len(s13['excess_vals']) if s13['excess_vals'] else 0
        print(f"  准确率: {acc:.1f}% ({s13['correct']}/{actionable})")
        print(f"  平均超额收益: {avg_excess:+.2f}%")
        if acc >= 65:
            print(f"  ✓ 达到设计目标 (≥65%)")
        else:
            print(f"  ⚠ 低于设计目标 (65%)")
    else:
        print('  尚无可验证记录 (13W尚未到期 或 无价格数据)')

    # 按 cross3_grade 分组
    if any(v['correct'] + v['wrong'] > 0 for v in stats['by_grade'].values()):
        print(f"\n  ── 按 cross3_grade 细分 ──")
        print(f"  {'Grade':<15} {'N':>5} {'Correct':>8} {'Wrong':>6} {'Acc%':>7} {'AvgExcess':>10}")
        print(f"  {'-'*55}")
        for grade, g in sorted(stats['by_grade'].items(), key=lambda x: -(x[1]['correct'] + x[1]['wrong'])):
            act = g['correct'] + g['wrong']
            if act == 0:
                continue
            acc = g['correct'] / act * 100
            avg_ex = sum(g['excess_vals']) / len(g['excess_vals']) if g['excess_vals'] else 0
            print(f"  {grade:<15} {g['n']:>5} {g['correct']:>8} {g['wrong']:>6} {acc:>6.1f}% {avg_ex:>+9.2f}%")

    # 1W 参考（噪声）
    act1 = s1['correct'] + s1['wrong']
    print(f"\n  ── 1W 参考 (噪声级别，仅供参考) ──")
    if act1 > 0:
        acc1 = s1['correct'] / act1 * 100
        avg1 = sum(s1['excess_vals']) / len(s1['excess_vals']) if s1['excess_vals'] else 0
        print(f"  准确率: {acc1:.1f}% ({s1['correct']}/{act1}) | 平均超额: {avg1:+.2f}%")
    else:
        print('  无可验证 1W 记录')

    print(f"\n  注: CORRECT = 三层信号方向 × 实际超额收益 一致")
    print(f"      OUTPERFORM信号 → 超额>0 = CORRECT")
    print(f"      UNDERPERFORM信号 → 超额≤0 = CORRECT")


# ============================================================
# 主函数
# ============================================================

def main():
    print('=' * 60)
    print('FCAS AUTO-VERIFIER v2.0')
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print('=' * 60)

    history = load_history()
    if not history:
        print('No scan history found.')
        return

    print(f"\n  历史记录: {len(history)} 条")

    flat = flatten_history(history)
    print(f"  v4.0格式记录 (含cross3_grade): {len(flat)} 条")

    if not flat:
        print('  无 v4.0+ 格式记录 (需要含 cross3_grade 字段的扫描历史)')
        return

    existing_data = load_json_file(
        VERIFICATION_FILE,
        {'records': [], 'last_run': None},
        label='Verification',
        expected_type=dict,
    )
    existing_records = existing_data.get('records', [])

    all_records, newly_verified = run_verification(flat, existing_records)

    if newly_verified:
        print(f"\n  本次新验证: {len(newly_verified)} 条 (13W到期)")
        for nv in newly_verified:
            icon = '✅' if nv['grade'] == 'CORRECT' else '❌'
            print(f"  {icon} {nv['stock']} {nv['scan_date']} | {nv['grade_label']} ({nv['direction']})")
            print(f"       个股{nv['stock_ret']:+.2f}% - 基准{nv['bench_ret']:+.2f}% = 超额{nv['excess']:+.2f}% → {nv['grade']}")
    else:
        print('\n  无新验证 (13W均未到期 或 数据不足)')

    stats = compute_stats(all_records)
    print_stats(stats)

    # 保存
    existing_data['records'] = all_records
    existing_data['last_run'] = datetime.now().strftime('%Y-%m-%d %H:%M')
    save_json_file(VERIFICATION_FILE, existing_data)
    print(f"\n  结果已保存: {VERIFICATION_FILE}")

    # Telegram 推送
    if newly_verified:
        lines = ['FCAS Verification v2.0 — 13W超额收益', '']
        for nv in newly_verified:
            icon = '✅' if nv['grade'] == 'CORRECT' else '❌'
            lines.append(f"{icon} {nv['stock']} | {nv['grade_label']}")
            lines.append(f"   超额: {nv['excess']:+.2f}% → {nv['grade']}")
        s = compute_stats(all_records)['summary_13w']
        act = s['correct'] + s['wrong']
        if act > 0:
            lines.append(f"\n13W准确率: {s['correct']/act*100:.1f}% ({s['correct']}/{act})")
        send_telegram('\n'.join(lines))

    print('\n[Done]')


if __name__ == '__main__':
    main()
