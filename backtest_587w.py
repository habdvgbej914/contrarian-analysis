#!/usr/bin/env python3
"""
FCAS 587周×8标的完整回测脚本
backtest_587w.py

基于现有backtest_115w架构扩展:
- 8标的 × 587周 = 4,696次 Claude Opus API调用
- 完整证据包: 周度行情 + 市场指标 + 宏观月度 + 季度财务
- 断点续传: 每完成1条立即保存
- 数据可用性规则: 周度T-1, 月度滞后1月, 季度按法定披露时限

Usage:
    python3 backtest_587w.py                    # 正常运行
    python3 backtest_587w.py --resume            # 断点续传
    python3 backtest_587w.py --dry-run           # 测试模式(不调API)
    python3 backtest_587w.py --dry-run --weeks 3 # 只跑3周测试
    python3 backtest_587w.py --stock 000651.SZ   # 只跑单只股票
"""

import json
import os
import sys
import time
import signal
import argparse
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

# ============================================================
# AUTO-LOAD .env (so nohup background processes get the API key)
# ============================================================
_env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_env_file):
    with open(_env_file) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _val = _line.split("=", 1)
                os.environ.setdefault(_key.strip(), _val.strip())

# ============================================================
# CONFIGURATION
# ============================================================

# 8标的定义 (含行业分类, 用于sector-specific宏观数据选择)
STOCKS = [
    {
        "code": "000651.SZ", "name": "格力电器", "sector": "manufacturing",
        "qimen_stem": "己", "qimen_plate": "天盘",
        "macro_keys": ["pmi_mfg", "ppi_yoy", "cpi_yoy", "m2_yoy", "social_financing"],
        "index_keys": ["sse_index", "csi300", "margin_total", "cn10y_yield", "usdcny"],
    },
    {
        "code": "000063.SZ", "name": "中兴通讯", "sector": "technology",
        "qimen_stem": "戊", "qimen_plate": "天盘",
        "macro_keys": ["pmi_mfg", "semiconductor_yoy", "ic_production_yoy", "m2_yoy", "social_financing"],
        "index_keys": ["sse_index", "csi300", "sw_electronics", "sw_computer", "star50", "usdcny"],
    },
    {
        "code": "000858.SZ", "name": "五粮液", "sector": "consumer",
        "qimen_stem": "壬", "qimen_plate": "天盘",
        "macro_keys": ["cpi_yoy", "ppi_yoy", "m2_yoy", "social_financing", "pmi_non_mfg"],
        "index_keys": ["sse_index", "csi300", "margin_total", "cn10y_yield", "northbound_flow"],
    },
    {
        "code": "600276.SH", "name": "恒瑞医药", "sector": "healthcare",
        "qimen_stem": "乙(月干)", "qimen_plate": "地盘",
        "macro_keys": ["cpi_yoy", "m2_yoy", "social_financing", "pmi_non_mfg", "pmi_mfg"],
        "index_keys": ["sse_index", "csi300", "margin_total", "northbound_flow", "cn10y_yield"],
    },
    {
        "code": "600036.SH", "name": "招商银行", "sector": "finance",
        "qimen_stem": "丁", "qimen_plate": "天盘",
        "macro_keys": ["m2_yoy", "social_financing", "cpi_yoy", "ppi_yoy", "pmi_mfg"],
        "index_keys": ["sse_index", "csi300", "cn10y_yield", "margin_total", "usdcny"],
    },
    {
        "code": "601318.SH", "name": "中国平安", "sector": "finance",
        "qimen_stem": "辛", "qimen_plate": "天盘",
        "macro_keys": ["m2_yoy", "social_financing", "cpi_yoy", "ppi_yoy", "pmi_non_mfg"],
        "index_keys": ["sse_index", "csi300", "cn10y_yield", "margin_total", "northbound_flow"],
    },
    {
        "code": "601857.SH", "name": "中国石油", "sector": "energy",
        "qimen_stem": "庚(月干)", "qimen_plate": "天盘",
        "macro_keys": ["ppi_yoy", "pmi_mfg", "cpi_yoy", "m2_yoy", "social_financing"],
        "index_keys": ["sse_index", "csi300", "comex_gold", "usdcny", "shanghai_gold"],
    },
    {
        "code": "601012.SH", "name": "隆基绿能", "sector": "new_energy",
        "qimen_stem": "癸(月干)", "qimen_plate": "地盘",
        "macro_keys": ["pmi_mfg", "ppi_yoy", "semiconductor_yoy", "m2_yoy", "social_financing"],
        "index_keys": ["sse_index", "csi300", "sw_electronics", "star50", "usdcny"],
    },
]

