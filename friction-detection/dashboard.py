#!/usr/bin/env python3
"""
CLI Dashboard — real-time friction state for Guardian AI.

Run standalone:
    python -m friction_detection.dashboard
    python friction-detection/dashboard.py
"""

import sys
import os
from datetime import datetime

# Allow running as standalone script — handle both hyphenated dir and package import
_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_pkg_dir = os.path.join(_parent, "friction-detection")
sys.path.insert(0, _parent)
sys.path.insert(0, _pkg_dir)

try:
    from friction_detection.detector import FrictionDetector, FrictionEvent
    from friction_detection.experience_agent import ExperienceAgent
except ImportError:
    # Direct import when running from inside the directory
    from detector import FrictionDetector, FrictionEvent
    from experience_agent import ExperienceAgent


# ANSI colors
RED = "\033[91m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

SEVERITY_COLOR = {
    "critical": RED,
    "high": YELLOW,
    "medium": CYAN,
    "low": GREEN,
}


def print_header():
    print(f"\n{BOLD}{'=' * 64}{RESET}")
    print(f"{BOLD}  GUARDIAN AI  —  Experience Agent Friction Dashboard{RESET}")
    print(f"{DIM}  Qualtrics-inspired compliance monitoring for credit unions{RESET}")
    print(f"{BOLD}{'=' * 64}{RESET}")
    print(f"{DIM}  Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}{RESET}\n")


def print_active_frictions(detector: FrictionDetector):
    active = detector.get_active_frictions()
    print(f"{BOLD}ACTIVE FRICTIONS ({len(active)}){RESET}")
    print(f"{'-' * 50}")

    if not active:
        print(f"  {GREEN}No active friction events.{RESET}\n")
        return

    # Group by severity
    by_severity: dict[str, list] = {"critical": [], "high": [], "medium": [], "low": []}
    for f in active:
        by_severity.get(f["severity"], []).append(f)

    for severity in ("critical", "high", "medium", "low"):
        items = by_severity[severity]
        if not items:
            continue
        color = SEVERITY_COLOR[severity]
        print(f"\n  {color}{BOLD}{severity.upper()} ({len(items)}){RESET}")
        for f in items:
            members = len(f.get("affected_members", []))
            print(f"    {color}[{f['type']}]{RESET} {f['description'][:60]}")
            print(f"      {DIM}ID: {f['id'][:8]}...  Members: {members}  Time: {f['timestamp']}{RESET}")
    print()


def print_resolution_stats(agent: ExperienceAgent):
    report = agent.generate_report()
    print(f"{BOLD}RESOLUTION STATUS{RESET}")
    print(f"{'-' * 50}")

    by_status = report.get("by_status", {})
    total = report.get("total_frictions_handled", 0)

    resolved = by_status.get("resolved", 0)
    in_progress = by_status.get("in_progress", 0)
    escalated = by_status.get("escalated", 0)

    if total > 0:
        rate = (resolved / total) * 100
        print(f"  Resolution rate:    {GREEN}{rate:.0f}%{RESET} ({resolved}/{total})")
    else:
        print(f"  Resolution rate:    {DIM}N/A (no events){RESET}")

    print(f"  In progress:        {CYAN}{in_progress}{RESET}")
    print(f"  Escalated:          {YELLOW}{escalated}{RESET}")
    print(f"  Resolved:           {GREEN}{resolved}{RESET}")
    print(f"  Audit trail entries: {report.get('total_audit_entries', 0)}")
    print()


def print_friction_type_breakdown(agent: ExperienceAgent):
    report = agent.generate_report()
    by_type = report.get("by_type", {})

    print(f"{BOLD}TOP FRICTION TYPES{RESET}")
    print(f"{'-' * 50}")

    if not by_type:
        print(f"  {DIM}No friction data yet.{RESET}\n")
        return

    sorted_types = sorted(by_type.items(), key=lambda x: x[1], reverse=True)
    max_count = max(by_type.values()) if by_type else 1

    for ftype, count in sorted_types:
        bar_len = int((count / max_count) * 20)
        bar = "#" * bar_len
        label = ftype.replace("_", " ").title()
        print(f"  {label:<28} {CYAN}{bar}{RESET} {count}")
    print()


