"""拼音生成与 IME 校验。"""

from __future__ import annotations

import re
from typing import Optional, Tuple

PYPINYIN_AVAILABLE = False
try:
    from pypinyin import Style, lazy_pinyin

    PYPINYIN_AVAILABLE = True
except ImportError:  # pragma: no cover
    Style = None  # type: ignore
    lazy_pinyin = None  # type: ignore

PENDING_MARK = "拼音待核"

# IME：仅 a-z，最长 32，不以 u/v 开头
_VALID_PY_RE = re.compile(r"^[a-z]{1,32}$")


def to_pinyin(text: str, existing: Optional[str] = None) -> str:
    """
    Style.NORMAL，小写，音节之间无空格。
    若已有合法拼音则沿用；缺 pypinyin 时返回「拼音待核」。
    """
    if existing:
        cleaned = re.sub(r"[\s'\-]", "", existing.strip().lower())
        if _VALID_PY_RE.match(cleaned) and cleaned[0] not in "uv":
            return cleaned
        if cleaned.isalpha() and cleaned.islower():
            # 可能超长或 u/v 开头，仍返回清理后的供人工核
            return cleaned

    if not PYPINYIN_AVAILABLE:
        return PENDING_MARK

    syllables = lazy_pinyin(text, style=Style.NORMAL)
    joined = "".join(s.lower() for s in syllables if s)
    joined = re.sub(r"[^a-z]", "", joined)
    return joined or PENDING_MARK


def is_valid_ime_pinyin(py: str) -> bool:
    """微软拼音用户自定义短语：a-z，≤32，不以 u/v 开头。"""
    if not py or py == PENDING_MARK:
        return False
    if not _VALID_PY_RE.match(py):
        return False
    if py[0] in ("u", "v"):
        return False
    return True


def validate_phrase_for_dat(text: str, pinyin: str) -> Tuple[bool, str]:
    """返回 (ok, reason)。"""
    if not text or len(text) > 64:
        return False, "短语须 1–64 字"
    if not is_valid_ime_pinyin(pinyin):
        return False, "拼音须为 a-z、最长 32、不以 u/v 开头"
    return True, ""
