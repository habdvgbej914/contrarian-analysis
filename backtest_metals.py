"""
Contrarian Framework Backtest: Precious Metals & Base Metals
逆向框架回测：贵金属与有色金属
Tests GLD (Gold ETF) and COPX (Copper Miners ETF)

用法: python3 backtest_metals.py
"""

import yfinance as yf
import pandas as pd
import json
import os

from contrarian_analysis_mcp import run_analysis

# ============================================================
# GLD (Gold) Test Cases / 黄金测试案例
# ============================================================

GLD_CASES = [
    {
        "date": "2008-10-24",
        "label": "Financial Crisis Gold Selloff / 金融危机黄金抛售",
        "description": "Gold sold off with everything in liquidity crisis despite being safe haven.",
        "judgments": {
            "c1": 1,  # aligned: financial crisis = safe haven demand structural driver
            "c2": 1,  # accumulating: Fed printing money, dollar debasement beginning
            "c3": 0,  # misaligned: forced selling, margin calls, gold sold for liquidity
            "c4": 1,
            "c5": 1,  # solid: physical gold, ultimate store of value
            "c6": 1,  # heavy: mining, refining, physical custody infrastructure
        },
    },
    {
        "date": "2009-09-01",
        "label": "QE Gold Rally Start / QE黄金牛市启动",
        "description": "Fed QE in full swing, dollar weakening, gold beginning multi-year rally.",
        "judgments": {
            "c1": 1,  # aligned: monetary debasement driving gold
            "c2": 1,  # accumulating: central bank buying, ETF inflows
            "c3": 0,  # misaligned: mainstream still focused on equity recovery
            "c4": 1,
            "c5": 1,  # solid
            "c6": 1,  # heavy
        },
    },
    {
        "date": "2011-09-06",
        "label": "Gold Bubble Peak / 黄金泡沫顶部",
        "description": "Gold hit $1900, parabolic move. Everyone talking about $3000 gold.",
        "judgments": {
            "c1": 1,  # aligned: QE still ongoing
            "c2": 1,  # accumulating: but euphoric, not quiet
            "c3": 1,  # matched: everyone is buying gold, no contrarian edge
            "c4": 1,
            "c5": 1,  # solid: gold is still gold
            "c6": 1,  # heavy
        },
    },
    {
        "date": "2013-04-15",
        "label": "Gold Crash / 黄金崩盘",
        "description": "Gold crashed 13% in two days. Cyprus gold sale rumors, taper talk.",
        "judgments": {
            "c1": 0,  # misaligned: taper talk = less money printing = gold headwind
            "c2": 0,  # dissipating: massive ETF outflows, GLD losing tonnage
            "c3": 0,  # misaligned: panic selling
            "c4": 1,
            "c5": 1,  # solid: physical gold unchanged
            "c6": 1,  # heavy
        },
    },
    {
        "date": "2015-12-17",
        "label": "First Fed Rate Hike / 首次加息",
        "description": "Fed raised rates for first time since 2006. Gold at multi-year low $1050.",
        "judgments": {
            "c1": 0,  # misaligned: rate hikes = strong dollar = gold headwind
            "c2": 1,  # accumulating: maximum pessimism on gold, central banks quietly buying
            "c3": 0,  # misaligned: consensus says gold is dead, rates going higher
            "c4": 1,
            "c5": 1,  # solid: physical gold at production cost floor
            "c6": 1,  # heavy
        },
    },
    {
        "date": "2018-08-16",
        "label": "Gold Bear Market Low / 黄金熊市低点",
        "description": "Gold hit $1160, strong dollar, EM crisis, no one wants gold.",
        "judgments": {
            "c1": 0,  # misaligned: strong dollar, rate hikes
            "c2": 1,  # accumulating: central banks record buying, price near production cost
            "c3": 0,  # misaligned: consensus bearish, positioned short
            "c4": 1,
            "c5": 1,  # solid
            "c6": 1,  # heavy
        },
    },
    {
        "date": "2020-03-19",
        "label": "COVID Gold Selloff / 疫情黄金抛售",
        "description": "Gold sold off in COVID panic despite being safe haven. Liquidity crisis repeat of 2008.",
        "judgments": {
            "c1": 1,  # aligned: unlimited QE announced, ultimate gold catalyst
            "c2": 1,  # accumulating: forced selling creating opportunity
            "c3": 0,  # misaligned: selling for liquidity, not fundamentals
            "c4": 1,
            "c5": 1,  # solid
            "c6": 1,  # heavy
        },
    },
    {
        "date": "2020-08-06",
        "label": "Gold All-Time High / 黄金历史新高",
        "description": "Gold broke $2000 for first time. Massive QE, negative real rates, everyone buying.",
        "judgments": {
            "c1": 1,  # aligned: QE infinity
            "c2": 1,  # accumulating: but getting euphoric
            "c3": 1,  # matched: consensus bullish, everyone in
            "c4": 1,
            "c5": 1,  # solid
            "c6": 1,  # heavy
        },
    },
    {
        "date": "2022-09-28",
        "label": "Strong Dollar Gold Selloff / 强美元黄金抛售",
        "description": "Gold at $1620, hammered by strongest dollar in 20 years and rate hikes.",
        "judgments": {
            "c1": 0,  # misaligned: rate hikes, strong dollar
            "c2": 1,  # accumulating: central banks buying record amounts despite price drop
            "c3": 0,  # misaligned: institutional selling, but central banks doing opposite
            "c4": 1,
            "c5": 1,  # solid
            "c6": 1,  # heavy
        },
    },
    {
        "date": "2023-10-06",
        "label": "Pre-Rally Base / 大涨前底部",
        "description": "Gold at $1820 after months of consolidation. 10Y yield at 4.8%. No one bullish on gold.",
        "judgments": {
            "c1": 1,  # aligned: fiscal deficits exploding, de-dollarization accelerating
            "c2": 1,  # accumulating: BRICS buying, China/India central banks accumulating
            "c3": 0,  # misaligned: Western institutions still selling, missing central bank bid
            "c4": 1,
            "c5": 1,  # solid
            "c6": 1,  # heavy
        },
    },
    {
        "date": "2024-03-08",
        "label": "Gold Breakout / 黄金突破",
        "description": "Gold broke above $2100 to new all-time high. BRICS + central bank buying.",
        "judgments": {
            "c1": 1,  # aligned: de-dollarization + fiscal crisis narrative
            "c2": 1,  # accumulating: breakout momentum
            "c3": 0,  # misaligned: Western funds still underweight, chasing tech
            "c4": 1,
            "c5": 1,  # solid
            "c6": 1,  # heavy
        },
    },
    {
        "date": "2025-10-15",
        "label": "Gold After Tariff Surge / 关税后黄金飙升",
        "description": "Gold surged on trade war + geopolitical uncertainty. Safe haven bid.",
        "judgments": {
            "c1": 1,  # aligned: deglobalization = gold positive
            "c2": 1,  # accumulating: record central bank demand
            "c3": 1,  # matched: now everyone is bullish on gold
            "c4": 1,
            "c5": 1,  # solid
            "c6": 1,  # heavy
        },
    },
    {
        "date": "2026-01-29",
        "label": "Gold Peak ~$2800 / 黄金高点约$2800",
        "description": "GLD at all-time high ~$496. Maximum bullishness.",
        "judgments": {
            "c1": 1,  # aligned
            "c2": 1,  # accumulating
            "c3": 1,  # matched: consensus very bullish
            "c4": 1,
            "c5": 1,  # solid
            "c6": 1,  # heavy
        },
    },
    {
        "date": "2026-03-10",
        "label": "Gold Correction Iran War / 黄金回调伊朗冲突",
        "description": "Gold pulled back from highs despite Iran war. Profit taking + margin calls.",
        "judgments": {
            "c1": 1,  # aligned: war should support gold
            "c2": 0,  # dissipating: profit taking, some forced selling
            "c3": 0,  # misaligned: short-term traders exiting
            "c4": 1,
            "c5": 1,  # solid
            "c6": 1,  # heavy
        },
    },
]

