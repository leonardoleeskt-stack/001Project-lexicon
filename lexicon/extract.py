"""从授权文件中提取中文词条 / 关键词。"""

from __future__ import annotations

import csv
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Sequence, Set, Tuple

ALLOWED_SUFFIXES = {".txt", ".md", ".csv", ".tsv"}

# 中文词块：连续汉字，长度 2–12（句子级长串不要）
_CN_WORD_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]{2,12}")
_SENTENCE_PUNCT_RE = re.compile(r"[。！？；!?…]")
_MAX_TERM_LEN = 12
_MAX_EXPLICIT_LEN = 16  # 词表里显式「词\t拼音」可稍长，仍拒句子

# 禁止扫描的盘符 / 路径前缀（本地安全约束）
_BLOCKED_PREFIXES = (
    "E:\\",
    "E:/",
    "/e/",
    "/mnt/e",
)


@dataclass(frozen=True)
class RawTerm:
    """原始提取词条。"""

    text: str
    pinyin: Optional[str] = None  # 若源文件已提供
    source: str = ""


def _is_blocked_path(path: Path) -> bool:
    s = str(path).replace("/", "\\")
    upper = s.upper()
    for p in _BLOCKED_PREFIXES:
        if upper.startswith(p.upper().replace("/", "\\")):
            return True
    # 拒绝根盘扫描
    if re.fullmatch(r"[A-Za-z]:\\?", s):
        return True
    return False


def iter_authorized_files(paths: Sequence[str | Path]) -> Iterator[Path]:
    """仅遍历用户明确授权的文件/文件夹内允许后缀的文件。不递归整盘。"""
    seen: Set[str] = set()
    for raw in paths:
        p = Path(raw).expanduser()
        if _is_blocked_path(p):
            continue
        if not p.exists():
            continue
        if p.is_file():
            if p.suffix.lower() in ALLOWED_SUFFIXES:
                key = str(p.resolve())
                if key not in seen:
                    seen.add(key)
                    yield p
            continue
        if p.is_dir():
            # 仅一层 + 有限深度递归（最多 4 层），绝不跨到授权根之外
            for root, dirs, files in os.walk(p):
                root_path = Path(root)
                try:
                    depth = len(root_path.relative_to(p).parts)
                except ValueError:
                    dirs.clear()
                    continue
                if depth > 4:
                    dirs.clear()
                    continue
                # 阻止进入 E: 等
                if _is_blocked_path(root_path):
                    dirs.clear()
                    continue
                for name in files:
                    fp = root_path / name
                    if fp.suffix.lower() in ALLOWED_SUFFIXES:
                        key = str(fp.resolve())
                        if key not in seen:
                            seen.add(key)
                            yield fp


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _parse_line_pair(line: str) -> Optional[Tuple[str, Optional[str]]]:
    """支持：纯词 / 词\\t拼音 / 词,拼音。"""
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if "\t" in line:
        parts = line.split("\t")
        word = parts[0].strip()
        py = parts[1].strip() if len(parts) > 1 else None
        if word:
            return word, (py or None)
        return None
    if "," in line and not line.startswith('"'):
        # 简单 csv 两列
        parts = [x.strip() for x in line.split(",", 1)]
        if len(parts) == 2 and _CN_WORD_RE.fullmatch(parts[0]) and re.fullmatch(
            r"[a-zA-Z]+", parts[1]
        ):
            return parts[0], parts[1].lower()
    return line, None


