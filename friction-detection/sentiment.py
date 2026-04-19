"""
SentimentAnalyzer — lightweight, offline sentiment classification for
member interactions at credit unions.

No external API dependency. Uses keyword matching and pattern detection
with financial-specific vocabulary.
"""

import re


class SentimentAnalyzer:
    """
    Classifies text as: positive, neutral, negative, or escalation_risk.

    Tuned for credit union member interactions — covers overdraft disputes,
    fee complaints, fraud reports, hold frustrations, and more.
    """

    # --- Escalation risk signals (highest priority) ---
    ESCALATION_PATTERNS = [
        r"\b(lawsuit|attorney|lawyer|regulator|sue\b|legal action)",
        r"\b(clos(e|ing) my account|switch(ing)? bank)",
        r"\b(report(ing)? (you|this)|fil(e|ing) (a )?complaint)",
        r"\b(ncua|cfpb|bbb|better business bureau)",
        r"\b(discriminat|bias|racist|sexist|unfair treatment)",
        r"\b(threaten|harass|hostile|unsafe)",
    ]

    # --- Negative vocabulary (financial-specific) ---
    NEGATIVE_WORDS = {
        # fees & charges
        "overdraft", "overcharge", "excessive fee", "hidden fee", "late fee",
        "penalty", "surcharge",
        # denials & holds
        "denied", "declined", "rejected", "hold", "frozen", "locked out",
        "blocked", "restricted",
        # fraud & security
        "fraud", "unauthorized", "stolen", "hacked", "identity theft",
        "suspicious", "scam",
        # service quality
        "rude", "unhelpful", "incompetent", "terrible", "horrible",
        "worst", "unacceptable", "ridiculous", "outrageous",
        # emotions
        "angry", "furious", "frustrated", "upset", "disgusted",
        "disappointed", "livid", "fed up", "sick of",
        # demands
        "refund", "reimburse", "compensate", "escalate", "supervisor",
        "manager",
    }

    # --- Positive vocabulary ---
    POSITIVE_WORDS = {
        "thank", "thanks", "appreciate", "grateful", "helpful",
        "excellent", "great", "wonderful", "amazing", "fantastic",
        "resolved", "satisfied", "happy", "pleased", "quick",
        "efficient", "friendly", "professional", "courteous",
        "recommend", "love", "perfect", "impressed",
    }

    # --- Intensifiers that amplify negative sentiment ---
    INTENSIFIERS = {
        "very", "extremely", "absolutely", "completely", "totally",
        "utterly", "incredibly", "seriously", "really", "so",
    }

    def __init__(self):
        self._escalation_re = [re.compile(p, re.IGNORECASE) for p in self.ESCALATION_PATTERNS]

    def analyze(self, text: str) -> str:
        """
        Classify text sentiment.

        Returns one of: 'positive', 'neutral', 'negative', 'escalation_risk'
        """
        if not text or not text.strip():
            return "neutral"

        text_lower = text.lower()

        # 1. Check escalation risk first (overrides everything)
        for pattern in self._escalation_re:
            if pattern.search(text_lower):
                return "escalation_risk"

        # 2. Score negative and positive signals
        neg_score = self._count_matches(text_lower, self.NEGATIVE_WORDS)
        pos_score = self._count_matches(text_lower, self.POSITIVE_WORDS)

        # Intensifiers boost negative score
        intensifier_count = self._count_matches(text_lower, self.INTENSIFIERS)
        if neg_score > 0:
            neg_score += intensifier_count * 0.5

        # ALL-CAPS segments add to negative score
        caps_words = len([w for w in text.split() if w.isupper() and len(w) > 2])
        neg_score += caps_words * 0.3

        # Exclamation marks add mild negative signal
        neg_score += text.count("!") * 0.1

        # 3. Classify
        total = neg_score + pos_score
        if total == 0:
            return "neutral"

        if neg_score >= 3 and neg_score > pos_score * 2:
            return "escalation_risk"
        elif neg_score > pos_score:
            return "negative"
        elif pos_score > neg_score:
            return "positive"
        else:
            return "neutral"

    def analyze_batch(self, texts: list[str]) -> dict[str, int]:
        """Classify a batch of texts and return counts by category."""
        counts = {"positive": 0, "neutral": 0, "negative": 0, "escalation_risk": 0}
        for text in texts:
            result = self.analyze(text)
            counts[result] += 1
        return counts

    @staticmethod
    def _count_matches(text: str, word_set: set) -> float:
        count = 0.0
        for word in word_set:
            if word in text:
                count += 1.0
        return count
