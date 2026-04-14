# FCAS — Force Configuration Analysis System / 气象分析系统

A structural analysis framework that diagnoses the state of any domain using a 6-criterion binary system, maps it to one of 64 configurations, determines lifecycle positioning and structural relationships, and provides intent-based guidance.

**Core question the framework answers:** "Given the current structural conditions, what action best serves my intent?"

## How It Works

### 1. Six Binary Criteria

Each analysis starts with six binary judgments about the domain:

| Position | Criterion | Question |
|----------|-----------|----------|
| C1 (五爻) | Trend Alignment / 趋势方向 | Aligned with macro trend? |
| C2 (上爻) | Energy State / 能量状态 | Energy accumulating or dissipating? |
| C3 (三爻) | Internal Harmony / 内部协调 | System internally coordinated? |
| C4 (四爻) | Personal Sustainability / 个人持续力 | Can you sustain through this? |
| C5 (初爻) | Ecosystem Support / 生态支撑 | Ecosystem supporting or rejecting? |
| C6 (二爻) | Foundation Depth / 根基深浅 | Foundation deep or shallow? |

### 2. 64 Configurations

The six bits generate a binary code (e.g., `111101`) that maps to one of 64 named configurations. Each has a structural family, evolution stage, and lifecycle positioning derived from classical systems.

Example: `111101` = **Aligned Vision / 愿景一致** (Return to Core stage)

### 3. Three-Layer Judgment

Each position is assessed through three layers:

1. **Direction** (扶抑): Is this position being supported or suppressed?
2. **Vitality** (有气无气): Is it in a vital or depleted lifecycle stage?
3. **Relations** (合德刑克): Are there harmonizing or conflicting relationships with other positions?

### 4. Intent-Based Guidance

Users bring a specific intent. The framework identifies which structural relationships serve that intent:

| Intent | Target | Helper | Threat |
|--------|--------|--------|--------|
| Seek Profit / 求财 | Accessible Resource | Derivative Output | Peer Competitor |
| Seek Position / 求职求名 | External Pressure | Accessible Resource | Derivative Output |
| Seek Protection / 求庇护 | Upstream Support | External Pressure | Accessible Resource |
| Seek Output / 求产出 | Derivative Output | Peer Competitor | Upstream Support |
| Assess Competition / 看竞争 | Peer Competitor | Upstream Support | External Pressure |

**Assessment outcomes:**
- **Strongly Supported** — Target and helpers vital, no strong threats
- **Supported with Resistance** — Conditions support but with friction
- **Supported but Weak** — Present but lacking vitality
- **Contested** — Active support and active threats coexist
- **Possible but Unsupported** — Target exists without helper support
- **Indirect Path** — Target inactive, build through helpers
- **Dormant** — Nothing active, wait for change
- **Challenged** — Target faces threats without support
- **Not Viable** — No target, no helpers, active threats

## Backtest Results (SPY 2008-2026, 25 events)

Supported intents (Strongly Supported / Supported with Resistance / Supported but Weak / Contested):

| Horizon | Total | Correct | Accuracy | Avg Return |
|---------|-------|---------|----------|------------|
| 1W | 9 | 8 | 88.9% | +4.60% |
| 1M | 9 | 8 | 88.9% | +7.59% |
| 3M | 9 | 8 | 88.9% | +11.28% |

Not Viable assessments correctly identified Meme Peak 2021 (-16.5% in 6M) and Pre-Rate-Hike Peak 2022 (-19.2% in 6M).

## File Structure

```
fcas_engine_v2.py           — Core engine (standalone, no MCP dependency)
fcas_mcp.py                 — MCP server wrapper (re-exports fcas_engine_v2 and adds FastMCP tools)
fcas_utils.py               — Shared utilities (Telegram push)
stock_positioning.py        — Per-stock palace positioning config + assessment logic
daily_scan.py               — Daily auto-scanner (H4 frequency, Telegram push)
verify_predictions.py       — Auto-verifier tracking predictions at 1w/1m/3m
backtest_extended.py        — SPY backtest (2008-2026, 25 events)
backtest_115w.py            — 115-week backtest
backtest.py                 — Original SPY backtest (v0.1)
backtest_metals.py          — GLD/SLV/COPX backtest (v0.1)
LIMITATIONS.md              — Known limitations
DESIGN_PRINCIPLES.md        — Design principles and constraints
daily_scan_history.json     — Daily scanner results (auto-trimmed to 500 records)
verification_results.json   — Prediction verification records
```

## Tech Stack

- Python 3
- Claude API (Sonnet, with web search)
- Finnhub API (market data)
- Telegram Bot API (notifications)
- yfinance (backtest price data)
- MCP Python SDK

## Daily Automation

```
# H4 frequency (crontab, London time)
0 8 * * 1-5   python3 daily_scan.py
0 12 * * 1-5  python3 daily_scan.py
0 16 * * 1-5  python3 daily_scan.py
0 20 * * 1-5  python3 daily_scan.py
0 0 * * 2-6   python3 daily_scan.py
30 8 * * 1-5  python3 verify_predictions.py
```

## Theoretical Foundation

The structural engine is based on classical Chinese analytical systems, fully converted to business language in all outputs:

- **64 configurations** from binary combination theory
- **Eight structural families** with evolution stages
- **Twelve lifecycle stages** (Conception → Transformation)
- **Five structural relationships** between positions
- **Three-layer judgment** (Direction → Vitality → Relations)
- **Intent guidance** via structural relationship mapping

No metaphysical terminology appears in any output. The classical foundations provide the logical structure; the output is pure business language.


## Design Philosophy

FCAS is a **structural state diagnosis system**, not a directional forecasting tool.

Key design constraints (from classical source texts):

- **Precision target: 70%** — Pursuing higher accuracy leads to overfitting. Backtest accuracy of 100% is a warning sign.
- **~30% directional signals, ~70% neutral** — Intentional. The system honestly reports inconclusive conditions.
- **No price predictions** — Outputs are structural diagnoses and intent guidance, not BUY/SELL signals.
- **Immutable core rules** — Scoring thresholds are not adjusted within a validation period.
- **Layered architecture** — Data (目) → LLM annotation (心) → Structural engine (理).

Full design principles: see `DESIGN_PRINCIPLES.md`.

## Backtest Disclaimer

Historical backtest results (SPY 88.9%, GLD 100%, COPX 100%) carry hindsight bias. Only forward-looking validation data has genuine evidential value. The system has 36+ forward-looking records (since 2026-03-29) with verification pending.

## License

Personal project. Not financial advice.
