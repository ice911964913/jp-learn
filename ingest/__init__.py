from .jisho import lookup as jisho_lookup
from .nhk_easy import fetch_latest as nhk_fetch_latest
from .furigana import annotate as add_furigana

__all__ = ["jisho_lookup", "nhk_fetch_latest", "add_furigana"]