def extract_from_file(path: Path) -> List[RawTerm]:
    """从单个文件提取词条。"""
    text = _read_text(path)
    suffix = path.suffix.lower()
    results: List[RawTerm] = []
    src = str(path)

    if suffix in {".csv", ".tsv"}:
        delim = "\t" if suffix == ".tsv" else ","
        reader = csv.reader(text.splitlines(), delimiter=delim)
        for row in reader:
            if not row:
                continue
            # 跳过表头启发式
            first = row[0].strip()
            if first.lower() in {"word", "term", "词", "词语", "短语"}:
                continue
            word = first
            py = row[1].strip() if len(row) > 1 and row[1].strip() else None
            if py and not re.fullmatch(r"[a-zA-Z]+", py):
                # 第二列不是拼音，整行当文本扫
                for cell in row:
                    for m in _CN_WORD_RE.finditer(cell):
                        results.append(RawTerm(text=m.group(), source=src))
                continue
            if _CN_WORD_RE.fullmatch(word) or (
                len(word) >= 2 and re.search(r"[\u4e00-\u9fff]", word)
            ):
                # 截断到 64
                word = word.strip()
                if is_sentence_like(word):
                    continue
                word = word[:_MAX_EXPLICIT_LEN]
                results.append(RawTerm(text=word, pinyin=py.lower() if py else None, source=src))
            else:
                for m in _CN_WORD_RE.finditer(word):
                    results.append(RawTerm(text=m.group(), source=src))
        return results

    # .txt / .md：逐行尝试 pair，否则抽中文词
    for line in text.splitlines():
        parsed = _parse_line_pair(line)
        if parsed is None:
            continue
        word, py = parsed
        if py is not None and _looks_like_term(word):
            results.append(RawTerm(text=word[:_MAX_EXPLICIT_LEN], pinyin=py, source=src))
            continue
        # 整行已是句子/散文：不从中切词（避免切出半句）
        if is_sentence_like(word) or len(word) > 20:
            continue
        for m in _CN_WORD_RE.finditer(word):
            chunk = m.group()
            if is_sentence_like(chunk):
                continue
            results.append(RawTerm(text=chunk, source=src))
    return results


def is_sentence_like(word: str) -> bool:
    """整句/过长串/口语分句：不进词库。"""
    if not word:
        return True
    t = word.strip()
    if _SENTENCE_PUNCT_RE.search(t):
        return True
    if "，" in t or "," in t or "、" in t:
        return True
    cn = re.findall(r"[\u4e00-\u9fff\u3400-\u4dbf]", t)
    if len(cn) > _MAX_EXPLICIT_LEN:
        return True
    # 口语句尾 / 疑问尾巴
    if re.search(r"(了吗|了嘛|对吧|是不是|怎么样|不错|好了|好的)$", t):
        return True
    # 偏长且像从句：含常见虚词/主语
    if len(cn) >= 6 and re.search(
        r"(我们|你们|他们|已经|可以|需要|进行|情况|工作|完成|开始|准备|这个|那个|什么)",
        t,
    ):
        return True
    if len(cn) >= 8 and ("的" in t or "了" in t or "着" in t):
        return True
    return False


def _looks_like_term(word: str) -> bool:
    if not word or is_sentence_like(word):
        return False
    t = word.strip()
    cn_len = len(re.findall(r"[\u4e00-\u9fff\u3400-\u4dbf]", t))
    if cn_len < 2:
        return False
    if _CN_WORD_RE.fullmatch(t):
        return True
    # 显式词条允许到 16 字，且无句子标点
    return cn_len <= _MAX_EXPLICIT_LEN and bool(re.search(r"[\u4e00-\u9fff]", t))


def extract_terms(paths: Sequence[str | Path]) -> List[RawTerm]:
    """从授权路径集合提取全部原始词条（尚未去重 / 脱敏）。"""
    out: List[RawTerm] = []
    for fp in iter_authorized_files(paths):
        out.extend(extract_from_file(fp))
    return out


def dedupe_terms(
    terms: Iterable[Tuple[str, str]],
) -> List[Tuple[str, str]]:
    """按 (词, 拼音) 去重，保持顺序。"""
    seen: Set[Tuple[str, str]] = set()
    result: List[Tuple[str, str]] = []
    for word, py in terms:
        key = (word, py)
        if key in seen:
            continue
        seen.add(key)
        result.append(key)
    return result
