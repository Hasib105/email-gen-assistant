"""Three custom evaluation metrics for email generation quality.

1. Fact Recall Score: Measures whether all key facts from input are included in the generated email.
   Uses keyword extraction and coverage analysis per fact.
   Score: 0.0 (no facts recalled) to 1.0 (all facts perfectly included).

2. Tone Alignment Score: Evaluates how well the generated email matches the requested tone.
   Uses lexical analysis of tone-indicative words and contradiction detection.
   Score: 0.0 (completely wrong tone) to 1.0 (perfect tone match).

3. Clarity & Conciseness Score: Assesses readability, appropriate length, and redundancy.
   Combines sentence length analysis, word count bounds, and phrase repetition detection.
   Score: 0.0 (unclear/verbose) to 1.0 (crystal clear and concise).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class MetricResult:
    name: str
    score: float
    details: str


class FactRecallMetric:
    """Did every key fact make it into the email?"""

    def evaluate(self, key_facts: list[str], email_body: str) -> MetricResult:
        if not key_facts:
            return MetricResult(name="fact_recall", score=1.0, details="No facts to check.")

        email_lower = email_body.lower()
        facts_found = 0
        details: list[str] = []

        for fact in key_facts:
            words = [w.lower() for w in re.findall(r"\b[a-zA-Z]{3,}\b", fact)]
            if not words:
                facts_found += 1
                details.append(f"  '{fact[:50]}' -> SKIPPED (no keywords)")
                continue

            found = [w for w in words if w in email_lower]
            coverage = len(found) / len(words)

            if coverage >= 0.4:
                facts_found += 1
                details.append(f"  '{fact[:50]}' -> FOUND ({coverage:.0%})")
            else:
                details.append(f"  '{fact[:50]}' -> MISSING ({coverage:.0%})")

        score = facts_found / len(key_facts)
        summary = f"Recalled {facts_found}/{len(key_facts)} facts."
        return MetricResult(
            name="fact_recall",
            score=score,
            details=summary + "\n" + "\n".join(details),
        )


class ToneAlignmentMetric:
    """Does the email match the requested tone?"""

    TONE_INDICATORS: ClassVar[dict[str, list[str]]] = {
        "professional": [
            "regards", "sincerely", "appreciate", "opportunity",
            "discuss", "review", "looking forward", "thank you",
        ],
        "formal": [
            "dear", "sincerely", "respectfully", "request",
            "pursuant", "hereby", "for your review", "at your convenience",
        ],
        "casual": [
            "hey", "hi", "what's up", "cool", "awesome",
            "wanna", "let me know", "cheers", "talk soon", "no worries",
        ],
        "urgent": [
            "urgent", "immediately", "critical", "asap", "right away",
            "priority", "emergency", "at once", "without delay",
        ],
        "empathetic": [
            "understand", "sincerely sorry", "apologize", "frustration",
            "commitment", "value", "trust", "personally",
        ],
        "enthusiastic": [
            "amazing", "incredible", "fantastic", "excited",
            "thrilled", "proud", "phenomenal", "outstanding",
        ],
    }

    CONTRADICTING_TONES: ClassVar[dict[str, list[str]]] = {
        "formal": ["hey", "wanna", "gonna", "cool", "awesome", "no worries"],
        "casual": ["hereby", "pursuant", "respectfully"],
        "urgent": [
            "at your convenience", "no rush",
            "whenever possible", "take your time",
        ],
        "empathetic": ["unacceptable", "demand", "failure"],
    }

    def evaluate(self, tone: str, email_body: str) -> MetricResult:
        tone_lower = tone.lower().strip()
        email_lower = email_body.lower()

        indicators = self.TONE_INDICATORS.get(tone_lower, [])
        if not indicators:
            return MetricResult(name="tone_alignment", score=0.5, details=f"Unknown tone '{tone}'.")

        matched = [ind for ind in indicators if ind in email_lower]
        indicator_score = len(matched) / len(indicators)

        contradictions = self.CONTRADICTING_TONES.get(tone_lower, [])
        contradicted = [c for c in contradictions if c in email_lower]
        penalty = min(0.3, len(contradicted) * 0.1)

        score = max(0.0, min(1.0, indicator_score - penalty))
        details = f"Matched: {matched}\nContradictions: {contradicted}\nScore: {score:.2f}"
        return MetricResult(name="tone_alignment", score=score, details=details)


class ClarityConcisenessMetric:
    """Is the email readable and not bloated?"""

    def evaluate(self, email_subject: str, email_body: str) -> MetricResult:
        scores: list[float] = []
        parts: list[str] = []

        # Readability (sentence length)
        sentences = [s.strip() for s in re.split(r"[.!?]+", email_body) if s.strip()]
        if sentences:
            avg_len = sum(len(s.split()) for s in sentences) / len(sentences)
            if 10 <= avg_len <= 25:
                r_score = 1.0
            elif avg_len < 10:
                r_score = max(0.5, avg_len / 10)
            else:
                r_score = max(0.3, 1.0 - (avg_len - 25) / 25)
            scores.append(r_score)
            parts.append(f"Readability: {avg_len:.1f} words/sentence -> {r_score:.2f}")

        # Length (50-400 words ideal)
        word_count = len(email_body.split())
        if 50 <= word_count <= 400:
            l_score = 1.0
        elif word_count < 50:
            l_score = max(0.3, word_count / 50)
        else:
            l_score = max(0.3, 1.0 - (word_count - 400) / 400)
        scores.append(l_score)
        parts.append(f"Length: {word_count} words -> {l_score:.2f}")

        # Redundancy
        phrases = re.findall(r"\b\w+(?:\s+\w+){2,}\b", email_body.lower())
        phrase_counts: dict[str, int] = {}
        for p in phrases:
            phrase_counts[p] = phrase_counts.get(p, 0) + 1
        repeated = {p: c for p, c in phrase_counts.items() if c > 2}
        rpen = min(0.3, len(repeated) * 0.05)
        red_score = max(0.0, 1.0 - rpen)
        scores.append(red_score)
        parts.append(f"Redundancy: {len(repeated)} repeated phrases -> {red_score:.2f}")

        # Subject quality
        subj_words = len(email_subject.split())
        if 3 <= subj_words <= 12:
            s_score = 1.0
        elif subj_words < 3:
            s_score = 0.6
        else:
            s_score = max(0.4, 1.0 - (subj_words - 12) / 10)
        scores.append(s_score)
        parts.append(f"Subject: {subj_words} words -> {s_score:.2f}")

        score = sum(scores) / len(scores) if scores else 0.5
        return MetricResult(name="clarity_conciseness", score=score, details="\n".join(parts))
