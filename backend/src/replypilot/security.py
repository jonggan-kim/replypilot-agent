from __future__ import annotations

import hashlib
import re
import secrets

from fastapi import Header, HTTPException, status

from .config import get_settings

EMAIL_RE = re.compile(r"(?P<name>[A-Za-z0-9._%+-]{1,64})@(?P<domain>[A-Za-z0-9.-]+\.[A-Za-z]{2,})")
TOKEN_RE = re.compile(
    r"(?i)(bearer\s+|api[_-]?key[=:]\s*|token[=:]\s*)([A-Za-z0-9._~+/=-]{12,})"
)


def redact_sensitive(value: str) -> str:
    def redact_email(match: re.Match[str]) -> str:
        digest = hashlib.sha256(match.group(0).lower().encode()).hexdigest()[:10]
        return f"email:{digest}"

    value = EMAIL_RE.sub(redact_email, value)
    return TOKEN_RE.sub(lambda match: f"{match.group(1)}[REDACTED]", value)


def require_control_token(x_replypilot_key: str | None = Header(default=None)) -> None:
    expected = get_settings().control_token
    if not x_replypilot_key or not secrets.compare_digest(x_replypilot_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid control token",
        )

