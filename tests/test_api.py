import pytest
from jarvis.db import Job


def test_authentication_and_origin_checks(client):
    assert client.get("/api/health", headers={"Authorization": ""}).status_code == 200
    assert client.get("/api/calendars", headers={"Authorization": ""}).status_code == 401
    assert client.get("/api/calendars").status_code == 200
    assert (
        client.post(
            "/api/proposals", json={}, headers={"Origin": "https://attacker.test"}
        ).status_code
        == 403
    )
    response = client.get("/api/calendars")
    assert response.headers["Cache-Control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_http_proposal_review_and_reject(client, event_data):
    result = client.post(
        "/api/proposals", json={"operation": "event_create", "payload": event_data}
    )
    assert result.status_code == 201
    p = result.json()
    assert client.get(f"/api/proposals/{p['id']}").json()["status"] == "pending"
    assert client.post(f"/api/proposals/{p['id']}/reject").status_code == 200
    assert client.post(f"/api/proposals/{p['id']}/approve", json={}).status_code == 409
    assert client.get("/api/proposals/missing").status_code == 404


def test_duplicate_capture_and_conversation_serialization(client, db):
    payload = {"text": "Dinner tomorrow", "request_id": "one"}
    first = client.post("/api/messages", json=payload).json()
    assert client.post("/api/messages", json=payload).json()["id"] == first["id"]
    assert client.post("/api/messages", json={**payload, "text": "Different"}).status_code == 409
    next_turn = {
        "text": "At seven",
        "request_id": "two",
        "conversation_id": first["conversation_id"],
    }
    assert client.post("/api/messages", json=next_turn).status_code == 409
    with db.sessions.begin() as s:
        s.get(Job, first["id"]).status = "completed"
    assert client.post("/api/messages", json=next_turn).status_code == 202


def test_upload_limits_idempotency_and_private_paths(client, settings):
    response = client.post(
        "/api/recordings",
        data={"request_id": "audio1"},
        files={"audio": ("../../evil.wav", b"sample audio", "audio/wav")},
    )
    assert response.status_code == 202
    first = response.json()
    second = client.post(
        "/api/recordings",
        data={"request_id": "audio1"},
        files={"audio": ("other", b"sample audio", "audio/webm")},
    )
    assert second.json()["id"] == first["id"]
    assert len(list((settings.data_dir / "audio").iterdir())) == 1
    assert "payload" not in client.get(f"/api/jobs/{first['id']}").json()
    assert (
        client.post(
            "/api/recordings", data={"request_id": "empty"}, files={"audio": ("empty", b"")}
        ).status_code
        == 422
    )
    settings.max_upload_bytes = 3
    assert (
        client.post(
            "/api/recordings", data={"request_id": "large"}, files={"audio": ("large", b"four")}
        ).status_code
        == 413
    )
    assert len(list((settings.data_dir / "audio").iterdir())) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"text": " ", "request_id": "x"},
        {"text": "hi", "request_id": "x", "timezone": "Invalid"},
        {"text": "hi", "request_id": "x", "captured_at": "2026-10-21T20:00:00"},
    ],
)
def test_bad_message_metadata_is_rejected(client, payload):
    assert client.post("/api/messages", json=payload).status_code == 422


def test_unknown_approval_fields_are_not_accepted(client, event_data):
    p = client.post(
        "/api/proposals", json={"operation": "event_create", "payload": event_data}
    ).json()
    assert (
        client.post(
            f"/api/proposals/{p['id']}/approve", json={"override_version": True}
        ).status_code
        == 422
    )
