# skill-voice-pipeline

Standalone voice pipeline service repo for voice runtime inspection and speech-to-text processing.

## Responsibility

This repo owns the voice pipeline boundary as a service skill. Core should call it only through the service contract declared in `skill.yaml`.

Capabilities declared in `skill.yaml`:

- `voice_pipeline.runtime_snapshot`
- `voice_pipeline.health_snapshot`
- `voice_pipeline.speech_to_text`

## Contract

- Mode: `service`
- Entrypoint: `src.skill_voice_pipeline_service.app:app`
- Healthcheck: `http://127.0.0.1:8420/health`
- Execute endpoint: `http://127.0.0.1:8420/execute`
- Manifest endpoint: `http://127.0.0.1:8420/manifest`
- Core API compatibility: `>=1.0,<2.0`

## Permissions

- `external_actions: false`
- `internet_access: true`
- `file_write: true`
- `read_memory: false`
- `write_memory: false`

## Integration rule

Core integration must stay at the service boundary defined by `skill.yaml`. Core should not couple directly to internal transcription helpers from this repo.
## Verification

- Recommended command: `python -m pytest -q`
- Current minimum coverage: manifest and contract smoke tests inside `tests/`

## Implementation status

This repo already owns the service boundary. A controlled local fallback may still exist in core during rollout, but the intended long-term integration path is the HTTP contract exposed by this repo.

Current dependency note: the service still resolves the core repo location, so implementation independence is not complete yet.
