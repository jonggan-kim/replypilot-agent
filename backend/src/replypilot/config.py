from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Load non-ReplyPilot provider settings (OpenAI/LangSmith) from the same local file.
load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="REPLYPILOT_",
        extra="ignore",
    )

    mode: Literal["mock", "live"] = "mock"
    control_token: str = "local-dev-only"
    database_path: Path = Path(".data/replypilot.sqlite3")
    openai_model: str = "gpt-4.1-mini"
    google_client_secret_path: Path | None = None
    google_account: str = "default"

    @model_validator(mode="after")
    def validate_live_configuration(self) -> "Settings":
        if self.mode == "live":
            if self.control_token == "local-dev-only" or len(self.control_token) < 24:
                raise ValueError("Live mode requires a control token of at least 24 characters")
            if self.google_client_secret_path is None:
                raise ValueError("Live mode requires REPLYPILOT_GOOGLE_CLIENT_SECRET_PATH")
        return self

    @property
    def is_mock(self) -> bool:
        return self.mode == "mock"


@lru_cache
def get_settings() -> Settings:
    return Settings()
