from __future__ import annotations

import hashlib
import os
import threading
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import uuid4

from .chunking import chunk_text
from .config import Settings
from .ollama import OllamaEmbedder
from .parsers import SUPPORTED_EXTENSIONS, extract_text
from .store import KnowledgeStore

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024
EMBED_BATCH_SIZE = 16


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _drive_item_id(path: Path) -> str | None:
    for attribute in (
        "com.google.drivefs.item-id#S",
        "user.com.google.drivefs.item-id#S",
    ):
        try:
            raw = os.getxattr(path, attribute)
            value = raw.decode("utf-8", errors="ignore").strip("\x00 ")
            if value:
                return value
        except (AttributeError, OSError):
            continue
    return None


class KnowledgeService:
    def __init__(
        self,
        settings: Settings,
        store: KnowledgeStore | None = None,
        embedder: OllamaEmbedder | None = None,
    ):
        self.settings = settings
        self.store = store or KnowledgeStore(settings.db_path)
        self.embedder = embedder or OllamaEmbedder(
            settings.ollama_base_url, settings.ollama_embed_model
        )
        self._ingest_lock = threading.Lock()

    def close(self) -> None:
        self.store.close()

    def _source_uri(self, drive_item_id: str | None) -> str:
        if drive_item_id:
            return f"https://drive.google.com/open?id={drive_item_id}"
        if self.settings.drive_folder_id:
            return (
                "https://drive.google.com/drive/folders/"
                f"{self.settings.drive_folder_id}"
            )
        return ""

    def _scan_files(self) -> list[Path]:
        files: list[Path] = []
        for directory_name in self.settings.scan_dirs:
            directory = (self.settings.knowledge_root / directory_name).resolve()
            if (
                not directory.is_relative_to(self.settings.knowledge_root)
                or not directory.is_dir()
            ):
                continue
            for path in directory.rglob("*"):
                if (
                    path.is_file()
                    and path.suffix.lower() in SUPPORTED_EXTENSIONS
                    and not any(part.startswith(".") for part in path.relative_to(directory).parts)
                ):
                    files.append(path)
        return sorted(files)

    def ingest(self) -> dict[str, Any]:
        if not self._ingest_lock.acquire(blocking=False):
            return {"status": "already_running", **self.store.stats()}

        report: dict[str, Any] = {
            "status": "completed",
            "scanned": 0,
            "indexed": 0,
            "unchanged": 0,
            "failed": 0,
            "deleted": 0,
            "errors": [],
        }
        seen: set[str] = set()
        try:
            for path in self._scan_files():
                relative_path = path.relative_to(self.settings.knowledge_root).as_posix()
                seen.add(relative_path)
                report["scanned"] += 1
                try:
                    stat = path.stat()
                    if stat.st_size > MAX_FILE_SIZE_BYTES:
                        raise ValueError(
                            f"File exceeds {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB limit"
                        )
                    sha256 = _hash_file(path)
                    drive_item_id = _drive_item_id(path)
                    state = self.store.document_state(relative_path)
                    if (
                        state
                        and state.sha256 == sha256
                        and state.embedding_model == self.settings.ollama_embed_model
                        and state.last_error is None
                    ):
                        report["unchanged"] += 1
                        continue

                    text = extract_text(path)
                    chunks = chunk_text(
                        text,
                        size=self.settings.chunk_size,
                        overlap=self.settings.chunk_overlap,
                    )
                    if not chunks:
                        raise ValueError("Document contained no indexable text")

                    embeddings: list[list[float]] = []
                    for start in range(0, len(chunks), EMBED_BATCH_SIZE):
                        embeddings.extend(
                            self.embedder.embed(chunks[start : start + EMBED_BATCH_SIZE])
                        )

                    self.store.store_document(
                        relative_path=relative_path,
                        sha256=sha256,
                        modified_ns=stat.st_mtime_ns,
                        size_bytes=stat.st_size,
                        extension=path.suffix.lower(),
                        drive_item_id=drive_item_id,
                        source_uri=self._source_uri(drive_item_id),
                        embedding_model=self.settings.ollama_embed_model,
                        chunks=chunks,
                        embeddings=embeddings,
                    )
                    report["indexed"] += 1
                except Exception as error:
                    report["failed"] += 1
                    message = f"{relative_path}: {error}"
                    report["errors"].append(message)
                    try:
                        stat = path.stat()
                        self.store.store_error(
                            relative_path=relative_path,
                            sha256=_hash_file(path),
                            modified_ns=stat.st_mtime_ns,
                            size_bytes=stat.st_size,
                            extension=path.suffix.lower(),
                            drive_item_id=_drive_item_id(path),
                            source_uri=self._source_uri(_drive_item_id(path)),
                            embedding_model=self.settings.ollama_embed_model,
                            error=str(error),
                        )
                    except OSError:
                        pass

            report["deleted"] = self.store.delete_missing(seen)
            report.update(self.store.stats())
            return report
        finally:
            self._ingest_lock.release()

    def search(self, query: str, limit: int = 5) -> dict[str, Any]:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("query is required")
        vector = self.embedder.embed([normalized_query])[0]
        results = self.store.search(
            vector,
            model=self.settings.ollama_embed_model,
            limit=max(1, min(limit, 20)),
        )
        return {
            "query": normalized_query,
            "embedding_model": self.settings.ollama_embed_model,
            "results": results,
        }

    def write_output(self, relative_path: str, content: str) -> dict[str, str]:
        requested = PurePosixPath(relative_path)
        if requested.is_absolute() or ".." in requested.parts or not requested.parts:
            raise ValueError("relative_path must be a safe relative path")
        if requested.suffix.lower() not in {".md", ".txt"}:
            raise ValueError("generated outputs must use .md or .txt")

        output_root = (self.settings.knowledge_root / "40 Generated").resolve()
        target = (output_root / Path(*requested.parts)).resolve()
        if not target.is_relative_to(output_root):
            raise ValueError("output path escapes 40 Generated")

        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
        temporary.write_text(content, encoding="utf-8")
        os.replace(temporary, target)

        relative_to_drive = target.relative_to(self.settings.knowledge_root).as_posix()
        return {
            "relative_path": relative_to_drive,
            "source_uri": self._source_uri(_drive_item_id(target)),
        }
