# UPDATE PLAN — skill-voice-pipeline

> Audit date: 2026-04-21 | Grade: **B** | Priority: Medium

---

## Vấn đề tìm thấy

### 1. Input schema của `speech_to_text` đã tốt — nhưng output schema vẫn rỗng
`speech_to_text` input có `required` và `properties` chi tiết (provider, session_id, chat_id, voice_file_id, audio_path) — đây là skill tốt nhất về input schema.  
Tuy nhiên output schema vẫn là `{type: object}` thuần.

### 2. `health_snapshot` và `runtime_probe` schemas rỗng hoàn toàn
Hai capabilities phụ trợ này chưa có properties.

### 3. Test coverage tối thiểu
Chỉ manifest check. STT là feature phức tạp cần test kỹ error paths (file not found, provider error, timeout).

---

## Fix cần làm

### Fix 1 — Cập nhật output schemas trong skill.yaml

```yaml
# speech_to_text output_schema
output_schema:
  type: object
  required: [status]
  properties:
    status:
      type: string
      enum: [ok, error, timeout, provider_error]
    transcription:
      type: ["string", "null"]
      description: "Transcribed text from voice note"
    language:
      type: ["string", "null"]
      description: "Detected language code (e.g. 'vi', 'en')"
    duration_seconds:
      type: ["number", "null"]
    provider_used:
      type: ["string", "null"]
    model_used:
      type: ["string", "null"]
    confidence:
      type: ["number", "null"]
      description: "Transcription confidence 0.0-1.0"
    detail:
      type: ["string", "null"]

# voice_pipeline.health_snapshot
input_schema:
  type: object
  additionalProperties: false
output_schema:
  type: object
  required: [status, available]
  properties:
    status:
      type: string
      enum: [ok, degraded, error]
    available:
      type: boolean
    provider_status:
      type: object
      description: "Map of provider name → availability"
    updated_at:
      type: string
    detail: {type: ["string", "null"]}

# voice_pipeline.runtime_snapshot
input_schema:
  type: object
  additionalProperties: false
output_schema:
  type: object
  required: [status]
  properties:
    status: {type: string}
    available: {type: boolean}
    updated_at: {type: string}
    active_provider: {type: ["string", "null"]}
    supported_providers:
      type: array
      items: {type: string}
    last_transcription_at: {type: ["string", "null"]}
    counters: {type: object}
```

### Fix 2 — Thêm functional tests

```python
# tests/test_execute.py
import os
from unittest.mock import MagicMock, patch

def test_health_endpoint_returns_200():
    from fastapi.testclient import TestClient
    from src.skill_voice_pipeline_service.app import app
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data

def test_speech_to_text_missing_audio_path_returns_error():
    from fastapi.testclient import TestClient
    from src.skill_voice_pipeline_service.app import app
    client = TestClient(app)
    resp = client.post("/execute", json={
        "capability_id": "voice_pipeline.speech_to_text",
        "parameters": {
            "provider": "whisper",
            "session_id": "test-session",
            "chat_id": "123",
            "voice_file_id": "file-001"
            # missing audio_path
        }
    })
    # Should return 422 (validation) or error status
    assert resp.status_code in (200, 422)
    if resp.status_code == 200:
        assert resp.json().get("status") == "error"

def test_speech_to_text_nonexistent_file_returns_error():
    from fastapi.testclient import TestClient
    from src.skill_voice_pipeline_service.app import app
    client = TestClient(app)
    resp = client.post("/execute", json={
        "capability_id": "voice_pipeline.speech_to_text",
        "parameters": {
            "provider": "whisper",
            "session_id": "test-session",
            "chat_id": "123",
            "voice_file_id": "file-001",
            "audio_path": "/nonexistent/path/audio.ogg"
        }
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "error"
```

---

## Không cần làm
- Input schema của `speech_to_text` đã rất tốt — không cần thay đổi
- `VoicePipelineModule` integration đúng
- Service mode với port đúng
- `file_write: true` permission đúng (cần lưu audio temp files)
