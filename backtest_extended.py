"""
Contrarian Framework Extended Backtest / 逆向框架扩展回测
Tests across multiple market cycles from 2008 to 2026
with 1-week, 1-month, 3-month, and 6-month horizons.

用法: python3 backtest_extended.py
"""

import yfinance as yf
import pandas as pd
from datetime import datetime
import json
import os

from contrarian_analysis_mcp import run_analysis, CRITERIA

# ============================================================
# Extended Test Cases / 扩展测试案例
# Covering 2008-2026, multiple market cycles
# ============================================================

TEST_CASES = [
    # === 2008-2009 Financial Crisis / 金融危机 ===
    {
        "date": "2008-09-29",
        "label": "Lehman Collapse / 雷曼倒闭后首个交易日暴跌",
        "judgments": {
            "c1": 0,  # misaligned: financial system collapsing
            "c2": 0,  # dissipating: capital destruction accelerating
            "c3": 0,  # misaligned: everyone panic selling
            "c4": 1,  # can sustain (if long horizon)
            "c5": 1,  # solid: real economy still exists
            "c6": 0,  # light
        },
    },
    {
        "date": "2008-11-20",
        "label": "2008 Near-Bottom / 2008接近底部",
        "judgments": {
            "c1": 0,  # misaligned: recession deepening
            "c2": 0,  # dissipating: no signs of recovery yet
            "c3": 0,  # misaligned: maximum fear
            "c4": 1,
            "c5": 1,  # solid: S&P companies will survive
            "c6": 0,
        },
    },
    {
        "date": "2009-03-09",
        "label": "2009 Absolute Bottom / 2009绝对底部",
        "judgments": {
            "c1": 0,  # misaligned: still in recession
            "c2": 1,  # accumulating: Fed QE announced, TARP working
            "c3": 0,  # misaligned: consensus says more downside
            "c4": 1,
            "c5": 1,  # solid
            "c6": 0,
        },
    },
    # === 2010-2011 Euro Crisis / 欧债危机 ===
    {
        "date": "2011-08-08",
        "label": "US Downgrade + Euro Crisis / 美国评级下调+欧债危机",
        "judgments": {
            "c1": 1,  # aligned: US economy recovering despite headlines
            "c2": 0,  # dissipating: fear spike, VIX surged
            "c3": 0,  # misaligned: panic selling on downgrade
            "c4": 1,
            "c5": 1,  # solid: US companies profitable
            "c6": 0,
        },
    },
    # === 2015-2016 China Scare / 中国恐慌 ===
    {
        "date": "2015-08-24",
        "label": "China Black Monday / 中国黑色星期一",
        "judgments": {
            "c1": 1,  # aligned: US economy strong, China fears overblown for US
            "c2": 0,  # dissipating: sudden panic
            "c3": 0,  # misaligned: selling on China fears, US fundamentals intact
            "c4": 1,
            "c5": 1,  # solid
            "c6": 0,
        },
    },
    {
        "date": "2016-02-11",
        "label": "Oil Crash + Recession Fears / 油价崩盘+衰退恐惧",
        "judgments": {
            "c1": 1,  # aligned: US economy actually growing
            "c2": 1,  # accumulating: oil crash bottoming, fear peaking
            "c3": 0,  # misaligned: recession calls everywhere, wrong
            "c4": 1,
            "c5": 1,  # solid
            "c6": 0,
        },
    },
    # === 2018 Trade War / 贸易战 ===
    {
        "date": "2018-02-08",
        "label": "Volmageddon / 波动率末日",
        "judgments": {
            "c1": 1,  # aligned: economy strong, tax cuts just passed
            "c2": 1,  # accumulating: technical crash, fundamentals strong
            "c3": 0,  # misaligned: VIX products blew up, mechanical selling
            "c4": 1,
            "c5": 1,  # solid: earnings booming from tax cuts
            "c6": 0,
        },
    },
    {
        "date": "2018-12-24",
        "label": "Christmas Eve Crash / 平安夜暴跌",
        "judgments": {
            "c1": 0,  # misaligned: Fed overtightening fears, trade war
            "c2": 1,  # accumulating: extreme oversold, Powell about to pivot
            "c3": 0,  # misaligned: maximum pessimism
            "c4": 1,
            "c5": 1,  # solid: earnings still growing
            "c6": 0,
        },
    },
    # === 2019-2020 ===
    {
        "date": "2019-06-03",
        "label": "Trade War Escalation May 2019 / 2019年贸易战升级",
        "judgments": {
            "c1": 1,  # aligned: economy growing, Fed pivoted dovish
            "c2": 0,  # dissipating: trade uncertainty
            "c3": 0,  # misaligned: fear of recession from tariffs
            "c4": 1,
            "c5": 1,  # solid
            "c6": 0,
        },
    },
    # === 2020 (original cases) ===
    {
        "date": "2020-03-23",
        "label": "COVID Crash Bottom / 疫情暴跌底部",
        "judgments": {
            "c1": 1, "c2": 1, "c3": 0, "c4": 1, "c5": 1, "c6": 0,
        },
    },
    {
        "date": "2020-09-02",
        "label": "Post-COVID Tech Euphoria / 疫情后科技狂热",
        "judgments": {
            "c1": 1, "c2": 1, "c3": 1, "c4": 1, "c5": 1, "c6": 0,
        },
    },
    # === 2021 Peak ===
    {
        "date": "2021-11-18",
        "label": "2021 Meme/Crypto Peak / 2021 Meme股/加密货币顶峰",
        "judgments": {
            "c1": 1,  # aligned: economy reopening
            "c2": 1,  # accumulating: liquidity everywhere
            "c3": 1,  # matched: everyone buying, no edge
            "c4": 1,
            "c5": 0,  # hollow: many overvalued, meme frenzy, crypto bubble
            "c6": 0,
        },
    },
    # === 2022 (original cases) ===
    {
        "date": "2022-01-03",
        "label": "Pre-Rate-Hike Peak / 加息前高点",
        "judgments": {
            "c1": 0, "c2": 0, "c3": 1, "c4": 1, "c5": 1, "c6": 0,
        },
    },
    {
        "date": "2022-06-16",
        "label": "Mid-2022 Rate Hike Fear / 2022年中加息恐惧",
        "judgments": {
            "c1": 0, "c2": 0, "c3": 0, "c4": 1, "c5": 1, "c6": 0,
        },
    },
    {
        "date": "2022-10-12",
        "label": "2022 Bear Market Bottom / 2022年熊市底部",
        "judgments": {
            "c1": 0, "c2": 1, "c3": 0, "c4": 1, "c5": 1, "c6": 0,
        },
    },
    # === 2023 ===
    {
        "date": "2023-03-13",
        "label": "SVB Bank Crisis / 硅谷银行危机",
        "judgments": {
            "c1": 1,  # aligned: economy resilient
            "c2": 0,  # dissipating: bank contagion fear
            "c3": 0,  # misaligned: panic about banking system, overblown
            "c4": 1,
            "c5": 1,  # solid: FDIC backstop, not 2008
            "c6": 0,
        },
    },
    {
        "date": "2023-10-27",
        "label": "Late 2023 Bond Scare / 2023年末债券恐慌",
        "judgments": {
            "c1": 1, "c2": 1, "c3": 0, "c4": 1, "c5": 1, "c6": 0,
        },
    },
    # === 2024 ===
    {
        "date": "2024-04-19",
        "label": "Iran-Israel Tensions / 伊以紧张局势",
        "judgments": {
            "c1": 1,  # aligned: US economy strong
            "c2": 0,  # dissipating: geopolitical fear
            "c3": 0,  # misaligned: selling on geopolitics
            "c4": 1,
            "c5": 1,  # solid
            "c6": 0,
        },
    },
    {
        "date": "2024-08-05",
        "label": "Yen Carry Trade Unwind / 日元套利交易崩盘",
        "judgments": {
            "c1": 1, "c2": 1, "c3": 0, "c4": 1, "c5": 1, "c6": 0,
        },
    },
    {
        "date": "2024-10-31",
        "label": "Pre-Election Uncertainty / 大选前不确定性",
        "judgments": {
            "c1": 1,  # aligned: economy strong
            "c2": 1,  # accumulating: earnings season strong
            "c3": 1,  # matched: market broadly positioned
            "c4": 1,
            "c5": 1,  # solid
            "c6": 0,
        },
    },
    # === 2025-2026 Recent Events / 近期事件 ===
    {
        "date": "2025-01-13",
        "label": "DeepSeek Shock / DeepSeek冲击前",
        "judgments": {
            "c1": 1,  # aligned: AI boom continuing
            "c2": 1,  # accumulating: capital flowing into AI
            "c3": 1,  # matched: consensus bullish
            "c4": 1,
            "c5": 1,  # solid: earnings strong
            "c6": 0,
        },
    },
    {
        "date": "2025-03-13",
        "label": "Tariff War Escalation / 关税战升级",
        "judgments": {
            "c1": 1, "c2": 0, "c3": 0, "c4": 1, "c5": 1, "c6": 0,
        },
    },
    {
        "date": "2025-08-05",
        "label": "Summer 2025 Correction / 2025年夏季回调",
        "judgments": {
            "c1": 1,  # aligned: AI capex still growing
            "c2": 1,  # accumulating: correction bought quickly
            "c3": 0,  # misaligned: retail fear
            "c4": 1,
            "c5": 1,  # solid
            "c6": 0,
        },
    },
    {
        "date": "2025-12-18",
        "label": "Year-End 2025 Rotation / 2025年末板块轮动",
        "judgments": {
            "c1": 1,  # aligned: economy stable
            "c2": 0,  # dissipating: rotation out of tech
            "c3": 1,  # matched: orderly rotation, not panic
            "c4": 1,
            "c5": 1,  # solid
            "c6": 0,
        },
    },
    {
        "date": "2026-03-10",
        "label": "Iran War Selloff / 伊朗冲突引发抛售",
        "judgments": {
            "c1": 1,  # aligned: US economy fundamentally sound
            "c2": 0,  # dissipating: war fear, VIX spiking
            "c3": 0,  # misaligned: panic selling on geopolitics
            "c4": 1,
            "c5": 1,  # solid: corporate earnings intact
            "c6": 0,
        },
    },
]


