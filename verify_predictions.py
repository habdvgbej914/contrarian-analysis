"""
FCAS Auto-Verifier v0.3 / 气象分析自动验证器
Force Configuration Analysis System
Checks past predictions against actual market prices.
Grades based on intent assessment (seek_profit).

用法: python3 verify_predictions.py
"""

import os
import json
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
import requests

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SCAN_HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "daily_scan_history.json")
VERIFICATION_REPORT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "verification_report.json")

TICKER_MAP = {"GLD": "GLD", "SLV": "SLV", "SPY": "SPY", "QQQ": "QQQ", "XLE": "XLE", "COPX": "COPX"}
HORIZONS = {"1w": 7, "1m": 30, "3m": 90}

# Intent assessments classified for grading
# "strongly_supported" and "supported_with_resistance" → expect positive returns
# "not_viable" and "challenged" → expect negative or flat returns
# Others → neutral, not graded directionally
POSITIVE_INTENTS = {"strongly_supported", "supported_with_resistance", "supported_but_weak", "contested"}
NEGATIVE_INTENTS = {"not_viable", "challenged"}
NEUTRAL_INTENTS = {"possible_but_unsupported", "indirect_path", "dormant", "uncertain"}


def load_scan_history():
    try:
        with open(SCAN_HISTORY_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_scan_history(history):
    with open(SCAN_HISTORY_FILE, "w") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def get_price_on_date(ticker, target_date):
    try:
        start = target_date - timedelta(days=5)
        end = target_date + timedelta(days=5)
        data = yf.download(ticker, start=start.strftime("%Y-%m-%d"),
                          end=end.strftime("%Y-%m-%d"), progress=False)
        if data.empty:
            return None
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        available = data.index[data.index >= pd.Timestamp(target_date)]
        if len(available) > 0:
            return float(data.loc[available[0], "Close"])
        available = data.index[data.index < pd.Timestamp(target_date)]
        if len(available) > 0:
            return float(data.loc[available[-1], "Close"])
        return None
    except Exception as e:
        print(f"  Error fetching {ticker} price for {target_date}: {e}")
        return None


def parse_entry_price(price_str):
    if not price_str or price_str == "N/A":
        return None
    clean = price_str.replace("$", "").replace(",", "").replace("~", "").strip()
    if "-" in clean:
        parts = clean.split("-")
        try:
            return (float(parts[0].strip().replace("$", "")) +
                    float(parts[1].strip().replace("$", ""))) / 2
        except ValueError:
            pass
    clean = clean.split("(")[0].strip()
    clean = clean.split(" ")[0].strip()
    try:
        return float(clean)
    except ValueError:
        return None


def get_intent_assessment(record):
    """Extract intent assessment from record, handling both old and new formats"""
    # New format: intent dict with "overall" key
    intent = record.get("intent", {})
    if isinstance(intent, dict) and "overall" in intent:
        return intent["overall"]

    # Old format: signal field (BUY/SELL etc) — convert to closest intent equivalent
    signal = record.get("signal", "")
    if signal in ["STRONG BUY", "BUY"]:
        return "strongly_supported"
    elif signal in ["AVOID"]:
        return "not_viable"
    elif signal in ["WATCH", "CAUTION"]:
        return "possible_but_unsupported"
    elif signal in ["HOLD"]:
        return "indirect_path"
    return "uncertain"


def grade_prediction(intent_assessment, return_pct):
    """Grade based on intent assessment and actual return"""
    if return_pct is None:
        return "PENDING"

    if intent_assessment in POSITIVE_INTENTS:
        return "CORRECT" if return_pct > 0 else "WRONG"
    elif intent_assessment in NEGATIVE_INTENTS:
        return "CORRECT" if return_pct <= 0 else "MISSED"
    else:
        return "NEUTRAL"


def verify_predictions():
    today = datetime.now().date()
    history = load_scan_history()

    if not history:
        print("No scan history found. Run daily_scan.py first.")
        return

    print(f"{'=' * 70}")
    print(f"FCAS AUTO-VERIFIER v0.3")
    print(f"Date: {today}")
    print(f"Total records to check: {len(history)}")
    print(f"{'=' * 70}")

    updated_count = 0
    newly_verified = []

    for record in history:
        ticker = record.get("ticker", "")
        scan_date_str = record.get("date", "")
        verification = record.get("verification", {})

        if not ticker or not scan_date_str:
            continue

        yf_ticker = TICKER_MAP.get(ticker)
        if not yf_ticker:
            continue

        try:
            scan_date = datetime.strptime(scan_date_str, "%Y-%m-%d").date()
        except ValueError:
            continue

        entry_price = parse_entry_price(record.get("price_estimate", ""))
        if entry_price is None:
            entry_price = get_price_on_date(yf_ticker, scan_date)
            if entry_price:
                record["entry_price_actual"] = entry_price

        if entry_price is None:
            continue

        intent_assessment = get_intent_assessment(record)

        for horizon_label, days in HORIZONS.items():
            target_date = scan_date + timedelta(days=days)
            date_key = f"{horizon_label}_date"
            price_key = f"{horizon_label}_price"
            return_key = f"{horizon_label}_return"
            grade_key = f"{horizon_label}_grade"

            if verification.get(return_key) is not None:
                continue

            if target_date > today:
                continue

            actual_price = get_price_on_date(yf_ticker, target_date)
            if actual_price is None:
                continue

            return_pct = round((actual_price - entry_price) / entry_price * 100, 2)
            grade = grade_prediction(intent_assessment, return_pct)

            verification[date_key] = target_date.strftime("%Y-%m-%d")
            verification[price_key] = actual_price
            verification[return_key] = return_pct
            verification[grade_key] = grade

            record["verification"] = verification
            updated_count += 1

            icon = {"CORRECT": "✅", "WRONG": "❌", "MISSED": "⚠️",
                    "NEUTRAL": "⚪", "PENDING": "⏳"}.get(grade, "⚪")

            intent_short = intent_assessment.upper().replace("_", " ")
            newly_verified.append({
                "ticker": ticker,
                "scan_date": scan_date_str,
                "horizon": horizon_label,
                "intent": intent_short,
                "entry_price": entry_price,
                "actual_price": actual_price,
                "return_pct": return_pct,
                "grade": grade,
                "icon": icon
            })

            print(f"  {icon} {ticker} {scan_date_str} | {horizon_label}: "
                  f"Entry ${entry_price:.2f} → ${actual_price:.2f} = {return_pct:+.2f}% "
                  f"| Intent: {intent_short} | Grade: {grade}")

    save_scan_history(history)

    report = generate_report(history)
    with open(VERIFICATION_REPORT_FILE, "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 70}")
    print("VERIFICATION SUMMARY / 验证总结")
    print(f"{'=' * 70}")
    print(f"  Records updated this run: {updated_count}")

    if report["total_verified"] > 0:
        print(f"\n  OVERALL:")
        print(f"    Total verified: {report['total_verified']}")
        print(f"    Correct: {report['correct']} | Wrong: {report['wrong']} | Missed: {report['missed']} | Neutral: {report['neutral']}")
        if report["actionable_total"] > 0:
            print(f"    Actionable accuracy: {report['actionable_accuracy']:.1f}%")

        for horizon in ["1w", "1m", "3m"]:
            h = report["by_horizon"].get(horizon, {})
            if h.get("total", 0) > 0:
                print(f"\n  {horizon.upper()} HORIZON:")
                if h["positive_total"] > 0:
                    print(f"    Positive intents: {h['positive_total']} | Correct: {h['positive_correct']} | Accuracy: {h['positive_accuracy']:.1f}%")
                    print(f"    Avg return: {h['positive_avg_return']:+.2f}%")
                if h["negative_total"] > 0:
                    print(f"    Negative intents: {h['negative_total']} | Correct: {h['negative_correct']} | Accuracy: {h['negative_accuracy']:.1f}%")

        for ticker in report["by_ticker"]:
            t = report["by_ticker"][ticker]
            if t["total"] > 0:
                print(f"\n  {ticker}: {t['total']} verified | Correct: {t['correct']} | Avg return (positive): {t['positive_avg_return']:+.2f}%")

    if newly_verified:
        send_verification_telegram(newly_verified, report)

    return report


def generate_report(history):
    report = {
        "generated": datetime.now().isoformat(),
        "total_records": len(history),
        "total_verified": 0,
        "correct": 0, "wrong": 0, "missed": 0, "neutral": 0,
        "actionable_total": 0, "actionable_accuracy": 0,
        "by_horizon": {}, "by_ticker": {}
    }

    for horizon in ["1w", "1m", "3m"]:
        report["by_horizon"][horizon] = {
            "total": 0,
            "positive_total": 0, "positive_correct": 0, "positive_accuracy": 0, "positive_returns": [],
            "negative_total": 0, "negative_correct": 0, "negative_accuracy": 0,
            "positive_avg_return": 0,
        }

    for record in history:
        ticker = record.get("ticker", "")
        verification = record.get("verification", {})
        intent_assessment = get_intent_assessment(record)

        if ticker not in report["by_ticker"]:
            report["by_ticker"][ticker] = {
                "total": 0, "correct": 0, "wrong": 0,
                "positive_avg_return": 0, "positive_returns": []
            }

        for horizon in ["1w", "1m", "3m"]:
            grade = verification.get(f"{horizon}_grade")
            return_pct = verification.get(f"{horizon}_return")

            if grade is None or grade == "PENDING":
                continue

            report["total_verified"] += 1
            report["by_horizon"][horizon]["total"] += 1
            report["by_ticker"][ticker]["total"] += 1

            if grade == "CORRECT":
                report["correct"] += 1
                report["by_ticker"][ticker]["correct"] += 1
            elif grade == "WRONG":
                report["wrong"] += 1
                report["by_ticker"][ticker]["wrong"] += 1
            elif grade == "MISSED":
                report["missed"] += 1
            elif grade == "NEUTRAL":
                report["neutral"] += 1

            h = report["by_horizon"][horizon]
            if intent_assessment in POSITIVE_INTENTS:
                h["positive_total"] += 1
                if grade == "CORRECT":
                    h["positive_correct"] += 1
                if return_pct is not None:
                    h["positive_returns"].append(return_pct)
                    report["by_ticker"][ticker]["positive_returns"].append(return_pct)
            elif intent_assessment in NEGATIVE_INTENTS:
                h["negative_total"] += 1
                if grade == "CORRECT":
                    h["negative_correct"] += 1

    actionable = report["correct"] + report["wrong"]
    report["actionable_total"] = actionable
    report["actionable_accuracy"] = (report["correct"] / actionable * 100) if actionable > 0 else 0

    for horizon in ["1w", "1m", "3m"]:
        h = report["by_horizon"][horizon]
        h["positive_accuracy"] = (h["positive_correct"] / h["positive_total"] * 100) if h["positive_total"] > 0 else 0
        h["positive_avg_return"] = (sum(h["positive_returns"]) / len(h["positive_returns"])) if h["positive_returns"] else 0
        h["negative_accuracy"] = (h["negative_correct"] / h["negative_total"] * 100) if h["negative_total"] > 0 else 0

    for ticker in report["by_ticker"]:
        t = report["by_ticker"][ticker]
        t["positive_avg_return"] = (sum(t["positive_returns"]) / len(t["positive_returns"])) if t["positive_returns"] else 0

    return report


def send_verification_telegram(newly_verified, report):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return

    lines = ["📋 *Verification Update v0.3*", ""]
    for v in newly_verified:
        lines.append(
            f"{v['icon']} {v['ticker']} ({v['scan_date']}) {v['horizon']}: "
            f"{v['return_pct']:+.1f}% | {v['intent']} → {v['grade']}"
        )

    if report["actionable_total"] > 0:
        lines.extend(["", f"📊 Accuracy: {report['actionable_accuracy']:.1f}% ({report['correct']}/{report['actionable_total']})"])

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": "\n".join(lines),
            "parse_mode": "Markdown"
        }, timeout=30)
        print("  Verification Telegram sent.")
    except Exception as e:
        print(f"  Telegram error: {e}")


if __name__ == "__main__":
    verify_predictions()