def print_affected_members(detector: FrictionDetector):
    active = detector.get_active_frictions()
    all_members = set()
    for f in active:
        all_members.update(f.get("affected_members", []))

    print(f"{BOLD}AFFECTED MEMBERS{RESET}")
    print(f"{'-' * 50}")
    print(f"  Total unique members impacted: {YELLOW}{len(all_members)}{RESET}")
    if all_members and len(all_members) <= 10:
        for m in sorted(all_members):
            print(f"    - {m}")
    elif all_members:
        sample = sorted(all_members)[:10]
        for m in sample:
            print(f"    - {m}")
        print(f"    {DIM}... and {len(all_members) - 10} more{RESET}")
    print()


def run_demo():
    """Run a demo with sample data to showcase the dashboard."""
    detector = FrictionDetector()
    agent = ExperienceAgent()

    # Sample events simulating a busy credit union day
    sample_events = [
        {"type": "complaint", "timestamp": "2026-04-18T14:00:00", "member_id": "M1001", "detail": "Fee dispute"},
        {"type": "complaint", "timestamp": "2026-04-18T14:05:00", "member_id": "M1002", "detail": "Long wait time"},
        {"type": "complaint", "timestamp": "2026-04-18T14:10:00", "member_id": "M1003", "detail": "Rude teller"},
        {"type": "complaint", "timestamp": "2026-04-18T14:15:00", "member_id": "M1004", "detail": "Wrong balance"},
        {"type": "complaint", "timestamp": "2026-04-18T14:20:00", "member_id": "M1005", "detail": "Card issue"},
        {"type": "transaction_failed", "timestamp": "2026-04-18T14:01:00", "member_id": "M2001", "detail": "Declined at POS"},
        {"type": "transaction_failed", "timestamp": "2026-04-18T14:02:00", "member_id": "M2001", "detail": "Declined at ATM"},
        {"type": "transaction_failed", "timestamp": "2026-04-18T14:03:00", "member_id": "M2001", "detail": "Declined online"},
        {"type": "call_log", "timestamp": "2026-04-18T13:30:00", "member_id": "M3001",
         "detail": "I am extremely frustrated with this overdraft fee. I want to speak to a manager NOW. "
                   "This is unacceptable and I am considering closing my account."},
        {"type": "call_log", "timestamp": "2026-04-18T13:45:00", "member_id": "M3002",
         "detail": "Your staff was very helpful and resolved my issue quickly. Thank you!"},
        {"type": "account_lockout", "timestamp": "2026-04-18T15:00:00", "member_id": "M4001", "detail": "Failed login x3"},
        {"type": "account_lockout", "timestamp": "2026-04-18T15:01:00", "member_id": "M4002", "detail": "Failed login x3"},
        {"type": "account_lockout", "timestamp": "2026-04-18T15:02:00", "member_id": "M4003", "detail": "Failed login x3"},
        {"type": "email", "timestamp": "2026-04-18T12:00:00", "member_id": "M5001",
         "detail": "Unauthorized transaction on my account. Someone accessed my account without permission."},
    ]

    # Detect friction
    frictions = detector.detect_friction(sample_events)

    # Agent handles each friction
    for f in frictions:
        agent.handle_friction(f.to_dict())

    # Print dashboard
    print_header()
    print_active_frictions(detector)
    print_resolution_stats(agent)
    print_friction_type_breakdown(agent)
    print_affected_members(detector)

    print(f"{DIM}{'=' * 64}{RESET}")
    print(f"{DIM}  Guardian AI  |  Zero-Trust Autonomous Compliance  |  $500M CU{RESET}")
    print(f"{DIM}{'=' * 64}{RESET}\n")


def main():
    """Entry point — runs demo mode by default."""
    if "--help" in sys.argv or "-h" in sys.argv:
        print("Usage: python dashboard.py [--demo]")
        print("  --demo    Run with sample friction data (default)")
        print("  --empty   Show empty dashboard")
        return

    if "--empty" in sys.argv:
        detector = FrictionDetector()
        agent = ExperienceAgent()
        print_header()
        print_active_frictions(detector)
        print_resolution_stats(agent)
        print_friction_type_breakdown(agent)
        print_affected_members(detector)
    else:
        run_demo()


if __name__ == "__main__":
    main()
