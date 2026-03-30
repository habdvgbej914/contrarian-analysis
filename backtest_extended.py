"""
Contrarian Framework Extended Backtest v0.3 / 框架扩展回测
Tests across multiple market cycles from 2008 to 2026.
Uses three-layer structural judgment.

C3 = Internal Harmony (内部协调): Is the system internally coordinated?
No inversion — C3=1 means harmonized, C3=0 means dissonant.

用法: python3 backtest_extended.py
"""

import yfinance as yf
import pandas as pd
from datetime import datetime
import json
import os

from contrarian_analysis_mcp import run_analysis

# ============================================================
# Judgment Classification for Grading
# ============================================================

POSITIVE_JUDGMENTS = {
    "strongly_favorable", "favorable", "favorable_with_tension",
    "latent_potential", "emerging", "restrained_but_safe", "stable"
}

NEGATIVE_JUDGMENTS = {
    "adverse", "strongly_adverse", "critically_adverse",
    "depleted_negative", "suppressed"
}

NEUTRAL_JUDGMENTS = {
    "transitional", "stagnant", "weak_positive", "unstable", "dormant"
}

def classify_judgment(judgment):
    if judgment in POSITIVE_JUDGMENTS: return "positive"
    if judgment in NEGATIVE_JUDGMENTS: return "negative"
    return "neutral"

# ============================================================
# Test Cases — C3 is now Internal Harmony (1=harmonized, 0=dissonant)
# ============================================================

