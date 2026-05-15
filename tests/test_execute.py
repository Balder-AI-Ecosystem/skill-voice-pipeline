from fastapi.testclient import TestClient

from skill_voice_pipeline_service.app import app


def test_health_endpoint_returns_200() -> None:
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data


def test_speech_to_text_missing_audio_path_returns_error() -> None:
    client = TestClient(app)
    resp = client.post(
        "/execute",
        json={
            "capability": "voice_pipeline.speech_to_text",
            "parameters": {
                "provider": "whisper",
                "session_id": "test-session",
                "chat_id": "123",
                "voice_file_id": "file-001",
                # missing audio_path
            },
        },
    )
    assert resp.status_code == 400


def test_speech_to_text_nonexistent_file_returns_error() -> None:
    client = TestClient(app)
    resp = client.post(
        "/execute",
        json={
            "capability": "voice_pipeline.speech_to_text",
            "parameters": {
                "provider": "whisper",
                "session_id": "test-session",
                "chat_id": "123",
                "voice_file_id": "file-001",
                "audio_path": "/nonexistent/path/audio.ogg",
            },
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "error"
