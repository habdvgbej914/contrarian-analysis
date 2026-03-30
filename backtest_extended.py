"""
Structural Analysis Extended Backtest v0.3
Tests across multiple market cycles from 2008 to 2026.
Grades based on intent assessment (seek_profit).

用法: python3 backtest_extended.py
"""

import yfinance as yf
import pandas as pd
from datetime import datetime
import json
import os

from contrarian_analysis_mcp import run_analysis, _analyze_intent

POSITIVE_INTENTS = {"strongly_supported", "supported_with_resistance", "supported_but_weak", "contested"}
NEGATIVE_INTENTS = {"not_viable", "challenged"}
NEUTRAL_INTENTS = {"possible_but_unsupported", "indirect_path", "dormant", "uncertain"}

TEST_CASES = [
    {"date": "2008-09-29", "label": "Lehman Collapse / 雷曼倒闭后首个交易日暴跌",
     "judgments": {"c1": 0, "c2": 0, "c3": 0, "c4": 1, "c5": 1, "c6": 0}},
    {"date": "2008-11-20", "label": "2008 Near-Bottom / 2008接近底部",
     "judgments": {"c1": 0, "c2": 0, "c3": 0, "c4": 1, "c5": 1, "c6": 0}},
    {"date": "2009-03-09", "label": "2009 Absolute Bottom / 2009绝对底部",
     "judgments": {"c1": 0, "c2": 1, "c3": 0, "c4": 1, "c5": 1, "c6": 0}},
    {"date": "2011-08-08", "label": "US Downgrade + Euro Crisis / 美国评级下调+欧债危机",
     "judgments": {"c1": 1, "c2": 0, "c3": 1, "c4": 1, "c5": 1, "c6": 0}},
    {"date": "2015-08-24", "label": "China Black Monday / 中国黑色星期一",
     "judgments": {"c1": 1, "c2": 0, "c3": 1, "c4": 1, "c5": 1, "c6": 0}},
    {"date": "2016-02-11", "label": "Oil Crash + Recession Fears / 油价崩盘+衰退恐惧",
     "judgments": {"c1": 1, "c2": 1, "c3": 1, "c4": 1, "c5": 1, "c6": 0}},
    {"date": "2018-02-08", "label": "Volmageddon / 波动率末日",
     "judgments": {"c1": 1, "c2": 1, "c3": 1, "c4": 1, "c5": 1, "c6": 0}},
    {"date": "2018-12-24", "label": "Christmas Eve Crash / 平安夜暴跌",
     "judgments": {"c1": 0, "c2": 1, "c3": 1, "c4": 1, "c5": 1, "c6": 0}},
    {"date": "2019-06-03", "label": "Trade War Escalation May 2019 / 2019年贸易战升级",
     "judgments": {"c1": 1, "c2": 0, "c3": 1, "c4": 1, "c5": 1, "c6": 0}},
    {"date": "2020-03-23", "label": "COVID Crash Bottom / 疫情暴跌底部",
     "judgments": {"c1": 1, "c2": 1, "c3": 0, "c4": 1, "c5": 1, "c6": 0}},
    {"date": "2020-09-02", "label": "Post-COVID Tech Euphoria / 疫情后科技狂热",
     "judgments": {"c1": 1, "c2": 1, "c3": 1, "c4": 1, "c5": 1, "c6": 0}},
    {"date": "2021-11-18", "label": "2021 Meme/Crypto Peak / 2021 Meme股/加密货币顶峰",
     "judgments": {"c1": 1, "c2": 1, "c3": 0, "c4": 1, "c5": 0, "c6": 0}},
    {"date": "2022-01-03", "label": "Pre-Rate-Hike Peak / 加息前高点",
     "judgments": {"c1": 0, "c2": 0, "c3": 0, "c4": 1, "c5": 1, "c6": 0}},
    {"date": "2022-06-16", "label": "Mid-2022 Rate Hike Fear / 2022年中加息恐惧",
     "judgments": {"c1": 0, "c2": 0, "c3": 0, "c4": 1, "c5": 1, "c6": 0}},
    {"date": "2022-10-12", "label": "2022 Bear Market Bottom / 2022年熊市底部",
     "judgments": {"c1": 0, "c2": 1, "c3": 1, "c4": 1, "c5": 1, "c6": 0}},
    {"date": "2023-03-13", "label": "SVB Bank Crisis / 硅谷银行危机",
     "judgments": {"c1": 1, "c2": 0, "c3": 0, "c4": 1, "c5": 1, "c6": 0}},
    {"date": "2023-10-27", "label": "Late 2023 Bond Scare / 2023年末债券恐慌",
     "judgments": {"c1": 1, "c2": 1, "c3": 1, "c4": 1, "c5": 1, "c6": 0}},
    {"date": "2024-04-19", "label": "Iran-Israel Tensions / 伊以紧张局势",
     "judgments": {"c1": 1, "c2": 0, "c3": 1, "c4": 1, "c5": 1, "c6": 0}},
    {"date": "2024-08-05", "label": "Yen Carry Trade Unwind / 日元套利交易崩盘",
     "judgments": {"c1": 1, "c2": 1, "c3": 1, "c4": 1, "c5": 1, "c6": 0}},
    {"date": "2024-10-31", "label": "Pre-Election Uncertainty / 大选前不确定性",
     "judgments": {"c1": 1, "c2": 1, "c3": 1, "c4": 1, "c5": 1, "c6": 0}},
    {"date": "2025-01-13", "label": "DeepSeek Shock / DeepSeek冲击前",
     "judgments": {"c1": 1, "c2": 1, "c3": 1, "c4": 1, "c5": 1, "c6": 0}},
    {"date": "2025-03-13", "label": "Tariff War Escalation / 关税战升级",
     "judgments": {"c1": 1, "c2": 0, "c3": 0, "c4": 1, "c5": 1, "c6": 0}},
    {"date": "2025-08-05", "label": "Summer 2025 Correction / 2025年夏季回调",
     "judgments": {"c1": 1, "c2": 1, "c3": 1, "c4": 1, "c5": 1, "c6": 0}},
    {"date": "2025-12-18", "label": "Year-End 2025 Rotation / 2025年末板块轮动",
     "judgments": {"c1": 1, "c2": 0, "c3": 1, "c4": 1, "c5": 1, "c6": 0}},
    {"date": "2026-03-10", "label": "Iran War Selloff / 伊朗冲突引发抛售",
     "judgments": {"c1": 1, "c2": 0, "c3": 1, "c4": 1, "c5": 1, "c6": 0}},
]