TEST_CASES = [
    # === 2008-2009 Financial Crisis ===
    {
        "date": "2008-09-29",
        "label": "Lehman Collapse / 雷曼倒闭后首个交易日暴跌",
        "judgments": {"c1": 0, "c2": 0, "c3": 0, "c4": 1, "c5": 1, "c6": 0},
        # C3=0: financial system in collapse, extreme internal dissonance
    },
    {
        "date": "2008-11-20",
        "label": "2008 Near-Bottom / 2008接近底部",
        "judgments": {"c1": 0, "c2": 0, "c3": 0, "c4": 1, "c5": 1, "c6": 0},
        # C3=0: still in chaos
    },
    {
        "date": "2009-03-09",
        "label": "2009 Absolute Bottom / 2009绝对底部",
        "judgments": {"c1": 0, "c2": 1, "c3": 0, "c4": 1, "c5": 1, "c6": 0},
        # C3=0: system still broken despite QE beginning
    },
    # === 2011 ===
    {
        "date": "2011-08-08",
        "label": "US Downgrade + Euro Crisis / 美国评级下调+欧债危机",
        "judgments": {"c1": 1, "c2": 0, "c3": 1, "c4": 1, "c5": 1, "c6": 0},
        # C3=1: US economy actually functioning well, downgrade symbolic
    },
    # === 2015-2016 ===
    {
        "date": "2015-08-24",
        "label": "China Black Monday / 中国黑色星期一",
        "judgments": {"c1": 1, "c2": 0, "c3": 1, "c4": 1, "c5": 1, "c6": 0},
        # C3=1: US internal economy strong
    },
    {
        "date": "2016-02-11",
        "label": "Oil Crash + Recession Fears / 油价崩盘+衰退恐惧",
        "judgments": {"c1": 1, "c2": 1, "c3": 1, "c4": 1, "c5": 1, "c6": 0},
        # C3=1: US economy growing well
    },
    # === 2018 ===
    {
        "date": "2018-02-08",
        "label": "Volmageddon / 波动率末日",
        "judgments": {"c1": 1, "c2": 1, "c3": 1, "c4": 1, "c5": 1, "c6": 0},
        # C3=1: economy strong, tax cuts boosting
    },
    {
        "date": "2018-12-24",
        "label": "Christmas Eve Crash / 平安夜暴跌",
        "judgments": {"c1": 0, "c2": 1, "c3": 1, "c4": 1, "c5": 1, "c6": 0},
        # C3=1: economy slowing but still functional
    },
    # === 2019 ===
    {
        "date": "2019-06-03",
        "label": "Trade War Escalation May 2019 / 2019年贸易战升级",
        "judgments": {"c1": 1, "c2": 0, "c3": 1, "c4": 1, "c5": 1, "c6": 0},
        # C3=1: US economy growing, trade war is external
    },
    # === 2020 ===
    {
        "date": "2020-03-23",
        "label": "COVID Crash Bottom / 疫情暴跌底部",
        "judgments": {"c1": 1, "c2": 1, "c3": 0, "c4": 1, "c5": 1, "c6": 0},
        # C3=0: economy shut down, internal disruption
    },
    {
        "date": "2020-09-02",
        "label": "Post-COVID Tech Euphoria / 疫情后科技狂热",
        "judgments": {"c1": 1, "c2": 1, "c3": 1, "c4": 1, "c5": 1, "c6": 0},
        # C3=1: economy reopening, functioning
    },
    # === 2021 ===
    {
        "date": "2021-11-18",
        "label": "2021 Meme/Crypto Peak / 2021 Meme股/加密货币顶峰",
        "judgments": {"c1": 1, "c2": 1, "c3": 0, "c4": 1, "c5": 0, "c6": 0},
        # C3=0: speculative excess, internal distortion
    },
    # === 2022 ===
    {
        "date": "2022-01-03",
        "label": "Pre-Rate-Hike Peak / 加息前高点",
        "judgments": {"c1": 0, "c2": 0, "c3": 0, "c4": 1, "c5": 1, "c6": 0},
        # C3=0: inflation running, Fed behind curve
    },
    {
        "date": "2022-06-16",
        "label": "Mid-2022 Rate Hike Fear / 2022年中加息恐惧",
        "judgments": {"c1": 0, "c2": 0, "c3": 0, "c4": 1, "c5": 1, "c6": 0},
        # C3=0: aggressive tightening disrupting
    },
    {
        "date": "2022-10-12",
        "label": "2022 Bear Market Bottom / 2022年熊市底部",
        "judgments": {"c1": 0, "c2": 1, "c3": 1, "c4": 1, "c5": 1, "c6": 0},
        # C3=1: inflation peaking, economy adjusting orderly
    },
    # === 2023 ===
    {
        "date": "2023-03-13",
        "label": "SVB Bank Crisis / 硅谷银行危机",
        "judgments": {"c1": 1, "c2": 0, "c3": 0, "c4": 1, "c5": 1, "c6": 0},
        # C3=0: banking system stress
    },
    {
        "date": "2023-10-27",
        "label": "Late 2023 Bond Scare / 2023年末债券恐慌",
        "judgments": {"c1": 1, "c2": 1, "c3": 1, "c4": 1, "c5": 1, "c6": 0},
        # C3=1: economy strong
    },
    # === 2024 ===
    {
        "date": "2024-04-19",
        "label": "Iran-Israel Tensions / 伊以紧张局势",
        "judgments": {"c1": 1, "c2": 0, "c3": 1, "c4": 1, "c5": 1, "c6": 0},
        # C3=1: US economy functioning well
    },
    {
        "date": "2024-08-05",
        "label": "Yen Carry Trade Unwind / 日元套利交易崩盘",
        "judgments": {"c1": 1, "c2": 1, "c3": 1, "c4": 1, "c5": 1, "c6": 0},
        # C3=1: US economy strong
    },
    {
        "date": "2024-10-31",
        "label": "Pre-Election Uncertainty / 大选前不确定性",
        "judgments": {"c1": 1, "c2": 1, "c3": 1, "c4": 1, "c5": 1, "c6": 0},
        # C3=1: economy stable
    },
    # === 2025 ===
    {
        "date": "2025-01-13",
        "label": "DeepSeek Shock / DeepSeek冲击前",
        "judgments": {"c1": 1, "c2": 1, "c3": 1, "c4": 1, "c5": 1, "c6": 0},
        # C3=1: economy stable
    },
    {
        "date": "2025-03-13",
        "label": "Tariff War Escalation / 关税战升级",
        "judgments": {"c1": 1, "c2": 0, "c3": 0, "c4": 1, "c5": 1, "c6": 0},
        # C3=0: trade policy disrupting economy
    },
    {
        "date": "2025-08-05",
        "label": "Summer 2025 Correction / 2025年夏季回调",
        "judgments": {"c1": 1, "c2": 1, "c3": 1, "c4": 1, "c5": 1, "c6": 0},
        # C3=1: economy healthy
    },
    {
        "date": "2025-12-18",
        "label": "Year-End 2025 Rotation / 2025年末板块轮动",
        "judgments": {"c1": 1, "c2": 0, "c3": 1, "c4": 1, "c5": 1, "c6": 0},
        # C3=1: orderly rotation
    },
    {
        "date": "2026-03-10",
        "label": "Iran War Selloff / 伊朗冲突引发抛售",
        "judgments": {"c1": 1, "c2": 0, "c3": 1, "c4": 1, "c5": 1, "c6": 0},
        # C3=1: economy sound, war is external
    },
]


