"""Deterministic text lint rules."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Iterable


@dataclass(frozen=True)
class Finding:
    source: str
    line: int
    column: int
    severity: str
    rule: str
    message: str
    matched_text: str = ""
    suggestion: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


PHRASE_RULES = {
    "wording.cliche": {
        "phrases": ("晴雨表", "压舱石", "指南针"),
        "message": "该词属于高频套话，容易削弱表述的针对性。",
        "suggestion": "改为与具体职责、措施、对象或效果直接对应的表述。",
    },
    "wording.military_metaphor": {
        "phrases": ("铁军", "新兵"),
        "message": "该军事化比喻通常不适合一般政府机关工作语境。",
        "suggestion": "直接说明人员范围、能力要求、职责分工或培养措施。",
    },
    "wording.evasive": {
        "phrases": ("不一定", "不等于", "不能保证"),
        "message": "该表述可能回避对问题、条件或责任的实质分析。",
        "suggestion": "明确适用条件、现实问题、责任边界和针对性措施。",
    },
}

PLACEHOLDER_PATTERN = re.compile(r"(?i)TODO|待补充|待完善|某某|X{2,}|×{2,}")
REPEATED_PUNCTUATION = re.compile(r"[，。；：！？、]{2,}")
HALFWIDTH_AFTER_CJK = re.compile(r"(?<=[\u3400-\u9fff])[,;:!?]")
SENTENCE_PATTERN = re.compile(r"[^。！？\n]+[。！？]?")
BAD_LEVEL_ONE = re.compile(r"^\s*([一二三四五六七八九十]+)[.．]")
ASCII_LEVEL_TWO = re.compile(r"^\s*\(([一二三四五六七八九十]+)\)")
BAD_LEVEL_THREE = re.compile(r"^\s*(\d+)[、．。]")
ASCII_LEVEL_FOUR = re.compile(r"^\s*\((\d+)\)")
BAD_ATTACHMENT_COLON = re.compile(r"^\s*附件\s*:")
ATTACHMENT_END_PUNCTUATION = re.compile(r"^\s*附件[：:].*[。；;，,]\s*$")
BAD_YEAR_BRACKETS = re.compile(r"[（(［\[]\d{4}[）)］\]]")
DOC_NUMBER_PREFIX = re.compile(r"〔\d{4}〕\s*第\s*\d+\s*号")
DOC_NUMBER_LEADING_ZERO = re.compile(r"〔\d{4}〕\s*0\d+\s*号")
DATE_LEADING_ZERO = re.compile(r"\d{4}年0\d月|\d{4}年\d{1,2}月0\d日")


def _find_all(text: str, needle: str) -> Iterable[int]:
    start = 0
    while True:
        index = text.find(needle, start)
        if index < 0:
            return
        yield index
        start = index + len(needle)


def lint_text(text: str, *, source: str = "<text>", max_sentence_length: int = 120) -> list[Finding]:
    """Return explainable findings for plain text without modifying it."""

    findings: list[Finding] = []
    lines = text.splitlines() or [""]

    for line_number, line in enumerate(lines, start=1):
        for rule_id, rule in PHRASE_RULES.items():
            for phrase in rule["phrases"]:
                for index in _find_all(line, phrase):
                    findings.append(
                        Finding(
                            source=source,
                            line=line_number,
                            column=index + 1,
                            severity="warning",
                            rule=rule_id,
                            message=rule["message"],
                            matched_text=phrase,
                            suggestion=rule["suggestion"],
                        )
                    )

        for match in PLACEHOLDER_PATTERN.finditer(line):
            findings.append(
                Finding(
                    source=source,
                    line=line_number,
                    column=match.start() + 1,
                    severity="error",
                    rule="draft.placeholder",
                    message="文稿中仍含未清理的占位内容。",
                    matched_text=match.group(0),
                    suggestion="核实并补全内容；无法补全时删除占位符并说明实际情况。",
                )
            )

        for match in REPEATED_PUNCTUATION.finditer(line):
            findings.append(
                Finding(
                    source=source,
                    line=line_number,
                    column=match.start() + 1,
                    severity="warning",
                    rule="punctuation.repeated",
                    message="连续使用了多个中文标点。",
                    matched_text=match.group(0),
                    suggestion="根据句意保留一个恰当标点。",
                )
            )

        for match in HALFWIDTH_AFTER_CJK.finditer(line):
            findings.append(
                Finding(
                    source=source,
                    line=line_number,
                    column=match.start() + 1,
                    severity="warning",
                    rule="punctuation.halfwidth",
                    message="中文语句中使用了半角标点。",
                    matched_text=match.group(0),
                    suggestion="按语义改用全角中文标点。",
                )
            )

        for match in SENTENCE_PATTERN.finditer(line):
            compact = re.sub(r"\s+", "", match.group(0))
            if len(compact) <= max_sentence_length:
                continue
            findings.append(
                Finding(
                    source=source,
                    line=line_number,
                    column=match.start() + 1,
                    severity="warning",
                    rule="style.long_sentence",
                    message=f"该句去除空白后为 {len(compact)} 个字符，信息层次可能过密。",
                    matched_text=compact[:24] + "…",
                    suggestion="按事项、条件或逻辑层次拆分，并补足主语和谓语。",
                )
            )

        structure_rules = (
            (
                BAD_LEVEL_ONE,
                "gbt9704.structure.level_one",
                "第一层结构序数的标点不规范。",
                "使用“一、”形式。",
            ),
            (
                ASCII_LEVEL_TWO,
                "gbt9704.structure.level_two",
                "第二层结构序数使用了半角括号。",
                "使用“（一）”形式。",
            ),
            (
                BAD_LEVEL_THREE,
                "gbt9704.structure.level_three",
                "第三层结构序数的标点不规范。",
                "使用“1.”形式。",
            ),
            (
                ASCII_LEVEL_FOUR,
                "gbt9704.structure.level_four",
                "第四层结构序数使用了半角括号。",
                "使用“（1）”形式。",
            ),
            (
                BAD_ATTACHMENT_COLON,
                "gbt9704.attachment.colon",
                "附件说明使用了半角冒号。",
                "“附件”二字后使用全角冒号。",
            ),
            (
                ATTACHMENT_END_PUNCTUATION,
                "gbt9704.attachment.ending",
                "附件名称末尾不应加标点符号。",
                "删除附件名称后的标点。",
            ),
            (
                BAD_YEAR_BRACKETS,
                "gbt9704.document_number.year_brackets",
                "发文字号中的年份括号可能不规范。",
                "年份标全称，并使用六角括号“〔〕”。",
            ),
            (
                DOC_NUMBER_PREFIX,
                "gbt9704.document_number.prefix",
                "发文顺序号前不应使用“第”字。",
                "删除“第”字，阿拉伯数字后保留“号”。",
            ),
            (
                DOC_NUMBER_LEADING_ZERO,
                "gbt9704.document_number.leading_zero",
                "发文顺序号不应编虚位。",
                "删除顺序号前的0，例如将01号改为1号。",
            ),
            (
                DATE_LEADING_ZERO,
                "gbt9704.date.leading_zero",
                "成文日期的月或日不应编虚位。",
                "月、日前不加0，年份使用四位数字。",
            ),
        )
        for pattern, rule_id, message, suggestion in structure_rules:
            for match in pattern.finditer(line):
                findings.append(
                    Finding(
                        source=source,
                        line=line_number,
                        column=match.start() + 1,
                        severity="warning",
                        rule=rule_id,
                        message=message,
                        matched_text=match.group(0),
                        suggestion=suggestion,
                    )
                )

    return sorted(findings, key=lambda item: (item.source, item.line, item.column, item.rule))
