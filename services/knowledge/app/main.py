from __future__ import annotations

import asyncio
import contextlib
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .config import Settings
from .service import KnowledgeService

settings = Settings.from_env()
service = KnowledgeService(settings)


async def _ingest_loop() -> None:
    while True:
        try:
            await asyncio.to_thread(service.ingest)
        except Exception as error:
            print(f"[knowledge] background ingest failed: {error}", flush=True)
        if settings.scan_interval_seconds <= 0:
            return
        await asyncio.sleep(settings.scan_interval_seconds)


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(_ingest_loop())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        service.close()


app = FastAPI(title="NanoAYX Knowledge Service", version="0.1.0", lifespan=lifespan)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    limit: int = Field(default=5, ge=1, le=20)


class WriteOutputRequest(BaseModel):
    relative_path: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1, max_length=2_000_000)


@app.get("/health")
async def health() -> dict[str, Any]:
    ollama_available = await asyncio.to_thread(service.embedder.is_available)
    return {
        "status": "ok" if ollama_available else "degraded",
        "ollama_available": ollama_available,
        "embedding_model": settings.ollama_embed_model,
        **service.store.stats(),
    }


@app.get("/stats")
async def stats() -> dict[str, Any]:
    return {
        "knowledge_root": str(settings.knowledge_root),
        "scan_dirs": settings.scan_dirs,
        "embedding_model": settings.ollama_embed_model,
        **service.store.stats(),
    }


@app.post("/ingest")
async def ingest() -> dict[str, Any]:
    try:
        return await asyncio.to_thread(service.ingest)
    except Exception as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/search")
async def search(request: SearchRequest) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(service.search, request.query, request.limit)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/outputs")
async def write_output(request: WriteOutputRequest) -> dict[str, str]:
    try:
        return await asyncio.to_thread(
            service.write_output, request.relative_path, request.content
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except OSError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