def run_backtest():
    print("Downloading SPY historical data (2008-2026)... / 下载SPY历史数据...")
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
    print("结构分析回测 v0.3：SPY (2008-2026)")
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
                ret = (future_price - entry_price) / entry_price * 100
                returns[label] = round(ret, 2)
            else:
                returns[label] = None

        analysis = run_analysis(f"SPY @ {date_str}", case["judgments"])
        binary = analysis["binary_code"]
        config = analysis["configuration"]
        judgment = config["overall_judgment"]
        judgment_label = config["overall_judgment_label"]
        config_name = config["configuration_name"]
        config_zh = config["configuration_zh"]
        evolution = config["evolution_stage"]
        mislocation = analysis["mislocation"]["type"]
        direction = classify_judgment(judgment)

        grades = {}
        for horizon in ["1w", "1m", "3m"]:
            ret = returns.get(horizon)
            if ret is None:
                grades[horizon] = "PENDING"
            elif direction == "positive":
                grades[horizon] = "CORRECT" if ret > 0 else "WRONG"
            elif direction == "negative":
                grades[horizon] = "CORRECT" if ret <= 0 else "MISSED"
            else:
                grades[horizon] = "NEUTRAL"

        print(f"\n{'─' * 80}")
        print(f"📅 {date_str} | {case['label']}")
        print(f"   Price: ${entry_price:.2f} | Binary: {binary}")
        print(f"   Config: {config_name} / {config_zh}")
        print(f"   Assessment: {judgment_label} [{direction}]")
        print(f"   Evolution: {evolution} | Mislocation: {mislocation}")

        pos_str = "   Positions: "
        for p in config["positions"]:
            s = "+" if p["state"] == 1 else "-"
            short_j = p["judgment_label"].split(" / ")[0]
            pos_str += f"[{s}]{p['criterion'].upper()}:{short_j}  "
        print(pos_str)

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
            "date": date_str,
            "label": case["label"],
            "entry_price": entry_price,
            "binary": binary,
            "configuration": config_name,
            "configuration_zh": config_zh,
            "judgment": judgment,
            "judgment_label": judgment_label,
            "direction": direction,
            "evolution": evolution,
            "mislocation": mislocation,
            "returns": returns,
            "grades": grades,
            "position_judgments": {p["criterion"]: p["judgment"] for p in config["positions"]}
        })

    # === Summary ===
    print(f"\n{'=' * 90}")
    print("BACKTEST SUMMARY v0.3 / 回测总结")
    print(f"{'=' * 90}")

    for horizon in ["1w", "1m", "3m"]:
        positive = [r for r in results if r["direction"] == "positive" and r["grades"][horizon] != "PENDING"]
        correct = len([r for r in positive if r["grades"][horizon] == "CORRECT"])
        wrong = len([r for r in positive if r["grades"][horizon] == "WRONG"])
        total = len(positive)
        acc = correct / total * 100 if total > 0 else 0
        print(f"\n  {horizon.upper()} — Positive assessments:")
        print(f"    Total: {total} | Correct: {correct} | Wrong: {wrong} | Accuracy: {acc:.1f}%")
        valid_rets = [r["returns"][horizon] for r in positive if r["returns"].get(horizon) is not None]
        if valid_rets:
            print(f"    Average return: {sum(valid_rets)/len(valid_rets):+.2f}%")

    for horizon in ["1w", "1m", "3m"]:
        negative = [r for r in results if r["direction"] == "negative" and r["grades"][horizon] != "PENDING"]
        correct = len([r for r in negative if r["grades"][horizon] == "CORRECT"])
        missed = len([r for r in negative if r["grades"][horizon] == "MISSED"])
        total = len(negative)
        acc = correct / total * 100 if total > 0 else 0
        if total > 0:
            print(f"\n  {horizon.upper()} — Negative assessments:")
            print(f"    Total: {total} | Correct: {correct} | Missed: {missed} | Accuracy: {acc:.1f}%")
            valid_rets = [r["returns"][horizon] for r in negative if r["returns"].get(horizon) is not None]
            if valid_rets:
                print(f"    Average return: {sum(valid_rets)/len(valid_rets):+.2f}%")

    neutral = [r for r in results if r["direction"] == "neutral" and r["returns"].get("3m") is not None]
    if neutral:
        print(f"\n  Neutral assessments:")
        for r in neutral:
            print(f"    {r['date']} {r['label']}: {r['judgment_label']} → 3m={r['returns']['3m']:+.1f}%")

    print(f"\n{'─' * 80}")
    print("JUDGMENT DISTRIBUTION / 判断分布")
    from collections import Counter
    j_counts = Counter(r["judgment"] for r in results)
    for j, count in j_counts.most_common():
        label = next((r["judgment_label"] for r in results if r["judgment"] == j), j)
        print(f"  {label}: {count}")

    print(f"\n{'─' * 80}")
    print("HYPOTHETICAL STRATEGY (positive assessments)")
    pos_signals = [r for r in results if r["direction"] == "positive"]
    for horizon in ["1w", "1m", "3m", "6m"]:
        valid = [r for r in pos_signals if r["returns"].get(horizon) is not None]
        if valid:
            avg = sum(r["returns"][horizon] for r in valid) / len(valid)
            win_rate = len([r for r in valid if r["returns"][horizon] > 0]) / len(valid) * 100
            print(f"  {horizon.upper()}: {len(valid)} trades | Avg return: {avg:+.2f}% | Win rate: {win_rate:.0f}%")

    output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backtest_extended_results.json")
    with open(output_file, "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nFull results saved to {output_file}")


if __name__ == "__main__":
    run_backtest()