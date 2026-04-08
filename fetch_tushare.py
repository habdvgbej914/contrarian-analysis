"""
fetch_tushare.py — Evidence pack builder for FCAS人事层

数据来源: data/json/ 本地周频文件（不依赖Tushare API权限）
缓存: 同一天同一标的只构建一次
"""

import os
import json
from datetime import datetime, timedelta

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(_SCRIPT_DIR, 'data', 'json')

# stock_code → 文件前缀
CODE_TO_ALIAS = {
    '000651.SZ': 'gree',
    '000063.SZ': 'zte',
    '000858.SZ': 'wuliangye',
    '600276.SH': 'hengrui',
    '600036.SH': 'cmb',
    '601318.SH': 'ping_an',
    '601857.SH': 'petrochina',
    '601012.SH': 'longi',
    '601899.SH': None,   # 紫金矿业：无本地数据
    '600547.SH': None,   # 山东黄金：无本地数据
}

STOCK_SECTOR = {
    '000651.SZ': 'manufacturing / consumer appliances',
    '000063.SZ': 'technology / telecom equipment',
    '000858.SZ': 'consumer / spirits',
    '600276.SH': 'healthcare / pharma',
    '600036.SH': 'financials / banking',
    '601318.SH': 'financials / insurance',
    '601857.SH': 'energy / oil & gas',
    '601012.SH': 'energy / solar manufacturing',
    '601899.SH': 'materials / mining',
    '600547.SH': 'materials / gold mining',
}

# 宏观文件 → 显示标签
MACRO_FILES = {
    'csi300_index':     'CSI 300 Index',
    'sse_index':        'SSE Composite Index',
    'china_10y_bond_yield': '10Y Bond Yield (%)',
    'margin_balance':   'Margin Balance (trillion CNY)',
    'mfg_pmi':          'Manufacturing PMI',
    'usdcny':           'USD/CNY Mid Rate',
}

# 内存缓存: (stock_code, date_str) → evidence_pack str
_CACHE = {}


