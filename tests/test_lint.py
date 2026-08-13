from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

from gongwen_lint.cli import main
from gongwen_lint.docx import read_docx
from gongwen_lint.lint import lint_text


class TextRulesTests(unittest.TestCase):
    def test_finds_targeted_wording_and_placeholder(self) -> None:
        text = "发挥压舱石作用，打造铁军。此项工作不一定完成。TODO"
        findings = lint_text(text, source="draft.txt")
        rules = [item.rule for item in findings]
        self.assertIn("wording.cliche", rules)
        self.assertIn("wording.military_metaphor", rules)
        self.assertIn("wording.evasive", rules)
        self.assertIn("draft.placeholder", rules)

    def test_finds_punctuation_problems(self) -> None:
        findings = lint_text("请抓紧落实！！并按期反馈,谢谢。")
        rules = [item.rule for item in findings]
        self.assertIn("punctuation.repeated", rules)
        self.assertIn("punctuation.halfwidth", rules)

    def test_long_sentence_threshold_is_configurable(self) -> None:
        findings = lint_text("这是一个很长的句子。", max_sentence_length=5)
        self.assertIn("style.long_sentence", [item.rule for item in findings])

    def test_finds_gbt9704_structure_and_numbering_problems(self) -> None:
        text = "一. 工作要求\n(一) 重点任务\n附件:方案。\n某发〔2026〕第01号\n2026年08月01日"
        rules = [item.rule for item in lint_text(text)]
        self.assertIn("gbt9704.structure.level_one", rules)
        self.assertIn("gbt9704.structure.level_two", rules)
        self.assertIn("gbt9704.attachment.colon", rules)
        self.assertIn("gbt9704.attachment.ending", rules)
        self.assertIn("gbt9704.document_number.prefix", rules)
        self.assertIn("gbt9704.date.leading_zero", rules)


class DocxTests(unittest.TestCase):
    def _make_docx(self, path: Path) -> None:
        document = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body><w:p><w:r><w:rPr><w:rFonts w:eastAsia="方正小标宋简体_2312"/></w:rPr>
  <w:t>这是压舱石。</w:t></w:r></w:p>
  <w:sectPr>
    <w:pgSz w:w="11906" w:h="16838"/>
    <w:pgMar w:top="2098" w:right="1474" w:bottom="1984" w:left="1587"/>
  </w:sectPr></w:body>
</w:document>"""
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("word/document.xml", document)

    def test_extracts_text_and_flags_legacy_font(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sample.docx"
            self._make_docx(path)
            text, findings = read_docx(path, require_gbk_font=True)
            self.assertEqual(text, "这是压舱石。")
            rules = [item.rule for item in findings]
            self.assertIn("font.legacy_2312", rules)
            self.assertIn("font.gbk_not_explicit", rules)
            self.assertNotIn("gbt9704.layout.a4_portrait", rules)
            self.assertNotIn("gbt9704.layout.top_margin", rules)
            self.assertNotIn("gbt9704.layout.left_margin", rules)
            self.assertNotIn("gbt9704.layout.text_area", rules)

    def test_cli_writes_json_report(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            draft = root / "draft.txt"
            draft.write_text("这里还有待补充内容。", encoding="utf-8")
            report_path = root / "result.json"
            exit_code = main([str(draft), "--json", str(report_path)])
            self.assertEqual(exit_code, 1)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["summary"]["file_count"], 1)
            self.assertEqual(report["findings"][0]["rule"], "draft.placeholder")

    def test_rejects_path_traversal_member(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "traversal.docx"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("../outside.xml", "unsafe")
                archive.writestr("word/document.xml", "<document />")
            with self.assertRaisesRegex(ValueError, "unsafe ZIP member path"):
                read_docx(path)

    def test_rejects_excessive_member_count(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "many-members.docx"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("word/document.xml", "<document />")
                for number in range(4):
                    archive.writestr(f"word/item-{number}.xml", "<item />")
            with mock.patch("gongwen_lint.docx.MAX_ZIP_MEMBERS", 4):
                with self.assertRaisesRegex(ValueError, "too many ZIP members"):
                    read_docx(path)

    def test_rejects_suspicious_compression_ratio(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "compressed.docx"
            payload = "<document>" + ("A" * 100_000) + "</document>"
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("word/document.xml", payload)
            with mock.patch("gongwen_lint.docx.MAX_COMPRESSION_RATIO", 10):
                with self.assertRaisesRegex(ValueError, "suspicious compression ratio"):
                    read_docx(path)

    def test_rejects_xml_dtd_and_entities(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "entity.docx"
            payload = '<!DOCTYPE doc [<!ENTITY sample "text">]><doc>&sample;</doc>'
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("word/document.xml", payload)
            with self.assertRaisesRegex(ValueError, "forbidden DTD or entity"):
                read_docx(path)

    def test_rejects_oversized_xml_member(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "large-xml.docx"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("word/document.xml", "<document />")
            with mock.patch("gongwen_lint.docx.MAX_XML_MEMBER_SIZE", 4):
                with self.assertRaisesRegex(ValueError, "XML member.*too large"):
                    read_docx(path)


if __name__ == "__main__":
    unittest.main()