# ============================================================
# COPX (Copper) Test Cases / 铜矿测试案例
# ============================================================

COPX_CASES = [
    {
        "date": "2020-03-23",
        "label": "COVID Copper Crash / 疫情铜价崩盘",
        "description": "Copper crashed on demand destruction fears. Industrial metals devastated.",
        "judgments": {
            "c1": 0,  # misaligned: demand destruction, global shutdown
            "c2": 1,  # accumulating: China stimulus coming, supply constrained
            "c3": 0,  # misaligned: everyone dumping cyclicals
            "c4": 1,
            "c5": 1,  # solid: copper essential for everything
            "c6": 1,  # heavy: mining is ultimate heavy industry
        },
    },
    {
        "date": "2021-05-10",
        "label": "Copper All-Time High / 铜价历史新高",
        "description": "Copper hit $4.80/lb. Green energy narrative, supercycle talk everywhere.",
        "judgments": {
            "c1": 1,  # aligned: electrification megatrend
            "c2": 1,  # accumulating
            "c3": 1,  # matched: everyone is bullish copper supercycle
            "c4": 1,
            "c5": 1,  # solid
            "c6": 1,  # heavy
        },
    },
    {
        "date": "2022-07-15",
        "label": "Copper Recession Fear Crash / 铜价衰退恐惧暴跌",
        "description": "Copper crashed 30% from peak on China lockdowns + global recession fears.",
        "judgments": {
            "c1": 0,  # misaligned: recession fears, China lockdowns
            "c2": 0,  # dissipating: demand uncertainty
            "c3": 0,  # misaligned: Dr. Copper signaling recession
            "c4": 1,
            "c5": 1,  # solid: structural deficit still building
            "c6": 1,  # heavy
        },
    },
    {
        "date": "2023-10-23",
        "label": "Copper Low Before AI Demand / AI需求前铜价低点",
        "description": "Copper depressed at $3.60. Market ignoring AI data center power demand for copper.",
        "judgments": {
            "c1": 1,  # aligned: electrification + AI power demand = structural driver
            "c2": 1,  # accumulating: supply deficit growing, mines depleting
            "c3": 0,  # misaligned: market focused on China weakness, missing AI demand
            "c4": 1,
            "c5": 1,  # solid: physical deficit
            "c6": 1,  # heavy
        },
    },
    {
        "date": "2024-05-20",
        "label": "Copper Squeeze / 铜价逼空",
        "description": "Copper spiked to $5.10 on short squeeze. AI + electrification narrative peaked.",
        "judgments": {
            "c1": 1,  # aligned
            "c2": 1,  # accumulating: but getting euphoric
            "c3": 1,  # matched: everyone talking copper supercycle again
            "c4": 1,
            "c5": 1,  # solid
            "c6": 1,  # heavy
        },
    },
    {
        "date": "2025-03-13",
        "label": "Copper Tariff Fear / 铜关税恐惧",
        "description": "Copper miners sold off on tariff war escalation + China demand concerns.",
        "judgments": {
            "c1": 1,  # aligned: long-term electrification intact
            "c2": 0,  # dissipating: tariff uncertainty, China slowdown fears
            "c3": 0,  # misaligned: selling on trade war fear, structural deficit ignored
            "c4": 1,
            "c5": 1,  # solid
            "c6": 1,  # heavy
        },
    },
    {
        "date": "2026-03-10",
        "label": "Copper Iran War Selloff / 铜伊朗冲突抛售",
        "description": "COPX sold off on Iran war + recession fears + tariff retaliation.",
        "judgments": {
            "c1": 1,  # aligned: electrification megatrend unchanged
            "c2": 0,  # dissipating: war fear, demand uncertainty
            "c3": 0,  # misaligned: panic selling cyclicals
            "c4": 1,
            "c5": 1,  # solid: physical deficit growing
            "c6": 1,  # heavy
        },
    },
]