def _load_json(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def _get_weekly_history(stock_code, n=12):
    """获取最近n周的周频数据，返回list（升序，最新在最后）"""
    alias = CODE_TO_ALIAS.get(stock_code)
    if not alias:
        return []
    data = _load_json(f'{alias}_weekly.json')
    if not data:
        return []
    return data[-n:]


def _get_quarterly(stock_code):
    """获取最近一期季报数据"""
    alias = CODE_TO_ALIAS.get(stock_code)
    if not alias:
        return None
    data = _load_json(f'{alias}_quarterly.json')
    if not data:
        return None
    return data[-1]


def _get_macro_recent(key, n=4):
    """获取宏观指标最近n期"""
    data = _load_json(f'{key}.json')
    if not data:
        return []
    return data[-n:]


def build_evidence_pack(stock_code: str, stock_name: str, now: datetime) -> dict:
    """
    构建evidence_pack供人事层Opus判断C1-C6。

    返回 dict:
        {'text': str, 'error': None}  —— 成功
        {'text': None, 'error': str}  —— 失败
    """
    date_key = now.strftime('%Y-%m-%d')
    cache_key = (stock_code, date_key)
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    alias = CODE_TO_ALIAS.get(stock_code)
    if alias is None:
        result = {'text': None, 'error': f'no local data for {stock_code}'}
        _CACHE[cache_key] = result
        return result

    sector = STOCK_SECTOR.get(stock_code, 'unknown')

    # Detect latest data date for lag annotation
    history_raw = _get_weekly_history(stock_code, n=1)
    latest_data_date = history_raw[0]['date'] if history_raw else None
    lag_lines = []
    if latest_data_date:
        from datetime import date as _date
        try:
            d0 = _date.fromisoformat(latest_data_date)
            d1 = now.date() if hasattr(now, 'date') else now
            days_lag = (d1 - d0).days
            lag_lines.append(
                f"⚠ Data as of: {latest_data_date} ({days_lag} days ago)."
                f" Recent price action not reflected."
            )
            if days_lag > 14:
                lag_lines.append(
                    "WARNING: Data lag exceeds 2 weeks."
                    " C1 (trend) and C2 (energy) assessments may be stale."
                )
        except Exception:
            lag_lines.append(f"⚠ Data as of: {latest_data_date} (lag unknown).")
    else:
        lag_lines.append("⚠ Data as of: unknown.")

    lines = []
    lines.append(f"=== EVIDENCE PACK: {stock_name} ({stock_code}) | As of {date_key} ===")
    lines.append(f"Sector: {sector}")
    lines.extend(lag_lines)
    lines.append("")

    # --- Section 1: Stock Weekly Data (last 12 weeks) ---
    lines.append("--- STOCK WEEKLY DATA (last 12 weeks) ---")
    history = _get_weekly_history(stock_code, n=12)
    if history:
        header = f"{'Date':<12} {'Close':>8} {'Ret%':>8} {'Vol(M)':>9} {'TO(B)':>8} {'TO%':>7} {'Margin(B)':>11}"
        lines.append(header)
        for r in history:
            vol_m = r['volume'] / 1e6 if r.get('volume') else None
            vol_s = f"{vol_m:.1f}" if vol_m is not None else "N/A"
            to_s  = f"{r['turnover_billion']:.2f}" if r.get('turnover_billion') is not None else "N/A"
            top_s = f"{r['turnover_pct']:.2f}" if r.get('turnover_pct') is not None else "N/A"
            ret_s = f"{r['weekly_return_pct']:+.2f}" if r.get('weekly_return_pct') is not None else "N/A"
            mg_s  = f"{r['margin_balance_billion']:.2f}" if r.get('margin_balance_billion') is not None else "N/A"
            close_s = str(r['close']) if r.get('close') is not None else "N/A"
            lines.append(f"{r['date']:<12} {close_s:>8} {ret_s:>8} {vol_s:>9} {to_s:>8} {top_s:>7} {mg_s:>11}")

        # Derived metrics
        closes = [r['close'] for r in history if r.get('close') is not None]
        if len(closes) >= 2:
            ret_12w = (closes[-1] - closes[0]) / closes[0] * 100
            lines.append(f"\n12-week cumulative return: {ret_12w:+.2f}%")
        if len(closes) >= 5:
            ret_4w = (closes[-1] - closes[-5]) / closes[-5] * 100
            lines.append(f"4-week cumulative return: {ret_4w:+.2f}%")

        volumes = [r['volume'] for r in history if r.get('volume') is not None]
        if len(volumes) >= 4:
            avg_recent = sum(volumes[-4:]) / 4
            avg_prior  = sum(volumes[:-4]) / max(len(volumes) - 4, 1)
            if avg_prior > 0:
                vol_chg = (avg_recent - avg_prior) / avg_prior * 100
                lines.append(f"Volume trend (recent 4w vs prior): {vol_chg:+.1f}%")

        margins = [(r['date'], r['margin_balance_billion']) for r in history
                   if r.get('margin_balance_billion') is not None]
        if len(margins) >= 2:
            mg_chg = margins[-1][1] - margins[0][1]
            lines.append(f"Margin balance change (12w): {mg_chg:+.2f} billion CNY")
    else:
        lines.append("No stock weekly data available.")

    lines.append("")

    # --- Section 2: Market Context ---
    lines.append("--- MARKET CONTEXT ---")
    for key, label in MACRO_FILES.items():
        recs = _get_macro_recent(key, n=5)
        if not recs:
            continue
        # 最新值
        latest = recs[-1]
        val_field = None
        for f in ['close', 'yield_pct', 'balance_trillion', 'pmi_pct', 'mid_rate']:
            if f in latest and latest[f] is not None:
                val_field = f
                break
        if val_field is None:
            continue
        val = latest[val_field]
        lines.append(f"{label}: {val} (as of {latest['date']})")
        if len(recs) >= 2:
            prev_val = recs[-2].get(val_field)
            if prev_val and val and prev_val != 0:
                chg_pct = (val - prev_val) / abs(prev_val) * 100
                lines.append(f"  4-week change: {chg_pct:+.2f}%")

    lines.append("")

    # --- Section 3: Quarterly Financials ---
    lines.append("--- QUARTERLY FINANCIALS (most recent available) ---")
    fin = _get_quarterly(stock_code)
    if fin:
        lines.append(f"Quarter: {fin.get('date', 'N/A')}")
        for key, label in [
            ('revenue_billion',          'Revenue (billion CNY)'),
            ('net_profit_billion',       'Net Profit (billion CNY)'),
            ('operating_cashflow_billion', 'Operating Cash Flow (billion CNY)'),
            ('revenue_yoy_pct',          'Revenue YoY Growth (%)'),
            ('net_profit_yoy_pct',       'Net Profit YoY Growth (%)'),
            ('gross_margin_pct',         'Gross Margin (%)'),
            ('debt_ratio_pct',           'Debt Ratio (%)'),
        ]:
            val = fin.get(key)
            if val is not None:
                lines.append(f"  {label}: {val}")
    else:
        lines.append("No quarterly financials available.")

    lines.append("")

    text = "\n".join(lines)
    result = {'text': text, 'error': None}
    _CACHE[cache_key] = result
    return result
