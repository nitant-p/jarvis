"""Start the native Mac/Linux development stack; Ctrl+C stops only these child processes."""

import argparse
import os
import secrets
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

from alembic import command
from alembic.config import Config
from jarvis.config import Settings
from jarvis.db import Database

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--no-model", action="store_true", help="Use an already running model server"
    )
    parser.add_argument(
        "--calendar-only", action="store_true", help="Start manual CRUD without AI runtimes"
    )
    args = parser.parse_args()
    os.chdir(ROOT)
    envfile = ROOT / ".env"
    if not envfile.exists():
        envfile.write_text(f"JARVIS_TOKEN={secrets.token_urlsafe(32)}\n")
        envfile.chmod(0o600)
    settings = Settings()
    settings.prepare()
    if not args.calendar_only:
        for binary in (settings.ffmpeg_bin, settings.whisper_bin):
            if not shutil.which(binary):
                raise SystemExit(f"Missing {binary}; see docs/development.md")
        if not settings.whisper_model.exists():
            raise SystemExit("Download models first: python scripts/download_models.py")
    if not args.no_model and not args.calendar_only and not shutil.which("llama-server"):
        raise SystemExit("Install llama.cpp first; see docs/development.md")
    command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
    Database(settings).initialize(settings.timezone)
    commands = [
        [
            sys.executable,
            "-m",
            "uvicorn",
            "jarvis.api:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
        [sys.executable, "-m", "jarvis.worker"],
        ["npm", "run", "dev", "--prefix", "frontend"],
    ]
    if not args.no_model and not args.calendar_only:
        commands.insert(
            0,
            [
                "llama-server",
                "-m",
                "models/Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
                "--host",
                "127.0.0.1",
                "--port",
                "8081",
                "-c",
                "4096",
                "--jinja",
                "--reasoning",
                "off",
                "-np",
                "1",
                "-t",
                "4",
            ],
        )
    children = []

    def stop(*_):
        for child in children:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    print("Open http://127.0.0.1:5173 · workspace token is in .env", flush=True)
    try:
        for cmd in commands:
            children.append(subprocess.Popen(cmd, start_new_session=True))
        while all(child.poll() is None for child in children):
            time.sleep(0.5)
    finally:
        stop()
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
        failed = [c.returncode for c in children if c.returncode not in (0, -signal.SIGTERM)]
        if failed:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
