"""漢字 → 平假名 標注（furigana）.

兩種輸出：
  - annotate(text)       → 純文字（漢字後括號標假名）
  - annotate_ruby(text)  → HTML <ruby> 標籤，給 Streamlit st.markdown 用
"""
from __future__ import annotations

import re
from functools import lru_cache

_KANJI_RE = re.compile(r"[一-龥々]+")


@lru_cache(maxsize=1)
def _get_kakasi():
    import pykakasi
    return pykakasi.kakasi()


def _segments(text: str) -> list[dict]:
    """回傳 pykakasi 分段結果：[{'orig': ..., 'hira': ..., 'kana': ..., ...}, ...]

    pykakasi 遇到換行會把前一段重複輸出（「行こう\n東京」→ 行こ/う/\n/う/東京），
    所以逐行轉換再自己補回換行。
    """
    kks = _get_kakasi()
    out: list[dict] = []
    for i, line in enumerate(text.split("\n")):
        if i:
            out.append({"orig": "\n", "hira": "\n"})
        if line:
            out.extend(kks.convert(line))
    return out


def annotate(text: str) -> str:
    """`日本語を勉強します` → `日本語(にほんご)を勉強(べんきょう)します`"""
    parts = _segments(text)
    out: list[str] = []
    for seg in parts:
        orig = seg.get("orig", "")
        hira = seg.get("hira", "")
        if orig and hira and orig != hira and _KANJI_RE.search(orig):
            out.append(f"{orig}({hira})")
        else:
            out.append(orig)
    return "".join(out)


def annotate_ruby(text: str) -> str:
    """產出 HTML ruby 標籤，瀏覽器會在漢字上方顯示小字假名。"""
    parts = _segments(text)
    out: list[str] = []
    for seg in parts:
        orig = seg.get("orig", "")
        hira = seg.get("hira", "")
        if orig and hira and orig != hira and _KANJI_RE.search(orig):
            out.append(f"<ruby>{orig}<rt>{hira}</rt></ruby>")
        else:
            out.append(orig)
    return "".join(out)


def tokenize(text: str) -> list[tuple[str, str]]:
    """分詞，回傳 [(原文, 假名)]，給「點字加入生字本」用。"""
    parts = _segments(text)
    return [(seg.get("orig", ""), seg.get("hira", "")) for seg in parts if seg.get("orig")]
