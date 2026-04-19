"""
ExperienceAgent — acts on detected friction events with automated
resolution strategies.

Inspired by Qualtrics Experience Agents: closes the loop between detection
and resolution, ensuring every friction point gets a response proportional
to its severity and type.

All actions are logged for the audit trail (NCUA / BSA-AML compliance).
"""

import uuid
from datetime import datetime
from typing import Optional


class AuditEntry:
    """Immutable audit record for every action taken by the agent."""

    def __init__(self, friction_id: str, action: str, detail: str):
        self.id = str(uuid.uuid4())
        self.friction_id = friction_id
        self.action = action
        self.detail = detail
        self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "friction_id": self.friction_id,
            "action": self.action,
            "detail": self.detail,
            "timestamp": self.timestamp,
        }


class ResolutionStatus:
    """Tracks resolution progress for a friction event."""

    def __init__(self, friction_id: str, friction_type: str, severity: str):
        self.friction_id = friction_id
        self.friction_type = friction_type
        self.severity = severity
        self.actions_taken: list[str] = []
        self.status = "in_progress"  # in_progress | resolved | escalated
        self.created_at = datetime.utcnow().isoformat()
        self.updated_at = self.created_at

    def to_dict(self) -> dict:
        return {
            "friction_id": self.friction_id,
            "friction_type": self.friction_type,
            "severity": self.severity,
            "actions_taken": self.actions_taken,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class ExperienceAgent:
    """
    Automated response engine for friction events.

    Resolution strategies per friction type:
        - complaint_velocity  -> alert branch manager, generate member comms
        - failed_transaction  -> adjust risk thresholds, notify member
        - negative_sentiment  -> escalate to supervisor, draft service recovery
        - compliance_violation -> trigger compliance review, lock accounts
        - lockout_cascade     -> auto-adjust thresholds, check system health
    """

    def __init__(self):
        self._resolutions: dict[str, ResolutionStatus] = {}
        self._audit_log: list[AuditEntry] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def handle_friction(self, friction_event: dict) -> ResolutionStatus:
        """
        Dispatch resolution strategy based on friction type and severity.

        Accepts a friction event dict (from FrictionEvent.to_dict()).
        Returns the ResolutionStatus tracking object.
        """
        fid = friction_event["id"]
        ftype = friction_event["type"]
        severity = friction_event["severity"]

        status = ResolutionStatus(fid, ftype, severity)
        self._resolutions[fid] = status

        # Always log receipt
        self._log(fid, "received", f"Friction event received: {ftype} ({severity})")

        # Critical severity always gets immediate escalation
        if severity == "critical":
            self._escalate_to_supervisor(friction_event, status)

        # Type-specific strategies
        handler = {
            "complaint_velocity": self._handle_complaint_velocity,
            "failed_transaction": self._handle_failed_transaction,
            "negative_sentiment": self._handle_negative_sentiment,
            "compliance_violation": self._handle_compliance_violation,
            "lockout_cascade": self._handle_lockout_cascade,
        }.get(ftype)

        if handler:
            handler(friction_event, status)

        status.updated_at = datetime.utcnow().isoformat()
        return status

    def get_resolution_status(self, friction_id: Optional[str] = None) -> list[dict]:
        """Get resolution status for one or all friction events."""
        if friction_id:
            s = self._resolutions.get(friction_id)
            return [s.to_dict()] if s else []
        return [s.to_dict() for s in self._resolutions.values()]

    def generate_report(self) -> dict:
        """Generate a summary report of all actions taken."""
        total = len(self._resolutions)
        by_status = {"in_progress": 0, "resolved": 0, "escalated": 0}
        by_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}

        for s in self._resolutions.values():
            by_status[s.status] = by_status.get(s.status, 0) + 1
            by_type[s.friction_type] = by_type.get(s.friction_type, 0) + 1
            by_severity[s.severity] = by_severity.get(s.severity, 0) + 1

        return {
            "generated_at": datetime.utcnow().isoformat(),
            "total_frictions_handled": total,
            "by_status": by_status,
            "by_type": by_type,
            "by_severity": by_severity,
            "total_audit_entries": len(self._audit_log),
            "audit_trail": [e.to_dict() for e in self._audit_log[-50:]],
        }

    def get_audit_log(self, limit: int = 100) -> list[dict]:
        """Return recent audit entries (most recent first)."""
        return [e.to_dict() for e in self._audit_log[-limit:][::-1]]

    # ------------------------------------------------------------------
    # Resolution strategies
    # ------------------------------------------------------------------

    def _handle_complaint_velocity(self, event: dict, status: ResolutionStatus):
        """Alert branch manager and generate member communication drafts."""
        members = event.get("affected_members", [])

        # Alert branch manager with location-specific insights
        self._log(event["id"], "alert_branch_manager",
                  f"Complaint spike alert sent to branch manager. "
                  f"{len(members)} member(s) affected.")
        status.actions_taken.append("branch_manager_alerted")

        # Generate member communication drafts
        for member_id in members[:10]:  # cap at 10 to avoid spam
            draft = self._generate_member_communication(
                member_id, "complaint_velocity", event
            )
            self._log(event["id"], "communication_draft",
                      f"Service recovery draft generated for member {member_id}: "
                      f"{draft[:80]}...")
        status.actions_taken.append("member_communications_drafted")

    def _handle_failed_transaction(self, event: dict, status: ResolutionStatus):
        """Adjust risk thresholds and notify affected members."""
        members = event.get("affected_members", [])

        # Auto-adjust risk thresholds temporarily
        self._log(event["id"], "threshold_adjustment",
                  "Temporary risk threshold relaxation applied for affected members. "
                  "Duration: 2 hours. Auto-reverts.")
        status.actions_taken.append("risk_thresholds_adjusted")

        # Notify members
        for member_id in members:
            draft = self._generate_member_communication(
                member_id, "failed_transaction", event
            )
            self._log(event["id"], "member_notification",
                      f"Transaction failure notification drafted for {member_id}")
        status.actions_taken.append("members_notified")

    def _handle_negative_sentiment(self, event: dict, status: ResolutionStatus):
        """Escalate to supervisor and draft service recovery."""
        self._escalate_to_supervisor(event, status)

        members = event.get("affected_members", [])
        for member_id in members:
            draft = self._generate_member_communication(
                member_id, "service_recovery", event
            )
            self._log(event["id"], "service_recovery_draft",
                      f"Service recovery offer drafted for {member_id}: {draft[:80]}...")
        status.actions_taken.append("service_recovery_drafted")

    def _handle_compliance_violation(self, event: dict, status: ResolutionStatus):
        """Trigger compliance review workflow and lock accounts."""
        # Trigger compliance review
        self._log(event["id"], "compliance_review_triggered",
                  "Compliance review workflow initiated. BSA/AML officer notified. "
                  "Documentation preserved for examination.")
        status.actions_taken.append("compliance_review_triggered")

        # Lock affected accounts pending investigation
        members = event.get("affected_members", [])
        self._log(event["id"], "accounts_locked",
                  f"Precautionary hold placed on {len(members)} account(s) "
                  f"pending compliance review.")
        status.actions_taken.append("accounts_locked")
        status.status = "escalated"

    def _handle_lockout_cascade(self, event: dict, status: ResolutionStatus):
        """Auto-adjust thresholds and check system health."""
        # Auto-adjust risk thresholds
        self._log(event["id"], "threshold_adjustment",
                  "Lockout thresholds temporarily elevated to prevent cascade. "
                  "Auto-reverts in 30 minutes.")
        status.actions_taken.append("lockout_thresholds_adjusted")

        # System health check
        self._log(event["id"], "system_health_check",
                  "Authentication system health check initiated. "
                  "Checking: AD/LDAP, core banking, MFA provider.")
        status.actions_taken.append("system_health_check_initiated")

        # If critical, also alert security
        if event.get("severity") == "critical":
            self._log(event["id"], "security_alert",
                      "Security team alerted for potential credential-stuffing "
                      "or brute-force attack investigation.")
            status.actions_taken.append("security_team_alerted")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _escalate_to_supervisor(self, event: dict, status: ResolutionStatus):
        """Auto-escalate to supervisor."""
        self._log(event["id"], "supervisor_escalation",
                  f"Auto-escalated to supervisor. Severity: {event['severity']}. "
                  f"Type: {event['type']}. "
                  f"Affected members: {len(event.get('affected_members', []))}.")
        status.actions_taken.append("escalated_to_supervisor")
        if status.status != "escalated":
            status.status = "escalated"

    def _generate_member_communication(
        self, member_id: str, reason: str, event: dict
    ) -> str:
        """Generate a service recovery communication draft."""
        templates = {
            "complaint_velocity": (
                f"Dear Member {member_id}, we value your membership and want to "
                f"address your recent concern. A member of our team will contact "
                f"you within 24 hours to ensure your needs are met."
            ),
            "failed_transaction": (
                f"Dear Member {member_id}, we noticed a recent transaction issue "
                f"on your account. We have reviewed your account and made "
                f"adjustments to prevent further disruption. Please contact us "
                f"if you experience any additional issues."
            ),
            "service_recovery": (
                f"Dear Member {member_id}, your experience matters to us. "
                f"We would like to schedule a call with a senior representative "
                f"to discuss your recent interaction and make things right."
            ),
        }
        return templates.get(reason, f"Dear Member {member_id}, we are reviewing your case.")

    def _log(self, friction_id: str, action: str, detail: str):
        """Append to the immutable audit log."""
        entry = AuditEntry(friction_id, action, detail)
        self._audit_log.append(entry)
