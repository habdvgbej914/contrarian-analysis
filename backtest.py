"""
Contrarian Framework Backtest / 逆向框架历史回测
Tests the framework's structural judgments against actual SPY price movements
at historically significant moments.

用法: python3 backtest.py
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import json
import os

# Import framework logic / 导入框架逻辑
from contrarian_analysis_mcp import run_analysis, detect_mislocation, CRITERIA

# ============================================================
# Historical Test Cases / 历史测试案例
# Each case represents a moment when an investor might ask:
# "Should I buy SPY right now?"
# 每个案例代表投资者可能问"现在应该买SPY吗？"的时刻
# ============================================================

TEST_CASES = [
    {
        "date": "2020-03-23",
        "label": "COVID Crash Bottom / 疫情暴跌底部",
        "description": "SPY hit $218, down 34% from high. Pandemic panic at peak. Fed emergency rate cut to zero.",
        "judgments": {
            # C1: Trend - US economy long-term growth intact despite pandemic
            "c1": 1,  # aligned: pandemic is temporary, US economy will recover
            # C2: Energy - extreme fear, VIX at 82, but Fed printing money
            "c2": 1,  # accumulating: unprecedented monetary stimulus being deployed
            # C3: Incumbents - everyone selling in panic, maximum fear
            "c3": 0,  # misaligned: institutions dumping at worst possible time
            # C4: Can sustain - if you have cash and 12+ month horizon
            "c4": 1,  # can sustain
            # C5: Fundamentals - S&P 500 companies are real, profitable businesses
            "c5": 1,  # solid: temporary earnings hit, not permanent destruction
            # C6: Heavy - index investing is easy
            "c6": 0,  # light: anyone can buy SPY
        },
        "framework_reasoning": "Form-flow mislocation: real businesses exist (form) but panic removes all attention (no flow). Classic contrarian entry."
    },
    {
        "date": "2020-09-02",
        "label": "Post-COVID Tech Euphoria / 疫情后科技狂热",
        "description": "SPY hit $356, full recovery + new highs. Tech stocks euphoric. 'Stocks only go up' narrative.",
        "judgments": {
            "c1": 1,  # aligned: recovery underway
            "c2": 1,  # accumulating: massive liquidity
            "c3": 1,  # matched: everyone is buying, correctly positioned
            "c4": 1,  # can sustain
            "c5": 1,  # solid: earnings recovering
            "c6": 0,  # light
        },
        "framework_reasoning": "No mislocation. Both form and flow present. Mainstream opportunity - no contrarian edge."
    },
    {
        "date": "2022-01-03",
        "label": "Pre-Rate-Hike Peak / 加息前高点",
        "description": "SPY at $477, all-time high. Fed about to start aggressive rate hikes. Inflation at 7%.",
        "judgments": {
            "c1": 0,  # misaligned: rising rates are headwind for equities
            "c2": 0,  # dissipating: liquidity about to be withdrawn
            "c3": 1,  # matched: bulls still buying at highs
            "c4": 1,  # can sustain
            "c5": 1,  # solid: companies still profitable
            "c6": 0,  # light
        },
        "framework_reasoning": "Momentum turning negative. Trend misaligned with rate cycle. Framework says caution, not entry."
    },
    {
        "date": "2022-06-16",
        "label": "Mid-2022 Rate Hike Fear / 2022年中加息恐惧",
        "description": "SPY at $366, down 24% from peak. 75bp rate hike. Recession fears. Bear market declared.",
        "judgments": {
            "c1": 0,  # misaligned: rate hikes ongoing, more coming
            "c2": 0,  # dissipating: liquidity withdrawal accelerating
            "c3": 0,  # misaligned: panic selling, but for valid reasons
            "c4": 1,  # can sustain
            "c5": 1,  # solid: companies still making money
            "c6": 0,  # light
        },
        "framework_reasoning": "Weak momentum + solid substance = potential undervalued opportunity. But trend still against. Framework says: wait for trend alignment signal."
    },
    {
        "date": "2022-10-12",
        "label": "2022 Bear Market Bottom / 2022年熊市底部",
        "description": "SPY at $348, down 27% from peak. Peak pessimism. CPI still high but showing signs of peaking.",
        "judgments": {
            "c1": 0,  # misaligned: rates still rising, but inflation peaking
            "c2": 1,  # accumulating: smart money starting to position, worst priced in
            "c3": 0,  # misaligned: consensus says more downside, 'don't catch falling knife'
            "c4": 1,  # can sustain
            "c5": 1,  # solid
            "c6": 0,  # light
        },
        "framework_reasoning": "Counter-trend but energy accumulating. Potential contrarian opportunity. Incumbents misaligned (too bearish). Framework gives cautious green light."
    },
    {
        "date": "2023-10-27",
        "label": "Late 2023 Bond Scare / 2023年末债券恐慌",
        "description": "SPY at $409, 10Y yield hit 5%. 'Higher for longer' panic. Market fears Fed overtightening.",
        "judgments": {
            "c1": 1,  # aligned: economy surprisingly resilient, AI boom starting
            "c2": 1,  # accumulating: corporate earnings beating expectations
            "c3": 0,  # misaligned: market focused on rates, missing earnings strength
            "c4": 1,  # can sustain
            "c5": 1,  # solid: best earnings growth in quarters
            "c6": 0,  # light
        },
        "framework_reasoning": "Strong momentum + solid substance + incumbents misaligned = highest conviction entry. Market panic about rates while earnings accelerate."
    },
    {
        "date": "2024-08-05",
        "label": "Yen Carry Trade Unwind / 日元套利交易崩盘",
        "description": "SPY flash crash to $510. Japan rate hike triggered global carry trade unwind. VIX spiked to 65.",
        "judgments": {
            "c1": 1,  # aligned: US economy strong, AI investment accelerating
            "c2": 1,  # accumulating: technical crash, not fundamental
            "c3": 0,  # misaligned: mechanical forced selling, not fundamental reassessment
            "c4": 1,  # can sustain
            "c5": 1,  # solid: nothing changed in corporate fundamentals
            "c6": 0,  # light
        },
        "framework_reasoning": "Extreme form-flow dislocation caused by technical event. Form intact, flow disrupted mechanically. Framework says: strong buy."
    },
    {
        "date": "2025-03-13",
        "label": "Tariff War Escalation / 关税战升级",
        "description": "SPY dropped to ~$545 on Trump tariff escalation + China retaliation. Trade war fears.",
        "judgments": {
            "c1": 1,  # aligned: US economy still growing, AI capex continues
            "c2": 0,  # dissipating: uncertainty causing capital withdrawal
            "c3": 0,  # misaligned: fear-driven selling
            "c4": 1,  # can sustain
            "c5": 1,  # solid: corporate earnings still strong
            "c6": 0,  # light
        },
        "framework_reasoning": "Trend aligned but energy dissipating. Momentum weakening. Framework says: opportunity exists but wait for energy to stabilize."
    },
]


def run_backtest():
    """Run the complete backtest / 运行完整回测"""

    print("Downloading SPY historical data... / 下载SPY历史数据...")
    spy = yf.download("SPY", start="2020-01-01", end="2026-03-28", progress=False)

    if spy.empty:
        print("ERROR: Could not download SPY data. Check internet connection.")
        return

    # Flatten multi-level columns if present
    if isinstance(spy.columns, pd.MultiIndex):
        spy.columns = spy.columns.get_level_values(0)

    print(f"Downloaded {len(spy)} trading days of data.\n")

    results = []
    print("=" * 80)
    print("CONTRARIAN FRAMEWORK BACKTEST: SPY")
    print("逆向框架历史回测：SPY")
    print("=" * 80)

    for case in TEST_CASES:
        date_str = case["date"]
        target_date = pd.Timestamp(date_str)

        # Find closest trading day / 找到最近的交易日
        available_dates = spy.index[spy.index >= target_date]
        if len(available_dates) == 0:
            print(f"\nSkipping {date_str}: no data available")
            continue
        actual_date = available_dates[0]

        entry_price = float(spy.loc[actual_date, "Close"])

        # Calculate returns at different horizons / 计算不同周期的收益率
        horizons = {"1w": 5, "1m": 21, "3m": 63, "6m": 126}
        returns = {}

        for label, days in horizons.items():
            future_dates = spy.index[spy.index > actual_date]
            if len(future_dates) > days:
                future_price = float(spy.iloc[spy.index.get_loc(actual_date) + days]["Close"])
                ret = (future_price - entry_price) / entry_price * 100
                returns[label] = round(ret, 2)
            else:
                returns[label] = None

        # Run framework analysis / 运行框架分析
        analysis = run_analysis(f"SPY @ {date_str}", case["judgments"])

        # Determine framework signal / 确定框架信号
        binary = analysis["binary_code"]
        momentum = analysis["cross_layer"]["momentum"]
        substance = analysis["cross_layer"]["substance"]
        mislocation = analysis["mislocation"]["type"]

        # Framework recommendation / 框架建议
        if mislocation == "form_without_flow" and momentum == "strong":
            signal = "STRONG BUY"
        elif mislocation == "form_without_flow" and momentum == "weak":
            signal = "WATCH (form-flow mislocation but momentum weak)"
        elif momentum == "strong" and substance == "solid":
            if case["judgments"]["c3"] == 0:  # incumbents misaligned
                signal = "BUY"
            else:
                signal = "HOLD (no contrarian edge)"
        elif momentum == "weak" and substance == "solid":
            signal = "WATCH (undervalued but momentum weak)"
        elif momentum == "weak" and substance == "hollow":
            signal = "AVOID"
        else:
            signal = "NEUTRAL"

        # Print result / 打印结果
        print(f"\n{'─' * 70}")
        print(f"📅 {date_str} | {case['label']}")
        print(f"   Entry Price: ${entry_price:.2f}")
        print(f"   Binary: {binary} | Signal: {signal}")
        print(f"   Momentum: {momentum} | Substance: {substance} | Mislocation: {mislocation}")
        print(f"   Reasoning: {case['framework_reasoning']}")
        print(f"   Returns:  1w={returns.get('1w', 'N/A')}%  |  1m={returns.get('1m', 'N/A')}%  |  3m={returns.get('3m', 'N/A')}%  |  6m={returns.get('6m', 'N/A')}%")

        # Grade the call / 评估判断
        if returns.get("3m") is not None:
            if signal in ["STRONG BUY", "BUY"] and returns["3m"] > 0:
                grade = "✅ CORRECT"
            elif signal in ["STRONG BUY", "BUY"] and returns["3m"] <= 0:
                grade = "❌ WRONG"
            elif signal in ["AVOID", "WATCH (undervalued but momentum weak)"] and returns["3m"] <= 0:
                grade = "✅ CORRECT"
            elif signal in ["AVOID", "WATCH (undervalued but momentum weak)"] and returns["3m"] > 0:
                grade = "❌ MISSED"
            elif signal in ["HOLD (no contrarian edge)", "NEUTRAL"]:
                grade = "⚪ NEUTRAL (no strong signal)"
            else:
                grade = "⚪ NEUTRAL"
        else:
            grade = "⏳ PENDING"

        print(f"   3-Month Grade: {grade}")

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
            "grade": grade
        })

    # Summary / 总结
    print(f"\n{'=' * 80}")
    print("BACKTEST SUMMARY / 回测总结")
    print(f"{'=' * 80}")

    total = len([r for r in results if "PENDING" not in r["grade"]])
    correct = len([r for r in results if "CORRECT" in r["grade"]])
    wrong = len([r for r in results if "WRONG" in r["grade"]])
    missed = len([r for r in results if "MISSED" in r["grade"]])
    neutral = len([r for r in results if "NEUTRAL" in r["grade"]])

    print(f"\nTotal judgments: {total}")
    print(f"Correct: {correct}")
    print(f"Wrong: {wrong}")
    print(f"Missed opportunities: {missed}")
    print(f"Neutral (no strong signal): {neutral}")
    if total - neutral > 0:
        accuracy = correct / (total - neutral) * 100
        print(f"\nAccuracy (excluding neutrals): {accuracy:.1f}%")

    # Calculate hypothetical returns / 计算假设收益
    print(f"\n{'─' * 70}")
    print("HYPOTHETICAL STRATEGY / 假设策略")
    print("If you followed every BUY/STRONG BUY signal with equal weight:")
    buy_signals = [r for r in results if r["signal"] in ["STRONG BUY", "BUY"] and r["returns"].get("3m") is not None]
    if buy_signals:
        avg_return_3m = sum(r["returns"]["3m"] for r in buy_signals) / len(buy_signals)
        avg_return_6m_list = [r["returns"]["6m"] for r in buy_signals if r["returns"].get("6m") is not None]
        avg_return_6m = sum(avg_return_6m_list) / len(avg_return_6m_list) if avg_return_6m_list else 0
        print(f"  Number of trades: {len(buy_signals)}")
        print(f"  Average 3-month return: {avg_return_3m:.2f}%")
        print(f"  Average 6-month return: {avg_return_6m:.2f}%")

    # Save results / 保存结果
    output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backtest_results.json")
    with open(output_file, "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nFull results saved to {output_file}")
    print(f"完整结果已保存至 {output_file}")


if __name__ == "__main__":
    run_backtest()