from pathlib import Path

from replypilot.agents import DeterministicAgentSuite
from replypilot.gmail.mock import MockGmailAdapter
from replypilot.models import DecisionRequest, ScanRequest
from replypilot.service import ReplyPilotService
from replypilot.store import RunStore


def make_service(path: Path) -> tuple[ReplyPilotService, MockGmailAdapter]:
    gmail = MockGmailAdapter()
    return ReplyPilotService(gmail, DeterministicAgentSuite(), RunStore(path)), gmail


def test_workflow_waits_for_approval_before_creating_draft(tmp_path: Path) -> None:
    service, gmail = make_service(tmp_path / "replypilot.sqlite3")
    runs = service.scan(ScanRequest(max_results=1))

    assert runs[0].status == "awaiting_approval"
    assert runs[0].review_score is not None and runs[0].review_score >= 4.0
    assert gmail.drafts == {}

    completed = service.decide(runs[0].id, DecisionRequest(decision="approve"))

    assert completed.status == "draft_saved"
    assert completed.gmail_draft_id in gmail.drafts


def test_no_reply_email_completes_without_human_review(tmp_path: Path) -> None:
    service, gmail = make_service(tmp_path / "replypilot.sqlite3")
    runs = service.scan(ScanRequest(max_results=2))

    assert runs[1].status == "no_reply_needed"
    assert runs[1].needs_reply is False
    assert gmail.drafts == {}


def test_rejection_never_creates_gmail_draft(tmp_path: Path) -> None:
    service, gmail = make_service(tmp_path / "replypilot.sqlite3")
    run = service.scan(ScanRequest(max_results=1))[0]

    rejected = service.decide(run.id, DecisionRequest(decision="reject"))

    assert rejected.status == "rejected"
    assert rejected.gmail_draft_id is None
    assert gmail.drafts == {}

