from __future__ import annotations

import json
import os
from statistics import mean
from typing import Any

from langsmith import Client
from langsmith.evaluation import evaluate

from .agents import DeterministicAgentSuite, OpenAIAgentSuite
from .config import get_settings
from .models import EmailMessage


EVAL_CASES = [
    {
        "inputs": {
            "sender": "customer@example.com",
            "subject": "미팅 가능 시간 문의",
            "body": "목요일 오전 10시에 미팅이 가능할까요? 회신 부탁드립니다.",
        },
        "outputs": {"needs_reply": True},
    },
    {
        "inputs": {
            "sender": "newsletter@example.com",
            "subject": "주간 뉴스레터",
            "body": "이번 주 소식입니다. 본 메일은 발신 전용입니다.",
        },
        "outputs": {"needs_reply": False},
    },
    {
        "inputs": {
            "sender": "partner@example.com",
            "subject": "견적 검토 요청",
            "body": "견적 내용을 검토하시고 금요일까지 의견 부탁드립니다.",
        },
        "outputs": {"needs_reply": True},
    },
]


def _message(inputs: dict[str, str]) -> EmailMessage:
    return EmailMessage(
        id="eval-message",
        thread_id="eval-thread",
        recipients=["me@example.com"],
        **inputs,
    )


def run_local_eval() -> dict[str, Any]:
    settings = get_settings()
    agents = DeterministicAgentSuite() if settings.is_mock else OpenAIAgentSuite(settings.openai_model)
    triage_hits: list[float] = []
    draft_scores: list[float] = []
    details = []
    for case in EVAL_CASES:
        message = _message(case["inputs"])
        triage = agents.triage(message)
        hit = float(triage.needs_reply == case["outputs"]["needs_reply"])
        triage_hits.append(hit)
        score = None
        if triage.needs_reply:
            draft = agents.draft(message, [message])
            review = agents.review(message, draft)
            score = review.score
            draft_scores.append(score)
        details.append({"subject": message.subject, "triage_correct": bool(hit), "draft_score": score})
    return {
        "triage_accuracy": mean(triage_hits),
        "mean_draft_score": mean(draft_scores) if draft_scores else None,
        "draft_threshold_passed": bool(draft_scores) and mean(draft_scores) >= 4.0,
        "details": details,
    }


def run_langsmith_eval() -> None:
    """Upload/reuse a small dataset and execute the same target in LangSmith."""
    settings = get_settings()
    agents = DeterministicAgentSuite() if settings.is_mock else OpenAIAgentSuite(settings.openai_model)
    client = Client()
    dataset_name = os.getenv("LANGSMITH_DATASET", "replypilot-smoke-eval-v1")
    if not client.has_dataset(dataset_name=dataset_name):
        dataset = client.create_dataset(dataset_name=dataset_name, description="ReplyPilot triage smoke cases")
        client.create_examples(dataset_id=dataset.id, examples=EVAL_CASES)

    def target(inputs: dict[str, str]) -> dict[str, Any]:
        result = agents.triage(_message(inputs))
        return result.model_dump(mode="json")

    def triage_accuracy(run, example) -> dict[str, Any]:
        expected = example.outputs["needs_reply"]
        return {"key": "triage_accuracy", "score": int(run.outputs["needs_reply"] == expected)}

    evaluate(
        target,
        data=dataset_name,
        evaluators=[triage_accuracy],
        experiment_prefix="replypilot-triage",
    )


def main() -> None:
    print(json.dumps(run_local_eval(), ensure_ascii=False, indent=2))
    if os.getenv("LANGSMITH_API_KEY"):
        run_langsmith_eval()
