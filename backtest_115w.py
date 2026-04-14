"""
FCAS 115-Week Backtest — Zero Hindsight Bias
天时层（奇门引擎）× 人事层（Claude API + Wind证据包）

Usage:
  # Smoke test: 1 week × 1 stock
  python3 backtest_115w.py --smoke
  
  # Full run: 115 weeks × 4 stocks
  python3 backtest_115w.py --full
  
  # Resume from last checkpoint
  python3 backtest_115w.py --full --resume

Requires: ANTHROPIC_API_KEY in environment or .env
"""

import json
import os
import sys
import time
import argparse
from datetime import datetime, timedelta

from contrarian_analysis_mcp import run_analysis, _analyze_intent

# ============================================================
# CONFIG
# ============================================================

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_DIR = os.path.join(DATA_DIR, "wind_data_json")
RESULTS_FILE = os.path.join(DATA_DIR, "backtest_115w_results.json")
LOG_FILE = os.path.join(DATA_DIR, "backtest_115w_log.txt")

STOCKS = [
    {"code": "688256.SH", "name": "寒武纪", "sector": "tech", "file_key": "688256_SH"},
    {"code": "600547.SH", "name": "山东黄金", "sector": "gold", "file_key": "600547_SH"},
    {"code": "601138.SH", "name": "工业富联", "sector": "tech", "file_key": "601138_SH"},
    {"code": "601899.SH", "name": "紫金矿业", "sector": "gold", "file_key": "601899_SH"},
]

MODEL = "claude-opus-4-20250514"
RESULT_SIGNAL_MODE = "intent_profit_v1"

POSITIVE_INTENTS = {"strongly_supported", "supported_with_resistance", "supported_but_weak", "contested"}
NEGATIVE_INTENTS = {"not_viable", "challenged"}
INTENT_TO_SIGNAL = {
    "strongly_supported": "STRONGLY_FAVORABLE",
    "supported_with_resistance": "FAVORABLE",
    "supported_but_weak": "FAVORABLE",
    "contested": "FAVORABLE",
    "possible_but_unsupported": "MIXED",
    "indirect_path": "MIXED",
    "dormant": "MIXED",
    "uncertain": "MIXED",
    "challenged": "CAUTIOUS",
    "not_viable": "ADVERSE",
}

# Quarterly report availability dates (conservative)
# Q1 available May 1, Q2 available Sep 1, Q3 available Nov 1, Q4 available next May 1
QUARTERLY_AVAILABILITY = {
    "Q1 FY2024": "2024-05-01",
    "Q2 FY2024": "2024-09-01",
    "Q3 FY2024": "2024-11-01",
    "Q4 FY2024": "2025-05-01",
    "Q1 FY2025": "2025-05-01",
    "Q2 FY2025": "2025-09-01",
    "Q3 FY2025": "2025-11-01",
    "Q4 FY2025": "2026-05-01",
}

# ============================================================
# DATA LOADING
# ============================================================

_cache = {}

def load_json(filename):
    if filename not in _cache:
        path = os.path.join(JSON_DIR, filename)
        with open(path, 'r', encoding='utf-8') as f:
            _cache[filename] = json.load(f)
    return _cache[filename]


def get_weekly_dates():
    """Get all unique weekly dates from stock data."""
    data = load_json("weekly_688256_SH.json")
    return [r["date"] for r in data["data"]]


def get_stock_weekly(file_key, before_date):
    """Get stock weekly data available BEFORE the judgment date.
    Rule: Week N judgment uses data up to week N-1 (last Friday close)."""
    data = load_json(f"weekly_{file_key}.json")
    return [r for r in data["data"] if r["date"] < before_date]


def get_macro_available(macro_file, judgment_date):
    """Get macro data available at judgment time.
    Conservative rule: monthly data delayed 1 full month.
    If judgment is in March, latest available = January data."""
    data = load_json(macro_file)
    
    jd = datetime.strptime(judgment_date, "%Y-%m-%d")
    first_of_month = datetime(jd.year, jd.month, 1)
    cutoff = first_of_month - timedelta(days=1)
    
    cutoff_str = cutoff.strftime("%Y-%m-%d")
    return [r for r in data["data"] if r["date"] <= cutoff_str]


