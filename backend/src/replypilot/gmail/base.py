from __future__ import annotations

from typing import Protocol

from ..models import DraftContent, EmailMessage


class GmailPort(Protocol):
    """The deliberately narrow Gmail capability surface. There is no send method."""

    def list_candidate_messages(self, query: str, max_results: int) -> list[EmailMessage]: ...

    def get_thread_messages(self, thread_id: str) -> list[EmailMessage]: ...

    def create_draft(self, message: EmailMessage, draft: DraftContent) -> str: ...

