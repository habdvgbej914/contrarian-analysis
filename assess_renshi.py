"""
assess_renshi.py — 人事层评估模块 (FCAS v4.0)

调用Claude API评估C1-C6六项指标，返回人事层标签。
SYSTEM_PROMPT和API调用逻辑精确复现backtest_587w.py。
"""

import json
import signal

SYSTEM_PROMPT = """You are an FCAS (Force Configuration Analysis System) structural analyst.

Your task: Given an evidence pack of market data, assess 6 binary criteria (C1-C6) for the specified entity.

## Criteria Definitions

- C1 TREND DIRECTION: Is the entity aligned with the macro structural trend of its era? (1=aligned, 0=misaligned)
- C2 ENERGY STATE: Is current energy accumulating or dissipating? (1=accumulating, 0=dissipating)
- C3 INTERNAL HARMONY: Is the internal system coordinating smoothly? (1=harmonious, 0=discordant)
- C4 PERSONAL ENDURANCE: Can it survive a hibernation/dormancy cycle? (1=can endure, 0=fragile)
- C5 ECOSYSTEM SUPPORT: Is the surrounding ecosystem supporting or rejecting it? (1=supporting, 0=rejecting)
- C6 FOUNDATION DEPTH: Does it have deep structural load-bearing capacity and time-accumulated foundation? (1=deep, 0=shallow)

## Rules

1. Each criterion is BINARY: 1 (MET) or 0 (NOT MET). No middle ground.
2. Base judgments ONLY on the evidence provided. Do not use external knowledge.
3. If previous week's assessment is provided, maintain continuity unless there is CLEAR STRUCTURAL EVIDENCE of change.
4. A flip (0→1 or 1→0) requires explicit justification citing specific data points.
5. This is STATE DIAGNOSIS, not price prediction. You are assessing structural condition, not forecasting direction.

## Output Format (STRICT JSON)

{
  "C1": {"bit": 0 or 1, "reason": "brief justification citing specific data"},
  "C2": {"bit": 0 or 1, "reason": "brief justification citing specific data"},
  "C3": {"bit": 0 or 1, "reason": "brief justification citing specific data"},
  "C4": {"bit": 0 or 1, "reason": "brief justification citing specific data"},
  "C5": {"bit": 0 or 1, "reason": "brief justification citing specific data"},
  "C6": {"bit": 0 or 1, "reason": "brief justification citing specific data"},
  "signal": "STRONGLY_FAVORABLE|FAVORABLE|MIXED|CAUTIOUS|ADVERSE",
  "summary": "one-sentence structural state summary"
}

Signal mapping:
- STRONGLY_FAVORABLE: 5-6 criteria met (binary ≥ 101111)
- FAVORABLE: 4 criteria met
- MIXED: 3 criteria met
- CAUTIOUS: 2 criteria met
- ADVERSE: 0-1 criteria met

Output ONLY valid JSON. No markdown, no explanation outside the JSON."""

SIGNAL_MAP = {
    0: "ADVERSE",
    1: "ADVERSE",
    2: "CAUTIOUS",
    3: "MIXED",
    4: "FAVORABLE",
    5: "STRONGLY_FAVORABLE",
    6: "STRONGLY_FAVORABLE",
}

# Direction mapping (matches backtest_587w.py logic)
H_DIRECTION_MAP = {
    "STRONGLY_FAVORABLE": "H_FAV",
    "FAVORABLE":          "H_FAV",
    "MIXED":              "H_NEU",
    "CAUTIOUS":           "H_ADV",
    "ADVERSE":            "H_ADV",
}

_API_TIMEOUT = 30  # seconds per call for daily_scan (shorter than backtest)
_MAX_RETRIES = 2


class _TimeoutError(Exception):
    pass


def _timeout_handler(signum, frame):
    raise _TimeoutError(f"API call timed out after {_API_TIMEOUT}s")


def _parse_judgment(text: str) -> dict:
    """Extract and validate JSON from Claude response text."""
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    # Bracket-match to extract JSON object
    start = text.find("{")
    if start == -1:
        raise json.JSONDecodeError("No JSON object found", text, 0)
    depth = 0
    end = start
    in_string = False
    escape_next = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape_next:
            escape_next = False
            continue
        if ch == '\\' and in_string:
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    text = text[start:end]

    result = json.loads(text)

    # Validate and normalize C1-C6
    for c in ["C1", "C2", "C3", "C4", "C5", "C6"]:
        if c not in result:
            raise ValueError(f"Missing {c} in response")
        if "bit" not in result[c]:
            raise ValueError(f"Missing bit in {c}")
        bit = result[c]["bit"]
        if isinstance(bit, str):
            bit = int(bit)
        if bit not in [0, 1]:
            raise ValueError(f"Invalid bit in {c}: {result[c]['bit']}")
        result[c]["bit"] = bit
        if "reason" not in result[c]:
            result[c]["reason"] = "no reason provided"

    if "signal" not in result:
        total = sum(result[c]["bit"] for c in ["C1", "C2", "C3", "C4", "C5", "C6"])
        result["signal"] = SIGNAL_MAP[total]
    if "summary" not in result:
        result["summary"] = ""

    return result


def assess_stock_renshi(
    stock_code: str,
    stock_name: str,
    evidence_pack: str,
    model: str = "claude-sonnet-4-20250514",
) -> dict:
    """
    调用Claude API评估C1-C6，返回人事层标签。

    返回 dict:
        成功: {'h_label': str, 'h_direction': str, 'c_values': dict, 'ones': int}
        失败: {'h_label': 'MIXED', 'h_direction': 'H_NEU', 'error': str}
    """
    try:
        import anthropic
        import httpx
    except ImportError as e:
        return {
            "h_label": "MIXED",
            "h_direction": "H_NEU",
            "error": f"Import error: {e}",
        }

    client = anthropic.Anthropic(timeout=httpx.Timeout(90.0, connect=10.0))

    last_error = None
    for attempt in range(_MAX_RETRIES):
        try:
            old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(_API_TIMEOUT)
            try:
                response = client.messages.create(
                    model=model,
                    max_tokens=1024,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": evidence_pack}],
                )
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)

            text = response.content[0].text.strip()
            judgment = _parse_judgment(text)

            ones = sum(judgment[c]["bit"] for c in ["C1", "C2", "C3", "C4", "C5", "C6"])
            h_label = SIGNAL_MAP[ones]
            h_direction = H_DIRECTION_MAP.get(h_label, "H_NEU")
            c_values = {c: judgment[c]["bit"] for c in ["C1", "C2", "C3", "C4", "C5", "C6"]}

            return {
                "h_label":     h_label,
                "h_direction": h_direction,
                "c_values":    c_values,
                "ones":        ones,
                "summary":     judgment.get("summary", ""),
            }

        except (json.JSONDecodeError, ValueError) as e:
            last_error = f"Parse error: {e}"
        except _TimeoutError as e:
            last_error = str(e)
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"

    return {
        "h_label":     "MIXED",
        "h_direction": "H_NEU",
        "error":       last_error or "unknown error",
    }