def get_quarterly_available(file_key, judgment_date):
    """Get quarterly financial data available at judgment time.
    Uses QUARTERLY_AVAILABILITY map for disclosure lag."""
    data = load_json(f"quarterly_{file_key}.json")
    available = []
    for record in data["data"]:
        quarter = record.get("quarter", "")
        avail_date = QUARTERLY_AVAILABILITY.get(quarter)
        if avail_date and judgment_date >= avail_date:
            available.append(record)
    return available


def get_market_context(judgment_date):
    """Get market-wide context data."""
    context = {}
    
    # Shanghai gold
    try:
        gold = load_json("weekly_shanghai_gold.json")
        avail = [r for r in gold["data"] if r["date"] < judgment_date]
        if avail:
            context["shanghai_gold"] = avail[-1]["shanghai_gold_close"]
            context["shanghai_gold_date"] = avail[-1]["date"]
    except: pass
    
    # USD/CNY
    try:
        fx = load_json("weekly_usd_cny.json")
        avail = [r for r in fx["data"] if r["date"] < judgment_date]
        if avail:
            context["usd_cny"] = avail[-1]["usd_cny"]
    except: pass
    
    # Northbound
    try:
        nb = load_json("weekly_northbound.json")
        avail = [r for r in nb["data"] if r["date"] < judgment_date]
        if avail and len(avail) >= 4:
            recent4 = avail[-4:]
            context["northbound_4w_avg"] = round(sum(r["total_net"] for r in recent4 if r["total_net"]) / 4, 2)
    except: pass
    
    # Margin
    try:
        mg = load_json("weekly_margin_total.json")
        avail = [r for r in mg["data"] if r["date"] < judgment_date]
        if avail:
            context["margin_total_trillion"] = avail[-1]["margin_trillion"]
    except: pass
    
    return context


def get_future_price(file_key, from_date, weeks_ahead):
    """Get price N weeks after from_date for verification."""
    data = load_json(f"weekly_{file_key}.json")
    dates = [r["date"] for r in data["data"]]
    
    if from_date not in dates:
        # Find nearest date
        later = [d for d in dates if d >= from_date]
        if not later:
            return None, None
        from_date = later[0]
    
    idx = dates.index(from_date)
    target_idx = idx + weeks_ahead
    
    if target_idx >= len(data["data"]):
        return None, None
    
    return data["data"][target_idx]["close"], data["data"][target_idx]["date"]


# ============================================================
# EVIDENCE PACK BUILDER
# ============================================================