# 季度财务披露时间映射 (Q1→4/30, Q2→8/31, Q3→10/31, Q4→次年4/30)
# 实际可用日期 = 披露截止日 + 1天 (保守估计)
QUARTERLY_DISCLOSURE = {
    1: (4, 30),   # Q1 results available by April 30
    2: (8, 31),   # Q2 results available by August 31
    3: (10, 31),  # Q3 results available by October 31
    4: (4, 30),   # Q4 results available by next year April 30
}

# API配置
MODEL = "claude-sonnet-4-20250514"  # 用sonnet降低成本, 也可改为opus
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds
RATE_LIMIT_DELAY = 1.2  # seconds between calls

# 文件路径
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
RESULTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backtest_587w_results.json")
CHECKPOINT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backtest_587w_checkpoint.json")

# ============================================================
# DATA LOADING
# ============================================================

class DataStore:
    """Loads and indexes all JSON data for fast lookup."""

    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.stocks_weekly = {}    # code -> [{date, close, ...}]
        self.market_indicators = {} # key -> [{date, value}]
        self.macro_monthly = {}     # key -> [{date, value}]
        self.quarterly_fin = {}     # code -> [{quarter, revenue_billion, ...}]

        # Date-indexed lookups (built after loading)
        self._stock_by_date = {}   # code -> {date: record}
        self._indicator_by_date = {} # key -> {date: value}
        self._macro_by_month = {}  # key -> {YYYY-MM: value}
        self._fin_by_quarter = {}  # code -> {quarter_str: record}

        self._load_all()
        self._build_indexes()

    def _load_all(self):
        with open(os.path.join(self.data_dir, "stocks_weekly.json"), "r") as f:
            self.stocks_weekly = json.load(f)
        with open(os.path.join(self.data_dir, "market_indicators.json"), "r") as f:
            self.market_indicators = json.load(f)
        with open(os.path.join(self.data_dir, "macro_monthly.json"), "r") as f:
            self.macro_monthly = json.load(f)
        with open(os.path.join(self.data_dir, "quarterly_financials.json"), "r") as f:
            self.quarterly_fin = json.load(f)

        print(f"[DataStore] Loaded: {len(self.stocks_weekly)} stocks, "
              f"{len(self.market_indicators)} indicators, "
              f"{len(self.macro_monthly)} macro series, "
              f"{len(self.quarterly_fin)} financial series")

    def _build_indexes(self):
        # Stock data by date
        for code, records in self.stocks_weekly.items():
            self._stock_by_date[code] = {r["date"]: r for r in records if r.get("date")}

        # Indicators by date
        for key, records in self.market_indicators.items():
            self._indicator_by_date[key] = {r["date"]: r["value"] for r in records if r.get("date")}

        # Macro by month (YYYY-MM)
        for key, records in self.macro_monthly.items():
            self._macro_by_month[key] = {}
            for r in records:
                if r.get("date"):
                    month_key = r["date"][:7]  # YYYY-MM
                    self._macro_by_month[key][month_key] = r["value"]

        # Financials by quarter
        for code, records in self.quarterly_fin.items():
            self._fin_by_quarter[code] = {r["quarter"]: r for r in records if r.get("quarter")}

    def get_stock_dates(self, code):
        """Get sorted list of all dates for a stock."""
        return sorted(self._stock_by_date.get(code, {}).keys())

    def get_stock_record(self, code, date):
        """Get stock record for exact date."""
        return self._stock_by_date.get(code, {}).get(date)

    def get_stock_history(self, code, end_date, weeks=12):
        """Get stock history up to end_date (inclusive), last N weeks."""
        all_dates = self.get_stock_dates(code)
        idx = None
        for i, d in enumerate(all_dates):
            if d <= end_date:
                idx = i
        if idx is None:
            return []
        start = max(0, idx - weeks + 1)
        return [self._stock_by_date[code][all_dates[i]] for i in range(start, idx + 1)]

    def get_indicator_value(self, key, date):
        """Get indicator value for date, or nearest prior date."""
        idx = self._indicator_by_date.get(key, {})
        if date in idx:
            return idx[date]
        # Find nearest prior
        sorted_dates = sorted(idx.keys())
        for d in reversed(sorted_dates):
            if d <= date:
                return idx[d]
        return None

    def get_indicator_history(self, key, end_date, n=12):
        """Get last N indicator values up to end_date."""
        idx = self._indicator_by_date.get(key, {})
        sorted_dates = sorted(d for d in idx.keys() if d <= end_date)
        return [(d, idx[d]) for d in sorted_dates[-n:]]

    def get_macro_value(self, key, target_date, lag_months=1):
        """Get macro value available at target_date (with publication lag)."""
        dt = datetime.strptime(target_date, "%Y-%m-%d")
        # Go back lag_months to find available data
        avail_dt = dt - timedelta(days=lag_months * 31)
        avail_month = avail_dt.strftime("%Y-%m")

        idx = self._macro_by_month.get(key, {})
        # Find the most recent available month
        sorted_months = sorted(m for m in idx.keys() if m <= avail_month)
        if sorted_months:
            return sorted_months[-1], idx[sorted_months[-1]]
        return None, None

    def get_macro_history(self, key, target_date, n=6, lag_months=1):
        """Get last N months of macro data available at target_date."""
        dt = datetime.strptime(target_date, "%Y-%m-%d")
        avail_dt = dt - timedelta(days=lag_months * 31)
        avail_month = avail_dt.strftime("%Y-%m")

        idx = self._macro_by_month.get(key, {})
        sorted_months = sorted(m for m in idx.keys() if m <= avail_month)
        return [(m, idx[m]) for m in sorted_months[-n:]]

    def get_latest_quarterly(self, code, target_date):
        """Get most recent quarterly financials available at target_date."""
        dt = datetime.strptime(target_date, "%Y-%m-%d")
        records = self.quarterly_fin.get(code, [])

        available = []
        for rec in records:
            q = rec.get("quarter", "")
            if not q:
                continue
            # Parse quarter string like "Q1 FY2015"
            try:
                parts = q.replace("FY", "").strip().split()
                q_num = int(parts[0].replace("Q", ""))
                year = int(parts[1])
            except:
                continue

            # Determine disclosure date
            disc_month, disc_day = QUARTERLY_DISCLOSURE[q_num]
            disc_year = year + 1 if q_num == 4 else year
            disc_date = datetime(disc_year, disc_month, disc_day)

            if disc_date <= dt:
                available.append((disc_date, rec))

        if available:
            available.sort(key=lambda x: x[0])
            return available[-1][1]  # Most recent available
        return None

    def compute_forward_returns(self, code, date):
        """Compute 1w, 4w, 13w forward returns from date."""
        all_dates = self.get_stock_dates(code)
        try:
            idx = all_dates.index(date)
        except ValueError:
            return {}

        current = self._stock_by_date[code][date]
        if current["close"] is None:
            return {}

        returns = {}
        for label, offset in [("1w", 1), ("4w", 4), ("13w", 13)]:
            future_idx = idx + offset
            if future_idx < len(all_dates):
                future = self._stock_by_date[code][all_dates[future_idx]]
                if future["close"] is not None:
                    ret = (future["close"] - current["close"]) / current["close"] * 100
                    returns[label] = round(ret, 4)
        return returns


