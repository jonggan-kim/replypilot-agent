from __future__ import annotations

import base64
import json
from email.message import EmailMessage as MimeMessage
from email.utils import parseaddr
from pathlib import Path
from typing import Any

import keyring
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from ..config import get_settings
from ..models import DraftContent, EmailMessage

# Google classifies both as restricted scopes. The adapter still exposes no send method.
GMAIL_SCOPES = (
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
)
KEYRING_SERVICE = "replypilot-google-oauth"


def _header(headers: list[dict[str, str]], name: str) -> str:
    expected = name.lower()
    return next((item.get("value", "") for item in headers if item.get("name", "").lower() == expected), "")


def _decode_body(payload: dict[str, Any]) -> str:
    body = payload.get("body", {}).get("data")
    if payload.get("mimeType") == "text/plain" and body:
        return base64.urlsafe_b64decode(body + "===").decode("utf-8", errors="replace")
    for part in payload.get("parts", []):
        decoded = _decode_body(part)
        if decoded:
            return decoded
    return ""


def _load_credentials(account: str) -> Credentials | None:
    raw = keyring.get_password(KEYRING_SERVICE, account)
    if not raw:
        return None
    return Credentials.from_authorized_user_info(json.loads(raw), GMAIL_SCOPES)


def _save_credentials(account: str, credentials: Credentials) -> None:
    keyring.set_password(KEYRING_SERVICE, account, credentials.to_json())


def authorize(client_secret_path: Path, account: str) -> Credentials:
    """Run installed-app Authorization Code flow and store the refresh token in OS keyring."""
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), GMAIL_SCOPES)
    credentials = flow.run_local_server(host="127.0.0.1", port=0, open_browser=True)
    _save_credentials(account, credentials)
    return credentials


def authorize_cli() -> None:
    settings = get_settings()
    if settings.google_client_secret_path is None:
        raise SystemExit("Set REPLYPILOT_GOOGLE_CLIENT_SECRET_PATH before authorizing")
    authorize(settings.google_client_secret_path, settings.google_account)
    print("Google authorization completed; tokens were stored in the OS keyring.")


class GoogleGmailAdapter:
    def __init__(self, client_secret_path: Path, account: str = "default") -> None:
        self._client_secret_path = client_secret_path
        self._account = account

    def _credentials(self) -> Credentials:
        credentials = _load_credentials(self._account)
        if credentials is None:
            raise RuntimeError("Google OAuth is not initialized; run replypilot-google-auth")
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            _save_credentials(self._account, credentials)
        if not credentials.valid:
            raise RuntimeError("Google OAuth credentials are invalid; run replypilot-google-auth again")
        return credentials

    def _service(self):
        return build("gmail", "v1", credentials=self._credentials(), cache_discovery=False)

    def _get_message(self, message_id: str) -> EmailMessage:
        resource = self._service().users().messages().get(userId="me", id=message_id, format="full").execute()
        payload = resource.get("payload", {})
        headers = payload.get("headers", [])
        return EmailMessage(
            id=resource["id"],
            thread_id=resource["threadId"],
            sender=_header(headers, "From"),
            recipients=[address.strip() for address in _header(headers, "To").split(",") if address.strip()],
            subject=_header(headers, "Subject") or "(제목 없음)",
            body=_decode_body(payload),
            message_id_header=_header(headers, "Message-ID") or None,
            references=_header(headers, "References") or None,
        )

    def list_candidate_messages(self, query: str, max_results: int) -> list[EmailMessage]:
        response = self._service().users().messages().list(userId="me", q=query, maxResults=max_results).execute()
        return [self._get_message(item["id"]) for item in response.get("messages", [])]

    def get_thread_messages(self, thread_id: str) -> list[EmailMessage]:
        resource = self._service().users().threads().get(userId="me", id=thread_id, format="full").execute()
        return [self._get_message(message["id"]) for message in resource.get("messages", [])]

    def create_draft(self, message: EmailMessage, draft: DraftContent) -> str:
        mime = MimeMessage()
        mime["To"] = parseaddr(message.sender)[1] or message.sender
        mime["Subject"] = draft.subject
        if message.message_id_header:
            mime["In-Reply-To"] = message.message_id_header
            prior = f"{message.references or ''} {message.message_id_header}".strip()
            mime["References"] = prior
        mime.set_content(draft.body)
        raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
        created = (
            self._service()
            .users()
            .drafts()
            .create(userId="me", body={"message": {"raw": raw, "threadId": message.thread_id}})
            .execute()
        )
        return created["id"]

