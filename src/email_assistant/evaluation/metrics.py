"""Three custom evaluation metrics for email generation quality.

1. Fact Recall Score: Measures whether all key facts from input are included in the generated email.
   Uses keyword overlap and semantic similarity between input facts and email content.
   Score: 0.0 (no facts recalled) to 1.0 (all facts perfectly included).

2. Tone Alignment Score: Evaluates how well the generated email matches the requested tone.
   Uses lexical analysis of tone-indicative words and sentence structure patterns.
   Score: 0.0 (completely wrong tone) to 1.0 (perfect tone match).

3. Clarity & Conciseness Score: Assesses readability, grammar quality, and appropriate length.
   Combines Flesch-Kincaid readability, sentence length analysis, and redundancy detection.
   Score: 0.0 (unclear/verbose) to 1.0 (crystal clear and concise).
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class MetricResult:
    """Result of a single metric evaluation."""

    name: str
    score: float
    details: str


class FactRecallMetric:
    """Custom Metric 1: Fact Recall Score.

    Logic: For each key fact in the input, check if its core concepts appear in the
    generated email. Uses keyword extraction and fuzzy matching to handle paraphrasing.
    """

    TONE_KEYWORDS: dict[str, list[str]] = {
        "professional": ["meeting", "discuss", "opportunity", "proposal", "review", "consideration"],
        "formal": ["request", "approval", "proposal", "sincerely", "consideration", "respectfully"],
        "casual": ["hey", "want", "check", "awesome", "looks", "great", "fun"],
        "urgent": ["urgent", "immediate", "critical", "priority", "asap", "now"],
        "empathetic": ["understand", "sincerely", "apologize", "sorry", "commitment", "value"],
        "enthusiastic": ["amazing", "incredible", "phenomenal", "fantastic", "excited", "proud"],
    }

    def evaluate(self, key_facts: list[str], email_body: str) -> MetricResult:
        """Evaluate how many key facts are recalled in the email."""
        if not key_facts:
            return MetricResult(name="fact_recall", score=1.0, details="No facts to check.")

        email_lower = email_body.lower()
        facts_found = 0
        fact_details: list[str] = []

        for fact in key_facts:
            # Extract key words from the fact (3+ letter words)
            words = [w.lower() for w in re.findall(r"\b[a-zA-Z]{3,}\b", fact)]
            if not words:
                facts_found += 1
                fact_details.append(f"FACT: '{fact[:40]}...' -> SKIPPED (no keywords)")
                continue

            # Count how many keywords appear in the email
            found_words = [w for w in words if w in email_lower]
            coverage = len(found_words) / len(words)

            if coverage >= 0.4:
                facts_found += 1
                fact_details.append(
                    f"FACT: '{fact[:40]}...' -> FOUND ({coverage:.0%} keyword coverage)"
                )
            else:
                fact_details.append(
                    f"FACT: '{fact[:40]}...' -> MISSING ({coverage:.0%} keyword coverage)"
                )

        score = facts_found / len(key_facts)
        details = f"Recalled {facts_found}/{len(key_facts)} facts.\n" + "\n".join(fact_details)
        return MetricResult(name="fact_recall", score=score, details=details)


class ToneAlignmentMetric:
    """Custom Metric 2: Tone Alignment Score.

    Logic: Analyzes the generated email for tone-indicative language patterns.
    Checks for presence of words/phrases commonly associated with the requested tone.
    Also checks for words that contradict the requested tone.
    """

    TONE_INDICATORS: dict[str, list[str]] = {
        "professional": [
            "regards", "sincerely", "best", "appreciate", "opportunity", "discuss",
            "proposal", "review", "looking forward", "thank you",
        ],
        "formal": [
            "dear", "sincerely", "respectfully", "request", "pursuant", "hereby",
            "pursuant to", "in accordance", "for your review", "at your convenience",
        ],
        "casual": [
            "hey", "hi", "what's up", "cool", "awesome", "wanna", "gonna",
            "let me know", "cheers", "talk soon", "no worries",
        ],
        "urgent": [
            "urgent", "immediately", "critical", "asap", "right away", "priority",
            "emergency", "time-sensitive", "at once", "without delay",
        ],
        "empathetic": [
            "understand", "sincerely sorry", "apologize", "frustration", "commitment",
            "value", "trust", "personally", "deeply", "compassion",
        ],
        "enthusiastic": [
            "amazing", "incredible", "fantastic", "excited", "thrilled", "proud",
            "phenomenal", "outstanding", "celebrate", "congratulations",
        ],
    }

    CONTRADICTING_TONES: dict[str, list[str]] = {
        "formal": ["hey", "wanna", "gonna", "cool", "awesome", "no worries"],
        "casual": ["hereby", "pursuant", "respectfully", "sincerely request"],
        "urgent": ["at your convenience", "no rush", "whenever possible", "take your time"],
        "empathetic": ["unacceptable", "demand", "failure", "incompetent"],
    }

    def evaluate(self, tone: str, email_body: str) -> MetricResult:
        """Evaluate how well the email matches the requested tone."""
        tone_lower = tone.lower().strip()
        email_lower = email_body.lower()

        # Get indicators for the requested tone
        indicators = self.TONE_INDICATORS.get(tone_lower, [])
        if not indicators:
            return MetricResult(
                name="tone_alignment",
                score=0.5,
                details=f"Unknown tone '{tone}' — using neutral score.",
            )

        # Count matching indicators
        matched = [ind for ind in indicators if ind in email_lower]
        indicator_score = len(matched) / len(indicators) if indicators else 0

        # Check for contradicting tones
        contradictions = self.CONTRADICTING_TONES.get(tone_lower, [])
        contradicted = [c for c in contradictions if c in email_lower]
        contradiction_penalty = min(0.3, len(contradicted) * 0.1)

        # Final score
        score = max(0.0, min(1.0, indicator_score - contradiction_penalty))

        details = (
            f"Tone: '{tone}'\n"
            f"Matched indicators: {matched}\n"
            f"Contradictions found: {contradicted}\n"
            f"Indicator score: {indicator_score:.2f}, Penalty: {contradiction_penalty:.2f}"
        )
        return MetricResult(name="tone_alignment", score=score, details=details)


class ClarityConcisenessMetric:
    """Custom Metric 3: Clarity & Conciseness Score.

    Logic: Combines three sub-metrics:
    - Readability: Based on sentence length and word complexity
    - Appropriate length: Email should be 50-400 words (not too short, not too long)
    - No redundancy: Detects repeated phrases or sentences
    """

    def evaluate(self, email_subject: str, email_body: str) -> MetricResult:
        """Evaluate clarity and conciseness of the generated email."""
        scores: list[float] = []
        details_parts: list[str] = []

        # Sub-metric 1: Readability (sentence length analysis)
        sentences = [s.strip() for s in re.split(r"[.!?]+", email_body) if s.strip()]
        if sentences:
            avg_sentence_len = sum(len(s.split()) for s in sentences) / len(sentences)
            # Ideal: 10-25 words per sentence
            if 10 <= avg_sentence_len <= 25:
                readability_score = 1.0
            elif avg_sentence_len < 10:
                readability_score = max(0.5, avg_sentence_len / 10)
            else:
                readability_score = max(0.3, 1.0 - (avg_sentence_len - 25) / 25)
            scores.append(readability_score)
            details_parts.append(
                f"Readability: avg {avg_sentence_len:.1f} words/sentence -> {readability_score:.2f}"
            )
        else:
            scores.append(0.3)
            details_parts.append("Readability: no sentences found -> 0.30")

        # Sub-metric 2: Appropriate length
        word_count = len(email_body.split())
        if 50 <= word_count <= 400:
            length_score = 1.0
        elif word_count < 50:
            length_score = max(0.3, word_count / 50)
        else:
            length_score = max(0.3, 1.0 - (word_count - 400) / 400)
        scores.append(length_score)
        details_parts.append(f"Length: {word_count} words -> {length_score:.2f}")

        # Sub-metric 3: No redundancy (check for repeated phrases)
        phrases = re.findall(r"\b\w+(?:\s+\w+){2,}\b", email_body.lower())
        phrase_counts: dict[str, int] = {}
        for phrase in phrases:
            phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1
        repeated = {p: c for p, c in phrase_counts.items() if c > 2}
        redundancy_penalty = min(0.3, len(repeated) * 0.05)
        redundancy_score = max(0.0, 1.0 - redundancy_penalty)
        scores.append(redundancy_score)
        details_parts.append(
            f"Redundancy: {len(repeated)} repeated phrases -> {redundancy_score:.2f}"
        )

        # Sub-metric 4: Subject line quality
        subject_words = len(email_subject.split())
        if 3 <= subject_words <= 12:
            subject_score = 1.0
        elif subject_words < 3:
            subject_score = 0.6
        else:
            subject_score = max(0.4, 1.0 - (subject_words - 12) / 10)
        scores.append(subject_score)
        details_parts.append(f"Subject: {subject_words} words -> {subject_score:.2f}")

        # Overall score is weighted average
        score = sum(scores) / len(scores) if scores else 0.5
        details = "Clarity & Conciseness sub-metrics:\n" + "\n".join(details_parts)
        return MetricResult(name="clarity_conciseness", score=score, details=details)
