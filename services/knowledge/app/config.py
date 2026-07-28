from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _csv(name: str, default: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in os.getenv(name, default).split(",") if part.strip())


@dataclass(frozen=True)
class Settings:
    knowledge_root: Path
    db_path: Path
    drive_folder_id: str
    scan_dirs: tuple[str, ...]
    scan_interval_seconds: int
    ollama_base_url: str
    ollama_embed_model: str
    chunk_size: int
    chunk_overlap: int

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            knowledge_root=Path(os.getenv("KNOWLEDGE_ROOT", "/knowledge/drive")).resolve(),
            db_path=Path(os.getenv("KNOWLEDGE_DB_PATH", "/data/knowledge.db")).resolve(),
            drive_folder_id=os.getenv("KNOWLEDGE_DRIVE_FOLDER_ID", ""),
            scan_dirs=_csv("KNOWLEDGE_SCAN_DIRS", "00 Inbox,10 Sources,20 Notes,30 Projects,90 Archive"),
            scan_interval_seconds=max(0, int(os.getenv("KNOWLEDGE_SCAN_INTERVAL_SECONDS", "300"))),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434").rstrip("/"),
            ollama_embed_model=os.getenv("OLLAMA_EMBED_MODEL", "embeddinggemma"),
            chunk_size=max(500, int(os.getenv("KNOWLEDGE_CHUNK_SIZE", "3000"))),
            chunk_overlap=max(0, int(os.getenv("KNOWLEDGE_CHUNK_OVERLAP", "300"))),
        )
