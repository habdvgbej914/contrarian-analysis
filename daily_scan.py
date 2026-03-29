"""
Contrarian Daily Auto-Scanner / 逆向每日自动扫描
Uses Claude API with web search to analyze markets daily.
Saves results and pushes to Telegram.

用法: python3 daily_scan.py
定时: crontab 每天伦敦时间早8点（美股盘前）运行
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

# Tickers to scan daily / 每日扫描标的
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

ANALYSIS_PROMPT = """You are a contrarian opportunity analyst. Today is {date}.

You just searched for current market information about {ticker} ({name}).

Based on the search results, make 6 binary judgments for the Contrarian Framework:

C1 - Trend Alignment: Is {ticker} aligned with the era's macro trend? (true/false)
C2 - Energy State: Is energy accumulating in this domain right now? (true/false)  
C3 - Incumbents Misaligned: Are most market participants positioned WRONG? (true/false)
C4 - Can Sustain: Can a retail investor with 12-month horizon sustain this position? (true/false)
C5 - Fundamentals Solid: Are the fundamentals real and validated? (true/false)
C6 - Domain Heavy: Is this a heavy, high-barrier domain? (true/false)

For each criterion, briefly assess across 5 dimensions:
- origin (root cause)
- visibility (market attention)  
- growth (expansion trajectory)
- constraint (barriers/limits)
- foundation (infrastructure/resources)

