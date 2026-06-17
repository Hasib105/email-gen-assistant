"""Evidence and draft grounding validation."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from case_assistant_api.config import Settings
from case_assistant_api.domains.cases.schemas import CaseRecord
from case_assistant_api.domains.rag.retriever import Evidence

_POLICY_COMMITMENT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(refund|refunded|refunding)\b", re.I), "refund"),
    (re.compile(r"\b(voucher|vouchers)\b", re.I), "voucher"),
    (re.compile(r"\b(rebook(?:ed|ing)?|re-book(?:ed|ing)?)\b", re.I), "rebooking"),
    (re.compile(r"\b(compensat(?:e|ed|ion))\b", re.I), "compensation"),
    (re.compile(r"\b(waive[ds]?|waiving)\b", re.I), "fee waiver"),
)

_CONFLICTING_TOPIC_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"refund", "no refund", "non-refundable"}),
    frozenset({"rebook", "no rebooking", "cannot rebook"}),
    frozenset({"voucher", "no voucher"}),
)


def validate_draft_grounding(
    *,
    case: CaseRecord,
    evidence: list[Evidence],
    itinerary_draft: str,
    reply_subject: str,
    reply_body: str,
    recommended_actions: list[str],
    settings: Settings,
) -> list[str]:
    """Return validation warnings for evidence strength and draft grounding."""
    warnings: list[str] = []
    warnings.extend(assess_evidence_quality(evidence, settings=settings))
    warnings.extend(detect_conflicting_evidence(evidence))
    warnings.extend(
        validate_itinerary_consistency(
            case=case,
            itinerary_draft=itinerary_draft,
            reply_body=reply_body,
        )
    )
    warnings.extend(
        validate_policy_claims(
            evidence=evidence,
            reply_subject=reply_subject,
            reply_body=reply_body,
            recommended_actions=recommended_actions,
        )
    )
    return _dedupe_warnings(warnings)


def assess_evidence_quality(evidence: list[Evidence], *, settings: Settings) -> list[str]:
    warnings: list[str] = []
    if not evidence:
        warnings.append("No SOP or history evidence was retrieved.")
        return warnings

    weak_sources = [
        item.source
        for item in evidence
        if item.relevance_score < settings.evidence_min_relevance_score
    ]
    if weak_sources:
        warnings.append(
            "Retrieved evidence has low relevance scores; review carefully before approving."
        )

    stale_cutoff = datetime.now(UTC) - timedelta(days=settings.evidence_stale_after_days)
    stale_sources = [item.source for item in evidence if _is_stale(item.indexed_at, stale_cutoff)]
    if stale_sources:
        warnings.append("Some evidence sources may be stale; verify SOP currency before approving.")

    if len(evidence) == 1 and evidence[0].relevance_score < settings.evidence_min_relevance_score:
        warnings.append("Only one weak evidence source was found; careful review is required.")

    return warnings


_MIN_EVIDENCE_FOR_CONFLICT = 2


def detect_conflicting_evidence(evidence: list[Evidence]) -> list[str]:
    if len(evidence) < _MIN_EVIDENCE_FOR_CONFLICT:
        return []

    corpus = " ".join(f"{item.title} {item.excerpt}" for item in evidence).lower()
    for topic_group in _CONFLICTING_TOPIC_GROUPS:
        matched = [topic for topic in topic_group if topic in corpus]
        if len(matched) >= _MIN_EVIDENCE_FOR_CONFLICT:
            return ["Conflicting evidence was retrieved; reconcile SOP guidance before approving."]
    return []


def validate_itinerary_consistency(
    *,
    case: CaseRecord,
    itinerary_draft: str,
    reply_body: str,
) -> list[str]:
    if not case.itinerary:
        return []

    combined = f"{itinerary_draft}\n{reply_body}".lower()
    conflicts: list[str] = []
    for segment in case.itinerary:
        origin = segment.origin.lower()
        destination = segment.destination.lower()
        flight_number = segment.flight_number.lower()
        if origin and destination and origin in combined and destination not in combined:
            conflicts.append(f"{segment.flight_number}: {segment.origin}->{segment.destination}")
        if flight_number and flight_number not in combined and origin in combined:
            conflicts.append(segment.flight_number)

    if conflicts:
        return [
            "Generated draft text may conflict with retrieved itinerary data; "
            "withhold approval until facts are reconciled."
        ]
    return []


def validate_policy_claims(
    *,
    evidence: list[Evidence],
    reply_subject: str,
    reply_body: str,
    recommended_actions: list[str],
) -> list[str]:
    combined = "\n".join([reply_subject, reply_body, *recommended_actions])
    evidence_text = " ".join(
        f"{item.title} {item.excerpt} {' '.join(item.tags)}" for item in evidence
    ).lower()

    warnings: list[str] = []
    for pattern, label in _POLICY_COMMITMENT_PATTERNS:
        if not pattern.search(combined):
            continue
        if label.replace(" ", "") not in evidence_text and label not in evidence_text:
            warnings.append(
                f"Draft mentions {label} but retrieved evidence does not support that commitment."
            )
    return warnings


def evidence_attribution_summary(evidence: list[Evidence]) -> list[str]:
    return [f"{item.title} ({item.source})" for item in evidence]


def _is_stale(indexed_at: str | None, cutoff: datetime) -> bool:
    if not indexed_at:
        return False
    try:
        parsed = datetime.fromisoformat(indexed_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed < cutoff


def _dedupe_warnings(warnings: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for warning in warnings:
        if warning in seen:
            continue
        seen.add(warning)
        ordered.append(warning)
    return ordered
