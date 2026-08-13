"""Command-line interface for gongwen-lint."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from xml.etree import ElementTree
import zipfile

from .docx import read_docx
from .lint import Finding, lint_text
from .report import build_report, render_markdown


SUPPORTED_SUFFIXES = {".txt", ".md", ".docx"}
SEVERITY = {"warning": 1, "error": 2}


def _prepare_console() -> None:
    """Use UTF-8 for Chinese diagnostics on Windows and in CI."""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="backslashreplace")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gongwen-lint",
        description="在本地对中文公文进行透明、只读的规则校对。",
    )
    parser.add_argument("paths", nargs="+", help="要检查的文件或目录")
    parser.add_argument("--json", dest="json_path", help="写入 JSON 报告")
    parser.add_argument("--markdown", dest="markdown_path", help="写入 Markdown 报告")
    parser.add_argument(
        "--require-gbk-font",
        action="store_true",
        help="要求 DOCX 显式使用名称含 _GBK 的字体",
    )
    parser.add_argument(
        "--no-layout-check",
        action="store_true",
        help="不检查 GB/T 9704—2012 的 DOCX 纸张、页边和版心设置",
    )
    parser.add_argument(
        "--max-sentence-length",
        type=int,
        default=120,
        help="超长句提示阈值，默认 120 字符",
    )
    parser.add_argument(
        "--fail-level",
        choices=("warning", "error", "never"),
        default="warning",
        help="达到该严重程度时返回 1，默认 warning",
    )
    return parser


def _collect_paths(values: list[str]) -> list[Path]:
    collected: set[Path] = set()
    for value in values:
        path = Path(value).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"路径不存在：{path}")
        if path.is_dir():
            for candidate in path.rglob("*"):
                if candidate.is_file() and candidate.suffix.lower() in SUPPORTED_SUFFIXES:
                    collected.add(candidate.resolve())
        elif path.suffix.lower() in SUPPORTED_SUFFIXES:
            collected.add(path.resolve())
        else:
            raise ValueError(f"不支持的文件类型：{path}")
    return sorted(collected, key=lambda item: str(item).casefold())


def _read_text(path: Path) -> str:
    payload = path.read_bytes()
    try:
        return payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        return payload.decode("gb18030")


def _write(path: str, content: str) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    _prepare_console()
    args = _parser().parse_args(argv)
    try:
        paths = _collect_paths(args.paths)
        findings: list[Finding] = []
        for path in paths:
            if path.suffix.lower() == ".docx":
                text, docx_findings = read_docx(
                    path,
                    require_gbk_font=args.require_gbk_font,
                    check_gbt9704=not args.no_layout_check,
                )
                findings.extend(docx_findings)
            else:
                text = _read_text(path)
            findings.extend(
                lint_text(
                    text,
                    source=str(path),
                    max_sentence_length=args.max_sentence_length,
                )
            )
    except (OSError, ValueError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2

    findings.sort(key=lambda item: (item.source, item.line, item.column, item.rule))
    file_names = [str(path) for path in paths]
    report = build_report(file_names, findings)
    if args.json_path:
        _write(args.json_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    if args.markdown_path:
        _write(args.markdown_path, render_markdown(report))

    for item in findings:
        location = "style" if item.line == 0 else f"{item.line}:{item.column}"
        print(f"{item.source}:{location} [{item.severity}] {item.rule}")
        print(f"  {item.message} {item.suggestion}")
    print(f"Checked {len(paths)} file(s); found {len(findings)} issue(s).")

    if args.fail_level == "never":
        return 0
    threshold = SEVERITY[args.fail_level]
    return 1 if any(SEVERITY[item.severity] >= threshold for item in findings) else 0
