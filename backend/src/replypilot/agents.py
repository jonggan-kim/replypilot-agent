from __future__ import annotations

import re
from typing import Protocol

from langchain_openai import ChatOpenAI
from langsmith import traceable

from .models import DraftContent, EmailMessage, ReviewResult, TriageResult


class AgentSuite(Protocol):
    def triage(self, message: EmailMessage) -> TriageResult: ...

    def draft(self, message: EmailMessage, context: list[EmailMessage]) -> DraftContent: ...

    def review(self, message: EmailMessage, draft: DraftContent) -> ReviewResult: ...


class DeterministicAgentSuite:
    """Credential-free behavior for local development and repeatable evaluations."""

    @traceable(name="triage", run_type="chain")
    def triage(self, message: EmailMessage) -> TriageResult:
        text = f"{message.subject}\n{message.body}".lower()
        automated = any(term in text for term in ("발신 전용", "뉴스레터", "unsubscribe", "no-reply"))
        asks_reply = any(
            term in text
            for term in ("회신", "부탁드립니다", "가능할까요", "검토", "의견", "확인해", "답변")
        )
        needs_reply = asks_reply and not automated
        return TriageResult(
            needs_reply=needs_reply,
            category="reply" if needs_reply else ("automated" if automated else "informational"),
            confidence=0.94 if needs_reply or automated else 0.72,
            reason="명시적인 요청과 발신 유형을 규칙 기반으로 판별했습니다.",
        )

    @traceable(name="draft", run_type="chain")
    def draft(self, message: EmailMessage, context: list[EmailMessage]) -> DraftContent:
        del context
        subject = message.subject if message.subject.lower().startswith("re:") else f"Re: {message.subject}"
        if "데모" in message.body:
            body = "안녕하세요.\n\n화요일 오후 2시 제품 데모 일정으로 확인했습니다. 참석 인원 4명에 맞춰 준비하겠습니다.\n\n감사합니다."
        elif "계약" in message.body or "검토" in message.body:
            body = "안녕하세요.\n\n수정안과 제8조 납기 조건을 검토한 뒤 금요일까지 의견을 전달드리겠습니다.\n\n감사합니다."
        else:
            body = "안녕하세요.\n\n보내주신 내용을 확인했습니다. 검토 후 회신드리겠습니다.\n\n감사합니다."
        return DraftContent(subject=subject, body=body)

    @traceable(name="review", run_type="chain")
    def review(self, message: EmailMessage, draft: DraftContent) -> ReviewResult:
        issues: list[str] = []
        if not draft.subject.lower().startswith("re:"):
            issues.append("회신 제목 형식이 아닙니다.")
        if len(draft.body.strip()) < 25:
            issues.append("본문이 너무 짧습니다.")
        source_terms = set(re.findall(r"[가-힣A-Za-z0-9]+", message.body))
        if not source_terms.intersection(re.findall(r"[가-힣A-Za-z0-9]+", draft.body)):
            issues.append("원문 요청과 연결되는 내용이 없습니다.")
        score = 5.0 if not issues else max(1.0, 5.0 - len(issues))
        return ReviewResult(
            score=score,
            passed=score >= 4.0,
            issues=issues,
            rationale="정확성, 관련성, 어조, 간결성 기준으로 평가했습니다.",
        )


class OpenAIAgentSuite:
    def __init__(self, model: str) -> None:
        base = ChatOpenAI(model=model, temperature=0)
        self._triage = base.with_structured_output(TriageResult)
        self._draft = base.with_structured_output(DraftContent)
        self._review = base.with_structured_output(ReviewResult)

    @traceable(name="triage", run_type="chain")
    def triage(self, message: EmailMessage) -> TriageResult:
        return self._triage.invoke(
            "회신이 필요한 이메일인지 분류하세요. 자동 알림, 뉴스레터, 스팸은 회신 불필요입니다.\n"
            f"보낸 사람: {message.sender}\n제목: {message.subject}\n본문: {message.body}"
        )

    @traceable(name="draft", run_type="chain")
    def draft(self, message: EmailMessage, context: list[EmailMessage]) -> DraftContent:
        history = "\n\n".join(f"{item.sender}: {item.body}" for item in context[-5:])
        return self._draft.invoke(
            "이메일 스레드에 대한 사실 기반의 간결하고 정중한 한국어 회신 초안을 작성하세요. "
            "원문에 없는 약속이나 사실을 만들지 마세요.\n"
            f"제목: {message.subject}\n현재 메시지: {message.body}\n스레드: {history}"
        )

    @traceable(name="review", run_type="chain")
    def review(self, message: EmailMessage, draft: DraftContent) -> ReviewResult:
        return self._review.invoke(
            "초안을 1~5점으로 평가하세요. 사실성, 요청 충족, 전문적 어조, 간결성을 모두 만족해야 4점 이상입니다.\n"
            f"원문: {message.body}\n초안 제목: {draft.subject}\n초안 본문: {draft.body}"
        )
