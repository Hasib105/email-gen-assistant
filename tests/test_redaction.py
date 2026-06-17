from __future__ import annotations

from case_assistant_api.observability.redaction import redact_sensitive


def test_redaction_removes_common_pii_and_secrets() -> None:
    value = {
        "message": (
            "email yuki.tanaka@example.jp phone +81 90-1234-5678 "
            "booking ref TYO9X7 token xoxb-1234567890-abcdef "
            "api sk-testsecretvalue123456"
        ),
        "api_key": "AIzaSyExampleSecretValueForTests",
    }

    redacted = redact_sensitive(value)
    rendered = str(redacted)

    assert "yuki.tanaka@example.jp" not in rendered
    assert "+81 90-1234-5678" not in rendered
    assert "TYO9X7" not in rendered
    assert "xoxb-1234567890-abcdef" not in rendered
    assert "sk-testsecretvalue123456" not in rendered
    assert "AIzaSyExampleSecretValueForTests" not in rendered
    assert "EMAIL_REDACTED" in rendered
    assert "PHONE_REDACTED" in rendered
    assert "BOOKING_REF_REDACTED" in rendered


def test_redaction_does_not_mask_iso_dates_as_phone_numbers() -> None:
    redacted = redact_sensitive("Flight departs on 2026-06-10.")

    assert redacted == "Flight departs on 2026-06-10."