def run_backtest():
    """Run the extended backtest / 运行扩展回测"""

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
    print("CONTRARIAN FRAMEWORK EXTENDED BACKTEST: SPY (2008-2026)")
    print("逆向框架扩展回测：SPY (2008-2026)")
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

        # Calculate returns at multiple horizons / 计算多周期收益率
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

        # Run framework / 运行框架
        analysis = run_analysis(f"SPY @ {date_str}", case["judgments"])
        binary = analysis["binary_code"]
        momentum = analysis["cross_layer"]["momentum"]
        substance = analysis["cross_layer"]["substance"]
        mislocation = analysis["mislocation"]["type"]

        # Signal logic (with momentum guard) / 信号逻辑（含势的保护）
        if mislocation == "form_without_flow" and momentum == "strong":
            signal = "STRONG BUY"
        elif mislocation == "form_without_flow" and momentum == "weak":
            signal = "WATCH"
        elif momentum == "strong" and substance == "solid":
            if case["judgments"]["c3"] == 0:
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

        # Grade at multiple horizons / 多周期评分
        grades = {}
        for horizon in ["1w", "1m", "3m"]:
            ret = returns.get(horizon)
            if ret is None:
                grades[horizon] = "PENDING"
            elif signal in ["STRONG BUY", "BUY"]:
                grades[horizon] = "CORRECT" if ret > 0 else "WRONG"
            elif signal in ["AVOID"]:
                grades[horizon] = "CORRECT" if ret <= 0 else "MISSED"
            elif signal in ["WATCH"]:
                grades[horizon] = "CORRECT" if ret <= 5 else "MISSED"  # WATCH means don't rush in
            elif signal in ["HOLD", "CAUTION"]:
                grades[horizon] = "NEUTRAL"
            else:
                grades[horizon] = "NEUTRAL"

        # Print / 打印
        print(f"\n{'─' * 80}")
        print(f"📅 {date_str} | {case['label']}")
        print(f"   Price: ${entry_price:.2f} | Binary: {binary} | Signal: {signal}")
        print(f"   Momentum: {momentum} | Substance: {substance} | Mislocation: {mislocation}")

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
            "signal": signal,
            "momentum": momentum,
            "substance": substance,
            "mislocation": mislocation,
            "returns": returns,
            "grades": grades
        })

    # === Summary / 总结 ===
    print(f"\n{'=' * 90}")
    print("EXTENDED BACKTEST SUMMARY / 扩展回测总结")
    print(f"{'=' * 90}")

    # Per-horizon accuracy for actionable signals (BUY/STRONG BUY)
    for horizon in ["1w", "1m", "3m"]:
        actionable = [r for r in results if r["signal"] in ["STRONG BUY", "BUY"] and r["grades"][horizon] != "PENDING"]
        correct = len([r for r in actionable if r["grades"][horizon] == "CORRECT"])
        wrong = len([r for r in actionable if r["grades"][horizon] == "WRONG"])
        total = len(actionable)
        acc = correct / total * 100 if total > 0 else 0
        print(f"\n  {horizon.upper()} horizon — BUY/STRONG BUY signals:")
        print(f"    Total: {total} | Correct: {correct} | Wrong: {wrong} | Accuracy: {acc:.1f}%")
        if actionable:
            avg_ret = sum(r["returns"][horizon] for r in actionable if r["returns"].get(horizon) is not None) / len(actionable)
            print(f"    Average return: {avg_ret:+.2f}%")

    # WATCH signals accuracy
    print(f"\n  WATCH signals (correctly avoided or timed):")
    watch_signals = [r for r in results if r["signal"] == "WATCH" and r["grades"]["3m"] != "PENDING"]
    for r in watch_signals:
        ret_3m = r["returns"].get("3m", "N/A")
        print(f"    {r['date']} {r['label']}: 3m return={ret_3m}% — {'Avoided loss ✅' if isinstance(ret_3m, (int, float)) and ret_3m < 0 else 'Missed gain ⚠️' if isinstance(ret_3m, (int, float)) and ret_3m > 10 else 'Prudent hold ✅'}")

    # HOLD/CAUTION signals
    print(f"\n  HOLD/CAUTION signals (no contrarian edge):")
    hold_signals = [r for r in results if r["signal"] in ["HOLD", "CAUTION"] and r["returns"].get("3m") is not None]
    for r in hold_signals:
        ret_3m = r["returns"]["3m"]
        print(f"    {r['date']} {r['label']}: 3m return={ret_3m:+.1f}%")

    # Overall strategy / 整体策略
    print(f"\n{'─' * 80}")
    print("HYPOTHETICAL STRATEGY / 假设策略")
    buy_signals = [r for r in results if r["signal"] in ["STRONG BUY", "BUY"]]

    for horizon in ["1w", "1m", "3m", "6m"]:
        valid = [r for r in buy_signals if r["returns"].get(horizon) is not None]
        if valid:
            avg = sum(r["returns"][horizon] for r in valid) / len(valid)
            win_rate = len([r for r in valid if r["returns"][horizon] > 0]) / len(valid) * 100
            print(f"  {horizon.upper()}: {len(valid)} trades | Avg return: {avg:+.2f}% | Win rate: {win_rate:.0f}%")

    # Save / 保存
    output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backtest_extended_results.json")
    with open(output_file, "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nFull results saved to {output_file}")


if __name__ == "__main__":
    run_backtest()