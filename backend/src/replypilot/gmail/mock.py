from __future__ import annotations

from copy import deepcopy

from ..models import DraftContent, EmailMessage


class MockGmailAdapter:
    def __init__(self) -> None:
        self.drafts: dict[str, DraftContent] = {}
        self.messages = [
            EmailMessage(
                id="msg-001",
                thread_id="thread-001",
                sender="minji@example.com",
                recipients=["me@example.com"],
                subject="다음 주 제품 데모 일정 확인",
                body="안녕하세요. 화요일 오후 2시에 제품 데모가 가능할까요? 참석 인원은 4명입니다. 회신 부탁드립니다.",
                message_id_header="<msg-001@example.com>",
            ),
            EmailMessage(
                id="msg-002",
                thread_id="thread-002",
                sender="newsletter@example.com",
                recipients=["me@example.com"],
                subject="9월 제품 업데이트 뉴스레터",
                body="새로운 기능과 릴리스 노트를 안내합니다. 본 메일은 발신 전용입니다.",
                message_id_header="<msg-002@example.com>",
            ),
            EmailMessage(
                id="msg-003",
                thread_id="thread-003",
                sender="partner@example.com",
                recipients=["me@example.com"],
                subject="계약서 수정안 검토 요청",
                body="첨부한 수정안의 제8조 납기 조건을 검토하시고 금요일까지 의견을 부탁드립니다.",
                message_id_header="<msg-003@example.com>",
            ),
        ]

    def list_candidate_messages(self, query: str, max_results: int) -> list[EmailMessage]:
        del query
        return deepcopy(self.messages[:max_results])

    def get_thread_messages(self, thread_id: str) -> list[EmailMessage]:
        return deepcopy([message for message in self.messages if message.thread_id == thread_id])

    def create_draft(self, message: EmailMessage, draft: DraftContent) -> str:
        draft_id = f"mock-draft-{len(self.drafts) + 1:03d}"
        self.drafts[draft_id] = draft.model_copy(deep=True)
        return draft_id
