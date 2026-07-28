from __future__ import annotations

import math
import sqlite3
import threading
from array import array
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DocumentState:
    sha256: str
    embedding_model: str
    last_error: str | None


def _encode_vector(vector: list[float]) -> bytes:
    return array("f", vector).tobytes()


def _decode_vector(raw: bytes) -> array[float]:
    values: array[float] = array("f")
    values.frombytes(raw)
    return values


def _cosine_similarity(left: list[float], right_raw: bytes) -> float:
    right = _decode_vector(right_raw)
    if len(left) != len(right):
        return -1.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return -1.0
    return dot / (left_norm * right_norm)


class KnowledgeStore:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(db_path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._connection.execute("PRAGMA busy_timeout=5000")
        self._lock = threading.RLock()
        self._migrate()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def _migrate(self) -> None:
        with self._lock, self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY,
                    relative_path TEXT NOT NULL UNIQUE,
                    sha256 TEXT NOT NULL,
                    modified_ns INTEGER NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    extension TEXT NOT NULL,
                    drive_item_id TEXT,
                    source_uri TEXT NOT NULL,
                    embedding_model TEXT NOT NULL,
                    embedding_dimension INTEGER,
                    indexed_at TEXT NOT NULL,
                    last_error TEXT
                );

                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY,
                    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    chunk_index INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    embedding BLOB NOT NULL,
                    UNIQUE(document_id, chunk_index)
                );

                CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);
                CREATE INDEX IF NOT EXISTS idx_documents_model ON documents(embedding_model);
                """
            )

    def document_state(self, relative_path: str) -> DocumentState | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT sha256, embedding_model, last_error FROM documents WHERE relative_path = ?",
                (relative_path,),
            ).fetchone()
        if row is None:
            return None
        return DocumentState(
            sha256=str(row["sha256"]),
            embedding_model=str(row["embedding_model"]),
            last_error=row["last_error"],
        )

    def store_document(
        self,
        *,
        relative_path: str,
        sha256: str,
        modified_ns: int,
        size_bytes: int,
        extension: str,
        drive_item_id: str | None,
        source_uri: str,
        embedding_model: str,
        chunks: list[str],
        embeddings: list[list[float]],
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunk and embedding counts differ")
        dimension = len(embeddings[0]) if embeddings else None
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO documents (
                    relative_path, sha256, modified_ns, size_bytes, extension,
                    drive_item_id, source_uri, embedding_model,
                    embedding_dimension, indexed_at, last_error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), NULL)
                ON CONFLICT(relative_path) DO UPDATE SET
                    sha256 = excluded.sha256,
                    modified_ns = excluded.modified_ns,
                    size_bytes = excluded.size_bytes,
                    extension = excluded.extension,
                    drive_item_id = excluded.drive_item_id,
                    source_uri = excluded.source_uri,
                    embedding_model = excluded.embedding_model,
                    embedding_dimension = excluded.embedding_dimension,
                    indexed_at = excluded.indexed_at,
                    last_error = NULL
                """,
                (
                    relative_path,
                    sha256,
                    modified_ns,
                    size_bytes,
                    extension,
                    drive_item_id,
                    source_uri,
                    embedding_model,
                    dimension,
                ),
            )
            document_id = int(
                self._connection.execute(
                    "SELECT id FROM documents WHERE relative_path = ?", (relative_path,)
                ).fetchone()["id"]
            )
            self._connection.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
            self._connection.executemany(
                """
                INSERT INTO chunks (document_id, chunk_index, text, embedding)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (document_id, index, text, _encode_vector(vector))
                    for index, (text, vector) in enumerate(
                        zip(chunks, embeddings, strict=True)
                    )
                ],
            )

    def store_error(
        self,
        *,
        relative_path: str,
        sha256: str,
        modified_ns: int,
        size_bytes: int,
        extension: str,
        drive_item_id: str | None,
        source_uri: str,
        embedding_model: str,
        error: str,
    ) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO documents (
                    relative_path, sha256, modified_ns, size_bytes, extension,
                    drive_item_id, source_uri, embedding_model,
                    embedding_dimension, indexed_at, last_error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, datetime('now'), ?)
                ON CONFLICT(relative_path) DO UPDATE SET
                    sha256 = excluded.sha256,
                    modified_ns = excluded.modified_ns,
                    size_bytes = excluded.size_bytes,
                    extension = excluded.extension,
                    drive_item_id = excluded.drive_item_id,
                    source_uri = excluded.source_uri,
                    embedding_model = excluded.embedding_model,
                    embedding_dimension = NULL,
                    indexed_at = excluded.indexed_at,
                    last_error = excluded.last_error
                """,
                (
                    relative_path,
                    sha256,
                    modified_ns,
                    size_bytes,
                    extension,
                    drive_item_id,
                    source_uri,
                    embedding_model,
                    error[:2000],
                ),
            )
            document_id = self._connection.execute(
                "SELECT id FROM documents WHERE relative_path = ?", (relative_path,)
            ).fetchone()["id"]
            self._connection.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))

    def delete_missing(self, seen_paths: set[str]) -> int:
        with self._lock, self._connection:
            rows = self._connection.execute("SELECT relative_path FROM documents").fetchall()
            missing = [str(row["relative_path"]) for row in rows if row["relative_path"] not in seen_paths]
            self._connection.executemany(
                "DELETE FROM documents WHERE relative_path = ?",
                [(relative_path,) for relative_path in missing],
            )
        return len(missing)

    def search(self, query_vector: list[float], model: str, limit: int) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT
                    c.chunk_index, c.text, c.embedding,
                    d.relative_path, d.drive_item_id, d.source_uri,
                    d.modified_ns, d.sha256
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                WHERE d.embedding_model = ? AND d.last_error IS NULL
                """,
                (model,),
            ).fetchall()

        scored = [
            (
                _cosine_similarity(query_vector, bytes(row["embedding"])),
                {
                    "score": 0.0,
                    "relative_path": str(row["relative_path"]),
                    "chunk_index": int(row["chunk_index"]),
                    "text": str(row["text"]),
                    "drive_item_id": row["drive_item_id"],
                    "source_uri": str(row["source_uri"]),
                    "modified_ns": int(row["modified_ns"]),
                    "sha256": str(row["sha256"]),
                },
            )
            for row in rows
        ]
        scored.sort(key=lambda item: item[0], reverse=True)
        results = []
        for score, result in scored[:limit]:
            result["score"] = round(score, 6)
            results.append(result)
        return results

    def stats(self) -> dict[str, Any]:
        with self._lock:
            document_row = self._connection.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN last_error IS NULL THEN 1 ELSE 0 END) AS indexed,
                    SUM(CASE WHEN last_error IS NOT NULL THEN 1 ELSE 0 END) AS failed
                FROM documents
                """
            ).fetchone()
            chunk_count = int(
                self._connection.execute("SELECT COUNT(*) AS count FROM chunks").fetchone()["count"]
            )
            models = [
                str(row["embedding_model"])
                for row in self._connection.execute(
                    "SELECT DISTINCT embedding_model FROM documents ORDER BY embedding_model"
                ).fetchall()
            ]
        return {
            "documents": int(document_row["total"] or 0),
            "indexed_documents": int(document_row["indexed"] or 0),
            "failed_documents": int(document_row["failed"] or 0),
            "chunks": chunk_count,
            "embedding_models": models,
        }
