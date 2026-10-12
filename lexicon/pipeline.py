"""提取 → 拼音 → 脱敏 → 导出 TSV / .dat 的流水线。"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import List, Optional, Sequence, Set, Tuple

from .extract import RawTerm, _read_text, dedupe_terms, extract_terms, iter_authorized_files
from .mask import (
    REASON_AMOUNT,
    REASON_CONTRACT,
    REASON_EMAIL,
    REASON_ID,
    REASON_PHONE,
    ClassifiedTerm,
    classify_terms,
    _AMOUNT_RE,
    _CONTRACT_RE,
    _EMAIL_RE,
    _ID_RE,
    _PHONE_RE,
)
from .mschxudp import write_dat
from .pinyin_util import is_valid_ime_pinyin, to_pinyin

DEFAULT_OUTPUT_DIR = r"D:\WorkBuddyData\001Project\lexicon-v0"
DEFAULT_INPUT_HINT = r"D:\WorkBuddyData\agent-memory\glossary"


def _harvest_sensitive_spans(paths: Sequence[str | Path]) -> List[ClassifiedTerm]:
    """从原文抓取电话/邮箱/金额等片段进入暂扣（即使不是汉字词）。"""
    found: List[ClassifiedTerm] = []
    seen: Set[str] = set()
    rules = [
        (_EMAIL_RE, REASON_EMAIL),
        (_ID_RE, REASON_ID),
        (_PHONE_RE, REASON_PHONE),
        (_AMOUNT_RE, REASON_AMOUNT),
        (_CONTRACT_RE, REASON_CONTRACT),
    ]
    for fp in iter_authorized_files(paths):
        try:
            text = _read_text(fp)
        except OSError:
            continue
        for cre, reason in rules:
            for m in cre.finditer(text):
                span = m.group().strip()[:64]
                if not span or span in seen:
                    continue
                # 跳过过短的「合同号」纯标签若已作为汉字词处理
                seen.add(span)
                found.append(
                    ClassifiedTerm(
                        text=span,
                        pinyin="",
                        sensitive=True,
                        reason=reason,
                        source=str(fp),
                        selected=False,
                    )
                )
    return found


def process_paths(paths: Sequence[str | Path]) -> Tuple[List[ClassifiedTerm], List[ClassifiedTerm]]:
    raw: List[RawTerm] = extract_terms(paths)
    paired: List[Tuple[str, str, str]] = []
    for r in raw:
        py = to_pinyin(r.text, r.pinyin)
        paired.append((r.text, py, r.source))

    uniq = dedupe_terms((t, p) for t, p, _ in paired)
    src_map = {}
    for t, p, s in paired:
        src_map.setdefault((t, p), s)
    items = [(t, p, src_map.get((t, p), "")) for t, p in uniq]
    candidates, held = classify_terms(items)

    # 合并原文敏感片段
    extra = _harvest_sensitive_spans(paths)
    held_texts = {h.text for h in held}
    for e in extra:
        if e.text not in held_texts:
            held.append(e)
            held_texts.add(e.text)
    return candidates, held


def write_tsv(path: Path, rows: Sequence[ClassifiedTerm], held: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        if held:
            w.writerow(["词", "拼音", "原因", "来源"])
            for r in rows:
                w.writerow([r.text, r.pinyin, r.reason, r.source])
        else:
            w.writerow(["词", "拼音", "候选位置", "来源"])
            for r in rows:
                w.writerow([r.text, r.pinyin, "1", r.source])


def export_bundle(
    candidates: Sequence[ClassifiedTerm],
    held_back: Sequence[ClassifiedTerm],
    output_dir: str | Path,
    *,
    dat_name: str = "UserDefinedPhrase.dat",
    include_dat: bool = True,
    candidate_pos: int = 1,
) -> dict:
    """
    写出 candidates.tsv、held-back.tsv，以及可选 .dat。
    仅 selected 且拼音合法的候选进入 .dat。
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    selected = [c for c in candidates if getattr(c, "selected", True)]
    write_tsv(out / "candidates.tsv", selected, held=False)
    write_tsv(out / "held-back.tsv", list(held_back), held=True)

    dat_path: Optional[Path] = None
    dat_count = 0
    if include_dat:
        entries = []
        for c in selected:
            if is_valid_ime_pinyin(c.pinyin) and c.text and len(c.text) <= 64:
                entries.append((c.text, c.pinyin, candidate_pos))
        dat_path = write_dat(out / dat_name, entries)
        dat_count = len(entries)

    return {
        "output_dir": str(out),
        "candidates_tsv": str(out / "candidates.tsv"),
        "held_back_tsv": str(out / "held-back.tsv"),
        "dat": str(dat_path) if dat_path else None,
        "dat_count": dat_count,
        "candidate_count": len(selected),
        "held_count": len(held_back),
    }