def run_single_backtest(ticker, cases, label):
    """Run backtest for a single ticker / 对单一标的运行回测"""

    print(f"\nDownloading {ticker} data... / 下载{ticker}数据...")
    data = yf.download(ticker, start="2008-01-01", end="2026-03-28", progress=False)

    if data.empty:
        print(f"ERROR: Could not download {ticker} data.")
        return []

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    print(f"Downloaded {len(data)} trading days.\n")

    results = []
    print(f"{'=' * 85}")
    print(f"BACKTEST: {label} ({ticker})")
    print(f"{'=' * 85}")

    for case in cases:
        date_str = case["date"]
        target_date = pd.Timestamp(date_str)

        available_dates = data.index[data.index >= target_date]
        if len(available_dates) == 0:
            print(f"\nSkipping {date_str}: no data")
            continue
        actual_date = available_dates[0]
        entry_price = float(data.loc[actual_date, "Close"])

        horizons = {"1w": 5, "2w": 10, "1m": 21, "3m": 63, "6m": 126}
        returns = {}
        entry_idx = data.index.get_loc(actual_date)
        for h_label, days in horizons.items():
            if entry_idx + days < len(data):
                fp = float(data.iloc[entry_idx + days]["Close"])
                returns[h_label] = round((fp - entry_price) / entry_price * 100, 2)
            else:
                returns[h_label] = None

        analysis = run_analysis(f"{ticker} @ {date_str}", case["judgments"])
        binary = analysis["binary_code"]
        momentum = analysis["cross_layer"]["momentum"]
        substance = analysis["cross_layer"]["substance"]
        mislocation = analysis["mislocation"]["type"]

        # Signal logic / 信号逻辑
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

        # Grade / 评分
        grades = {}
        for h in ["1w", "1m", "3m"]:
            ret = returns.get(h)
            if ret is None:
                grades[h] = "PENDING"
            elif signal in ["STRONG BUY", "BUY"]:
                grades[h] = "CORRECT" if ret > 0 else "WRONG"
            elif signal == "AVOID":
                grades[h] = "CORRECT" if ret <= 0 else "MISSED"
            elif signal == "WATCH":
                grades[h] = "CORRECT" if ret <= 5 else "MISSED"
            elif signal in ["HOLD", "CAUTION"]:
                grades[h] = "NEUTRAL"
            else:
                grades[h] = "NEUTRAL"

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
            "ticker": ticker,
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

    return results


