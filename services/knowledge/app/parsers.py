from __future__ import annotations

import json
from pathlib import Path

from docx import Document
from pypdf import PdfReader

from .chunking import normalize_text

TEXT_EXTENSIONS = {
    ".csv",
    ".html",
    ".json",
    ".log",
    ".md",
    ".rst",
    ".text",
    ".toml",
    ".tsv",
    ".txt",
    ".yaml",
    ".yml",
}
NATIVE_GOOGLE_EXTENSIONS = {".gdoc", ".gsheet", ".gslides"}
SUPPORTED_EXTENSIONS = TEXT_EXTENSIONS | {".docx", ".pdf"} | NATIVE_GOOGLE_EXTENSIONS


class NativeGoogleFileError(ValueError):
    pass


def parse_native_google_pointer(path: Path) -> dict[str, str]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return {str(key): str(value) for key, value in raw.items() if isinstance(value, (str, int))}


def extract_text(path: Path) -> str:
    extension = path.suffix.lower()
    if extension in TEXT_EXTENSIONS:
        return normalize_text(path.read_text(encoding="utf-8", errors="replace"))

    if extension == ".pdf":
        reader = PdfReader(str(path))
        return normalize_text("\n\n".join(page.extract_text() or "" for page in reader.pages))

    if extension == ".docx":
        document = Document(str(path))
        return normalize_text("\n\n".join(paragraph.text for paragraph in document.paragraphs))

    if extension in NATIVE_GOOGLE_EXTENSIONS:
        pointer = parse_native_google_pointer(path)
        url = pointer.get("url", pointer.get("doc_id", "unknown"))
        raise NativeGoogleFileError(
            f"Native Google file pointer requires Drive API export before indexing: {url}"
        )

    raise ValueError(f"Unsupported file extension: {extension or '<none>'}")
