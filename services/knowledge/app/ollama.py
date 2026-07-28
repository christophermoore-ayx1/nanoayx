from __future__ import annotations

from collections.abc import Sequence

import httpx


class OllamaEmbedder:
    def __init__(self, base_url: str, model: str, timeout_seconds: float = 180.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def is_available(self) -> bool:
        try:
            response = httpx.get(f"{self.base_url}/api/tags", timeout=5.0)
            response.raise_for_status()
            return True
        except (httpx.HTTPError, ValueError):
            return False

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        response = httpx.post(
            f"{self.base_url}/api/embed",
            json={"model": self.model, "input": list(texts), "truncate": True},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        embeddings = payload.get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise RuntimeError("Ollama returned an invalid embeddings payload")
        vectors = [[float(value) for value in vector] for vector in embeddings]
        dimensions = {len(vector) for vector in vectors}
        if len(dimensions) != 1 or 0 in dimensions:
            raise RuntimeError("Ollama returned inconsistent embedding dimensions")
        return vectors
