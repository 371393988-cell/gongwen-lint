"""Minimal DOCX text and font inspection using the standard library."""

from __future__ import annotations

from pathlib import Path
from pathlib import PurePosixPath
import stat
import zipfile
from xml.etree import ElementTree

from .lint import Finding


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": WORD_NS}
TWIPS_PER_MM = 1440 / 25.4

# Conservative defaults for documents accepted from untrusted sources.  The
# checks run against ZIP metadata before any member is decompressed.
MAX_ARCHIVE_SIZE = 100 * 1024 * 1024
MAX_ZIP_MEMBERS = 2048
MAX_MEMBER_SIZE = 64 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_SIZE = 256 * 1024 * 1024
MAX_COMPRESSION_RATIO = 1000
MAX_XML_MEMBER_SIZE = 32 * 1024 * 1024


def _safe_member_name(name: str) -> str:
    """Return a normalized ZIP member name or reject unsafe paths."""

    if not name or "\x00" in name:
        raise ValueError("DOCX contains an empty or invalid ZIP member name")
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if normalized.startswith("/") or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"DOCX contains an unsafe ZIP member path: {name!r}")
    if path.parts and ":" in path.parts[0]:
        raise ValueError(f"DOCX contains an unsafe ZIP member path: {name!r}")
    return path.as_posix()


def _preflight_archive(path: str | Path, archive: zipfile.ZipFile) -> None:
    """Validate ZIP metadata before reading untrusted DOCX members."""

    archive_size = Path(path).stat().st_size
    if archive_size > MAX_ARCHIVE_SIZE:
        raise ValueError(
            f"DOCX archive is too large ({archive_size} bytes; limit {MAX_ARCHIVE_SIZE})"
        )

    members = archive.infolist()
    if len(members) > MAX_ZIP_MEMBERS:
        raise ValueError(
            f"DOCX contains too many ZIP members ({len(members)}; limit {MAX_ZIP_MEMBERS})"
        )

    total_size = 0
    seen: set[str] = set()
    for info in members:
        normalized = _safe_member_name(info.filename)
        if normalized in seen:
            raise ValueError(f"DOCX contains a duplicate ZIP member: {normalized!r}")
        seen.add(normalized)

        if info.flag_bits & 0x1:
            raise ValueError(f"DOCX contains an encrypted ZIP member: {normalized!r}")

        file_type = (info.external_attr >> 16) & 0o170000
        if file_type == stat.S_IFLNK:
            raise ValueError(f"DOCX contains a symbolic-link ZIP member: {normalized!r}")

        if info.file_size > MAX_MEMBER_SIZE:
            raise ValueError(
                f"DOCX member {normalized!r} is too large "
                f"({info.file_size} bytes; limit {MAX_MEMBER_SIZE})"
            )
        total_size += info.file_size
        if total_size > MAX_TOTAL_UNCOMPRESSED_SIZE:
            raise ValueError(
                "DOCX uncompressed content exceeds the configured safety limit "
                f"({MAX_TOTAL_UNCOMPRESSED_SIZE} bytes)"
            )

        if info.file_size:
            if info.compress_size == 0:
                raise ValueError(
                    f"DOCX member {normalized!r} has an invalid compression size"
                )
            ratio = info.file_size / info.compress_size
            if ratio > MAX_COMPRESSION_RATIO:
                raise ValueError(
                    f"DOCX member {normalized!r} has a suspicious compression ratio "
                    f"({ratio:.0f}:1; limit {MAX_COMPRESSION_RATIO}:1)"
                )


def _attr(element: ElementTree.Element, name: str) -> str | None:
    return element.get(f"{{{WORD_NS}}}{name}")


def _to_mm(value: str | None) -> float | None:
    if value is None:
        return None
    return int(value) / TWIPS_PER_MM


def _near(actual: float | None, expected: float, tolerance: float = 1.0) -> bool:
    return actual is not None and abs(actual - expected) <= tolerance