def build_evidence_pack(stock, judgment_date):
    """Build the evidence pack for Claude API, strictly using only
    data available BEFORE judgment_date."""
    
    file_key = stock["file_key"]
    weekly = get_stock_weekly(file_key, judgment_date)
    
    if len(weekly) < 2:
        return None  # Not enough data
    
    last4 = weekly[-4:] if len(weekly) >= 4 else weekly
    last12 = weekly[-12:] if len(weekly) >= 12 else weekly
    
    # 12-week trend
    trend_12w = f"{last12[0]['close']} → {last12[-1]['close']}"
    ret_12w = ((last12[-1]['close'] / last12[0]['close']) - 1) * 100 if last12[0]['close'] else 0
    
    # Weekly summary
    weekly_summary = "\n".join([
        f"  {r['date']}: 收盘={r['close']}  涨跌={r.get('weekly_return_pct','N/A')}%  "
        f"换手={r.get('weekly_turnover_pct','N/A')}%  融资余额={r.get('margin_balance','N/A')}亿  "
        f"北向持股={r.get('northbound_holding','N/A')}"
        for r in last4
    ])
    
    # Macro data
    macro_lines = []
    
    pmi_data = get_macro_available("macro_pmi_manufacturing.json", judgment_date)
    if pmi_data:
        latest = pmi_data[-1]
        prev = pmi_data[-2] if len(pmi_data) >= 2 else None
        macro_lines.append(f"制造业PMI: {latest['manufacturing_pmi']}（{latest['date']}）" + 
                          (f"  前值: {prev['manufacturing_pmi']}" if prev else ""))
    
    cpi_data = get_macro_available("macro_cpi_ppi.json", judgment_date)
    if cpi_data:
        latest = cpi_data[-1]
        macro_lines.append(f"CPI同比: {latest['cpi_yoy_pct']}%  PPI同比: {latest['ppi_yoy_pct']}%（{latest['date']}）")
    
    m2_data = get_macro_available("macro_m2_money_supply.json", judgment_date)
    if m2_data:
        macro_lines.append(f"M2同比: {m2_data[-1]['m2_yoy_pct']}%（{m2_data[-1]['date']}）")
    
    tsf_data = get_macro_available("macro_social_financing.json", judgment_date)
    if tsf_data:
        latest = tsf_data[-1]
        val = latest.get('tsf_monthly_100m_rmb')
        if val:
            macro_lines.append(f"社融当月: {val}亿（{latest['date']}）")
    
    # Sector-specific macro
    if stock["sector"] == "tech":
        semi = get_macro_available("macro_semiconductor_sales.json", judgment_date)
        if semi:
            latest = semi[-1]
            v = latest.get('semi_sales_monthly_yoy_pct') or latest.get('semi_sales_yoy_pct')
            if v:
                macro_lines.append(f"半导体销售同比: {v}%（{latest['date']}）")
        
        ic = get_macro_available("macro_ic_production.json", judgment_date)
        if ic:
            latest = ic[-1]
            v = latest.get('ic_production_monthly_yoy_pct') or latest.get('ic_production_cumulative_yoy_pct')
            if v:
                macro_lines.append(f"集成电路产量同比: {v}%（{latest['date']}）")
    
    elif stock["sector"] == "gold":
        gold_res = get_macro_available("macro_gold_reserves.json", judgment_date)
        if gold_res:
            latest = gold_res[-1]
            macro_lines.append(f"央行黄金储备: {latest.get('gold_reserve_total_oz')}万盎司  "
                             f"月变动: {latest.get('gold_reserve_change_oz')}（{latest['date']}）")
    
    macro_text = "\n".join(macro_lines) if macro_lines else "暂无可用宏观数据"
    
    # Market context
    mkt = get_market_context(judgment_date)
    mkt_lines = []
    if "shanghai_gold" in mkt:
        mkt_lines.append(f"上海金: {mkt['shanghai_gold']}")
    if "usd_cny" in mkt:
        mkt_lines.append(f"美元兑人民币: {mkt['usd_cny']}")
    if "northbound_4w_avg" in mkt:
        mkt_lines.append(f"北向资金近4周均值: {mkt['northbound_4w_avg']}亿/周")
    if "margin_total_trillion" in mkt:
        mkt_lines.append(f"两市融资余额: {mkt['margin_total_trillion']}万亿")
    mkt_text = "\n".join(mkt_lines) if mkt_lines else "N/A"
    
    # Quarterly financials
    quarterly = get_quarterly_available(file_key, judgment_date)
    if quarterly:
        latest_q = quarterly[-1]
        q_text = (
            f"最新已披露报告期: {latest_q.get('quarter','?')}\n"
            f"营收: {latest_q.get('revenue_100m','N/A')}亿  同比: {latest_q.get('revenue_yoy_pct','N/A')}%\n"
            f"净利润: {latest_q.get('net_profit_100m','N/A')}亿  同比: {latest_q.get('net_profit_yoy_pct','N/A')}%\n"
            f"毛利率: {latest_q.get('gross_margin_pct','N/A')}%\n"
            f"经营现金流: {latest_q.get('operating_cashflow_100m','N/A')}亿\n"
            f"研发费用: {latest_q.get('rd_expense_100m','N/A')}亿\n"
            f"资产负债率: {latest_q.get('debt_ratio_pct','N/A')}%\n"
            f"PE_TTM: {latest_q.get('pe_ttm','N/A')}倍  PB: {latest_q.get('pb','N/A')}倍\n"
            f"机构持股: {latest_q.get('institutional_holding_pct','N/A')}%"
        )
    else:
        q_text = "暂无已披露财务数据（财报尚未公布）"
    
    # Assemble prompt
    prompt = f"""你是一个结构分析框架的判断引擎。你只能基于下方提供的数据做判断。
你不知道{judgment_date}之后发生了什么。不要使用你自己的知识或对未来的预期。

当前判断日期: {judgment_date}
分析标的: {stock['name']}（{stock['code']}）

== 个股近期表现（截至{last4[-1]['date']}）==
{weekly_summary}
过去{len(last12)}周趋势: {trend_12w}（{ret_12w:+.1f}%）

== 宏观环境 ==
{macro_text}

== 市场环境 ==
{mkt_text}

== 公司财务 ==
{q_text}

== 判断标准 ==
C1 趋势方向: 该标的是否与当前宏观趋势一致？（看PMI、产业景气度、政策方向）
C2 能量状态: 当下能量是在积蓄还是消散？（看成交量变化、资金流向、换手率趋势）
C3 内部协调: 公司/行业内部运行是否协调？（看财务健康度、现金流、负债率）
C4 个人持续力: 投资者能否撑过波动期？（看近期波动幅度、流动性、融资余额变化）
C5 生态支撑: 周围生态系统是支撑还是排斥？（看产业链上下游、行业景气度、政策环境）
C6 根基深浅: 结构承载力和时间积累？（看基本面质量、估值水平、机构持仓、护城河）

请严格基于上述数据做判断。每条标准输出1（正面）或0（负面），附一句话理由。
只输出JSON，不要任何其他内容：
{{"c1":0或1,"c1_reason":"理由","c2":0或1,"c2_reason":"理由","c3":0或1,"c3_reason":"理由","c4":0或1,"c4_reason":"理由","c5":0或1,"c5_reason":"理由","c6":0或1,"c6_reason":"理由"}}"""

    return prompt


