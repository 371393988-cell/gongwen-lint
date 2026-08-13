"""Report serialization helpers."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .lint import Finding


def build_report(files: Iterable[str], findings: Iterable[Finding]) -> dict:
    file_list = list(files)
    finding_list = list(findings)
    severity_counts = Counter(item.severity for item in finding_list)
    rule_counts = Counter(item.rule for item in finding_list)
    return {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "files": file_list,
        "summary": {
            "file_count": len(file_list),
            "finding_count": len(finding_list),
            "by_severity": dict(sorted(severity_counts.items())),
            "by_rule": dict(sorted(rule_counts.items())),
        },
        "findings": [item.to_dict() for item in finding_list],
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# 公文校对报告",
        "",
        f"- 文件数：{report['summary']['file_count']}",
        f"- 问题数：{report['summary']['finding_count']}",
        f"- 生成时间：{report['generated_at_utc']}",
        "",
        "| 严重程度 | 数量 |",
        "| --- | ---: |",
    ]
    for severity, count in report["summary"]["by_severity"].items():
        lines.append(f"| {severity} | {count} |")

    lines.extend(
        [
            "",
            "## 具体问题",
            "",
            "| 文件 | 位置 | 程度 | 规则 | 命中内容 | 说明与建议 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in report["findings"]:
        location = "文档样式" if item["line"] == 0 else f"{item['line']}:{item['column']}"
        source = Path(item["source"]).name.replace("|", "\\|")
        explanation = (item["message"] + " " + item["suggestion"]).replace("|", "\\|")
        matched = item["matched_text"].replace("|", "\\|")
        lines.append(
            f"| {source} | {location} | {item['severity']} | {item['rule']} | "
            f"{matched} | {explanation} |"
        )
    return "\n".join(lines) + "\n"
