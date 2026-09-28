from __future__ import annotations

from functools import lru_cache

from .agents import DeterministicAgentSuite, OpenAIAgentSuite
from .config import Settings, get_settings
from .gmail.google import GoogleGmailAdapter
from .gmail.mock import MockGmailAdapter
from .service import ReplyPilotService
from .store import RunStore


def create_service(settings: Settings) -> ReplyPilotService:
    store = RunStore(settings.database_path)
    if settings.is_mock:
        return ReplyPilotService(MockGmailAdapter(), DeterministicAgentSuite(), store)
    assert settings.google_client_secret_path is not None
    gmail = GoogleGmailAdapter(settings.google_client_secret_path, settings.google_account)
    agents = OpenAIAgentSuite(settings.openai_model)
    return ReplyPilotService(gmail, agents, store)


@lru_cache
def get_service() -> ReplyPilotService:
    return create_service(get_settings())

