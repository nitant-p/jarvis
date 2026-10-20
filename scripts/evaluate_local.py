"""Explicit real-model integration evaluation, isolated from personal data/calendars."""

import asyncio
import json
import tempfile
import time
from pathlib import Path

from jarvis.agent import Agent, LocalLLM, MCPTools
from jarvis.calendar import CalendarService
from jarvis.config import Settings
from jarvis.db import Database


async def main():
    root = Path(__file__).resolve().parents[1]
    settings = Settings(data_dir=Path(tempfile.mkdtemp(prefix="jarvis-model-eval-")))
    db = Database(settings)
    db.initialize()
    service = CalendarService(db)
    llm = LocalLLM(settings)
    cases = [
        (
            "create",
            "Add Dinner with Sam to the Personal calendar on October 21, 2026 at 7 p.m. "
            "Singapore time for 60 minutes. Location is Home.",
        ),
        ("clarify", "Schedule dinner with a friend tomorrow."),
        (
            "update",
            "Move Dinner with Sam on October 21, 2026 to 8 p.m. Singapore time. "
            "Keep everything else the same.",
        ),
        ("delete", "Delete Dinner with Sam on October 21, 2026 from my calendar."),
    ]
    reports = []
    for name, text in cases:
        started = time.monotonic()
        agent = Agent(llm, MCPTools(settings))
        result = await agent.run([], text, "2026-10-20T10:00:00+00:00", "Asia/Singapore")
        turns = 1
        if name == "delete" and not result["proposal_ids"]:
            # Exercise the dialogue, including the small model's occasional target check.
            agent = Agent(llm, MCPTools(settings))
            result = await agent.run(
                result["history"],
                "Yes, that is the exact event. Prepare its deletion proposal.",
                "2026-10-20T10:00:00+00:00",
                "Asia/Singapore",
            )
            turns += 1
        ids = result["proposal_ids"]
        if name == "clarify":
            assert not ids, result
        else:
            assert len(ids) == 1, result
            p = service.proposal(ids[0])
            assert p["operation"] == "event_" + name, p
            if name == "create":
                assert p["payload"]["start"] == "2026-10-21T11:00:00+00:00", p
            if name == "update":
                assert p["payload"]["start"] == "2026-10-21T12:00:00+00:00", p
            service.approve(ids[0])
            service.execute_local(ids[0])
        reports.append(
            {
                "case": name,
                "passed": True,
                "turns": turns,
                "seconds": round(time.monotonic() - started, 2),
                "answer": result["text"],
            }
        )
        print(json.dumps(reports[-1]), flush=True)
    report_path = root / "data" / "model-evaluation.json"
    report_path.parent.mkdir(exist_ok=True)
    report_path.write_text(json.dumps(reports, indent=2) + "\n")


if __name__ == "__main__":
    asyncio.run(main())
