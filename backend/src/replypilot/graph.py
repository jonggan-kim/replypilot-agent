from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from .agents import AgentSuite
from .gmail.base import GmailPort
from .models import DraftContent, EmailMessage, HumanDecision, ReviewResult, TriageResult


class WorkflowState(TypedDict, total=False):
    run_id: str
    message: EmailMessage
    context: list[EmailMessage]
    triage: TriageResult
    draft: DraftContent
    review: ReviewResult
    attempt: int
    human_decision: HumanDecision
    gmail_draft_id: str
    status: str
    events: Annotated[list[dict[str, Any]], operator.add]


def build_graph(agents: AgentSuite, gmail: GmailPort, checkpointer: Any):
    def triage_node(state: WorkflowState) -> dict[str, Any]:
        result = agents.triage(state["message"])
        return {
            "triage": result,
            "status": "triaged",
            "events": [{"type": "triage.completed", "needs_reply": result.needs_reply}],
        }

    def triage_route(state: WorkflowState) -> str:
        return "context" if state["triage"].needs_reply else "complete_no_reply"

    def complete_no_reply(state: WorkflowState) -> dict[str, Any]:
        return {"status": "no_reply_needed", "events": [{"type": "workflow.completed_no_reply"}]}

    def context_node(state: WorkflowState) -> dict[str, Any]:
        context = gmail.get_thread_messages(state["message"].thread_id)
        return {
            "context": context,
            "status": "context_ready",
            "events": [{"type": "context.loaded", "message_count": len(context)}],
        }

    def draft_node(state: WorkflowState) -> dict[str, Any]:
        attempt = state.get("attempt", 0) + 1
        draft = agents.draft(state["message"], state.get("context", []))
        return {
            "draft": draft,
            "attempt": attempt,
            "status": "drafted",
            "events": [{"type": "draft.generated", "attempt": attempt}],
        }

    def review_node(state: WorkflowState) -> dict[str, Any]:
        review = agents.review(state["message"], state["draft"])
        return {
            "review": review,
            "status": "reviewed",
            "events": [{"type": "review.completed", "score": review.score, "passed": review.passed}],
        }

    def review_route(state: WorkflowState) -> str:
        if state["review"].passed or state.get("attempt", 0) >= 2:
            return "human_review"
        return "draft"

    def human_review_node(state: WorkflowState) -> dict[str, Any]:
        payload = interrupt(
            {
                "run_id": state["run_id"],
                "email": state["message"].model_dump(mode="json"),
                "draft": state["draft"].model_dump(mode="json"),
                "review": state["review"].model_dump(mode="json"),
                "allowed_decisions": ["approve", "revise", "reject"],
            }
        )
        decision = HumanDecision.model_validate(payload)
        update: dict[str, Any] = {
            "human_decision": decision,
            "status": "approved" if decision.decision != "reject" else "rejected",
            "events": [{"type": "human.decision", "decision": decision.decision}],
        }
        if decision.decision == "revise":
            current = state["draft"]
            update["draft"] = DraftContent(
                subject=decision.edited_subject or current.subject,
                body=decision.edited_body or current.body,
            )
        return update

    def human_route(state: WorkflowState) -> str:
        return "persist_draft" if state["human_decision"].decision in {"approve", "revise"} else "end_rejected"

    def persist_draft_node(state: WorkflowState) -> dict[str, Any]:
        draft_id = gmail.create_draft(state["message"], state["draft"])
        return {
            "gmail_draft_id": draft_id,
            "status": "draft_saved",
            "events": [{"type": "gmail.draft_created", "draft_id": draft_id}],
        }

    def end_rejected(state: WorkflowState) -> dict[str, Any]:
        return {"status": "rejected", "events": [{"type": "workflow.rejected"}]}

    builder = StateGraph(WorkflowState)
    builder.add_node("triage", triage_node)
    builder.add_node("complete_no_reply", complete_no_reply)
    builder.add_node("context", context_node)
    builder.add_node("draft", draft_node)
    builder.add_node("review", review_node)
    builder.add_node("human_review", human_review_node)
    builder.add_node("persist_draft", persist_draft_node)
    builder.add_node("end_rejected", end_rejected)
    builder.add_edge(START, "triage")
    builder.add_conditional_edges("triage", triage_route)
    builder.add_edge("complete_no_reply", END)
    builder.add_edge("context", "draft")
    builder.add_edge("draft", "review")
    builder.add_conditional_edges("review", review_route)
    builder.add_conditional_edges("human_review", human_route)
    builder.add_edge("persist_draft", END)
    builder.add_edge("end_rejected", END)
    return builder.compile(checkpointer=checkpointer)

