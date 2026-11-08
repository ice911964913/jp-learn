from .jisho import lookup as jisho_lookup
from .matcha_easy import fetch_latest as easy_fetch_latest
from .furigana import annotate as add_furigana

__all__ = ["jisho_lookup", "easy_fetch_latest", "add_furigana"]
