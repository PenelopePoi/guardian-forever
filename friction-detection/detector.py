"""
FrictionDetector — monitors compliance workflow events and detects friction
patterns in credit union operations.

Inspired by Qualtrics Experience Agents: continuously watches operational
signals and surfaces friction before it cascades into member attrition,
compliance violations, or regulatory action.
"""

import uuid
import time
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional

try:
    from .sentiment import SentimentAnalyzer
except ImportError:
    from sentiment import SentimentAnalyzer


class FrictionEvent:
    """A detected friction point in credit union operations."""

    SEVERITIES = ("low", "medium", "high", "critical")
    TYPES = (
        "complaint_velocity",
        "failed_transaction",
        "negative_sentiment",
        "compliance_violation",
        "lockout_cascade",
    )

    def __init__(
        self,
        friction_type: str,
        severity: str,
        affected_members: list[str],
        description: str,
        recommended_action: str,
        source_events: Optional[list[dict]] = None,
    ):
        if severity not in self.SEVERITIES:
            raise ValueError(f"severity must be one of {self.SEVERITIES}")
        if friction_type not in self.TYPES:
            raise ValueError(f"type must be one of {self.TYPES}")

        self.id = str(uuid.uuid4())
        self.type = friction_type
        self.severity = severity
        self.timestamp = datetime.utcnow().isoformat()
        self.affected_members = affected_members
        self.description = description
        self.recommended_action = recommended_action
        self.source_events = source_events or []
        self.resolved = False
        self.resolved_at = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "severity": self.severity,
            "timestamp": self.timestamp,
            "affected_members": self.affected_members,
            "description": self.description,
            "recommended_action": self.recommended_action,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at,
        }


