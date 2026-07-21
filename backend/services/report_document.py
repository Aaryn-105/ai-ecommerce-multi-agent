"""Build and validate the semantic document consumed by report exporters."""
from __future__ import annotations

import re
from typing import Any


REPORT_DOCUMENT_VERSION = "1.0"


def _table_cells(line: str) -> list[str]:
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def _is_table_separator(line: str) -> bool:
    cells = _table_cells(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def _clean_text(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"```(?:markdown|md|json)?", "", text, flags=re.IGNORECASE)
    return text.replace("```", "").strip()


def build_report_document(
    content: str,
    *,
    title: str,
    summary: str,
) -> dict[str, Any]:
    """Normalize a generated report into semantic blocks for rich exporters.

    This conversion happens when a report is saved (or once for a legacy
    record). PDF and DOCX exporters consume the returned block model directly.
    """
    lines = _clean_text(content).replace("\r\n", "\n").replace("\r", "\n").split("\n")
    document: dict[str, Any] = {
        "version": REPORT_DOCUMENT_VERSION,
        "title": str(title or "").strip(),
        "summary": str(summary or "").strip(),
        "sections": [],
    }
    sections: list[dict[str, Any]] = document["sections"]
    current_section: dict[str, Any] | None = None
    paragraph_lines: list[str] = []

    def ensure_section(section_title: str = "\u62a5\u544a\u6b63\u6587") -> dict[str, Any]:
        nonlocal current_section
        if current_section is None:
            current_section = {"title": section_title, "blocks": []}
            sections.append(current_section)
        return current_section

    def append_block(block: dict[str, Any]) -> None:
        ensure_section()["blocks"].append(block)

    def flush_paragraph() -> None:
        text = " ".join(part.strip() for part in paragraph_lines if part.strip())
        paragraph_lines.clear()
        if text:
            append_block({"type": "paragraph", "text": text})

    index = 0
    while index < len(lines):
        raw_line = lines[index]
        stripped = raw_line.strip()
        if not stripped:
            flush_paragraph()
            index += 1
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading:
            flush_paragraph()
            level = len(heading.group(1))
            heading_text = heading.group(2).strip()
            if level == 1 and not document["title"]:
                document["title"] = heading_text
            elif level <= 2:
                current_section = {"title": heading_text, "blocks": []}
                sections.append(current_section)
            else:
                append_block({"type": "heading", "level": min(level, 4), "text": heading_text})
            index += 1
            continue

        if stripped.startswith("|") and index + 1 < len(lines) and _is_table_separator(lines[index + 1]):
            flush_paragraph()
            headers = _table_cells(stripped)
            rows: list[list[str]] = []
            index += 2
            while index < len(lines) and lines[index].strip().startswith("|"):
                row = _table_cells(lines[index])
                rows.append(row + [""] * max(0, len(headers) - len(row)))
                index += 1
            append_block({"type": "table", "headers": headers, "rows": rows})
            continue

        bullet = re.match(r"^\s*[-+*]\s+(.+)$", raw_line)
        ordered = re.match(r"^\s*(\d+)[.)]\s+(.+)$", raw_line)
        if bullet or ordered:
            flush_paragraph()
            block_type = "bullets" if bullet else "numbered"
            items: list[str] = []
            while index < len(lines):
                candidate = lines[index]
                match = (
                    re.match(r"^\s*[-+*]\s+(.+)$", candidate)
                    if block_type == "bullets"
                    else re.match(r"^\s*\d+[.)]\s+(.+)$", candidate)
                )
                if not match:
                    break
                items.append(match.group(1).strip())
                index += 1
            append_block({"type": block_type, "items": items})
            continue

        if stripped.startswith(">"):
            flush_paragraph()
            append_block({"type": "callout", "tone": "info", "text": stripped.lstrip(">").strip()})
            index += 1
            continue

        if re.fullmatch(r"[-*_]{3,}", stripped):
            flush_paragraph()
            index += 1
            continue

        paragraph_lines.append(stripped)
        index += 1

    flush_paragraph()
    if not sections:
        sections.append({
            "title": "\u5206\u6790\u7ed3\u679c",
            "blocks": [{"type": "paragraph", "text": document["summary"] or "\u6682\u65e0\u53ef\u5c55\u793a\u5185\u5bb9\u3002"}],
        })
    return normalize_report_document(document, title=title, summary=summary)


def normalize_report_document(
    value: Any,
    *,
    title: str = "",
    summary: str = "",
) -> dict[str, Any]:
    """Return a safe semantic report document with unsupported blocks removed."""
    source = value if isinstance(value, dict) else {}
    normalized: dict[str, Any] = {
        "version": str(source.get("version") or REPORT_DOCUMENT_VERSION),
        "title": str(source.get("title") or title or "").strip(),
        "summary": str(source.get("summary") or summary or "").strip(),
        "sections": [],
    }
    for section in source.get("sections") or []:
        if not isinstance(section, dict):
            continue
        section_title = str(section.get("title") or "\u5206\u6790\u7ed3\u679c").strip()
        blocks: list[dict[str, Any]] = []
        for block in section.get("blocks") or []:
            if not isinstance(block, dict):
                continue
            block_type = str(block.get("type") or "paragraph")
            if block_type in {"paragraph", "callout", "heading"}:
                text = _clean_text(block.get("text"))
                if text:
                    blocks.append({
                        "type": block_type,
                        "text": text,
                        "level": int(block.get("level") or 3),
                        "tone": str(block.get("tone") or "info"),
                    })
            elif block_type in {"bullets", "numbered"}:
                items = [_clean_text(item) for item in block.get("items") or []]
                items = [item for item in items if item]
                if items:
                    blocks.append({"type": block_type, "items": items})
            elif block_type == "table":
                headers = [_clean_text(cell) for cell in block.get("headers") or []]
                rows = [
                    [_clean_text(cell) for cell in row]
                    for row in block.get("rows") or []
                    if isinstance(row, list)
                ]
                if headers and rows:
                    blocks.append({"type": "table", "headers": headers, "rows": rows})
        if blocks:
            normalized["sections"].append({"title": section_title, "blocks": blocks})
    return normalized
