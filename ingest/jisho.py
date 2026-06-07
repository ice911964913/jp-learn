"""jisho.org API client.

免費、無金鑰、無速率限制（合理使用）。
API: https://jisho.org/api/v1/search/words?keyword=<word>
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import requests

JISHO_API = "https://jisho.org/api/v1/search/words"
DEFAULT_TIMEOUT = 8


@dataclass
class JishoEntry:
    word: str               # 漢字寫法（若無漢字則同 reading）
    reading: str            # ひらがな
    meanings_en: list[str]  # 英文釋義（jisho 不提供中文）
    pos: list[str]          # 詞性
    jlpt: Optional[str]     # 'n3' / 'n2' ... 若無則 None
    is_common: bool


def lookup(keyword: str, timeout: float = DEFAULT_TIMEOUT) -> list[JishoEntry]:
    """查詢 jisho.org，回傳全部結果（通常第一筆就是要的）。"""
    if not keyword.strip():
        return []

    resp = requests.get(JISHO_API, params={"keyword": keyword}, timeout=timeout)
    resp.raise_for_status()
    payload = resp.json()

    entries: list[JishoEntry] = []
    for item in payload.get("data", []):
        japanese = item.get("japanese", [{}])[0]
        word = japanese.get("word") or japanese.get("reading") or ""
        reading = japanese.get("reading") or ""

        senses = item.get("senses", [])
        meanings_en: list[str] = []
        pos: list[str] = []
        for sense in senses:
            meanings_en.extend(sense.get("english_definitions", []))
            pos.extend(sense.get("parts_of_speech", []))

        jlpt_tags = item.get("jlpt", [])
        jlpt = jlpt_tags[0].replace("jlpt-", "").upper() if jlpt_tags else None

        entries.append(
            JishoEntry(
                word=word,
                reading=reading,
                meanings_en=meanings_en,
                pos=list(dict.fromkeys(pos)),  # dedupe, preserve order
                jlpt=jlpt,
                is_common=item.get("is_common", False),
            )
        )

    return entries


def lookup_one(keyword: str) -> Optional[JishoEntry]:
    """便利函式：只回傳第一筆結果。"""
    results = lookup(keyword)
    return results[0] if results else None