def run_backtest():
    print("Downloading SPY historical data (2008-2026)...")
    spy = yf.download("SPY", start="2008-01-01", end="2026-03-28", progress=False)
    if spy.empty:
        print("ERROR: Could not download SPY data.")
        return
    if isinstance(spy.columns, pd.MultiIndex):
        spy.columns = spy.columns.get_level_values(0)
    print(f"Downloaded {len(spy)} trading days of data.\n")

    results = []
    print("=" * 90)
    print("STRUCTURAL ANALYSIS BACKTEST v0.3: SPY (2008-2026)")
    print("=" * 90)

    for case in TEST_CASES:
        date_str = case["date"]
        target_date = pd.Timestamp(date_str)
        available_dates = spy.index[spy.index >= target_date]
        if len(available_dates) == 0:
            print(f"\nSkipping {date_str}: no data available")
            continue
        actual_date = available_dates[0]
        entry_price = float(spy.loc[actual_date, "Close"])

        horizons = {"1w": 5, "2w": 10, "1m": 21, "3m": 63, "6m": 126}
        returns = {}
        entry_idx = spy.index.get_loc(actual_date)
        for label, days in horizons.items():
            if entry_idx + days < len(spy):
                future_price = float(spy.iloc[entry_idx + days]["Close"])
                returns[label] = round((future_price - entry_price) / entry_price * 100, 2)
            else:
                returns[label] = None

        analysis = run_analysis(f"SPY @ {date_str}", case["judgments"])
        config = analysis["configuration"]
        intent = _analyze_intent(config, "seek_profit")
        intent_assessment = intent["overall"]

        # Grade based on intent
        grades = {}
        for horizon in ["1w", "1m", "3m"]:
            ret = returns.get(horizon)
            if ret is None:
                grades[horizon] = "PENDING"
            elif intent_assessment in POSITIVE_INTENTS:
                grades[horizon] = "CORRECT" if ret > 0 else "WRONG"
            elif intent_assessment in NEGATIVE_INTENTS:
                grades[horizon] = "CORRECT" if ret <= 0 else "MISSED"
            else:
                grades[horizon] = "NEUTRAL"

        intent_short = intent_assessment.upper().replace("_", " ")

        print(f"\n{'─' * 80}")
        print(f"📅 {date_str} | {case['label']}")
        print(f"   Price: ${entry_price:.2f} | Binary: {analysis['binary_code']}")
        print(f"   Config: {config['configuration_name']} / {config['configuration_zh']}")
        print(f"   Profit Intent: {intent_short}")
        print(f"     {intent['guidance']}")

        # Show target/helper/threat summary
        target_info = intent["target"]
        for tp in target_info["positions"]:
            print(f"     Target [{tp['state']}] {tp['criterion'].upper()}: {tp['judgment']} (vitality: {tp['vitality']})")
        if not target_info["positions"]:
            print(f"     Target: none found")

        ret_str = "   Returns: "
        for h in ["1w", "2w", "1m", "3m", "6m"]:
            v = returns.get(h)
            ret_str += f" {h}={'N/A' if v is None else f'{v:+.1f}%'} |"
        print(ret_str.rstrip("|"))

        grade_str = "   Grades:  "
        for h in ["1w", "1m", "3m"]:
            g = grades[h]
            icon = {"CORRECT": "✅", "WRONG": "❌", "MISSED": "⚠️", "NEUTRAL": "⚪", "PENDING": "⏳"}[g]
            grade_str += f" {h}={icon}{g} |"
        print(grade_str.rstrip("|"))

        results.append({
            "date": date_str, "label": case["label"], "entry_price": entry_price,
            "binary": analysis["binary_code"],
            "configuration": config["configuration_name"],
            "configuration_zh": config["configuration_zh"],
            "intent_assessment": intent_assessment,
            "intent_guidance": intent["guidance"],
            "returns": returns, "grades": grades,
        })

    # === Summary ===
    print(f"\n{'=' * 90}")
    print("BACKTEST SUMMARY v0.3")
    print(f"{'=' * 90}")

    for horizon in ["1w", "1m", "3m"]:
        pos = [r for r in results if r["intent_assessment"] in POSITIVE_INTENTS and r["grades"][horizon] != "PENDING"]
        if pos:
            correct = len([r for r in pos if r["grades"][horizon] == "CORRECT"])
            wrong = len([r for r in pos if r["grades"][horizon] == "WRONG"])
            acc = correct / len(pos) * 100
            avg = sum(r["returns"][horizon] for r in pos if r["returns"].get(horizon) is not None) / len(pos)
            print(f"\n  {horizon.upper()} — Supported intents (expect profit):")
            print(f"    Total: {len(pos)} | Correct: {correct} | Wrong: {wrong} | Accuracy: {acc:.1f}% | Avg return: {avg:+.2f}%")

    for horizon in ["1w", "1m", "3m"]:
        neg = [r for r in results if r["intent_assessment"] in NEGATIVE_INTENTS and r["grades"][horizon] != "PENDING"]
        if neg:
            correct = len([r for r in neg if r["grades"][horizon] == "CORRECT"])
            missed = len([r for r in neg if r["grades"][horizon] == "MISSED"])
            acc = correct / len(neg) * 100
            avg = sum(r["returns"][horizon] for r in neg if r["returns"].get(horizon) is not None) / len(neg)
            print(f"\n  {horizon.upper()} — Unsupported intents (expect no profit):")
            print(f"    Total: {len(neg)} | Correct: {correct} | Missed: {missed} | Accuracy: {acc:.1f}% | Avg return: {avg:+.2f}%")

    neutral = [r for r in results if r["intent_assessment"] not in POSITIVE_INTENTS | NEGATIVE_INTENTS and r["returns"].get("3m") is not None]
    if neutral:
        print(f"\n  Neutral intents (no directional call):")
        for r in neutral:
            print(f"    {r['date']} {r['label']}: {r['intent_assessment']} → 3m={r['returns']['3m']:+.1f}%")

    # Distribution
    print(f"\n{'─' * 80}")
    print("INTENT DISTRIBUTION")
    from collections import Counter
    i_counts = Counter(r["intent_assessment"] for r in results)
    for ia, count in i_counts.most_common():
        print(f"  {ia}: {count}")

    output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backtest_extended_results.json")
    with open(output_file, "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nFull results saved to {output_file}")


if __name__ == "__main__":
    run_backtest()