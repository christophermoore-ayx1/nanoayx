from __future__ import annotations

import re


def normalize_text(text: str) -> str:
    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, size: int = 3000, overlap: int = 300) -> list[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []

    paragraphs = [part.strip() for part in normalized.split("\n\n") if part.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if len(paragraph) > size:
            if current:
                chunks.append(current)
                current = ""
            step = max(1, size - overlap)
            for start in range(0, len(paragraph), step):
                piece = paragraph[start : start + size].strip()
                if piece:
                    chunks.append(piece)
                if start + size >= len(paragraph):
                    break
            continue

        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if len(candidate) <= size:
            current = candidate
            continue

        chunks.append(current)
        prefix = current[-overlap:].strip() if overlap else ""
        current = f"{prefix}\n\n{paragraph}".strip() if prefix else paragraph

    if current:
        chunks.append(current)

    return chunks