# ============================================================
# CLAUDE API CALLER
# ============================================================

def call_claude(prompt, max_retries=3):
    """Call Claude API for C1-C6 judgment."""
    import anthropic
    
    client = anthropic.Anthropic()
    
    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )
            
            text = response.content[0].text.strip()
            
            # Parse JSON - handle markdown fences
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            
            result = json.loads(text)
            
            # Validate
            for key in ["c1", "c2", "c3", "c4", "c5", "c6"]:
                if key not in result:
                    raise ValueError(f"Missing key: {key}")
                if result[key] not in (0, 1):
                    result[key] = int(result[key])
            
            return result
            
        except json.JSONDecodeError as e:
            log(f"  JSON parse error (attempt {attempt+1}): {e}")
            log(f"  Raw response: {text[:200]}")
            if attempt < max_retries - 1:
                time.sleep(5)
        except Exception as e:
            log(f"  API error (attempt {attempt+1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(10)
    
    return None


# ============================================================
# FRAMEWORK CALCULATION
# ============================================================

def compute_framework_signal(stock, judgment_date, c_values):
    """Run the legacy FCAS framework on C1-C6 and map profit intent to 5-level signal."""
    domain = f"{stock['code']} @ {judgment_date}"
    analysis = run_analysis(domain, {f"c{i}": c_values[f"c{i}"] for i in range(1, 7)})
    config = analysis["configuration"]
    intent = _analyze_intent(config, "seek_profit")
    intent_assessment = intent["overall"]
    signal = INTENT_TO_SIGNAL.get(intent_assessment, "MIXED")

    return {
        "binary": analysis["binary_code"],
        "signal": signal,
        "positive_bits": sum(c_values[f"c{i}"] for i in range(1, 7)),
        "analysis": analysis,
        "intent": intent,
        "intent_assessment": intent_assessment,
    }


# ============================================================
# LOGGING
# ============================================================

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + "\n")


# ============================================================
# MAIN BACKTEST LOOP
# ============================================================

def load_results():
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"meta": {}, "results": []}


def save_results(data):
    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_completed(results, date, stock_code):
    """Check if this date×stock combination is already done."""
    for r in results["results"]:
        if r["date"] == date and r["stock_code"] == stock_code:
            return True
    return False


