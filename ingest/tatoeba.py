"""Tatoeba 例句 API.

免費、無金鑰，例句是 CC BY 授權。優先找有中文（cmn）翻譯的，沒有再退回英文。
API: https://api.tatoeba.org/unstable/sentences
"""
from __future__ import annotations

from dataclasses import dataclass

import requests

TATOEBA_API = "https://api.tatoeba.org/unstable/sentences"
DEFAULT_TIMEOUT = 10
_FETCH = 30
_MIN_LEN, _MAX_LEN = 8, 35


@dataclass
class Example:
    jp: str
    translation: str
    lang: str  # 'cmn' / 'eng'


def _search(word: str, trans_lang: str, limit: int) -> list[Example]:
    resp = requests.get(
        TATOEBA_API,
        params={
            "lang": "jpn",
            "q": word,
            "sort": "relevance",
            "limit": _FETCH,
            "trans:lang": trans_lang,
            "showtrans": "matching",
        },
        timeout=DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()
    out: list[Example] = []
    for s in resp.json().get("data", []):
        trans = s.get("translations") or []
        if trans:
            out.append(Example(jp=s["text"], translation=trans[0]["text"], lang=trans_lang))
    # relevance 排序偏好超短句（「行く？」），中等長度的句子比較有參考價值
    out.sort(key=lambda e: not (_MIN_LEN <= len(e.jp) <= _MAX_LEN))
    return out[:limit]


def examples(word: str, limit: int = 3) -> list[Example]:
    """回傳最多 limit 句例句，中文翻譯優先。"""
    out = _search(word, "cmn", limit)
    if len(out) < limit:
        out += _search(word, "eng", limit - len(out))
    return out
