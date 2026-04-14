#!/usr/bin/env python3
"""Convert all 37 Wind xlsx files to standardized JSON format."""

import json
import os
import re
from datetime import datetime, date

import openpyxl

XLSX_DIR = "data/xlsx"
JSON_DIR = "data/json"
os.makedirs(JSON_DIR, exist_ok=True)

# ── helpers ──────────────────────────────────────────────────────────────

def parse_date(val):
    """Convert various date formats to YYYY-MM-DD string."""
    if val is None:
        return None
    if isinstance(val, (datetime, date)):
        return val.strftime("%Y-%m-%d")
    s = str(val).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return s  # fallback


def to_float(val):
    """Convert to float or None."""
    if val is None:
        return None
    s = str(val).strip()
    if s in ("", "-", "--", "NA", "N/A", "None", "null"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def quarter_to_date(q_str):
    """Convert 'Q1 FY2015' → '2015-03-31', etc."""
    if q_str is None:
        return None
    s = str(q_str).strip()
    # Try direct date first
    d = parse_date(s)
    if re.match(r"\d{4}-\d{2}-\d{2}", str(d)):
        return d
    m = re.match(r"Q(\d)\s+FY(\d{4})", s)
    if m:
        q, y = int(m.group(1)), int(m.group(2))
        end_dates = {1: f"{y}-03-31", 2: f"{y}-06-30", 3: f"{y}-09-30", 4: f"{y}-12-31"}
        return end_dates.get(q)
    return None


def load_sheet(fname):
    """Load xlsx, return header row and data rows (excluding footer)."""
    fpath = os.path.join(XLSX_DIR, fname)
    wb = openpyxl.load_workbook(fpath, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    header = rows[0]
    data = []
    for row in rows[1:]:
        first = str(row[0]) if row[0] else ""
        if "数据来源" in first or "Wind" in first and "数据" in first:
            continue
        if all(v is None for v in row):
            continue
        data.append(row)
    return header, data


def save_json(records, out_name):
    """Save list of dicts as JSON."""
    path = os.path.join(JSON_DIR, out_name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    return path


# ── converters ───────────────────────────────────────────────────────────

def convert_stock_weekly(fname, en_name):
    """Convert stock weekly files (8 cols: date + 7 metrics)."""
    header, data = load_sheet(fname)
    records = []
    for row in data:
        d = parse_date(row[0])
        if not d:
            continue
        records.append({
            "date": d,
            "close": to_float(row[1]),
            "volume": to_float(row[2]),
            "turnover_billion": to_float(row[3]),
            "turnover_pct": to_float(row[4]),
            "weekly_return_pct": to_float(row[5]),
            "margin_balance_billion": to_float(row[6]),
            "northbound_holding": to_float(row[7]),
        })
    save_json(records, f"{en_name}_weekly.json")
    return en_name + "_weekly.json", records


def convert_quarterly(fname, en_name):
    """Convert quarterly financial data (paired value+time columns)."""
    header, data = load_sheet(fname)
    # Columns come in pairs: value, time (starting from col index 2)
    field_map = [
        ("revenue_billion", 2),
        ("net_profit_billion", 4),
        ("operating_cashflow_billion", 6),
        ("revenue_yoy_pct", 8),
        ("net_profit_yoy_pct", 10),
        ("gross_margin_pct", 12),
        ("debt_ratio_pct", 14),
        ("rd_ratio_pct", 16),
        ("pe_ratio", 18),
        ("pb_ratio", 20),
        ("institutional_holding_pct", 22),
    ]
    records = []
    for row in data:
        # Determine date from the first time column (col 3) or PE time (col 19)
        q_date = quarter_to_date(row[3])
        if not q_date:
            q_date = parse_date(row[19]) if len(row) > 19 else None
        if not q_date:
            continue
        rec = {"date": q_date}
        for field, col_idx in field_map:
            if col_idx < len(row):
                rec[field] = to_float(row[col_idx])
            else:
                rec[field] = None
        records.append(rec)
    save_json(records, f"{en_name}_quarterly.json")
    return en_name + "_quarterly.json", records


def convert_simple(fname, en_name, fields):
    """Convert simple 2+ column files."""
    header, data = load_sheet(fname)
    records = []
    for row in data:
        d = parse_date(row[0])
        if not d:
            continue
        rec = {"date": d}
        for i, field in enumerate(fields):
            rec[field] = to_float(row[i + 1]) if i + 1 < len(row) else None
        records.append(rec)
    save_json(records, f"{en_name}.json")
    return en_name + ".json", records


def convert_nonferrous_index(fname):
    """Special: filter 801050.SI rows, extract cols 8-9 (close + date)."""
    header, data = load_sheet(fname)
    records = []
    for row in data:
        if row[0] != "801050.SI":
            continue
        d = parse_date(row[8])  # date in col 9
        close = to_float(row[7])  # close in col 8
        if not d:
            continue
        records.append({"date": d, "close": close})
    save_json(records, "sw_nonferrous_metals_index.json")
    return "sw_nonferrous_metals_index.json", records


# ── file mapping ─────────────────────────────────────────────────────────

# 8 stocks - weekly
STOCKS = {
    "格力电器.xlsx": "gree",
    "中兴通讯.xlsx": "zte",
    "五粮液.xlsx": "wuliangye",
    "恒瑞医药.xlsx": "hengrui",
    "招商银行.xlsx": "cmb",
    "中国平安.xlsx": "ping_an",
    "中国石油.xlsx": "petrochina",
    "隆基绿能.xlsx": "longi",
}

# 8 stocks - quarterly
QUARTERLY = {
    "格力电器_季度财务数据_2015-2026.xlsx": "gree",
    "中兴通讯_季度财务数据_2015-2026.xlsx": "zte",
    "五粮液_季度财务数据_2015-2026.xlsx": "wuliangye",
    "恒瑞医药_季度财务数据_2015-2026.xlsx": "hengrui",
    "招商银行_季度财务数据_2015-2026.xlsx": "cmb",
    "中国平安_季度财务数据_2015-2026.xlsx": "ping_an",
    "中国石油_季度财务数据_2015-2026.xlsx": "petrochina",
    "隆基绿能_季度财务数据_2015-2026.xlsx": "longi",
}

# Simple files: (filename, en_name, field_list)
SIMPLE_FILES = [
    ("上证指数.xlsx", "sse_index", ["close"]),
    ("沪深300指数.xlsx", "csi300_index", ["close"]),
    ("科创50指数.xlsx", "star50_index", ["close"]),
    ("申万电子行业指数.xlsx", "sw_electronics_index", ["close"]),
    ("申万计算机行业指数.xlsx", "sw_computer_index", ["close"]),
    ("COMEX黄金期货.xlsx", "comex_gold", ["close_usd"]),
    ("上海金Au99.99每周五收盘价.xlsx", "shanghai_gold", ["close_cny"]),
    ("中国10年期国债收益率每周五数据.xlsx", "china_10y_bond_yield", ["yield_pct"]),
    ("两市融资余额.xlsx", "margin_balance", ["balance_trillion"]),
    ("美元兑人民币中间价.xlsx", "usdcny", ["mid_rate"]),
    ("北向资金周净流入（标准日期格式）.xlsx", "northbound_flow", ["net_inflow"]),
    ("CPI同比数据.xlsx", "cpi", ["cpi_yoy_pct", "cpi_cumulative_yoy_pct", "cpi_monthly_yoy_pct", "missing_flag"]),
    ("PPI同比数据.xlsx", "ppi", ["ppi_monthly_yoy_pct", "ppi_cumulative_yoy_pct"]),
    ("M2同比增速.xlsx", "m2", ["m2_yoy_pct", "broad_money_yoy_pct", "missing_flag"]),
    ("中国非制造业PMI.xlsx", "non_mfg_pmi", [
        "inventory_pct", "new_orders_pct", "business_activity_pct",
        "employment_pct", "backlog_orders_pct"
    ]),
    ("社会融资规模增量.xlsx", "social_financing", [
        "total_billion", "monthly_billion", "monthly_initial_billion",
        "total_anomaly", "monthly_anomaly", "monthly_initial_anomaly"
    ]),
    ("中国集成电路产量月度同比.xlsx", "ic_production", [
        "cumulative_yoy_pct", "monthly_yoy_pct",
        "cumulative_out_of_range", "monthly_out_of_range", "monthly_missing"
    ]),
    ("全球半导体销售额月度同比.xlsx", "global_semiconductor", [
        "yoy_pct", "quarterly_yoy_pct", "monthly_yoy_pct"
    ]),
]

# Files with special chars in name - need exact matching
SPECIAL_NAME_FILES = {
    "中国制造业PMI": ("mfg_pmi", ["pmi_pct"]),
    "中国央行黄金储备": ("pboc_gold_reserve", [
        "reserve_tons", "monthly_tons", "missing_flag"
    ]),
}


def find_file(partial_name):
    """Find file with potential hidden unicode chars."""
    for f in os.listdir(XLSX_DIR):
        clean = f.replace("\u200b", "").replace("\u200c", "").strip()
        if partial_name in clean and clean.endswith(".xlsx"):
            return f
    return None


# ── main ─────────────────────────────────────────────────────────────────

def main():
    results = []

    # 1. Stock weekly files
    for fname, en_name in STOCKS.items():
        out_name, records = convert_stock_weekly(fname, en_name)
        results.append((out_name, records))

    # 2. Quarterly files
    for fname, en_name in QUARTERLY.items():
        out_name, records = convert_quarterly(fname, en_name)
        results.append((out_name, records))

    # 3. Simple files
    for fname, en_name, fields in SIMPLE_FILES:
        actual_fname = fname
        if not os.path.exists(os.path.join(XLSX_DIR, fname)):
            actual_fname = find_file(fname.replace(".xlsx", ""))
            if not actual_fname:
                print(f"WARNING: {fname} not found, skipping")
                continue
        out_name, records = convert_simple(actual_fname, en_name, fields)
        results.append((out_name, records))

    # 4. Special name files (with hidden unicode)
    for partial, (en_name, fields) in SPECIAL_NAME_FILES.items():
        actual_fname = find_file(partial)
        if not actual_fname:
            print(f"WARNING: {partial} not found, skipping")
            continue
        out_name, records = convert_simple(actual_fname, en_name, fields)
        results.append((out_name, records))

    # 5. Nonferrous metals index (special structure)
    nf_fname = find_file("申万有色金属行业指数")
    if nf_fname:
        out_name, records = convert_nonferrous_index(nf_fname)
        results.append((out_name, records))
    else:
        print("WARNING: Nonferrous metals index not found")

    # ── Summary ──────────────────────────────────────────────────────
    print(f"\n{'='*80}")
    print(f"{'JSON File':<45} {'Rows':>6}  {'Date Range'}")
    print(f"{'='*80}")
    total_files = 0
    for out_name, records in sorted(results, key=lambda x: x[0]):
        total_files += 1
        n = len(records)
        if n > 0 and "date" in records[0]:
            dates = [r["date"] for r in records if r.get("date")]
            d_min = min(dates) if dates else "N/A"
            d_max = max(dates) if dates else "N/A"
            print(f"  {out_name:<43} {n:>6}  {d_min} ~ {d_max}")
        else:
            print(f"  {out_name:<43} {n:>6}  N/A")
    print(f"{'='*80}")
    print(f"  Total: {total_files} JSON files generated in {JSON_DIR}/")


if __name__ == "__main__":
    main()