def run_backtest(smoke=False, resume=False):
    """Run the 115-week backtest."""
    
    all_dates = get_weekly_dates()
    
    if smoke:
        # Just test 2 weeks × 1 stock
        test_dates = all_dates[10:12]  # ~week 10-11, around March 2024
        test_stocks = STOCKS[:1]  # Just 寒武纪
        log(f"=== SMOKE TEST: {len(test_dates)} weeks × {len(test_stocks)} stocks ===")
    else:
        test_dates = all_dates
        test_stocks = STOCKS
        log(f"=== FULL BACKTEST: {len(test_dates)} weeks × {len(test_stocks)} stocks = {len(test_dates)*len(test_stocks)} calls ===")
    
    # Load existing results for resume
    output = load_results() if resume else {"meta": {}, "results": []}
    if resume and output["results"]:
        existing_mode = output.get("meta", {}).get("signal_mode")
        if existing_mode != RESULT_SIGNAL_MODE:
            legacy_mode = existing_mode or "legacy_bitcount"
            log(f"ERROR: Existing results use signal mode '{legacy_mode}', not '{RESULT_SIGNAL_MODE}'.")
            log("       Resume would mix incompatible methodologies. Re-run without --resume or move the old results file.")
            return
    output["meta"]["model"] = MODEL
    output["meta"]["signal_mode"] = RESULT_SIGNAL_MODE
    output["meta"]["started"] = datetime.now().isoformat()
    output["meta"]["total_weeks"] = len(test_dates)
    output["meta"]["stocks"] = [s["code"] for s in test_stocks]
    
    completed = 0
    skipped = 0
    errors = 0
    
    for week_idx, judgment_date in enumerate(test_dates):
        log(f"\n{'='*60}")
        log(f"Week {week_idx+1}/{len(test_dates)}: {judgment_date}")
        
        for stock in test_stocks:
            # Skip if already done (resume mode)
            if resume and is_completed(output, judgment_date, stock["code"]):
                skipped += 1
                continue
            
            log(f"  {stock['name']} ({stock['code']})...")
            
            # Build evidence pack
            prompt = build_evidence_pack(stock, judgment_date)
            if prompt is None:
                log(f"  SKIP: insufficient data")
                continue
            
            # Call Claude API
            c_result = call_claude(prompt)
            if c_result is None:
                log(f"  ERROR: API call failed after retries")
                errors += 1
                continue
            
            # Compute signal
            framework = compute_framework_signal(stock, judgment_date, c_result)
            binary = framework["binary"]
            signal = framework["signal"]
            ones = framework["positive_bits"]
            analysis = framework["analysis"]
            intent = framework["intent"]
            
            # Get current price (judgment date close)
            stock_data = load_json(f"weekly_{stock['file_key']}.json")
            current_price = None
            for r in stock_data["data"]:
                if r["date"] == judgment_date:
                    current_price = r["close"]
                    break
            
            # Get future prices for verification
            price_1w, date_1w = get_future_price(stock["file_key"], judgment_date, 1)
            price_4w, date_4w = get_future_price(stock["file_key"], judgment_date, 4)
            price_13w, date_13w = get_future_price(stock["file_key"], judgment_date, 13)
            
            def calc_return(future, current):
                if future and current and current > 0:
                    return round(((future / current) - 1) * 100, 2)
                return None
            
            record = {
                "date": judgment_date,
                "stock_code": stock["code"],
                "stock_name": stock["name"],
                "sector": stock["sector"],
                "c1": c_result["c1"], "c1_reason": c_result.get("c1_reason", ""),
                "c2": c_result["c2"], "c2_reason": c_result.get("c2_reason", ""),
                "c3": c_result["c3"], "c3_reason": c_result.get("c3_reason", ""),
                "c4": c_result["c4"], "c4_reason": c_result.get("c4_reason", ""),
                "c5": c_result["c5"], "c5_reason": c_result.get("c5_reason", ""),
                "c6": c_result["c6"], "c6_reason": c_result.get("c6_reason", ""),
                "binary": binary,
                "signal": signal,
                "signal_mode": RESULT_SIGNAL_MODE,
                "positive_bits": ones,
                "configuration": analysis["configuration"]["configuration_name"],
                "configuration_zh": analysis["configuration"]["configuration_zh"],
                "evolution_stage": analysis["configuration"]["evolution_stage"],
                "intent_assessment": framework["intent_assessment"],
                "intent_guidance": intent["guidance"],
                "mislocation": analysis["mislocation"]["type"],
                "momentum": analysis["cross_layer"]["momentum"],
                "substance": analysis["cross_layer"]["substance"],
                "current_price": current_price,
                "return_1w": calc_return(price_1w, current_price),
                "return_4w": calc_return(price_4w, current_price),
                "return_13w": calc_return(price_13w, current_price),
            }
            
            output["results"].append(record)
            completed += 1
            
            log(f"  → Binary={binary} Signal={signal} Intent={framework['intent_assessment']} ({ones}/6)")
            log(f"    C1={c_result['c1']}({c_result.get('c1_reason','')[:30]})")
            log(f"    C2={c_result['c2']}({c_result.get('c2_reason','')[:30]})")
            log(f"    Price={current_price} → 1W:{calc_return(price_1w, current_price)}% 4W:{calc_return(price_4w, current_price)}% 13W:{calc_return(price_13w, current_price)}%")
            
            # Save after each stock (checkpoint)
            save_results(output)
            
            # Rate limiting
            time.sleep(1)
        
        # Save after each week
        save_results(output)
    
    # Final summary
    output["meta"]["completed"] = datetime.now().isoformat()
    output["meta"]["total_judgments"] = completed
    output["meta"]["skipped"] = skipped
    output["meta"]["errors"] = errors
    save_results(output)
    
    log(f"\n{'='*60}")
    log(f"BACKTEST COMPLETE")
    log(f"  Completed: {completed}")
    log(f"  Skipped: {skipped}")
    log(f"  Errors: {errors}")
    
    # Quick stats
    if output["results"]:
        analyze_results(output)


