"""
FastAPI service: POST /v1/analyze — runs video-robot-eval pipeline per request.
Each HTTP request is independent (uvicorn workers / thread pool inside pipeline).
"""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.pipeline import VideoEvalError, evaluate_video_report, resolve_task

app = FastAPI(title="VLA video AI analyzer", version="1.0.0")


class AnalyzeRequest(BaseModel):
    video_url: str = Field(..., description="HTTP(S) URL to MP4")
    task: str = Field(
        default="",
        description="Natural-language task for the robot (empty = default prompt)",
    )
    embed_png: bool = Field(
        default=True,
        description="If true, embed base64 PNGs for high-importance frames (large JSON)",
    )
    fps: float = Field(default=2.0, description="Sampling rate (2 ≈ one frame every 0.5 s)")
    frames_per_batch: int = Field(default=12, ge=1, le=24)


class AnalyzeResponse(BaseModel):
    ok: bool
    analysis: dict | None = None
    error: str | None = None


def _run_sync(body: AnalyzeRequest) -> dict:
    work_root = Path(os.environ.get("VIDEO_ANALYZER_WORK_ROOT", tempfile.gettempdir()))
    work_root.mkdir(parents=True, exist_ok=True)
    work_dir = work_root / f"job_{uuid.uuid4().hex}"
    task = resolve_task(body.task)
    try:
        return evaluate_video_report(
            video_url=body.video_url.strip(),
            task=task,
            work_dir=work_dir,
            fps=body.fps,
            frames_per_batch=body.frames_per_batch,
            embed_high_importance_png=body.embed_png,
            log=True,
        )
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "vla-video-analyzer"}


@app.post("/v1/analyze", response_model=AnalyzeResponse)
async def analyze(body: AnalyzeRequest) -> AnalyzeResponse:
    if not body.video_url or not body.video_url.strip():
        raise HTTPException(status_code=400, detail="video_url required")
    try:
        report = await asyncio.to_thread(_run_sync, body)
    except VideoEvalError as e:
        if e.exit_code == 1:
            raise HTTPException(status_code=503, detail=e.message) from e
        if e.exit_code == 2:
            raise HTTPException(status_code=400, detail=e.message) from e
        raise HTTPException(status_code=500, detail=e.message) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return AnalyzeResponse(ok=True, analysis=report)
