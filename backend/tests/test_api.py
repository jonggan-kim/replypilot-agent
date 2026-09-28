from pathlib import Path

from fastapi.testclient import TestClient

from replypilot.agents import DeterministicAgentSuite
from replypilot.api import create_app
from replypilot.config import Settings
from replypilot.gmail.mock import MockGmailAdapter
from replypilot.service import ReplyPilotService
from replypilot.store import RunStore


def test_api_auth_and_approval_flow(tmp_path: Path) -> None:
    settings = Settings(mode="mock", control_token="test-control-token", database_path=tmp_path / "api.sqlite3")
    gmail = MockGmailAdapter()
    service = ReplyPilotService(gmail, DeterministicAgentSuite(), RunStore(settings.database_path))
    client = TestClient(create_app(settings, service))

    assert client.post("/api/runs/scan", json={"max_results": 1}).status_code == 401

    headers = {"X-ReplyPilot-Key": "test-control-token"}
    scan = client.post("/api/runs/scan", json={"max_results": 1}, headers=headers)
    assert scan.status_code == 200
    run = scan.json()["runs"][0]
    assert run["status"] == "awaiting_approval"

    decision = client.post(
        f"/api/runs/{run['id']}/decision",
        json={"decision": "approve"},
        headers=headers,
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "draft_saved"

