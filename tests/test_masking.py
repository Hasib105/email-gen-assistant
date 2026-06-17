from __future__ import annotations

from email_assistant.domains.masking.service import PiiMasker


def test_masking_replaces_known_sensitive_values() -> None:
    result = PiiMasker().mask_text(
        "Yuki Tanaka uses booking TYO9X7 and email yuki.tanaka@example.jp.",
        known_values=[("CUSTOMER", "Yuki Tanaka"), ("BOOKING_REF", "TYO9X7")],
    )

    assert "Yuki Tanaka" not in result.text
    assert "TYO9X7" not in result.text
    assert "yuki.tanaka@example.jp" not in result.text
    assert "CUSTOMER_1" in result.text
    assert "BOOKING_REF_1" in result.text
    assert "EMAIL_1" in result.text