def analyze_results(output):
    """Compute summary statistics."""
    results = output["results"]
    
    log(f"\n{'='*60}")
    log(f"RESULTS ANALYSIS ({len(results)} judgments)")
    
    # Group by signal
    by_signal = {}
    for r in results:
        sig = r["signal"]
        by_signal.setdefault(sig, []).append(r)
    
    for sig in sorted(by_signal.keys()):
        records = by_signal[sig]
        
        ret_1w = [r["return_1w"] for r in records if r["return_1w"] is not None]
        ret_4w = [r["return_4w"] for r in records if r["return_4w"] is not None]
        ret_13w = [r["return_13w"] for r in records if r["return_13w"] is not None]
        
        log(f"\n  {sig} ({len(records)} judgments):")
        if ret_1w:
            log(f"    1W avg return: {sum(ret_1w)/len(ret_1w):+.2f}%  (win rate: {sum(1 for r in ret_1w if r>0)/len(ret_1w)*100:.0f}%)")
        if ret_4w:
            log(f"    4W avg return: {sum(ret_4w)/len(ret_4w):+.2f}%  (win rate: {sum(1 for r in ret_4w if r>0)/len(ret_4w)*100:.0f}%)")
        if ret_13w:
            log(f"   13W avg return: {sum(ret_13w)/len(ret_13w):+.2f}%  (win rate: {sum(1 for r in ret_13w if r>0)/len(ret_13w)*100:.0f}%)")
    
    # Per stock
    log(f"\n  BY STOCK:")
    for stock in STOCKS:
        stock_results = [r for r in results if r["stock_code"] == stock["code"]]
        if not stock_results:
            continue
        signals = {}
        for r in stock_results:
            signals[r["signal"]] = signals.get(r["signal"], 0) + 1
        log(f"    {stock['name']}: {len(stock_results)} judgments, signals: {signals}")
    
    # Key metric: FAVORABLE avg return vs ADVERSE avg return
    fav = [r for r in results if r["signal"] in ("STRONGLY_FAVORABLE", "FAVORABLE")]
    adv = [r for r in results if r["signal"] in ("ADVERSE", "CAUTIOUS")]
    
    fav_13w = [r["return_13w"] for r in fav if r["return_13w"] is not None]
    adv_13w = [r["return_13w"] for r in adv if r["return_13w"] is not None]
    
    if fav_13w and adv_13w:
        log(f"\n  KEY METRIC — FAVORABLE vs ADVERSE 13W returns:")
        log(f"    FAVORABLE avg: {sum(fav_13w)/len(fav_13w):+.2f}% ({len(fav_13w)} samples)")
        log(f"    ADVERSE   avg: {sum(adv_13w)/len(adv_13w):+.2f}% ({len(adv_13w)} samples)")
        log(f"    Spread: {sum(fav_13w)/len(fav_13w) - sum(adv_13w)/len(adv_13w):+.2f}%")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FCAS 115-Week Backtest")
    parser.add_argument("--smoke", action="store_true", help="Smoke test: 2 weeks × 1 stock")
    parser.add_argument("--full", action="store_true", help="Full run: 115 weeks × 4 stocks")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--analyze", action="store_true", help="Only analyze existing results")
    args = parser.parse_args()
    
    if args.analyze:
        output = load_results()
        if output["results"]:
            analyze_results(output)
        else:
            print("No results to analyze.")
    elif args.smoke:
        run_backtest(smoke=True, resume=False)
    elif args.full:
        run_backtest(smoke=False, resume=args.resume)
    else:
        print("Usage: python3 backtest_115w.py --smoke | --full [--resume] | --analyze")
        print("\nRequires ANTHROPIC_API_KEY environment variable")