# ============================================================
# EVIDENCE PACK BUILDER
# ============================================================

def build_evidence_pack(data: DataStore, stock_config: dict, target_date: str,
                        prev_judgment: dict = None) -> str:
    """
    构建证据包 - 供Claude API判断C1-C6.

    数据可用性规则:
    - 周度数据: T-1 (用target_date当周及之前的数据)
    - 月度宏观: 滞后1个月 (如3月数据4月中下旬才发布)
    - 季度财务: 按法定披露时限
    """
    code = stock_config["code"]
    name = stock_config["name"]
    sector = stock_config["sector"]

    lines = []
    lines.append(f"=== EVIDENCE PACK: {name} ({code}) | Week ending {target_date} ===")
    lines.append(f"Sector: {sector}")
    lines.append("")

    # --- Section 1: Stock Weekly Data (12-week history) ---
    lines.append("--- STOCK WEEKLY DATA (last 12 weeks) ---")
    history = data.get_stock_history(code, target_date, weeks=12)
    if history:
        lines.append(f"{'Date':<12} {'Close':>10} {'Return%':>10} {'Volume':>14} {'Turnover':>10} {'TurnoverRate':>12} {'MarginBal':>10} {'Northbound':>14}")
        for r in history:
            def _fmt(val, fmt_str):
                if val is None:
                    return "N/A"
                return format(val, fmt_str)
            ret_s = _fmt(r['weekly_return'], '.2f')
            vol_s = _fmt(r['volume'], '.0f')
            to_s = _fmt(r['turnover_billion'], '.2f')
            tr_s = _fmt(r['turnover_rate'], '.2f')
            mb_s = _fmt(r['margin_balance'], '.1f')
            nb_s = _fmt(r['northbound_shares'], '.0f')
            close_s = str(r['close']) if r['close'] is not None else "N/A"
            lines.append(
                f"{r['date']:<12} {close_s:>10} {ret_s:>10} {vol_s:>14} "
                f"{to_s:>10} {tr_s:>12} {mb_s:>10} {nb_s:>14}"
            )

        # Compute derived metrics
        closes = [r["close"] for r in history if r["close"] is not None]
        if len(closes) >= 2:
            ret_12w = (closes[-1] - closes[0]) / closes[0] * 100
            lines.append(f"\n12-week cumulative return: {ret_12w:.2f}%")
        if len(closes) >= 5:
            ret_4w = (closes[-1] - closes[-5]) / closes[-5] * 100
            lines.append(f"4-week cumulative return: {ret_4w:.2f}%")

        # Volume trend
        volumes = [r["volume"] for r in history if r["volume"] is not None]
        if len(volumes) >= 4:
            avg_recent = sum(volumes[-4:]) / 4
            avg_prior = sum(volumes[:-4]) / max(len(volumes) - 4, 1)
            if avg_prior > 0:
                vol_change = (avg_recent - avg_prior) / avg_prior * 100
                lines.append(f"Volume trend (recent 4w vs prior): {vol_change:+.1f}%")

        # Margin balance trend
        margins = [(r["date"], r["margin_balance"]) for r in history if r["margin_balance"] is not None]
        if len(margins) >= 2:
            mg_change = margins[-1][1] - margins[0][1]
            lines.append(f"Margin balance change (12w): {mg_change:+.2f} billion CNY")
    else:
        lines.append("No stock data available for this period.")

    lines.append("")

    # --- Section 2: Market Indicators ---
    lines.append("--- MARKET CONTEXT ---")
    for idx_key in stock_config["index_keys"]:
        hist = data.get_indicator_history(idx_key, target_date, n=12)
        if hist:
            current_val = hist[-1][1]
            label = idx_key.replace("_", " ").title()
            lines.append(f"{label}: {current_val}")
            if len(hist) >= 5:
                val_4w = hist[-5][1] if hist[-5][1] else None
                if val_4w and current_val:
                    chg = (current_val - val_4w) / val_4w * 100
                    lines.append(f"  4-week change: {chg:+.2f}%")
            if len(hist) >= 12:
                val_12w = hist[0][1] if hist[0][1] else None
                if val_12w and current_val:
                    chg = (current_val - val_12w) / val_12w * 100
                    lines.append(f"  12-week change: {chg:+.2f}%")

    lines.append("")

    # --- Section 3: Macro Data (with lag) ---
    lines.append("--- MACROECONOMIC DATA (with publication lag) ---")
    for macro_key in stock_config["macro_keys"]:
        hist = data.get_macro_history(macro_key, target_date, n=6, lag_months=1)
        if hist:
            label = macro_key.replace("_", " ").upper()
            recent = hist[-1]
            lines.append(f"{label}: {recent[1]} (as of {recent[0]})")
            if len(hist) >= 3:
                trend = [h[1] for h in hist[-3:] if h[1] is not None]
                if len(trend) >= 2:
                    direction = "rising" if trend[-1] > trend[0] else "falling" if trend[-1] < trend[0] else "stable"
                    lines.append(f"  3-month trend: {direction} ({trend[0]} → {trend[-1]})")

    lines.append("")

    # --- Section 4: Quarterly Financials ---
    lines.append("--- QUARTERLY FINANCIALS (most recent available) ---")
    fin = data.get_latest_quarterly(code, target_date)
    if fin:
        lines.append(f"Quarter: {fin.get('quarter', 'N/A')}")
        for key, label in [
            ("revenue_billion", "Revenue (billion CNY)"),
            ("net_profit_billion", "Net Profit (billion CNY)"),
            ("operating_cashflow_billion", "Operating Cash Flow (billion CNY)"),
            ("revenue_yoy_pct", "Revenue YoY Growth (%)"),
            ("profit_yoy_pct", "Net Profit YoY Growth (%)"),
            ("gross_margin_pct", "Gross Margin (%)"),
            ("debt_ratio_pct", "Debt Ratio (%)"),
            ("rd_ratio_pct", "R&D Ratio (%)"),
            ("pe_ratio", "P/E Ratio"),
            ("pb_ratio", "P/B Ratio"),
            ("institutional_pct", "Institutional Holdings (%)"),
        ]:
            val = fin.get(key)
            if val is not None:
                lines.append(f"  {label}: {val}")
    else:
        lines.append("No quarterly financials available for this period.")

    lines.append("")

    # --- Section 5: Previous Judgment (Continuity) ---
    if prev_judgment:
        lines.append("--- PREVIOUS WEEK'S ASSESSMENT (for continuity) ---")
        lines.append(f"Previous date: {prev_judgment.get('date', 'N/A')}")
        lines.append(f"Previous signal: {prev_judgment.get('signal', 'N/A')}")
        lines.append(f"Previous binary: {prev_judgment.get('binary', 'N/A')}")
        prev_criteria = prev_judgment.get("criteria", {})
        for c in ["C1", "C2", "C3", "C4", "C5", "C6"]:
            val = prev_criteria.get(c, {})
            bit = val.get("bit", "?")
            reason = val.get("reason", "N/A")
            lines.append(f"  {c}: {'1 (MET)' if bit == 1 else '0 (NOT MET)'} — {reason}")
        lines.append("")
        lines.append("CONTINUITY RULE: Each criterion should remain stable unless there is "
                     "clear structural evidence of change in the current week's data. "
                     "A flip (0→1 or 1→0) requires explicit justification.")

    return "\n".join(lines)


