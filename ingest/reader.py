"""文章 → 可點擊單字的 HTML（給點字查詢用）.

用 fugashi + unidic-lite 斷詞：每個實詞包成 <span class="w" data-w="原形">，
點擊時把「辭書形」（使われる → 使う）傳回 Python 查 jisho。
讀音也用 unidic，比 pykakasi 準，且不會有跨換行重複的問題。
"""
from __future__ import annotations

import html
import re
from functools import lru_cache

_KANJI_RE = re.compile(r"[一-龥々〆ヶ]")
# 這些詞性不給點（助詞、助動詞、標點）
_SKIP_POS = {"助詞", "助動詞", "補助記号", "記号", "空白"}


@lru_cache(maxsize=1)
def _get_tagger():
    import fugashi
    return fugashi.Tagger()


def _kata_to_hira(s: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def _ruby(surface: str, reading: str) -> str:
    """只在漢字部分上標假名：使わ/つかわ → <ruby>使<rt>つか</rt></ruby>わ"""
    if not reading or not _KANJI_RE.search(surface):
        return html.escape(surface)
    # 去掉前後跟讀音相同的假名（送假名）
    head = 0
    while head < len(surface) and head < len(reading) and surface[head] == reading[head] and not _KANJI_RE.match(surface[head]):
        head += 1
    tail = 0
    while (
        tail < len(surface) - head
        and tail < len(reading) - head
        and surface[-1 - tail] == reading[-1 - tail]
        and not _KANJI_RE.match(surface[-1 - tail])
    ):
        tail += 1
    core = surface[head:len(surface) - tail]
    core_reading = reading[head:len(reading) - tail]
    if not core_reading:
        return html.escape(surface)
    return (
        html.escape(surface[:head])
        + f"<ruby>{html.escape(core)}<rt>{html.escape(core_reading)}</rt></ruby>"
        + html.escape(surface[len(surface) - tail:])
    )


def _line_html(line: str) -> str:
    out: list[str] = []
    for w in _get_tagger()(line):
        f = w.feature
        out.append(html.escape(w.white_space))
        reading = _kata_to_hira(f.kana) if f.kana else ""
        inner = _ruby(w.surface, reading)
        if f.kana is None or f.pos1 in _SKIP_POS:
            out.append(inner)
            continue
        lookup = f.orthBase or w.surface
        out.append(f'<span class="w" data-w="{html.escape(lookup, quote=True)}">{inner}</span>')
    return "".join(out)


def to_clickable_html(text: str) -> str:
    """逐行斷詞，段落用 <p> 分開。"""
    return "".join(f"<p>{_line_html(line)}</p>" for line in text.split("\n") if line.strip())
