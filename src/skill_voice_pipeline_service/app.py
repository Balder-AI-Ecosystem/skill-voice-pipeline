from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


def _is_core_repo(candidate: Path) -> bool:
    return candidate.is_dir() and (candidate / "pyproject.toml").is_file() and (candidate / "ecosystem").is_dir()


def _candidate_core_repos() -> list[Path]:
    current_file = Path(__file__).resolve()
    repo_root = current_file.parents[2]
    candidates: list[Path] = []

    configured = str(os.getenv("AUTOBOT_CORE_REPO", "")).strip()
    if configured:
        candidates.append(Path(configured).expanduser())

    for anchor in (current_file.parent, Path.cwd().resolve()):
        candidates.extend([anchor, *anchor.parents])

    parent_dir = repo_root.parent
    if parent_dir.exists():
        candidates.extend(path for path in parent_dir.iterdir() if path.is_dir())

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        key = str(resolved).lower()
        if key not in seen:
            seen.add(key)
            unique.append(resolved)
    return unique


def _default_core_repo() -> Path:
    for candidate in _candidate_core_repos():
        if _is_core_repo(candidate):
            return candidate
    raise RuntimeError("Unable to locate the core repo. Set AUTOBOT_CORE_REPO to a valid core repo path.")


def _ensure_core_repo_on_path() -> Path:
    candidate = _default_core_repo()
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))
    return candidate


_CORE_REPO = _ensure_core_repo_on_path()

if TYPE_CHECKING:
    from ecosystem.domains.voice import VoicePipelineModule


class ExecuteRequest(BaseModel):
    capability: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    task_id: str | None = None
    session_id: str | None = None


class ExecuteResponse(BaseModel):
    task_id: str
    status: str
    detail: str
    capability: str
    module_name: str = "skill-voice-pipeline"
    artifacts: dict[str, Any] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)
    next_actions: list[str] = Field(default_factory=list)
    failure_category: str | None = None


app = FastAPI(title="skill-voice-pipeline", version="0.1.0")


def _runtime(parameters: dict[str, Any] | None = None) -> "VoicePipelineModule":
    from ecosystem.domains.voice import VoicePipelineModule

    params = dict(parameters or {})
    state_dir = str(params.get("state_dir") or "").strip() or None
    outputs_dir = str(params.get("outputs_dir") or "").strip() or None
    return VoicePipelineModule(
        state_dir=Path(state_dir) if state_dir else None,
        outputs_dir=Path(outputs_dir) if outputs_dir else None,
    )


def _manifest() -> dict[str, Any]:
    return {
        "name": "skill-voice-pipeline",
        "version": "0.1.0",
        "mode": "service",
        "entrypoint": "src.skill_voice_pipeline_service.app:app",
        "core_api": ">=1.0,<2.0",
        "service": {
            "base_url": "http://127.0.0.1:8420",
            "execute_path": "/execute",
            "health_path": "/health",
        },
        "capabilities": [
            "voice_pipeline.runtime_snapshot",
            "voice_pipeline.health_snapshot",
            "voice_pipeline.speech_to_text",
        ],
    }


def _task_result(
    *,
    task_id: str,
    capability: str,
    status: str,
    detail: str,
    artifacts: dict[str, Any] | None = None,
    evidence: dict[str, Any] | None = None,
    next_actions: list[str] | None = None,
    failure_category: str | None = None,
) -> ExecuteResponse:
    return ExecuteResponse(
        task_id=task_id,
        status=status,
        detail=detail,
        capability=capability,
        artifacts=dict(artifacts or {}),
        evidence=dict(evidence or {}),
        next_actions=list(next_actions or []),
        failure_category=failure_category,
    )


@app.get("/health")
def health() -> dict[str, Any]:
    runtime = _runtime()
    snapshot = runtime.health_snapshot().as_dict()
    snapshot["service"] = _manifest()["service"]
    return snapshot


@app.get("/manifest")
def manifest() -> dict[str, Any]:
    return _manifest()


@app.post("/execute")
async def execute(request: ExecuteRequest) -> dict[str, Any]:
    task_id = str(request.task_id or f"skill-voice-pipeline-{uuid4().hex}")
    capability = str(request.capability or "").strip()
    parameters = dict(request.parameters or {})
    runtime = _runtime(parameters)

    if capability == "voice_pipeline.runtime_snapshot":
        payload = runtime.snapshot()
        return _task_result(
            task_id=task_id,
            capability=capability,
            status="completed",
            detail="Voice pipeline runtime snapshot ready.",
            artifacts={"result": payload},
            evidence={"service_mode": True},
        ).model_dump()

    if capability == "voice_pipeline.health_snapshot":
        payload = runtime.health_snapshot().as_dict()
        return _task_result(
            task_id=task_id,
            capability=capability,
            status="completed",
            detail="Voice pipeline health snapshot ready.",
            artifacts={"result": payload},
            evidence={"service_mode": True},
        ).model_dump()

    if capability == "voice_pipeline.speech_to_text":
        audio_path = str(parameters.get("audio_path") or "").strip()
        if not audio_path:
            raise HTTPException(status_code=400, detail="voice_pipeline.speech_to_text requires audio_path.")
        payload = await runtime.transcribe_audio(
            provider=str(parameters.get("provider") or "").strip(),
            session_id=str(parameters.get("session_id") or request.session_id or "").strip(),
            chat_id=str(parameters.get("chat_id") or "").strip(),
            message_id=(int(parameters.get("message_id")) if isinstance(parameters.get("message_id"), int) else None),
            voice_file_id=str(parameters.get("voice_file_id") or "").strip(),
            audio_path=Path(audio_path),
            mime_type=str(parameters.get("mime_type") or "").strip() or None,
            duration_seconds=(
                int(parameters.get("duration_seconds"))
                if isinstance(parameters.get("duration_seconds"), int)
                else None
            ),
            file_size_bytes=(
                int(parameters.get("file_size_bytes"))
                if isinstance(parameters.get("file_size_bytes"), int)
                else None
            ),
            metadata=dict(parameters.get("metadata") or {}),
        )
        return _task_result(
            task_id=task_id,
            capability=capability,
            status=str(payload.get("status") or "failed"),
            detail=str(payload.get("detail") or "Voice pipeline transcription finished."),
            artifacts={"result": payload},
            evidence={"service_mode": True, "session_id": request.session_id},
            next_actions=list(payload.get("next_actions") or []),
            failure_category=str(payload.get("failure_category") or "").strip() or None,
        ).model_dump()

    raise HTTPException(status_code=404, detail=f"Unsupported capability: {capability}")
