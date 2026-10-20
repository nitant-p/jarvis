from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JARVIS_", env_file=".env", extra="ignore")
    data_dir: Path = Path("data")
    token: str = ""
    timezone: str = "Asia/Singapore"
    llm_url: str = "http://127.0.0.1:8081"
    llm_model: str = "Qwen3-4B-Instruct-2507"
    whisper_bin: str = "whisper-cli"
    whisper_model: Path = Path("models/ggml-small.en.bin")
    ffmpeg_bin: str = "ffmpeg"
    mcp_transport: Literal["stdio", "inprocess"] = "stdio"
    max_upload_bytes: int = 15 * 1024 * 1024
    max_recording_seconds: int = 120
    source_job_id: str | None = None

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        ZoneInfo(value)
        return value

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.data_dir.resolve() / 'jarvis.db'}"

    def prepare(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        (self.data_dir / "audio").mkdir(exist_ok=True, mode=0o700)

    def subprocess_env(self) -> dict[str, str]:
        # Only configuration needed by the private MCP child; never expose the session token.
        return {"JARVIS_DATA_DIR": str(self.data_dir.resolve()), "JARVIS_TIMEZONE": self.timezone}
