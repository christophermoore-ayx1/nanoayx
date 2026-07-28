from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.chunking import chunk_text
from app.config import Settings
from app.service import KnowledgeService


class FakeEmbedder:
    def is_available(self) -> bool:
        return True

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [
            [
                float(text.lower().count("nanoayx")),
                float(text.lower().count("telegram")),
                float(len(text)) / 1000.0,
            ]
            for text in texts
        ]


class KnowledgeServiceTest(unittest.TestCase):
    def test_chunking_preserves_overlap_and_limits_size(self) -> None:
        text = "\n\n".join(["alpha " * 100, "beta " * 100, "gamma " * 100])
        chunks = chunk_text(text, size=700, overlap=50)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 700 for chunk in chunks))

    def test_ingest_search_delete_and_safe_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "drive"
            source_dir = root / "10 Sources"
            source_dir.mkdir(parents=True)
            (root / "40 Generated").mkdir()
            source = source_dir / "operations.md"
            source.write_text(
                "NanoAYX communicates through Telegram and stores grounded citations.",
                encoding="utf-8",
            )
            settings = Settings(
                knowledge_root=root,
                db_path=Path(temp_dir) / "knowledge.db",
                drive_folder_id="folder-id",
                scan_dirs=("10 Sources",),
                scan_interval_seconds=0,
                ollama_base_url="http://unused",
                ollama_embed_model="fake-model",
                chunk_size=1000,
                chunk_overlap=100,
            )
            service = KnowledgeService(settings, embedder=FakeEmbedder())
            try:
                report = service.ingest()
                self.assertEqual(report["indexed"], 1)
                self.assertEqual(report["chunks"], 1)

                result = service.search("NanoAYX Telegram", limit=3)
                self.assertEqual(result["results"][0]["relative_path"], "10 Sources/operations.md")

                output = service.write_output("tests/result.md", "verified")
                self.assertEqual(output["relative_path"], "40 Generated/tests/result.md")
                self.assertEqual(
                    (root / "40 Generated/tests/result.md").read_text(encoding="utf-8"),
                    "verified",
                )

                source.unlink()
                deleted = service.ingest()
                self.assertEqual(deleted["deleted"], 1)
                self.assertEqual(deleted["documents"], 0)

                with self.assertRaises(ValueError):
                    service.write_output("../escape.md", "blocked")
            finally:
                service.close()


if __name__ == "__main__":
    unittest.main()
