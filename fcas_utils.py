"""
fcas_utils.py — Shared utilities for FCAS scripts
"""

import copy
import json
import os
import shutil
import tempfile
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

_MAX_CHUNK = 4000  # Telegram max is 4096; leave margin


def _split_telegram_chunks(text: str) -> list[str]:
    """Split text into Telegram-safe chunks.

    Prefer line boundaries, but if a single line is too long we still split it
    so we never emit an empty chunk or a chunk above the hard limit.
    """
    if not text:
        return []

    chunks: list[str] = []
    current = ""

    for line in text.split("\n"):
        line_parts = [line[i : i + _MAX_CHUNK] for i in range(0, len(line), _MAX_CHUNK)] or [""]

        for part in line_parts:
            separator = "\n" if current else ""
            if len(current) + len(separator) + len(part) > _MAX_CHUNK:
                if current:
                    chunks.append(current)
                current = part
            else:
                current = f"{current}{separator}{part}" if current else part

    if current:
        chunks.append(current)

    return chunks


def _backup_invalid_json(path: str, label: str) -> str | None:
    """Copy an invalid JSON file aside before callers overwrite it."""
    if not os.path.exists(path):
        return None

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = f"{path}.corrupt.{timestamp}"
    try:
        shutil.copy2(path, backup_path)
        print(f"[{label}] Backed up invalid file to {backup_path}")
        return backup_path
    except OSError as exc:
        print(f"[{label}] Could not back up invalid file {path}: {exc}")
        return None


def load_json_file(path: str, default, *, label: str, expected_type=None):
    """Load JSON with schema guardrails and a safe fallback."""
    if not os.path.exists(path):
        return copy.deepcopy(default)

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        _backup_invalid_json(path, label)
        print(f"[{label}] File unreadable, using default: {exc}")
        return copy.deepcopy(default)

    if expected_type is not None and not isinstance(data, expected_type):
        _backup_invalid_json(path, label)
        print(
            f"[{label}] Unexpected JSON type {type(data).__name__}, "
            f"expected {expected_type.__name__}; using default"
        )
        return copy.deepcopy(default)

    return data


def save_json_file(path: str, data) -> None:
    """Atomically save JSON to avoid partial writes on interruption."""
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(
        prefix=f".{os.path.basename(path)}.",
        suffix=".tmp",
        dir=directory,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        raise


def send_telegram(text: str) -> None:
    """Send a plain-text message to Telegram, splitting if > 4000 chars.

    Uses parse_mode=None (plain text). HTML special characters are NOT
    interpreted — no injection risk.
    """
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[Telegram] No token/chat_id configured, skipping push")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    chunks = _split_telegram_chunks(text)

    for i, chunk in enumerate(chunks):
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": chunk,
        }
        try:
            resp = requests.post(url, json=payload, timeout=30)
            if resp.status_code == 200:
                print(f"[Telegram] Sent chunk {i + 1}/{len(chunks)}")
            else:
                print(f"[Telegram] Error: {resp.status_code} {resp.text[:200]}")
        except Exception as e:
            print(f"[Telegram] Error: {e}")
