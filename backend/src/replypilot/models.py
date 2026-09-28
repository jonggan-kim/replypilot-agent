from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class EmailMessage(BaseModel):
    id: str
    thread_id: str
    sender: str
    recipients: list[str] = Field(default_factory=list)
    subject: str
    body: str
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    message_id_header: str | None = None
    references: str | None = None


class TriageResult(BaseModel):
    needs_reply: bool
    category: Literal["reply", "informational", "automated", "spam", "uncertain"]
    confidence: float = Field(ge=0, le=1)
    reason: str


class DraftContent(BaseModel):
    subject: str
    body: str


class ReviewResult(BaseModel):
    score: float = Field(ge=1, le=5)
    passed: bool
    issues: list[str] = Field(default_factory=list)
    rationale: str


class HumanDecision(BaseModel):
    decision: Literal["approve", "revise", "reject"]
    edited_subject: str | None = None
    edited_body: str | None = None


class RunSummary(BaseModel):
    id: str
    email_id: str
    thread_id: str
    sender: str
    subject: str
    status: str
    needs_reply: bool | None = None
    confidence: float | None = None
    review_score: float | None = None
    draft: DraftContent | None = None
    gmail_draft_id: str | None = None
    created_at: datetime
    updated_at: datetime


class ScanRequest(BaseModel):
    query: str = "in:inbox newer_than:7d"
    max_results: int = Field(default=10, ge=1, le=50)


class ScanResponse(BaseModel):
    runs: list[RunSummary]


class DecisionRequest(HumanDecision):
    pass

