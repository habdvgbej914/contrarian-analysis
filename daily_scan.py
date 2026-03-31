"""
FCAS Daily Scanner v0.4 / 气象分析每日扫描
Uses Claude API with web search to analyze markets daily.
Intent-based structural guidance with judgment continuity.

v0.4 Changes:
- Injects previous scan context into prompt (judgment continuity)
- Requires structural justification for any criterion flip
- Tracks flips per scan for stability analysis
"""

import os
import json
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SCAN_HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "daily_scan_history.json")

TICKERS = {
    "GLD": {
        "name": "Gold / 黄金",
        "search_query": "gold price today market analysis outlook"
    },
    "SLV": {
        "name": "Silver / 白银",
        "search_query": "silver price today market analysis industrial demand"
    },
    "SPY": {
        "name": "S&P 500 / 标普500",
        "search_query": "S&P 500 today market analysis sentiment outlook"
    },
    "QQQ": {
        "name": "Nasdaq 100 / 纳斯达克100",
        "search_query": "Nasdaq 100 today tech stocks analysis outlook"
    }
}

# ============================================================
# Criteria labels (for readable context injection)
# ============================================================
CRITERIA_LABELS = {
    "c1": "Trend Alignment / 趋势方向",
    "c2": "Energy State / 能量状态",
    "c3": "Internal Harmony / 内部协调",
    "c4": "Personal Sustainability / 个人持续力",
    "c5": "Ecosystem Support / 生态支撑",
    "c6": "Foundation Depth / 根基深浅"
}

# ============================================================
# Previous context extraction
# ============================================================
def get_previous_context(ticker, history):
    """Find the most recent scan record for this ticker and build context string."""
    # Search backwards for the most recent record of this ticker
    for record in reversed(history):
        if record.get("ticker") == ticker:
            return record
    return None


def build_previous_context_block(prev_record):
    """Build a prompt block describing the previous judgment for context."""
    if prev_record is None:
        return ""

    date = prev_record.get("date", "unknown")
    time = prev_record.get("time", "")
    price = prev_record.get("price_estimate", "N/A")
    binary = prev_record.get("binary_code", "N/A")
    reasoning = prev_record.get("reasoning", {})

    lines = []
    lines.append(f"=== YOUR PREVIOUS JUDGMENT ({date} {time}) ===")
    lines.append(f"Price at that time: {price}")
    lines.append(f"Binary code: {binary}")
    lines.append("")

    for c_id in ["c1", "c2", "c3", "c4", "c5", "c6"]:
        label = CRITERIA_LABELS.get(c_id, c_id)
        c_data = reasoning.get(c_id, {})
        judgment_val = c_data.get("judgment")
        # Handle both bool and int
        if isinstance(judgment_val, bool):
            j_str = "TRUE (1)" if judgment_val else "FALSE (0)"
        elif isinstance(judgment_val, int):
            j_str = "TRUE (1)" if judgment_val == 1 else "FALSE (0)"
        else:
            j_str = str(judgment_val)

        origin = c_data.get("origin", "")
        lines.append(f"{c_id.upper()} [{label}]: {j_str}")
        if origin:
            lines.append(f"  Key reason: {origin}")

    lines.append("")
    summary = prev_record.get("summary", "")
    if summary:
        lines.append(f"Previous summary: {summary}")

    return "\n".join(lines)


# ============================================================
# Prompt templates
# ============================================================
ANALYSIS_PROMPT_FIRST = """You are a structural analyst using the Force Configuration Analysis System (FCAS). Today is {date}.

You just searched for current market information about {ticker} ({name}).

This is your FIRST analysis of {ticker}. No previous judgment exists.

Based on the search results, make 6 binary judgments for the FCAS Framework:

C1 - Trend Alignment (趋势方向): Is {ticker} aligned with the era's macro trend? (true/false)
C2 - Energy State (能量状态): Is energy accumulating in this domain right now? (true/false)
C3 - Internal Harmony (内部协调): Is the system internally coordinated and functioning smoothly? (true/false)
C4 - Personal Sustainability (个人持续力): Can a retail investor with 12-month horizon sustain this position? (true/false)
C5 - Ecosystem Support (生态支撑): Is the surrounding ecosystem supporting this? (true/false)
C6 - Foundation Depth (根基深浅): Is the foundation deep? (true/false)

For each criterion, briefly assess across 5 dimensions:
- origin (root cause / fundamental driver)
- visibility (market attention / ecosystem nurturing)
- growth (expansion / root deepening)
- constraint (barriers / ecosystem forces)
- foundation (infrastructure / embeddedness)

RESPOND ONLY IN THIS EXACT JSON FORMAT, nothing else:
{json_template}"""