def print_summary(results, ticker, label):
    """Print summary for one ticker / 打印单一标的总结"""
    print(f"\n{'=' * 85}")
    print(f"SUMMARY: {label} ({ticker})")
    print(f"{'=' * 85}")

    for horizon in ["1w", "1m", "3m"]:
        actionable = [r for r in results if r["signal"] in ["STRONG BUY", "BUY"] and r["grades"][horizon] != "PENDING"]
        correct = len([r for r in actionable if r["grades"][horizon] == "CORRECT"])
        wrong = len([r for r in actionable if r["grades"][horizon] == "WRONG"])
        total = len(actionable)
        acc = correct / total * 100 if total > 0 else 0
        print(f"\n  {horizon.upper()} — BUY/STRONG BUY signals:")
        print(f"    Total: {total} | Correct: {correct} | Wrong: {wrong} | Accuracy: {acc:.1f}%")
        if actionable:
            avg = sum(r["returns"][horizon] for r in actionable if r["returns"].get(horizon) is not None) / len(actionable)
            print(f"    Average return: {avg:+.2f}%")

    # WATCH
    print(f"\n  WATCH signals:")
    for r in results:
        if r["signal"] == "WATCH":
            ret = r["returns"].get("3m", "N/A")
            status = "Avoided loss ✅" if isinstance(ret, (int, float)) and ret < 0 else "Missed gain ⚠️" if isinstance(ret, (int, float)) and ret > 10 else "Prudent hold ✅"
            print(f"    {r['date']} {r['label']}: 3m={ret}% — {status}")

    # HOLD
    print(f"\n  HOLD signals (no contrarian edge):")
    for r in results:
        if r["signal"] in ["HOLD", "CAUTION"]:
            ret = r["returns"].get("3m", "N/A")
            print(f"    {r['date']} {r['label']}: 3m={ret}%")

    # Strategy
    buy_signals = [r for r in results if r["signal"] in ["STRONG BUY", "BUY"]]
    print(f"\n  HYPOTHETICAL STRATEGY (BUY/STRONG BUY only):")
    for h in ["1w", "1m", "3m", "6m"]:
        valid = [r for r in buy_signals if r["returns"].get(h) is not None]
        if valid:
            avg = sum(r["returns"][h] for r in valid) / len(valid)
            wr = len([r for r in valid if r["returns"][h] > 0]) / len(valid) * 100
            print(f"    {h.upper()}: {len(valid)} trades | Avg: {avg:+.2f}% | Win rate: {wr:.0f}%")


def main():
    print("=" * 85)
    print("CONTRARIAN FRAMEWORK BACKTEST: PRECIOUS METALS & BASE METALS")
    print("逆向框架回测：贵金属与有色金属")
    print("=" * 85)

    # GLD Backtest
    gld_results = run_single_backtest("GLD", GLD_CASES, "Gold / 黄金")
    print_summary(gld_results, "GLD", "Gold / 黄金")

    # COPX Backtest
    copx_results = run_single_backtest("COPX", COPX_CASES, "Copper Miners / 铜矿")
    print_summary(copx_results, "COPX", "Copper Miners / 铜矿")

    # Combined summary
    all_results = gld_results + copx_results
    print(f"\n{'=' * 85}")
    print("COMBINED METALS SUMMARY / 贵金属+有色金属综合总结")
    print(f"{'=' * 85}")

    all_buy = [r for r in all_results if r["signal"] in ["STRONG BUY", "BUY"]]
    for h in ["1w", "1m", "3m", "6m"]:
        valid = [r for r in all_buy if r["returns"].get(h) is not None]
        if valid:
            correct = len([r for r in valid if r["returns"][h] > 0])
            avg = sum(r["returns"][h] for r in valid) / len(valid)
            wr = correct / len(valid) * 100
            print(f"  {h.upper()}: {len(valid)} trades | Correct: {correct} | Avg: {avg:+.2f}% | Win rate: {wr:.0f}%")

    # Save
    output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backtest_metals_results.json")
    with open(output_file, "w") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\nFull results saved to {output_file}")


if __name__ == "__main__":
    main()