RESPOND ONLY IN THIS EXACT JSON FORMAT, nothing else:
{{
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
    "c3_judgment_misaligned": true or false,
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


def call_claude_with_search(ticker_info):
    """Call Claude API with web search to analyze a ticker / 调用Claude API搜索并分析标的"""
    ticker = ticker_info["ticker"]
    name = ticker_info["name"]
    query = ticker_info["search_query"]
    date = datetime.now().strftime("%Y-%m-%d")

    prompt = ANALYSIS_PROMPT.format(ticker=ticker, name=name, date=date)

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

        # Extract text from response / 从响应中提取文本
        full_text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                full_text += block["text"]

        # Parse JSON from response / 解析JSON
        # Find JSON block in text
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
    """Run the framework logic on Claude's analysis / 对Claude的分析运行框架逻辑"""
    from contrarian_analysis_mcp import run_analysis

    states = {
        "c1": int(analysis_data["c1_judgment"]),
        "c2": int(analysis_data["c2_judgment"]),
        "c3": 0 if analysis_data["c3_judgment_misaligned"] else 1,
        "c4": int(analysis_data["c4_judgment"]),
        "c5": int(analysis_data["c5_judgment"]),
        "c6": int(analysis_data["c6_judgment"])
    }

    result = run_analysis(
        f"{analysis_data['ticker']} @ {datetime.now().strftime('%Y-%m-%d')}",
        states
    )

    # Determine signal / 确定信号
    momentum = result["cross_layer"]["momentum"]
    substance = result["cross_layer"]["substance"]
    mislocation = result["mislocation"]["type"]

    if mislocation == "form_without_flow" and momentum == "strong":
        signal = "STRONG BUY"
    elif mislocation == "form_without_flow" and momentum == "weak":
        signal = "WATCH"
    elif momentum == "strong" and substance == "solid":
        if states["c3"] == 0:
            signal = "BUY"
        else:
            signal = "HOLD"
    elif momentum == "strong" and substance == "hollow":
        signal = "CAUTION"
    elif momentum == "weak" and substance == "solid":
        signal = "WATCH"
    elif momentum == "weak" and substance == "hollow":
        signal = "AVOID"
    else:
        signal = "NEUTRAL"

    return {
        "signal": signal,
        "binary_code": result["binary_code"],
        "momentum": momentum,
        "substance": substance,
        "mislocation": mislocation,
        "states": states
    }


def send_telegram(message):
    """Send message to Telegram / 发送Telegram消息"""
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
    """Load scan history / 加载扫描历史"""
    try:
        with open(SCAN_HISTORY_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_scan_history(history):
    """Save scan history / 保存扫描历史"""
    with open(SCAN_HISTORY_FILE, "w") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def main():
    date_str = datetime.now().strftime("%Y-%m-%d")
    time_str = datetime.now().strftime("%H:%M")

    print(f"{'=' * 70}")
    print(f"CONTRARIAN DAILY SCAN / 逆向每日扫描")
    print(f"Date: {date_str} {time_str}")
    print(f"{'=' * 70}")

    if not ANTHROPIC_API_KEY:
        print("ERROR: ANTHROPIC_API_KEY not set in .env")
        return

    history = load_scan_history()
    today_results = []
    telegram_lines = [f"📊 *Contrarian Daily Scan*", f"📅 {date_str}", ""]

    for ticker, info in TICKERS.items():
        print(f"\n{'─' * 50}")
        print(f"Analyzing {ticker} ({info['name']})...")

        # Step 1: Claude searches and analyzes / Claude搜索并分析
        analysis = call_claude_with_search({"ticker": ticker, **info})

        if analysis is None:
            print(f"  FAILED: Could not get analysis for {ticker}")
            telegram_lines.append(f"❌ {ticker}: Analysis failed")
            continue

        # Step 2: Run framework / 运行框架
        framework_result = run_framework(analysis)

        # Step 3: Record / 记录
        record = {
            "date": date_str,
            "time": time_str,
            "ticker": ticker,
            "name": info["name"],
            "price_estimate": analysis.get("price_estimate", "N/A"),
            "signal": framework_result["signal"],
            "binary_code": framework_result["binary_code"],
            "momentum": framework_result["momentum"],
            "substance": framework_result["substance"],
            "mislocation": framework_result["mislocation"],
            "states": framework_result["states"],
            "summary": analysis.get("summary", ""),
            "reasoning": {
                c_id: {
                    "judgment": analysis.get(f"{c_id}_judgment", analysis.get(f"{c_id}_judgment_misaligned", None)),
                    "origin": analysis.get(f"{c_id}_origin", ""),
                    "visibility": analysis.get(f"{c_id}_visibility", ""),
                    "growth": analysis.get(f"{c_id}_growth", ""),
                    "constraint": analysis.get(f"{c_id}_constraint", ""),
                    "foundation": analysis.get(f"{c_id}_foundation", "")
                }
                for c_id in ["c1", "c2", "c3", "c4", "c5", "c6"]
            },
            "verification": {
                "1w_date": None, "1w_price": None, "1w_return": None,
                "1m_date": None, "1m_price": None, "1m_return": None,
                "3m_date": None, "3m_price": None, "3m_return": None
            }
        }

        today_results.append(record)
        history.append(record)

        # Print result / 打印结果
        signal_icon = {
            "STRONG BUY": "🟢🟢", "BUY": "🟢", "HOLD": "⚪",
            "WATCH": "🟡", "CAUTION": "🟠", "AVOID": "🔴", "NEUTRAL": "⚪"
        }.get(framework_result["signal"], "⚪")

        print(f"  Price: {analysis.get('price_estimate', 'N/A')}")
        print(f"  Signal: {signal_icon} {framework_result['signal']}")
        print(f"  Binary: {framework_result['binary_code']}")
        print(f"  Momentum: {framework_result['momentum']} | Substance: {framework_result['substance']}")
        print(f"  Mislocation: {framework_result['mislocation']}")
        print(f"  Summary: {analysis.get('summary', 'N/A')}")

        telegram_lines.append(
            f"{signal_icon} *{ticker}* ({info['name']}): {framework_result['signal']}\n"
            f"   Price: {analysis.get('price_estimate', 'N/A')} | Binary: {framework_result['binary_code']}\n"
            f"   {analysis.get('summary', '')}\n"
        )

    # Save history / 保存历史
    save_scan_history(history)
    print(f"\n{'=' * 70}")
    print(f"Results saved to {SCAN_HISTORY_FILE}")
    print(f"Total historical records: {len(history)}")

    # Send Telegram / 发送Telegram
    telegram_message = "\n".join(telegram_lines)
    send_telegram(telegram_message)

    # Print summary table / 打印总结表
    print(f"\n{'─' * 70}")
    print(f"TODAY'S SIGNALS / 今日信号 ({date_str})")
    print(f"{'─' * 70}")
    for r in today_results:
        signal_icon = {
            "STRONG BUY": "🟢🟢", "BUY": "🟢", "HOLD": "⚪",
            "WATCH": "🟡", "CAUTION": "🟠", "AVOID": "🔴"
        }.get(r["signal"], "⚪")
        print(f"  {signal_icon} {r['ticker']:5s} | {r['signal']:12s} | {r['binary_code']} | {r['price_estimate']}")


if __name__ == "__main__":
    main()