ANALYSIS_PROMPT_CONTINUING = """You are a structural analyst using the Force Configuration Analysis System (FCAS). Today is {date}.

You just searched for current market information about {ticker} ({name}).

{previous_context}

=== JUDGMENT CONTINUITY RULES ===
You are NOT judging from scratch. You have a previous judgment above. Follow these rules:

1. DEFAULT TO MAINTAINING your previous judgment for each criterion. Structural conditions (trend direction, ecosystem support, foundation depth) do not change in hours or days — they change over weeks or months.

2. TO FLIP any criterion from your previous judgment, you MUST find STRUCTURAL EVIDENCE of change — not just a single news article or short-term price movement. A structural change means the underlying driver identified in your previous "origin" assessment has fundamentally shifted.

3. C5 (Ecosystem Support) and C6 (Foundation Depth) should almost NEVER flip between consecutive scans. These are slow-moving structural conditions. Only flip if you find evidence of a major regime change (e.g., new regulation, ecosystem collapse, fundamental infrastructure shift).

4. C1 (Trend) and C2 (Energy) may flip more frequently, but still require evidence beyond a single data point. A trend reversal needs multiple confirming signals, not one bad day.

5. If you DO flip a criterion, your "origin" field for that criterion MUST explicitly state what changed since the previous scan. Start with "CHANGED: ..." to make flips traceable.

6. If nothing structural has changed, it is CORRECT to return the same judgments. Consistency is a feature, not a bug.
=== END RULES ===

Based on the search results AND your previous judgment context, make your updated 6 binary judgments:

C1 - Trend Alignment (趋势方向): Is {ticker} aligned with the era's macro trend? (true/false)
C2 - Energy State (能量状态): Is energy accumulating in this domain right now? (true/false)
C3 - Internal Harmony (内部协调): Is the system internally coordinated and functioning smoothly? (true/false)
C4 - Personal Sustainability (个人持续力): Can a retail investor with 12-month horizon sustain this position? (true/false)
C5 - Ecosystem Support (生态支撑): Is the surrounding ecosystem supporting this? (true/false)
C6 - Foundation Depth (根基深浅): Is the foundation deep? (true/false)

For each criterion, briefly assess across 5 dimensions:
- origin (root cause / fundamental driver — if changed from previous, start with "CHANGED: ")
- visibility (market attention / ecosystem nurturing)
- growth (expansion / root deepening)
- constraint (barriers / ecosystem forces)
- foundation (infrastructure / embeddedness)

RESPOND ONLY IN THIS EXACT JSON FORMAT, nothing else:
{json_template}"""

JSON_TEMPLATE = """{{
    "ticker": "{ticker}",
    "price_estimate": "current approximate price as string",
    "c1_judgment": true or false,
    "c1_origin": "brief assessment",
    "c1_visibility": "brief assessment",
    "c1_growth": "brief assessment",
    "c1_constraint": "brief assessment",
    "c1_foundation": "brief assessment",
    "c2_judgment": true or false,
    "c2_origin": "brief assessment",
    "c2_visibility": "brief assessment",
    "c2_growth": "brief assessment",
    "c2_constraint": "brief assessment",
    "c2_foundation": "brief assessment",
    "c3_judgment": true or false,
    "c3_origin": "brief assessment",
    "c3_visibility": "brief assessment",
    "c3_growth": "brief assessment",
    "c3_constraint": "brief assessment",
    "c3_foundation": "brief assessment",
    "c4_judgment": true or false,
    "c4_origin": "brief assessment",
    "c4_visibility": "brief assessment",
    "c4_growth": "brief assessment",
    "c4_constraint": "brief assessment",
    "c4_foundation": "brief assessment",
    "c5_judgment": true or false,
    "c5_origin": "brief assessment",
    "c5_visibility": "brief assessment",
    "c5_growth": "brief assessment",
    "c5_constraint": "brief assessment",
    "c5_foundation": "brief assessment",
    "c6_judgment": true or false,
    "c6_origin": "brief assessment",
    "c6_visibility": "brief assessment",
    "c6_growth": "brief assessment",
    "c6_constraint": "brief assessment",
    "c6_foundation": "brief assessment",
    "summary": "2-3 sentence overall assessment in business language"
}}"""


