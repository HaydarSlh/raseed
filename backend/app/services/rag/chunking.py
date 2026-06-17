"""Heading-aware Markdown chunker: produces passages with heading_path + ordinal (research R9)."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Passage:
    heading_path: str
    ordinal: int
    content: str


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


def chunk_markdown(text: str, *, max_chars: int = 1500, overlap_chars: int = 100) -> list[Passage]:
    """Split markdown into passages, tracking heading hierarchy.

    Each passage carries the heading breadcrumb as heading_path (e.g. 'Overview > Key Points')
    and an ordinal for ordering within a document.
    """
    # Split into sections by headings
    sections = _split_by_headings(text)
    passages: list[Passage] = []
    ordinal = 0

    for heading_path, content in sections:
        content = content.strip()
        if not content:
            continue
        if len(content) <= max_chars:
            passages.append(Passage(heading_path=heading_path, ordinal=ordinal, content=content))
            ordinal += 1
        else:
            # Chunk long sections with overlap
            chunks = _split_with_overlap(content, max_chars=max_chars, overlap=overlap_chars)
            for i, chunk in enumerate(chunks):
                suffix = f" (part {i + 1})" if len(chunks) > 1 else ""
                passages.append(Passage(heading_path=heading_path + suffix, ordinal=ordinal, content=chunk))
                ordinal += 1

    return passages


def _split_by_headings(text: str) -> list[tuple[str, str]]:
    """Return (heading_path, content) pairs by splitting on heading lines."""
    lines = text.split("\n")
    sections: list[tuple[str, str]] = []
    heading_stack: list[tuple[int, str]] = []  # (level, title)
    current_lines: list[str] = []

    def flush(stack: list[tuple[int, str]], lines: list[str]) -> None:
        if lines:
            path = " > ".join(t for _, t in stack) if stack else "Introduction"
            sections.append((path, "\n".join(lines)))
            lines.clear()

    for line in lines:
        m = _HEADING_RE.match(line)
        if m:
            flush(heading_stack, current_lines)
            level = len(m.group(1))
            title = m.group(2).strip()
            # Trim stack to current level
            heading_stack = [(lv, t) for lv, t in heading_stack if lv < level]
            heading_stack.append((level, title))
        else:
            current_lines.append(line)

    flush(heading_stack, current_lines)
    return sections


def _split_with_overlap(text: str, *, max_chars: int, overlap: int) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + max_chars
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = end - overlap
    return chunks
