"""敏感信息分类与暂扣（held-back）。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

# 敏感原因标签（中文）
REASON_AMOUNT = "金额"
REASON_PHONE = "电话"
REASON_EMAIL = "邮箱"
REASON_ID = "证件号"
REASON_CONTRACT = "合同号"
REASON_QUOTE = "报价"
REASON_CUSTOMER = "客户全称"
REASON_PERSON = "人名"
REASON_UNCERTAIN = "待机主判断"


@dataclass
class ClassifiedTerm:
    text: str
    pinyin: str = ""
    sensitive: bool = False
    reason: str = ""
    source: str = ""
    selected: bool = True  # 候选默认勾选；暂扣默认不入候选


_AMOUNT_RE = re.compile(
    r"(?:"
    r"[¥￥]\s*\d[\d,]*(?:\.\d+)?|"
    r"\$\s*\d[\d,]*(?:\.\d+)?|"
    r"(?:USD|RMB|CNY)\s*\d[\d,]*(?:\.\d+)?|"
    r"(?:报价|金额|总价|单价)\s*[:：]?\s*\d[\d,]*(?:\.\d+)?\s*(?:万|亿)?\s*元?|"
    r"\d[\d,]*(?:\.\d+)?\s*(?:万|亿)\s*元?|"
    r"\d[\d,]*(?:\.\d+)?\s*元"
    r")",
    re.IGNORECASE,
)

_PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_ID_RE = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
_CONTRACT_RE = re.compile(
    r"(?:"
    r"合同\s*[编号号]?[:：]?\s*[A-Za-z0-9\-_/]{4,}|"
    r"(?:HT|CON|CONTRACT)[\-_]?[A-Za-z0-9]{4,}|"
    r"[A-Z]{2,}\d{6,}|"
    r"合同号"
    r")",
    re.IGNORECASE,
)

_COMPANY_SUFFIX_RE = re.compile(
    r".{2,}(?:有限公司|股份有限公司|股份公司|集团有限公司)$"
)

_PERSON_HINT_RE = re.compile(
    r"(?:先生|女士|联系人|对接人)[:：\s]*([\u4e00-\u9fff]{2,3})"
)
_PERSON_TITLE_RE = re.compile(r"([\u4e00-\u9fff]{2,3})(?:先生|女士)")

_QUOTE_HINT_RE = re.compile(r"报价|单价|总价|含税价|未税价")


def classify_text(text: str) -> Tuple[bool, str]:
    """
    判断文本是否敏感。返回 (is_sensitive, reason)。
    不确定时放入「待机主判断」，不静默进入候选。
    """
    if not text or not text.strip():
        return True, REASON_UNCERTAIN

    t = text.strip()

    if _EMAIL_RE.search(t):
        return True, REASON_EMAIL
    if _ID_RE.search(t):
        return True, REASON_ID
    if _PHONE_RE.search(t):
        return True, REASON_PHONE
    if _AMOUNT_RE.search(t):
        if _QUOTE_HINT_RE.search(t):
            return True, REASON_QUOTE
        return True, REASON_AMOUNT
    if _QUOTE_HINT_RE.search(t) and re.search(r"\d", t):
        return True, REASON_QUOTE
    if _CONTRACT_RE.search(t):
        return True, REASON_CONTRACT
    if _COMPANY_SUFFIX_RE.match(t):
        return True, REASON_CUSTOMER

    m = _PERSON_HINT_RE.search(t)
    if m:
        return True, REASON_PERSON
    m2 = _PERSON_TITLE_RE.search(t)
    if m2:
        return True, REASON_PERSON

    # 纯 2–3 字且像人名的弱信号：短且无常见词根时进待机主判断
    if re.fullmatch(r"[\u4e00-\u9fff]{2,3}", t):
        # 常见非人名词保留；其余短词进待机主判断更安全
        common_ok = {
            "项目", "词库", "拼音", "输入", "微软", "短语", "候选",
            "导出", "导入", "设置", "文档", "表格", "文件", "目录",
            "公司", "客户", "合同", "报价", "金额", "电话", "邮箱",
            "复见", "作战", "信任", "代理", "助手", "模型", "训练",
            "测试", "版本", "模块", "界面", "启动", "安装", "依赖",
        }
        if t in common_ok:
            return False, ""
        # 其它 2–3 字：待机主判断（不静默入候选）
        return True, REASON_UNCERTAIN

    # 含明显数字串但未匹配上面规则 → 不确定
    if re.search(r"\d{6,}", t):
        return True, REASON_UNCERTAIN

    return False, ""


def classify_terms(
    items: Sequence[Tuple[str, str, str]],
) -> Tuple[List[ClassifiedTerm], List[ClassifiedTerm]]:
    """
    items: (text, pinyin, source)
    返回 (candidates, held_back)
    """
    candidates: List[ClassifiedTerm] = []
    held: List[ClassifiedTerm] = []
    for text, py, source in items:
        sens, reason = classify_text(text)
        term = ClassifiedTerm(
            text=text[:64],
            pinyin=py or "",
            sensitive=sens,
            reason=reason,
            source=source,
            selected=not sens,
        )
        if sens:
            held.append(term)
        else:
            candidates.append(term)
    return candidates, held