def _layout_findings(
    document: ElementTree.Element,
    styles: ElementTree.Element | None,
    source: str,
) -> list[Finding]:
    findings: list[Finding] = []
    sections = document.findall(".//w:sectPr", NS)
    if not sections:
        return [
            Finding(
                source=source,
                line=0,
                column=0,
                severity="warning",
                rule="gbt9704.layout.section_missing",
                message="未识别到可检查的 DOCX 页面设置。",
                suggestion="在 Word 中人工核对 A4 纵向纸张、页边和版心尺寸。",
            )
        ]

    for section_number, section in enumerate(sections, start=1):
        page_size = section.find("w:pgSz", NS)
        page_margin = section.find("w:pgMar", NS)
        if page_size is None or page_margin is None:
            findings.append(
                Finding(
                    source=source,
                    line=0,
                    column=0,
                    severity="warning",
                    rule="gbt9704.layout.incomplete",
                    message=f"第 {section_number} 节缺少完整的纸张或页边设置。",
                    suggestion="在 Word 页面设置中核对 GB/T 9704—2012 的版面要求。",
                )
            )
            continue

        width = _to_mm(_attr(page_size, "w"))
        height = _to_mm(_attr(page_size, "h"))
        orient = (_attr(page_size, "orient") or "portrait").lower()
        if not (_near(width, 210) and _near(height, 297) and orient != "landscape"):
            findings.append(
                Finding(
                    source=source,
                    line=0,
                    column=0,
                    severity="error",
                    rule="gbt9704.layout.a4_portrait",
                    message=(
                        f"第 {section_number} 节纸张约为 {width or 0:.1f} mm×"
                        f"{height or 0:.1f} mm，方向为 {orient}。"
                    ),
                    suggestion="设置为 A4 纵向纸张（210 mm×297 mm）。",
                )
            )

        top = _to_mm(_attr(page_margin, "top"))
        left = _to_mm(_attr(page_margin, "left"))
        right = _to_mm(_attr(page_margin, "right"))
        bottom = _to_mm(_attr(page_margin, "bottom"))
        if not _near(top, 37):
            findings.append(
                Finding(
                    source=source,
                    line=0,
                    column=0,
                    severity="warning",
                    rule="gbt9704.layout.top_margin",
                    message=f"第 {section_number} 节上白边约为 {top or 0:.1f} mm。",
                    suggestion="标准值为 37 mm，允许误差 ±1 mm。",
                )
            )
        if not _near(left, 28):
            findings.append(
                Finding(
                    source=source,
                    line=0,
                    column=0,
                    severity="warning",
                    rule="gbt9704.layout.left_margin",
                    message=f"第 {section_number} 节左白边约为 {left or 0:.1f} mm。",
                    suggestion="标准值为 28 mm，允许误差 ±1 mm。",
                )
            )

        text_width = None if None in (width, left, right) else width - left - right
        text_height = None if None in (height, top, bottom) else height - top - bottom
        if not (_near(text_width, 156) and _near(text_height, 225)):
            findings.append(
                Finding(
                    source=source,
                    line=0,
                    column=0,
                    severity="warning",
                    rule="gbt9704.layout.text_area",
                    message=(
                        f"第 {section_number} 节版心约为 {text_width or 0:.1f} mm×"
                        f"{text_height or 0:.1f} mm。"
                    ),
                    suggestion="标准版心尺寸为 156 mm×225 mm。",
                )
            )

    if styles is not None:
        normal_style = None
        for style in styles.findall(".//w:style", NS):
            style_id = _attr(style, "styleId") or ""
            name = style.find("w:name", NS)
            style_name = _attr(name, "val") if name is not None else ""
            if style_id == "Normal" or style_name in {"Normal", "正文"}:
                normal_style = style
                break
        if normal_style is not None:
            size = normal_style.find(".//w:rPr/w:sz", NS)
            value = _attr(size, "val") if size is not None else None
            if value is not None:
                points = int(value) / 2
                if abs(points - 16) > 0.1:
                    findings.append(
                        Finding(
                            source=source,
                            line=0,
                            column=0,
                            severity="warning",
                            rule="gbt9704.font.body_size",
                            message=f"正文样式字号为 {points:g} pt。",
                            suggestion="一般正文使用3号字（16 pt）；特殊情况可适当调整。",
                        )
                    )
    return findings


def _read_xml(archive: zipfile.ZipFile, member: str) -> ElementTree.Element | None:
    try:
        info = archive.getinfo(member)
    except KeyError:
        return None
    if info.file_size > MAX_XML_MEMBER_SIZE:
        raise ValueError(
            f"DOCX XML member {member!r} is too large "
            f"({info.file_size} bytes; limit {MAX_XML_MEMBER_SIZE})"
        )
    payload = archive.read(info)
    upper_payload = payload.upper()
    if b"<!DOCTYPE" in upper_payload or b"<!ENTITY" in upper_payload:
        raise ValueError(f"DOCX XML member {member!r} contains a forbidden DTD or entity")
    return ElementTree.fromstring(payload)


def read_docx(
    path: str | Path,
    *,
    require_gbk_font: bool = False,
    check_gbt9704: bool = True,
) -> tuple[str, list[Finding]]:
    """Extract paragraph text and return font-related findings."""

    source = str(path)
    findings: list[Finding] = []
    with zipfile.ZipFile(path) as archive:
        _preflight_archive(path, archive)
        document = _read_xml(archive, "word/document.xml")
        if document is None:
            raise ValueError("DOCX is missing word/document.xml")

        paragraphs: list[str] = []
        for paragraph in document.findall(".//w:p", NS):
            text = "".join(node.text or "" for node in paragraph.findall(".//w:t", NS))
            paragraphs.append(text)

        styles = _read_xml(archive, "word/styles.xml")
        font_names: set[str] = set()
        for member in ("word/document.xml", "word/styles.xml"):
            root = document if member == "word/document.xml" else styles
            if root is None:
                continue
            for fonts in root.findall(".//w:rFonts", NS):
                for value in fonts.attrib.values():
                    if value:
                        font_names.add(value)

    if check_gbt9704:
        findings.extend(_layout_findings(document, styles, source))

    for font in sorted(font_names):
        if "2312" in font:
            findings.append(
                Finding(
                    source=source,
                    line=0,
                    column=0,
                    severity="error",
                    rule="font.legacy_2312",
                    message=f"文档显式使用了旧字体“{font}”。",
                    matched_text=font,
                    suggestion="按本单位排版规范改用相应的方正_GBK系列字体，并人工复核版式。",
                )
            )

    if require_gbk_font and not any("_GBK" in font.upper() for font in font_names):
        findings.append(
            Finding(
                source=source,
                line=0,
                column=0,
                severity="warning",
                rule="font.gbk_not_explicit",
                message="未在文档或样式中识别到名称含“_GBK”的显式字体设置。",
                suggestion="检查正文和各级标题样式；主题字体可能需要在 Word 中人工复核。",
            )
        )

    return "\n".join(paragraphs), findings
