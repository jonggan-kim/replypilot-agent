from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from .agents import AgentSuite
from .gmail.base import GmailPort
from .graph import WorkflowState, build_graph
from .models import DecisionRequest, DraftContent, EmailMessage, RunSummary, ScanRequest
from .store import RunStore


class ReplyPilotService:
    def __init__(self, gmail: GmailPort, agents: AgentSuite, store: RunStore) -> None:
        self.gmail = gmail
        self.agents = agents
        self.store = store
        checkpoint_connection = sqlite3.connect(store.connection.execute("PRAGMA database_list").fetchone()[2], check_same_thread=False)
        self.graph = build_graph(agents, gmail, SqliteSaver(checkpoint_connection))

    @staticmethod
    def _config(run_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": run_id}, "run_name": "replypilot-email-workflow"}

    def _summary(self, run_id: str, state: WorkflowState, status: str | None = None) -> RunSummary:
        message = state["message"]
        prior = self.store.get_run(run_id)
        now = datetime.now(timezone.utc)
        triage = state.get("triage")
        review = state.get("review")
        draft = state.get("draft")
        return RunSummary(
            id=run_id,
            email_id=message.id,
            thread_id=message.thread_id,
            sender=message.sender,
            subject=message.subject,
            status=status or state.get("status", "running"),
            needs_reply=triage.needs_reply if triage else None,
            confidence=triage.confidence if triage else None,
            review_score=review.score if review else None,
            draft=draft,
            gmail_draft_id=state.get("gmail_draft_id"),
            created_at=datetime.fromisoformat(prior["created_at"]) if prior else now,
            updated_at=now,
        )

    def _save(self, summary: RunSummary) -> RunSummary:
        payload = summary.model_dump(mode="json")
        self.store.save_run(summary.id, payload)
        self.store.append_event(summary.id, "run.status", {"status": summary.status})
        return summary

    def process_message(self, message: EmailMessage) -> RunSummary:
        run_id = str(uuid.uuid4())
        initial: WorkflowState = {
            "run_id": run_id,
            "message": message,
            "attempt": 0,
            "status": "started",
            "events": [{"type": "workflow.started"}],
        }
        result = self.graph.invoke(initial, config=self._config(run_id))
        status = "awaiting_approval" if "__interrupt__" in result else result.get("status", "completed")
        return self._save(self._summary(run_id, result, status))

    def scan(self, request: ScanRequest) -> list[RunSummary]:
        messages = self.gmail.list_candidate_messages(request.query, request.max_results)
        return [self.process_message(message) for message in messages]

    def decide(self, run_id: str, decision: DecisionRequest) -> RunSummary:
        current = self.store.get_run(run_id)
        if current is None:
            raise KeyError(run_id)
        if current["status"] != "awaiting_approval":
            raise ValueError(f"Run is not awaiting approval: {current['status']}")
        result = self.graph.invoke(Command(resume=decision.model_dump(exclude_none=True)), config=self._config(run_id))
        return self._save(self._summary(run_id, result))

    def get_run(self, run_id: str) -> RunSummary | None:
        payload = self.store.get_run(run_id)
        return RunSummary.model_validate(payload) if payload else None

    def review_queue(self) -> list[RunSummary]:
        return [RunSummary.model_validate(item) for item in self.store.list_runs(status="awaiting_approval")]

