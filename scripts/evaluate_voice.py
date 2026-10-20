"""Transcribe a caller-supplied local clip and create a synthetic local proposal (no cloud)."""

import argparse
import asyncio
import json
import tempfile
import time
from pathlib import Path

from jarvis.agent import Agent, LocalLLM, MCPTools
from jarvis.audio import Transcriber
from jarvis.config import Settings
from jarvis.db import Database


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("recording", type=Path)
    args = parser.parse_args()
    settings = Settings(data_dir=Path(tempfile.mkdtemp(prefix="jarvis-voice-eval-")))
    settings.prepare()
    db = Database(settings)
    db.initialize()
    start = time.monotonic()
    transcript = Transcriber(settings).transcribe(args.recording)
    stt_seconds = time.monotonic() - start
    result = await Agent(LocalLLM(settings), MCPTools(settings)).run(
        [], transcript, "2026-10-20T10:00:00+00:00", "Asia/Singapore"
    )
    assert len(result["proposal_ids"]) == 1, result
    print(
        json.dumps(
            {
                "transcript": transcript,
                "stt_seconds": round(stt_seconds, 2),
                "total_seconds": round(time.monotonic() - start, 2),
                "proposal_created": True,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
