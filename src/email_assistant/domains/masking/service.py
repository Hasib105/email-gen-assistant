"""Sensitive data masking before LLM boundaries."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\w)(?!\d{4}-\d{2}-\d{2}\b)(?:\+?\d[\d .()/-]{7,}\d)(?!\w)")
PASSPORT_RE = re.compile(r"(?i)\b(?:passport(?: number)?\s*[:=#-]?\s*)?([A-Z]{1,2}\d{6,9})\b")
BOOKING_LABEL_RE = re.compile(
    r"(?i)\b(booking(?:[_ -]?(?:ref|reference))?\s*[:=#-]?\s*)([A-Z0-9]{5,16})\b"
)
ALLERGY_RE = re.compile(r"(?i)\b(allerg(?:y|ies)\s*[:=]\s*)([^.;\n]{2,80})")
HEALTH_RE = re.compile(
    r"(?i)\b((?:medical|health)(?: condition| note| notes)?\s*[:=]\s*)([^.;\n]{2,80})"
)
RELIGION_RE = re.compile(r"(?i)\b((?:religion|religious preference)\s*[:=]\s*)([^.;\n]{2,80})")


class MaskingResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    placeholder_map: dict[str, str] = Field(default_factory=dict)


class PiiMasker:
    def mask_text(self, text: str, known_values: list[tuple[str, str]]) -> MaskingResult:
        masked = text
        placeholder_map: dict[str, str] = {}

        for label, value in known_values:
            if not value:
                continue
            if value not in masked:
                continue
            placeholder = (
                f"{label}_{len([key for key in placeholder_map if key.startswith(label)]) + 1}"
            )
            masked = masked.replace(value, placeholder)
            placeholder_map[placeholder] = value

        masked, email_map = self._mask_regex(masked, EMAIL_RE, "EMAIL")
        placeholder_map.update(email_map)
        masked, phone_map = self._mask_regex(masked, PHONE_RE, "PHONE")
        placeholder_map.update(phone_map)
        masked, passport_map = self._mask_passports(masked)
        placeholder_map.update(passport_map)
        masked, booking_map = self._mask_labeled_value(masked, BOOKING_LABEL_RE, "BOOKING_REF")
        placeholder_map.update(booking_map)
        masked, allergy_map = self._mask_labeled_value(masked, ALLERGY_RE, "ALLERGY")
        placeholder_map.update(allergy_map)
        masked, health_map = self._mask_labeled_value(masked, HEALTH_RE, "HEALTH")
        placeholder_map.update(health_map)
        masked, religion_map = self._mask_labeled_value(masked, RELIGION_RE, "RELIGION")
        placeholder_map.update(religion_map)
        return MaskingResult(text=masked, placeholder_map=placeholder_map)

    @staticmethod
    def _mask_regex(
        text: str,
        pattern: re.Pattern[str],
        label: str,
    ) -> tuple[str, dict[str, str]]:
        placeholder_map: dict[str, str] = {}

        def replace(match: re.Match[str]) -> str:
            placeholder = f"{label}_{len(placeholder_map) + 1}"
            placeholder_map[placeholder] = match.group(0)
            return placeholder

        return pattern.sub(replace, text), placeholder_map

    @staticmethod
    def _mask_passports(text: str) -> tuple[str, dict[str, str]]:
        placeholder_map: dict[str, str] = {}

        def replace(match: re.Match[str]) -> str:
            placeholder = f"PASSPORT_{len(placeholder_map) + 1}"
            placeholder_map[placeholder] = match.group(1)
            prefix = match.group(0)[: match.start(1) - match.start(0)]
            return f"{prefix}{placeholder}"

        return PASSPORT_RE.sub(replace, text), placeholder_map

    @staticmethod
    def _mask_labeled_value(
        text: str,
        pattern: re.Pattern[str],
        label: str,
    ) -> tuple[str, dict[str, str]]:
        placeholder_map: dict[str, str] = {}

        def replace(match: re.Match[str]) -> str:
            placeholder = f"{label}_{len(placeholder_map) + 1}"
            placeholder_map[placeholder] = match.group(2).strip()
            return f"{match.group(1)}{placeholder}"

        return pattern.sub(replace, text), placeholder_map
