"""日文單字 → 繁體中文釋義（Claude）.

jisho 只有英文釋義。把「單字 + 讀音 + 英文釋義」交給 Claude 寫成台灣用語的繁中意思，
結果存在 SQLite zh_gloss 表，同一個字只會呼叫一次 API。
API key 沿用 stock_bot/.env 的 ANTHROPIC_API_KEY（跟 en_learn 一樣）。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from db import get_conn

_BASE = Path(__file__).resolve().parent.parent
load_dotenv(_BASE.parent / "stock_bot" / ".env")
load_dotenv(_BASE / ".env", override=True)

MODEL = os.getenv("JP_LEARN_MODEL", "claude-opus-5-5")

_SCHEMA = {
    "type": "object",
    "properties": {"meaning_zh": {"type": "string"}},
    "required": ["meaning_zh"],
    "additionalProperties": False,
}

_SYSTEM = (
    "你是日華辭典編輯。根據使用者給的日文單字、讀音與英文釋義，寫出給台灣日語學習者看的繁體中文意思。"
    "用台灣慣用詞，簡短精確，像辭典條目；多個意思用「；」分隔，最多 4 個，常用的放前面。"
    "專有名詞（地名、人名）寫成「地名：川崎（神奈川縣的城市）」這種形式。"
)


def has_api_key() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def _cached(word: str, reading: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT meaning_zh FROM zh_gloss WHERE word = ? AND reading = ?", (word, reading)
        ).fetchone()
    return row["meaning_zh"] if row else None


def _ask_claude(word: str, reading: str, meanings_en: list[str], pos: list[str]) -> str:
    client = anthropic.Anthropic()
    resp = client.beta.messages.create(
        model=MODEL,
        max_tokens=1024,
        output_config={
            "effort": "low",
            "format": {"type": "json_schema", "schema": _SCHEMA},
        },
        # 安全分類器誤擋時，伺服器自動改用其他模型重跑
        betas=["server-side-fallback-2026-07-01"],
        extra_body={"fallbacks": "default"},
        system=_SYSTEM,
        messages=[{
            "role": "user",
            "content": (
                f"單字：{word}\n讀音：{reading}\n"
                f"詞性：{', '.join(pos) or '—'}\n英文釋義：{'; '.join(meanings_en)}"
            ),
        }],
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("Claude 拒絕回答")
    text = next((b.text for b in resp.content if b.type == "text"), "")
    return json.loads(text)["meaning_zh"].strip()


def meaning_zh(word: str, reading: str, meanings_en: list[str], pos: list[str]) -> str:
    """回傳繁中釋義；先查快取，沒有才問 Claude 並寫回快取。"""
    hit = _cached(word, reading)
    if hit:
        return hit
    zh = _ask_claude(word, reading, meanings_en[:8], pos[:3])
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO zh_gloss (word, reading, meaning_zh) VALUES (?, ?, ?)",
            (word, reading, zh),
        )
    return zh
