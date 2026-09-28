from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .container import get_service
from .models import DecisionRequest, ScanRequest

mcp = FastMCP("replypilot")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False))
def scan_inbox(query: str = "in:inbox newer_than:7d", max_results: int = 10) -> list[dict]:
    """Classify candidate emails and prepare drafts for human review. Does not send email."""
    runs = get_service().scan(ScanRequest(query=query, max_results=max_results))
    return [run.model_dump(mode="json") for run in runs]


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True))
def get_run_status(run_id: str) -> dict:
    """Read one workflow status without changing Gmail."""
    run = get_service().get_run(run_id)
    if run is None:
        raise ValueError("Run not found")
    return run.model_dump(mode="json")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True))
def list_review_queue() -> list[dict]:
    """List drafts waiting for a human decision."""
    return [run.model_dump(mode="json") for run in get_service().review_queue()]


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False))
def review_draft(
    run_id: str,
    decision: str,
    edited_subject: str | None = None,
    edited_body: str | None = None,
) -> dict:
    """Approve, revise, or reject a draft. Approval creates a Gmail draft but never sends it."""
    request = DecisionRequest(
        decision=decision,
        edited_subject=edited_subject,
        edited_body=edited_body,
    )
    return get_service().decide(run_id, request).model_dump(mode="json")


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
