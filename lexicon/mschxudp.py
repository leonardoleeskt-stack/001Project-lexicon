"""
微软拼音用户自定义短语 .dat（mschxudp，Win10 1703+ / Win11）构建器。

布局（小端）：
- 0–7: magic b'mschxudp'
- uint32 unknown = 0x00600002
- uint32 version = 1
- uint32 phrase_offset_start = 0x40
- uint32 phrase_start
- uint32 phrase_end
- uint32 phrase_count
- uint32 timestamp (unix) + pad to 0x40
- 偏移表：phrase_count 个 uint32，相对 phrase_start
- 每条短语：
  - uint32 magic = 0x00100010
  - uint16 offset_to_phrase = 0x10 + len(pinyin_utf16le_with_nul)
  - uint8 candidate_pos
  - uint8 candidate2 = 6
  - uint64 unknown (0)
  - pinyin UTF-16LE + NUL
  - phrase UTF-16LE + NUL
"""

from __future__ import annotations

import struct
import time
from pathlib import Path
from typing import List, Sequence, Tuple

from .pinyin_util import validate_phrase_for_dat

MAGIC = b"mschxudp"
UNKNOWN_HEADER = 0x00600002
VERSION = 1
PHRASE_OFFSET_START = 0x40
PHRASE_MAGIC = 0x00100010
CANDIDATE2 = 6


def _utf16le_z(s: str) -> bytes:
    return s.encode("utf-16-le") + b"\x00\x00"


def build_phrase_bytes(
    pinyin: str,
    phrase: str,
    candidate_pos: int = 1,
    unknown8: int = 0,
) -> bytes:
    py_b = _utf16le_z(pinyin)
    ph_b = _utf16le_z(phrase)
    offset_to_phrase = 0x10 + len(py_b)
    pos = max(1, min(9, int(candidate_pos)))
    buf = bytearray()
    buf += struct.pack("<I", PHRASE_MAGIC)
    buf += struct.pack("<H", offset_to_phrase)
    buf += struct.pack("<BB", pos, CANDIDATE2)
    buf += struct.pack("<Q", unknown8)
    buf += py_b
    buf += ph_b
    return bytes(buf)


def build_dat(
    entries: Sequence[Tuple[str, str, int]],
    timestamp: int | None = None,
) -> bytes:
    """
    entries: (phrase_text, pinyin, candidate_pos)
    仅写入通过 IME 校验的条目；空列表仍写出合法空库头。
    """
    valid: List[Tuple[str, str, int]] = []
    for phrase, py, pos in entries:
        ok, _ = validate_phrase_for_dat(phrase, py)
        if ok:
            valid.append((phrase, py, pos))

    ts = int(time.time()) if timestamp is None else int(timestamp)
    count = len(valid)

    phrase_blobs: List[bytes] = []
    offsets: List[int] = []
    running = 0
    for phrase, py, pos in valid:
        offsets.append(running)
        blob = build_phrase_bytes(py, phrase, pos)
        phrase_blobs.append(blob)
        running += len(blob)

    phrase_start = PHRASE_OFFSET_START + 4 * count
    phrase_end = phrase_start + running

    header = bytearray(PHRASE_OFFSET_START)
    header[0:8] = MAGIC
    struct.pack_into("<I", header, 8, UNKNOWN_HEADER)
    struct.pack_into("<I", header, 12, VERSION)
    struct.pack_into("<I", header, 16, PHRASE_OFFSET_START)
    struct.pack_into("<I", header, 20, phrase_start)
    struct.pack_into("<I", header, 24, phrase_end)
    struct.pack_into("<I", header, 28, count)
    struct.pack_into("<I", header, 32, ts)
    # 36–63 保持 0

    out = bytearray()
    out += header
    for off in offsets:
        out += struct.pack("<I", off)
    for blob in phrase_blobs:
        out += blob

    # 回填 phrase_end（已正确）；确保长度一致
    assert len(out) == phrase_end, (len(out), phrase_end)
    return bytes(out)


def write_dat(
    path: str | Path,
    entries: Sequence[Tuple[str, str, int]],
    timestamp: int | None = None,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = build_dat(entries, timestamp=timestamp)
    path.write_bytes(data)
    return path


def read_magic(path: str | Path) -> bytes:
    return Path(path).read_bytes()[:8]


def verify_dat(path: str | Path) -> Tuple[bool, str]:
    raw = Path(path).read_bytes()
    if len(raw) < 0x40:
        return False, "文件过短"
    if raw[:8] != MAGIC:
        return False, f"magic 错误: {raw[:8]!r}"
    unknown, version, off_start, p_start, p_end, count, ts = struct.unpack_from(
        "<IIIIIII", raw, 8
    )
    if off_start != 0x40:
        return False, f"phrase_offset_start={off_start}"
    if p_start != 0x40 + 4 * count:
        return False, f"phrase_start 不一致: {p_start}"
    if p_end != len(raw):
        return False, f"phrase_end={p_end} len={len(raw)}"
    return True, f"ok count={count} version={version} unknown=0x{unknown:08x} ts={ts}"
