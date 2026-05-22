"""Audit event catalog — maps raw `event` strings to a human label, a category,
and a severity. This is the single source of truth that makes the audit log crisp:
the API attaches label/category/severity to every row, and the category filter is
derived from here. Unknown/future events degrade gracefully via `classify`.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EventMeta:
    label: str
    category: str   # auth | security | data | destructive | ai | compliance | other
    severity: str   # info | warning | danger | success | ai | neutral


EVENT_CATALOG: dict[str, EventMeta] = {
    # Auth
    "login_success": EventMeta("Login", "auth", "info"),
    "logout": EventMeta("Logout", "auth", "neutral"),
    "refresh_token_rotated": EventMeta("Session refreshed", "auth", "neutral"),
    "password_reset_requested": EventMeta("Password reset requested", "auth", "info"),
    "password_reset_confirmed": EventMeta("Password reset", "auth", "warning"),
    # Security
    "login_failed": EventMeta("Login failed", "security", "warning"),
    "login_blocked_lockout": EventMeta("Login blocked (lockout)", "security", "danger"),
    "refresh_token_reuse_detected": EventMeta("Token reuse detected", "security", "danger"),
    "malware_detected": EventMeta("Malware blocked", "security", "danger"),
    # Data / lifecycle
    "project.created": EventMeta("Project created", "data", "info"),
    "project.updated": EventMeta("Project updated", "data", "info"),
    "app.created": EventMeta("App created", "data", "info"),
    "app.updated": EventMeta("App updated", "data", "info"),
    "corpus.doc.uploaded": EventMeta("Corpus doc uploaded", "data", "info"),
    "source.uploaded": EventMeta("Source uploaded", "data", "info"),
    # Destructive
    "app.deleted": EventMeta("App deleted", "destructive", "danger"),
    "project.deleted": EventMeta("Project deleted", "destructive", "danger"),
    # AI / generation
    "app.reindex.triggered": EventMeta("Reindex triggered", "ai", "info"),
    "app.brain.ask": EventMeta("App Brain query", "ai", "neutral"),
    "understanding.generated": EventMeta("RU generated (AI)", "ai", "ai"),
    # Compliance
    "understanding.validated": EventMeta("RU validated", "compliance", "success"),
    "audit.exported": EventMeta("Audit exported", "compliance", "warning"),
}

# A filter tab may cover more than one underlying category (Security includes destructive).
_CATEGORY_TABS: dict[str, set[str]] = {
    "security": {"security", "destructive"},
    "auth": {"auth"},
    "data": {"data"},
    "ai": {"ai"},
    "compliance": {"compliance"},
}


def classify(event: str) -> EventMeta:
    """Catalog lookup with a graceful fallback for unknown/future events."""
    meta = EVENT_CATALOG.get(event)
    if meta is not None:
        return meta
    label = event.replace("_", " ").replace(".", " ").strip()
    return EventMeta(label[:1].upper() + label[1:] if label else event, "other", "neutral")


def events_for_category(category: str) -> list[str]:
    """The set of catalogued event strings that a category filter tab should match."""
    cats = _CATEGORY_TABS.get(category, {category})
    return [event for event, meta in EVENT_CATALOG.items() if meta.category in cats]
