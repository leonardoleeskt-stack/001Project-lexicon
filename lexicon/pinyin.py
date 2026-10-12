"""拼音模块（对外名称）；实现见 pinyin_util。"""
from .pinyin_util import (  # noqa: F401
    PENDING_MARK,
    PYPINYIN_AVAILABLE,
    is_valid_ime_pinyin,
    to_pinyin,
    validate_phrase_for_dat,
)
