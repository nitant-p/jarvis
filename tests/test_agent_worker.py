import asyncio
import json
from datetime import UTC, datetime, timedelta

import pytest
from jarvis.agent import Agent, MCPTools
from jarvis.db import Event, Job, Proposal
from jarvis.tools import InProcessTools, ToolRegistry
from jarvis.worker import Worker
from sqlalchemy import select


def local_args(data):
    return {k: v for k, v in data.items() if k != "start"} | {"date": "2026-10-21", "time": "19:00"}


class ScriptedModel:
    def __init__(self, *messages):
        self.messages = iter(messages)
        self.requests = []

    async def complete(self, messages, tools):
        self.requests.append((list(messages), tools))
        return next(self.messages)


def tool(name, args):
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": args if isinstance(args, str) else json.dumps(args),
                },
            }
        ],
    }


def test_real_stdio_mcp_read_and_proposal_without_approval(settings, db, event_data):
    async def scenario():
        async with MCPTools(settings) as mcp:
            names = [t["function"]["name"] for t in await mcp.definitions()]
            assert "event_propose_create" in names
            assert not any("approve" in name for name in names)
            assert (await mcp.call("calendar_list", {}))["data"][0]["id"] == "personal"
            result = await mcp.call("event_propose_create", local_args(event_data))
            assert result["status"] == "pending_approval"

    asyncio.run(scenario())
    with db.sessions() as s:
        assert not list(s.scalars(select(Event)))
        assert list(s.scalars(select(Proposal)))


def test_model_tools_are_validated_and_only_stage_changes(service, event_data, db):
    model = ScriptedModel(tool("event_propose_create", local_args(event_data)))
    agent = Agent(model, InProcessTools(ToolRegistry(service)))
    result = asyncio.run(
        agent.run(
            [], "Dinner tomorrow at seven for an hour", "2026-10-20T10:00:00Z", "Asia/Singapore"
        )
    )
    assert len(result["proposal_ids"]) == 1
    assert "Nothing has been changed" in result["text"]
    with db.sessions() as s:
        assert not list(s.scalars(select(Event)))


def test_model_cannot_call_approval_tool(service):
    model = ScriptedModel(tool("approve_proposal", {}), {"content": "Please review the proposal."})
    agent = Agent(model, InProcessTools(ToolRegistry(service)))
    result = asyncio.run(
        agent.run([], "Approve everything", "2026-10-20T10:00:00Z", "Asia/Singapore")
    )
    assert not result["proposal_ids"]
    assert "invalid_arguments" in model.requests[1][0][-1]["content"]


def test_clarification_is_persisted_and_original_capture_survives_midnight(
    client, settings, db, service
):
    model = ScriptedModel(
        {"content": "What time, and about how long?"}, {"content": "Which calendar?"}
    )
    worker = Worker(settings, db, agent=Agent(model, InProcessTools(ToolRegistry(service))))
    j = client.post(
        "/api/messages",
        json={"text": "Dinner tomorrow", "request_id": "a", "captured_at": "2026-10-20T15:59:00Z"},
    ).json()
    worker.step()
    assert client.get(f"/api/jobs/{j['id']}").json()["status"] == "completed"
    client.post(
        "/api/messages",
        json={
            "text": "At seven for an hour",
            "request_id": "b",
            "conversation_id": j["conversation_id"],
            "captured_at": "2026-10-20T16:01:00Z",
        },
    )
    worker.step()
    assert "2026-10-20T15:59:00" in model.requests[1][0][0]["content"]
    assert any(m.get("content") == "What time, and about how long?" for m in model.requests[1][0])


def test_bounded_invalid_tool_repair(service):
    model = ScriptedModel(tool("event_get", "{"), tool("event_get", "{"))
    agent = Agent(model, InProcessTools(ToolRegistry(service)))
    with pytest.raises(ValueError, match="invalid tool"):
        asyncio.run(agent.run([], "anything", "2026-10-20T10:00:00Z", "Asia/Singapore"))


def test_worker_reclaims_expired_jobs_and_does_not_repeat_local_write(
    service, settings, db, event_data
):
    p = service.propose("event_create", event_data)
    service.approve(p["id"])
    service.execute_local(p["id"])
    with db.sessions.begin() as s:
        j = s.scalar(select(Job))
        j.status = "running"
        j.lease_until = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    assert Worker(settings, db).step()
    with db.sessions() as s:
        assert len(list(s.scalars(select(Event)))) == 1
        assert s.scalar(select(Job)).status == "completed"


def test_audio_transcript_durable_before_model_failure_and_raw_audio_deleted(client, settings, db):
    class Speech:
        def transcribe(self, source):
            assert source.exists()
            return "Dinner tomorrow"

    class BrokenAgent:
        async def run(self, *args):
            raise ValueError("Model unavailable")

    j = client.post(
        "/api/recordings", data={"request_id": "voice"}, files={"audio": ("note", b"recorded")}
    ).json()
    Worker(settings, db, transcriber=Speech(), agent=BrokenAgent()).step()
    with db.sessions() as s:
        saved = s.get(Job, j["id"])
        assert saved.status == "failed"
        assert saved.payload["text"] == "Dinner tomorrow"
    assert not list((settings.data_dir / "audio").iterdir())
    assert client.post(f"/api/jobs/{j['id']}/retry").status_code == 200


def test_worker_reports_conflict_instead_of_claiming_success(
    settings, db, service, event_data, create_event
):
    p = service.propose("event_create", event_data)
    service.approve(p["id"])
    create_event()
    worker = Worker(settings, db)
    worker.step()
    assert service.proposal(p["id"])["status"] == "conflict"