# ============================================================
# CLAUDE API JUDGMENT
# ============================================================

SYSTEM_PROMPT = """You are an FCAS (Force Configuration Analysis System) structural analyst.

Your task: Given an evidence pack of market data, assess 6 binary criteria (C1-C6) for the specified entity.

## Criteria Definitions

- C1 TREND DIRECTION: Is the entity aligned with the macro structural trend of its era? (1=aligned, 0=misaligned)
- C2 ENERGY STATE: Is current energy accumulating or dissipating? (1=accumulating, 0=dissipating)
- C3 INTERNAL HARMONY: Is the internal system coordinating smoothly? (1=harmonious, 0=discordant)
- C4 PERSONAL ENDURANCE: Can it survive a hibernation/dormancy cycle? (1=can endure, 0=fragile)
- C5 ECOSYSTEM SUPPORT: Is the surrounding ecosystem supporting or rejecting it? (1=supporting, 0=rejecting)
- C6 FOUNDATION DEPTH: Does it have deep structural load-bearing capacity and time-accumulated foundation? (1=deep, 0=shallow)

## Rules

1. Each criterion is BINARY: 1 (MET) or 0 (NOT MET). No middle ground.
2. Base judgments ONLY on the evidence provided. Do not use external knowledge.
3. If previous week's assessment is provided, maintain continuity unless there is CLEAR STRUCTURAL EVIDENCE of change.
4. A flip (0→1 or 1→0) requires explicit justification citing specific data points.
5. This is STATE DIAGNOSIS, not price prediction. You are assessing structural condition, not forecasting direction.

## Output Format (STRICT JSON)

{
  "C1": {"bit": 0 or 1, "reason": "brief justification citing specific data"},
  "C2": {"bit": 0 or 1, "reason": "brief justification citing specific data"},
  "C3": {"bit": 0 or 1, "reason": "brief justification citing specific data"},
  "C4": {"bit": 0 or 1, "reason": "brief justification citing specific data"},
  "C5": {"bit": 0 or 1, "reason": "brief justification citing specific data"},
  "C6": {"bit": 0 or 1, "reason": "brief justification citing specific data"},
  "signal": "STRONGLY_FAVORABLE|FAVORABLE|MIXED|CAUTIOUS|ADVERSE",
  "summary": "one-sentence structural state summary"
}

Signal mapping:
- STRONGLY_FAVORABLE: 5-6 criteria met (binary ≥ 101111)
- FAVORABLE: 4 criteria met
- MIXED: 3 criteria met
- CAUTIOUS: 2 criteria met
- ADVERSE: 0-1 criteria met

Output ONLY valid JSON. No markdown, no explanation outside the JSON."""


