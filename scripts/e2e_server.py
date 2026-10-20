"""Isolated local-only application for browser tests; no model or provider calls required."""

import tempfile
import threading
import time
from pathlib import Path

import uvicorn
from jarvis.api import create_app
from jarvis.config import Settings
from jarvis.db import Database
from jarvis.worker import Worker

settings = Settings(
    web_dir=Path(__file__).resolve().parents[1] / "frontend" / "dist",
    data_dir=Path(tempfile.mkdtemp(prefix="jarvis-e2e-")),
    token="e2e-private-workspace-token",
    mcp_transport="inprocess",
    _env_file=None,
)
db = Database(settings)
db.initialize()


def work():
    worker = Worker(settings, db)
    while True:
        if not worker.step():
            time.sleep(0.1)


threading.Thread(target=work, daemon=True).start()
uvicorn.run(create_app(settings, db), host="127.0.0.1", port=8000)