# ============================================================
# Flip detection
# ============================================================
def detect_flips(current_analysis, prev_record):
    """Compare current judgment with previous and return list of flipped criteria."""
    if prev_record is None:
        return []

    prev_reasoning = prev_record.get("reasoning", {})
    flips = []

    for c_id in ["c1", "c2", "c3", "c4", "c5", "c6"]:
        current_val = current_analysis.get(f"{c_id}_judgment")
        prev_data = prev_reasoning.get(c_id, {})
        prev_val = prev_data.get("judgment")

        # Normalize to bool for comparison
        if isinstance(current_val, int):
            current_bool = current_val == 1
        else:
            current_bool = bool(current_val)

        if isinstance(prev_val, int):
            prev_bool = prev_val == 1
        elif isinstance(prev_val, bool):
            prev_bool = prev_val
        else:
            continue  # can't compare, skip

        if current_bool != prev_bool:
            flips.append({
                "criterion": c_id,
                "label": CRITERIA_LABELS.get(c_id, c_id),
                "previous": prev_bool,
                "current": current_bool,
                "reason": current_analysis.get(f"{c_id}_origin", "no reason provided")
            })

    return flips


# ============================================================
# Claude API call
# ============================================================
def call_claude_with_search(ticker_info, previous_context_block):
    """Call Claude API with web search to analyze a ticker"""
    ticker = ticker_info["ticker"]
    name = ticker_info["name"]
    query = ticker_info["search_query"]
    date = datetime.now().strftime("%Y-%m-%d")

    json_template = JSON_TEMPLATE.format(ticker=ticker)

    if previous_context_block:
        prompt = ANALYSIS_PROMPT_CONTINUING.format(
            ticker=ticker, name=name, date=date,
            previous_context=previous_context_block,
            json_template=json_template
        )
    else:
        prompt = ANALYSIS_PROMPT_FIRST.format(
            ticker=ticker, name=name, date=date,
            json_template=json_template
        )

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 2000,
                "tools": [
                    {
                        "type": "web_search_20250305",
                        "name": "web_search"
                    }
                ],
                "messages": [
                    {
                        "role": "user",
                        "content": f"Search for: {query}\n\nThen analyze using this framework:\n\n{prompt}"
                    }
                ]
            },
            timeout=120
        )

        data = response.json()

        full_text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                full_text += block["text"]

        json_start = full_text.find("{")
        json_end = full_text.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            json_str = full_text[json_start:json_end]
            return json.loads(json_str)
        else:
            print(f"  Warning: Could not parse JSON for {ticker}")
            print(f"  Raw response: {full_text[:500]}")
            return None

    except Exception as e:
        print(f"  Error analyzing {ticker}: {e}")
        return None


def run_framework(analysis_data):
    """Run the v0.3 framework with intent query"""
    from contrarian_analysis_mcp import run_analysis, _analyze_intent

    states = {
        "c1": int(analysis_data["c1_judgment"]),
        "c2": int(analysis_data["c2_judgment"]),
        "c3": int(analysis_data["c3_judgment"]),
        "c4": int(analysis_data["c4_judgment"]),
        "c5": int(analysis_data["c5_judgment"]),
        "c6": int(analysis_data["c6_judgment"])
    }

    result = run_analysis(
        f"{analysis_data['ticker']} @ {datetime.now().strftime('%Y-%m-%d')}",
        states
    )

    config = result["configuration"]

    # Intent analysis — default seek_profit for financial tickers
    intent_result = _analyze_intent(config, "seek_profit")

    position_judgments = {}
    for p in config["positions"]:
        position_judgments[p["criterion"]] = {
            "judgment": p["judgment"],
            "judgment_label": p["judgment_label"],
            "direction": p["direction"],
            "vitality": p["vitality"],
            "lifecycle_label": p["lifecycle_label"],
            "relation_label": p["relation_label"],
        }

    return {
        "binary_code": result["binary_code"],
        "configuration_name": config["configuration_name"],
        "configuration_zh": config["configuration_zh"],
        "evolution_stage": config["evolution_stage"],
        "overall_judgment": config["overall_judgment"],
        "overall_judgment_label": config["overall_judgment_label"],
        "judgment_distribution": config["judgment_distribution"],
        "mislocation": result["mislocation"]["type"],
        "mislocation_desc": result["mislocation"]["description"],
        "position_judgments": position_judgments,
        "intent": intent_result,
        "states": states
    }


