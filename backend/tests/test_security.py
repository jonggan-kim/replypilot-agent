from replypilot.security import redact_sensitive


def test_redacts_email_and_token() -> None:
    redacted = redact_sensitive("alice@example.com bearer super-secret-token-123")
    assert "alice@example.com" not in redacted
    assert "super-secret-token-123" not in redacted
    assert "email:" in redacted
    assert "[REDACTED]" in redacted