API_TIMEOUT = 90  # Hard timeout per API call in seconds

class APITimeoutError(Exception):
    pass

def _timeout_handler(signum, frame):
    raise APITimeoutError(f"API call timed out after {API_TIMEOUT}s")

def call_claude_api(evidence_pack: str, dry_run: bool = False) -> dict:
    """Call Claude API with evidence pack, return parsed judgment.
    Uses signal.SIGALRM as hard timeout to prevent infinite hangs."""

    if dry_run:
        # Return synthetic judgment for testing
        import random
        bits = [random.choice([0, 1]) for _ in range(6)]
        total = sum(bits)
        signal_map = {0: "ADVERSE", 1: "ADVERSE", 2: "CAUTIOUS", 3: "MIXED", 4: "FAVORABLE", 5: "STRONGLY_FAVORABLE", 6: "STRONGLY_FAVORABLE"}
        return {
            "C1": {"bit": bits[0], "reason": "[DRY RUN] synthetic"},
            "C2": {"bit": bits[1], "reason": "[DRY RUN] synthetic"},
            "C3": {"bit": bits[2], "reason": "[DRY RUN] synthetic"},
            "C4": {"bit": bits[3], "reason": "[DRY RUN] synthetic"},
            "C5": {"bit": bits[4], "reason": "[DRY RUN] synthetic"},
            "C6": {"bit": bits[5], "reason": "[DRY RUN] synthetic"},
            "signal": signal_map[total],
            "summary": f"[DRY RUN] {total}/6 criteria met",
        }

    import anthropic
    import httpx
    client = anthropic.Anthropic(timeout=httpx.Timeout(90.0, connect=10.0))

    for attempt in range(MAX_RETRIES):
        try:
            # Set hard timeout via signal (Linux/Mac only)
            old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(API_TIMEOUT)
            try:
                response = client.messages.create(
                    model=MODEL,
                    max_tokens=1024,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": evidence_pack}],
                )
            finally:
                signal.alarm(0)  # Cancel alarm
                signal.signal(signal.SIGALRM, old_handler)  # Restore handler

            text = response.content[0].text.strip()
            # Remove markdown code fence if present
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()

            # Extract JSON object even if there's extra text after it
            # Find the first { and match to its closing }
            start = text.find("{")
            if start == -1:
                raise json.JSONDecodeError("No JSON object found", text, 0)
            depth = 0
            end = start
            in_string = False
            escape_next = False
            for i in range(start, len(text)):
                ch = text[i]
                if escape_next:
                    escape_next = False
                    continue
                if ch == '\\' and in_string:
                    escape_next = True
                    continue
                if ch == '"' and not escape_next:
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            text = text[start:end]

            result = json.loads(text)

            # Validate and normalize structure
            for c in ["C1", "C2", "C3", "C4", "C5", "C6"]:
                if c not in result:
                    raise ValueError(f"Missing {c} in response")
                if "bit" not in result[c]:
                    raise ValueError(f"Missing bit in {c}")
                # Normalize bit to int (Sonnet sometimes returns "0"/"1" strings)
                bit = result[c]["bit"]
                if isinstance(bit, str):
                    bit = int(bit)
                if bit not in [0, 1]:
                    raise ValueError(f"Invalid bit in {c}: {result[c]['bit']}")
                result[c]["bit"] = bit
                # Ensure reason exists
                if "reason" not in result[c]:
                    result[c]["reason"] = "no reason provided"
            if "signal" not in result:
                # Auto-compute signal from bits
                total = sum(result[c]["bit"] for c in ["C1","C2","C3","C4","C5","C6"])
                signal_map = {0:"ADVERSE",1:"ADVERSE",2:"CAUTIOUS",3:"MIXED",4:"FAVORABLE",5:"STRONGLY_FAVORABLE",6:"STRONGLY_FAVORABLE"}
                result["signal"] = signal_map[total]
            if "summary" not in result:
                result["summary"] = ""

            return result

        except json.JSONDecodeError as e:
            print(f"  [WARN] JSON parse error (attempt {attempt+1}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
        except ValueError as e:
            print(f"  [WARN] Validation error (attempt {attempt+1}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
        except anthropic.RateLimitError:
            wait = RETRY_DELAY * (attempt + 2)
            print(f"  [WARN] Rate limited, waiting {wait}s...")
            time.sleep(wait)
        except APITimeoutError as e:
            print(f"\n  [TIMEOUT] Hard timeout (attempt {attempt+1}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
        except Exception as e:
            print(f"  [ERROR] API call failed (attempt {attempt+1}): {type(e).__name__}: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)

    return None


# ============================================================
# BINARY ENCODING
# ============================================================

def compute_binary(judgment: dict) -> str:
    """Compute 6-bit binary string from C1-C6 judgment.
    Bit order (MSB→LSB): C2→C1→C4→C3→C6→C5
    """
    bits = [
        judgment["C2"]["bit"],  # bit 6 (MSB)
        judgment["C1"]["bit"],  # bit 5
        judgment["C4"]["bit"],  # bit 4
        judgment["C3"]["bit"],  # bit 3
        judgment["C6"]["bit"],  # bit 2
        judgment["C5"]["bit"],  # bit 1 (LSB)
    ]
    return "".join(str(b) for b in bits)


# ============================================================
# CHECKPOINT / RESUME
# ============================================================

def load_checkpoint():
    """Load checkpoint file if exists."""
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r") as f:
            return json.load(f)
    return {"completed": {}, "last_judgments": {}}


def save_checkpoint(checkpoint):
    """Save checkpoint atomically."""
    tmp = CHECKPOINT_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(checkpoint, f, ensure_ascii=False)
    os.replace(tmp, CHECKPOINT_FILE)


def load_results():
    """Load existing results file."""
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, "r") as f:
            return json.load(f)
    return []


def save_results(results):
    """Save results atomically."""
    tmp = RESULTS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    os.replace(tmp, RESULTS_FILE)


# ============================================================
# MAIN BACKTEST LOOP
# ============================================================

def run_backtest(args):
    print("="*70)
    print("FCAS 587w × 8 STOCKS BACKTEST")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE API'}")
    print(f"Model: {MODEL}")
    print(f"Resume: {args.resume}")
    print("="*70)

    # Load data
    data = DataStore(DATA_DIR)

    # Filter stocks if specified
    stocks = STOCKS
    if args.stock:
        stocks = [s for s in STOCKS if s["code"] == args.stock]
        if not stocks:
            print(f"[ERROR] Stock {args.stock} not found in STOCKS list")
            sys.exit(1)

    # Get all unique dates (from first stock, they should all be the same)
    all_dates = data.get_stock_dates(stocks[0]["code"])

    # Skip first week (no prior data for continuity)
    scan_dates = all_dates[1:]

    if args.weeks:
        scan_dates = scan_dates[:args.weeks]

    total_tasks = len(scan_dates) * len(stocks)
    print(f"\nScan dates: {scan_dates[0]} ~ {scan_dates[-1]} ({len(scan_dates)} weeks)")
    print(f"Stocks: {len(stocks)}")
    print(f"Total API calls: {total_tasks}")

    if not args.dry_run:
        est_cost_sonnet = total_tasks * 0.015  # ~$0.015 per sonnet call
        est_cost_opus = total_tasks * 0.075    # ~$0.075 per opus call
        print(f"Estimated cost (Sonnet): ~${est_cost_sonnet:.0f}")
        print(f"Estimated cost (Opus):   ~${est_cost_opus:.0f}")
        est_time = total_tasks * RATE_LIMIT_DELAY / 3600
        print(f"Estimated time: ~{est_time:.1f} hours")

    # Load checkpoint
    checkpoint = load_checkpoint() if args.resume else {"completed": {}, "last_judgments": {}}
    results = load_results() if args.resume else []

    completed_count = len(checkpoint["completed"])
    print(f"\nCheckpoint: {completed_count} already completed")

    # Main loop
    done = completed_count
    start_time = time.time()

    for date_idx, date in enumerate(scan_dates):
        for stock_config in stocks:
            code = stock_config["code"]
            task_key = f"{code}_{date}"

            # Skip if already done
            if task_key in checkpoint["completed"]:
                continue

            done += 1
            elapsed = time.time() - start_time
            rate = done / max(elapsed, 1) * 3600
            remaining = (total_tasks - done) / max(rate / 3600, 0.001)

            print(f"[{done}/{total_tasks}] {code} {stock_config['name']} @ {date} "
                  f"({rate:.0f}/hr, ~{remaining:.1f}h left)", flush=True)

            # Get previous judgment for continuity
            prev_key = f"{code}_prev"
            prev_judgment = checkpoint["last_judgments"].get(prev_key)

            # Build evidence pack
            evidence = build_evidence_pack(data, stock_config, date, prev_judgment)

            # Call API
            judgment = call_claude_api(evidence, dry_run=args.dry_run)

            if judgment is None:
                print(f"\n  [SKIP] Failed to get judgment for {code} @ {date}")
                continue

            # Compute binary and forward returns
            binary = compute_binary(judgment)
            forward_returns = data.compute_forward_returns(code, date)

            # Get current price
            current_record = data.get_stock_record(code, date)
            current_price = current_record["close"] if current_record else None

            # Build result record
            record = {
                "stock_code": code,
                "stock_name": stock_config["name"],
                "sector": stock_config["sector"],
                "date": date,
                "binary": binary,
                "signal": judgment["signal"],
                "summary": judgment.get("summary", ""),
                "criteria": {
                    "C1": judgment["C1"],
                    "C2": judgment["C2"],
                    "C3": judgment["C3"],
                    "C4": judgment["C4"],
                    "C5": judgment["C5"],
                    "C6": judgment["C6"],
                },
                "price": current_price,
                "forward_returns": forward_returns,
            }

            results.append(record)

            # Update checkpoint
            checkpoint["completed"][task_key] = True
            checkpoint["last_judgments"][prev_key] = {
                "date": date,
                "signal": judgment["signal"],
                "binary": binary,
                "criteria": {
                    c: {"bit": judgment[c]["bit"], "reason": judgment[c]["reason"]}
                    for c in ["C1", "C2", "C3", "C4", "C5", "C6"]
                },
            }

            # Save after each record
            save_results(results)
            save_checkpoint(checkpoint)

            # Rate limiting
            if not args.dry_run:
                time.sleep(RATE_LIMIT_DELAY)

    print(f"\n\n{'='*70}")
    print(f"BACKTEST COMPLETE")
    print(f"{'='*70}")
    print(f"Total records: {len(results)}")
    print(f"Time: {(time.time() - start_time)/60:.1f} minutes")
    print(f"Results saved to: {RESULTS_FILE}")

    # Print signal distribution
    from collections import Counter
    signal_dist = Counter(r["signal"] for r in results)
    print(f"\nSignal distribution:")
    for sig in ["STRONGLY_FAVORABLE", "FAVORABLE", "MIXED", "CAUTIOUS", "ADVERSE"]:
        count = signal_dist.get(sig, 0)
        pct = count / len(results) * 100 if results else 0
        print(f"  {sig}: {count} ({pct:.1f}%)")

    # Print per-stock summary
    print(f"\nPer-stock summary:")
    for stock_config in stocks:
        code = stock_config["code"]
        stock_results = [r for r in results if r["stock_code"] == code]
        if stock_results:
            bits_met = sum(
                sum(r["criteria"][c]["bit"] for c in ["C1","C2","C3","C4","C5","C6"])
                for r in stock_results
            ) / len(stock_results)
            print(f"  {code} {stock_config['name']}: {len(stock_results)} weeks, avg bits met: {bits_met:.2f}/6")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FCAS 587w Backtest")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--dry-run", action="store_true", help="Test mode without API calls")
    parser.add_argument("--weeks", type=int, help="Limit to N weeks (for testing)")
    parser.add_argument("--stock", type=str, help="Run single stock (e.g., 000651.SZ)")
    parser.add_argument("--model", type=str, help="Override model (e.g., claude-opus-4-20250514)")
    args = parser.parse_args()

    if args.model:
        MODEL = args.model

    run_backtest(args)