def send_telegram(message):
    """Send message to Telegram"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("  Telegram not configured, skipping notification.")
        return

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            print("  Telegram notification sent.")
        else:
            print(f"  Telegram send failed: {response.status_code}")
    except Exception as e:
        print(f"  Telegram error: {e}")


def load_scan_history():
    try:
        with open(SCAN_HISTORY_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_scan_history(history):
    with open(SCAN_HISTORY_FILE, "w") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def main():
    date_str = datetime.now().strftime("%Y-%m-%d")
    time_str = datetime.now().strftime("%H:%M")

    print(f"{'=' * 70}")
    print(f"FCAS DAILY SCAN v0.4 / 气象分析每日扫描 (Judgment Continuity)")
    print(f"Date: {date_str} {time_str}")
    print(f"{'=' * 70}")

    if not ANTHROPIC_API_KEY:
        print("ERROR: ANTHROPIC_API_KEY not set in .env")
        return

    history = load_scan_history()
    today_results = []
    telegram_lines = [f"📊 *Structural Scan v0.4*", f"📅 {date_str} {time_str}", ""]

    for ticker, info in TICKERS.items():
        print(f"\n{'─' * 50}")
        print(f"Analyzing {ticker} ({info['name']})...")

        # === v0.4: Get previous context ===
        prev_record = get_previous_context(ticker, history)
        if prev_record:
            prev_date = prev_record.get("date", "?")
            prev_time = prev_record.get("time", "")
            prev_binary = prev_record.get("binary_code", "?")
            print(f"  Previous scan: {prev_date} {prev_time} | Binary: {prev_binary}")
            context_block = build_previous_context_block(prev_record)
        else:
            print(f"  No previous scan found — first analysis.")
            context_block = ""

        analysis = call_claude_with_search({"ticker": ticker, **info}, context_block)

        if analysis is None:
            print(f"  FAILED: Could not get analysis for {ticker}")
            telegram_lines.append(f"❌ {ticker}: Analysis failed")
            continue

        # === v0.4: Detect flips ===
        flips = detect_flips(analysis, prev_record)

        framework_result = run_framework(analysis)

        record = {
            "date": date_str,
            "time": time_str,
            "ticker": ticker,
            "name": info["name"],
            "price_estimate": analysis.get("price_estimate", "N/A"),
            "binary_code": framework_result["binary_code"],
            "configuration": framework_result["configuration_name"],
            "configuration_zh": framework_result["configuration_zh"],
            "evolution": framework_result["evolution_stage"],
            "judgment": framework_result["overall_judgment"],
            "judgment_label": framework_result["overall_judgment_label"],
            "judgment_distribution": framework_result["judgment_distribution"],
            "mislocation": framework_result["mislocation"],
            "states": framework_result["states"],
            "position_judgments": framework_result["position_judgments"],
            "intent": framework_result["intent"],
            "summary": analysis.get("summary", ""),
            "reasoning": {
                c_id: {
                    "judgment": analysis.get(f"{c_id}_judgment", None),
                    "origin": analysis.get(f"{c_id}_origin", ""),
                    "visibility": analysis.get(f"{c_id}_visibility", ""),
                    "growth": analysis.get(f"{c_id}_growth", ""),
                    "constraint": analysis.get(f"{c_id}_constraint", ""),
                    "foundation": analysis.get(f"{c_id}_foundation", "")
                }
                for c_id in ["c1", "c2", "c3", "c4", "c5", "c6"]
            },
            # v0.4: flip tracking
            "flips": flips,
            "flip_count": len(flips),
            "has_previous": prev_record is not None,
            "previous_binary": prev_record.get("binary_code") if prev_record else None,
            "verification": {
                "1w_date": None, "1w_price": None, "1w_return": None,
                "1m_date": None, "1m_price": None, "1m_return": None,
                "3m_date": None, "3m_price": None, "3m_return": None
            }
        }

        today_results.append(record)
        history.append(record)

        # Print result
        intent = framework_result["intent"]
        print(f"  Price: {analysis.get('price_estimate', 'N/A')}")
        print(f"  Config: {framework_result['configuration_name']} / {framework_result['configuration_zh']}")
        print(f"  Binary: {framework_result['binary_code']} | Evolution: {framework_result['evolution_stage']}")

        # v0.4: Show flip info
        if flips:
            print(f"  ⚠️  FLIPS ({len(flips)}):")
            for f in flips:
                direction = "0→1" if f["current"] else "1→0"
                print(f"    {f['criterion'].upper()} [{f['label']}]: {direction}")
                print(f"      Reason: {f['reason']}")
        else:
            if prev_record:
                print(f"  ✓ No flips — judgment stable")

        print(f"  Profit Assessment: {intent['overall'].upper().replace('_', ' ')}")
        print(f"    {intent['guidance']}")
        print(f"  Target ({intent['target']['relation_label']}):")
        for tp in intent['target']['positions']:
            print(f"    [{tp['state']}] {tp['criterion'].upper()}: {tp['judgment']} (vitality: {tp['vitality']})")
        print(f"  Helper ({intent['helper']['relation_label']}): {intent['helper']['logic']}")
        for hp in intent['helper']['positions']:
            print(f"    [{hp['state']}] {hp['criterion'].upper()}: {hp['judgment']} (vitality: {hp['vitality']})")
        print(f"  Threat ({intent['threat']['relation_label']}): {intent['threat']['logic']}")
        for tp in intent['threat']['positions']:
            print(f"    [{tp['state']}] {tp['criterion'].upper()}: {tp['judgment']} (vitality: {tp['vitality']})")
        print(f"  Summary: {analysis.get('summary', 'N/A')}")

        # Telegram line
        intent_short = intent['overall'].upper().replace('_', ' ')
        judgment_short = framework_result["overall_judgment_label"].split(" / ")[0]
        flip_note = f"  ⚠️ Flips: {len(flips)}\n" if flips else ""
        telegram_lines.append(
            f"*{ticker}* | {framework_result['configuration_name']}\n"
            f"  Profit: {intent_short}\n"
            f"  State: {judgment_short}\n"
            f"  Binary: {framework_result['binary_code']}\n"
            f"{flip_note}"
            f"  {analysis.get('summary', '')}\n"
        )

    save_scan_history(history)
    print(f"\n{'=' * 70}")
    print(f"Results saved to {SCAN_HISTORY_FILE}")
    print(f"Total historical records: {len(history)}")

    telegram_message = "\n".join(telegram_lines)
    send_telegram(telegram_message)

    # Summary table
    print(f"\n{'─' * 70}")
    print(f"TODAY'S ASSESSMENTS / 今日评估 ({date_str} {time_str})")
    print(f"{'─' * 70}")
    for r in today_results:
        intent_short = r.get("intent", {}).get("overall", "N/A").upper().replace("_", " ")
        flip_str = f"[{r['flip_count']} flips]" if r["flip_count"] > 0 else "[stable]"
        prev_str = f"prev:{r['previous_binary']}" if r["previous_binary"] else "first"
        print(f"  {r['ticker']:5s} | {r['configuration']:25s} | {intent_short:25s} | {r['binary_code']} {flip_str} ({prev_str}) | {r['price_estimate']}")

    # v0.4: Stability summary
    total_criteria = sum(r["flip_count"] for r in today_results)
    total_possible = len(today_results) * 6
    scans_with_prev = sum(1 for r in today_results if r["has_previous"])
    if scans_with_prev > 0:
        stability = 1 - (total_criteria / (scans_with_prev * 6))
        print(f"\n  Judgment Stability: {stability:.0%} ({total_criteria} flips across {scans_with_prev} tickers with history)")


if __name__ == "__main__":
    main()