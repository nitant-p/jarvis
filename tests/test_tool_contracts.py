import asyncio

from jarvis.agent import Agent
from jarvis.tools import InProcessTools, ToolRegistry
from test_agent_worker import ScriptedModel, local_args, tool


def test_llm_wall_clock_time_converted_by_code_not_by_model(service, event_data):
    registry = ToolRegistry(service)
    result = registry.call("event_propose_create", {**local_args(event_data), "time": "20:00"})
    assert result["proposal"]["payload"]["start"] == "2026-10-21T12:00:00+00:00"


def test_day_search_boundary_is_calculated_in_timezone(service, event_data, create_event):
    create_event(start="2026-10-21T00:30:00+08:00")
    registry = ToolRegistry(service)
    result = registry.call("event_list", {"date": "2026-10-21", "timezone": "Asia/Singapore"})
    assert len(result["data"]) == 1
    assert result["data"][0]["time"] == "00:30"
    assert "start" not in result["data"][0]  # Do not ask the model to subtract UTC offsets.


def test_dst_ambiguity_cannot_be_silently_resolved_by_a_tool(service, event_data):
    result = ToolRegistry(service).call(
        "event_propose_create",
        {
            **local_args(event_data),
            "date": "2026-11-01",
            "time": "01:30",
            "timezone": "America/New_York",
        },
    )
    assert result["status"] == "needs_clarification"
    assert "ambiguous" in result["message"]
    assert not service.proposals()


def test_one_durable_capture_cannot_stage_duplicate_proposals(service, event_data):
    service.source_job_id = "durable-capture-1"
    first = service.propose("event_create", event_data)
    recovered = service.propose("event_create", event_data)
    assert first["id"] == recovered["id"]
    assert len(service.proposals()) == 1


def test_proposal_claim_without_tool_is_repaired_before_showing_success(service, event_data):
    model = ScriptedModel(
        {"content": "Your proposal is ready to review."},
        tool("event_propose_create", local_args(event_data)),
    )
    result = asyncio.run(
        Agent(model, InProcessTools(ToolRegistry(service))).run(
            [], "Dinner tomorrow at seven for one hour", "2026-10-20T10:00:00Z", "Asia/Singapore"
        )
    )
    assert len(result["proposal_ids"]) == 1
    assert not any(m["role"] == "system" for m in result["history"])


def test_unknown_tool_cannot_approve_or_execute(service):
    assert ToolRegistry(service).call("approve_proposal", {})["status"] == "unknown_tool"