class FrictionDetector:
    """
    Monitors compliance workflow events and detects friction patterns.

    Friction types detected:
        - complaint_velocity: spike in complaints per hour
        - failed_transaction: repeated declines, holds
        - negative_sentiment: negative sentiment in call logs / interactions
        - compliance_violation: unusual access patterns, policy breaches
        - lockout_cascade: multiple members locked out simultaneously
    """

    # Thresholds — tuned for a $500M credit union
    COMPLAINT_VELOCITY_THRESHOLD = 5          # complaints per hour to trigger
    FAILED_TXN_THRESHOLD = 3                  # repeated declines per member
    LOCKOUT_CASCADE_THRESHOLD = 3             # simultaneous lockouts
    COMPLIANCE_RISK_KEYWORDS = (
        "unauthorized", "override", "bypass", "escalat", "breach",
        "policy violation", "suspicious", "unusual access",
    )

    def __init__(self):
        self._active: dict[str, FrictionEvent] = {}
        self._history: list[FrictionEvent] = []
        self._sentiment = SentimentAnalyzer()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect_friction(self, events: list[dict]) -> list[FrictionEvent]:
        """
        Analyze a batch of workflow events and return any new friction detected.

        Each event dict should contain at minimum:
            { "type": str, "timestamp": str (ISO), "member_id": str, "detail": str }

        Optional fields vary by event type (amount, channel, location, etc.).
        """
        detected: list[FrictionEvent] = []
        detected.extend(self._detect_complaint_velocity(events))
        detected.extend(self._detect_failed_transactions(events))
        detected.extend(self._detect_negative_sentiment(events))
        detected.extend(self._detect_compliance_violations(events))
        detected.extend(self._detect_lockout_cascades(events))

        for f in detected:
            self._active[f.id] = f

        return detected

    def get_active_frictions(self) -> list[dict]:
        """Return all unresolved friction events."""
        return [f.to_dict() for f in self._active.values()]

    def resolve_friction(self, friction_id: str, resolution_note: str = "") -> bool:
        """Mark a friction event as resolved. Returns False if not found."""
        if friction_id not in self._active:
            return False
        event = self._active.pop(friction_id)
        event.resolved = True
        event.resolved_at = datetime.utcnow().isoformat()
        self._history.append(event)
        return True

    def get_friction_history(self, limit: int = 100) -> list[dict]:
        """Return resolved friction events, most recent first."""
        return [f.to_dict() for f in self._history[-limit:][::-1]]

    # ------------------------------------------------------------------
    # Detection methods
    # ------------------------------------------------------------------

    def _detect_complaint_velocity(self, events: list[dict]) -> list[FrictionEvent]:
        complaints = [e for e in events if e.get("type") == "complaint"]
        if not complaints:
            return []

        # Group by hour bucket
        buckets: dict[str, list[dict]] = defaultdict(list)
        for c in complaints:
            hour = c.get("timestamp", "")[:13]  # YYYY-MM-DDTHH
            buckets[hour].append(c)

        results = []
        for hour, group in buckets.items():
            if len(group) >= self.COMPLAINT_VELOCITY_THRESHOLD:
                members = list({e.get("member_id", "unknown") for e in group})
                severity = "critical" if len(group) >= self.COMPLAINT_VELOCITY_THRESHOLD * 2 else "high"
                results.append(FrictionEvent(
                    friction_type="complaint_velocity",
                    severity=severity,
                    affected_members=members,
                    description=(
                        f"{len(group)} complaints in hour {hour}. "
                        f"Threshold is {self.COMPLAINT_VELOCITY_THRESHOLD}/hr."
                    ),
                    recommended_action=(
                        "Escalate to branch manager. Review common complaint "
                        "themes and initiate service recovery outreach."
                    ),
                    source_events=group,
                ))
        return results

    def _detect_failed_transactions(self, events: list[dict]) -> list[FrictionEvent]:
        txn_failures = [e for e in events if e.get("type") == "transaction_failed"]
        if not txn_failures:
            return []

        by_member: dict[str, list[dict]] = defaultdict(list)
        for e in txn_failures:
            by_member[e.get("member_id", "unknown")].append(e)

        results = []
        flagged_members = []
        source = []
        for member, failures in by_member.items():
            if len(failures) >= self.FAILED_TXN_THRESHOLD:
                flagged_members.append(member)
                source.extend(failures)

        if flagged_members:
            severity = "high" if len(flagged_members) > 1 else "medium"
            results.append(FrictionEvent(
                friction_type="failed_transaction",
                severity=severity,
                affected_members=flagged_members,
                description=(
                    f"{len(flagged_members)} member(s) with {self.FAILED_TXN_THRESHOLD}+ "
                    f"consecutive failed transactions."
                ),
                recommended_action=(
                    "Review hold/decline policies. Contact affected members "
                    "proactively to resolve card or account issues."
                ),
                source_events=source,
            ))
        return results

    def _detect_negative_sentiment(self, events: list[dict]) -> list[FrictionEvent]:
        interactions = [e for e in events if e.get("type") in ("call_log", "chat_log", "email")]
        if not interactions:
            return []

        negative = []
        escalation_risk = []
        for e in interactions:
            text = e.get("detail", "")
            result = self._sentiment.analyze(text)
            if result == "escalation_risk":
                escalation_risk.append(e)
            elif result == "negative":
                negative.append(e)

        results = []
        if escalation_risk:
            members = list({e.get("member_id", "unknown") for e in escalation_risk})
            results.append(FrictionEvent(
                friction_type="negative_sentiment",
                severity="critical",
                affected_members=members,
                description=(
                    f"{len(escalation_risk)} interaction(s) flagged as escalation risk."
                ),
                recommended_action=(
                    "Immediate supervisor callback. Prepare service recovery "
                    "offer and document interaction for compliance review."
                ),
                source_events=escalation_risk,
            ))
        elif len(negative) >= 3:
            members = list({e.get("member_id", "unknown") for e in negative})
            results.append(FrictionEvent(
                friction_type="negative_sentiment",
                severity="medium",
                affected_members=members,
                description=(
                    f"{len(negative)} interactions with negative sentiment detected."
                ),
                recommended_action=(
                    "Review interaction logs for common pain points. "
                    "Consider targeted training for front-line staff."
                ),
                source_events=negative,
            ))
        return results

    def _detect_compliance_violations(self, events: list[dict]) -> list[FrictionEvent]:
        results = []
        violations = []
        for e in events:
            detail = (e.get("detail", "") + " " + e.get("type", "")).lower()
            if any(kw in detail for kw in self.COMPLIANCE_RISK_KEYWORDS):
                violations.append(e)

        if violations:
            members = list({e.get("member_id", "unknown") for e in violations})
            severity = "critical" if len(violations) >= 3 else "high"
            results.append(FrictionEvent(
                friction_type="compliance_violation",
                severity=severity,
                affected_members=members,
                description=(
                    f"{len(violations)} event(s) matched compliance risk patterns: "
                    f"unauthorized access, policy bypass, or suspicious activity."
                ),
                recommended_action=(
                    "Initiate compliance review workflow. Lock affected accounts "
                    "pending investigation. Notify BSA/AML officer if applicable."
                ),
                source_events=violations,
            ))
        return results

    def _detect_lockout_cascades(self, events: list[dict]) -> list[FrictionEvent]:
        lockouts = [e for e in events if e.get("type") == "account_lockout"]
        if len(lockouts) < self.LOCKOUT_CASCADE_THRESHOLD:
            return []

        # Check if lockouts are clustered in time (within 10 minutes)
        timestamps = []
        for e in lockouts:
            ts = e.get("timestamp", "")
            try:
                timestamps.append(datetime.fromisoformat(ts))
            except (ValueError, TypeError):
                continue

        if len(timestamps) < self.LOCKOUT_CASCADE_THRESHOLD:
            return []

        timestamps.sort()
        # Sliding window: any 10-minute window with enough lockouts
        window = timedelta(minutes=10)
        for i in range(len(timestamps)):
            cluster = [t for t in timestamps if timestamps[i] <= t <= timestamps[i] + window]
            if len(cluster) >= self.LOCKOUT_CASCADE_THRESHOLD:
                members = list({e.get("member_id", "unknown") for e in lockouts})
                severity = "critical" if len(cluster) >= self.LOCKOUT_CASCADE_THRESHOLD * 2 else "high"
                return [FrictionEvent(
                    friction_type="lockout_cascade",
                    severity=severity,
                    affected_members=members,
                    description=(
                        f"{len(cluster)} account lockouts within 10 minutes. "
                        f"Possible system issue or coordinated attack."
                    ),
                    recommended_action=(
                        "Check authentication systems for outage. If no outage, "
                        "escalate to security team for potential credential-stuffing "
                        "or brute-force investigation."
                    ),
                    source_events=lockouts,
                )]

        return []
