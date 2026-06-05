"""
core/feature_flags.py

Centralized feature-flag system for deployment-level feature gating.

Reads from environment variables (``.env``) — NOT from the database — because
these are deployment-level configuration decisions.  Feature flags control
whether entire backend routes are registered / frontend panels are shown.

Convenience shortcuts:
    ``OFFLINE_MODE=true``  disables ALL internet-dependent features at once.
    ``OFFLINE_MODE=false`` (or unset) lets individual flags take over.

Usage:
    from core.feature_flags import features

    if features.email:
        app.include_router(email_router)

    if features.is_enabled("web_search"):
        # same as features.web_search

    features.to_dict()
    # {"email": false, "web_search": false, "calendar": true, ...}
"""

import os
import logging

logger = logging.getLogger(__name__)

# ── Environment variable prefix ────────────────────────────────────────
_PREFIX = "ODYSSEUS_FEATURE_"

# ── Feature definitions ────────────────────────────────────────────────
# (key, env_suffix, default, description)
_FEATURES = [
    # ── Internet-dependent (disabled when OFFLINE_MODE=true) ────────
    ("email",       "EMAIL",       True,  "IMAP/SMTP email integration"),
    ("web_search",  "WEB_SEARCH",  True,  "SearXNG / external web search"),
    ("research",    "RESEARCH",    True,  "Deep Research (multi-step web synthesis)"),
    ("gallery",     "GALLERY",     True,  "Generated image library"),
    ("compare",     "COMPARE",     True,  "Multi-model side-by-side comparison"),
    ("cookbook",    "COOKBOOK",    True,  "Model download/serve (HuggingFace)"),
    ("webhooks",    "WEBHOOKS",    True,  "Outgoing webhook notifications"),
    ("companion",   "COMPANION",   True,  "LAN companion pairing (QR codes)"),

    # ── Core productivity (always enabled by default) ────────────────
    ("calendar",    "CALENDAR",    True,  "Calendar (CalDAV sync)"),
    ("notes",       "NOTES",       True,  "Notes / Todos / Reminders"),
    ("tasks",       "TASKS",       True,  "Scheduled background tasks"),
    ("memory",      "MEMORY",      True,  "Persistent memory + vector search"),
    ("skills",      "SKILLS",      True,  "Agent skill definitions"),
    ("documents",   "DOCUMENTS",   True,  "Multi-tab document editor"),
    ("shell",       "SHELL",       True,  "Shell command execution"),
    ("presets",     "PRESETS",     True,  "Chat configuration presets"),
    ("settings",    "SETTINGS",    True,  "Application settings panel"),
    ("search_chats","SEARCH_CHATS",True,  "Chat message search (Ctrl+K)"),

    # ── Optional / debugging ─────────────────────────────────────────
    ("diagnostics", "DIAGNOSTICS", False, "Diagnostics and debug endpoints"),
    ("tts",         "TTS",         True,  "Text-to-speech"),
    ("stt",         "STT",         True,  "Speech-to-text"),
]

# Features that OFFLINE_MODE=true disables automatically
_OFFLINE_DISABLED = frozenset({
    "email", "web_search", "research", "gallery", "compare",
    "cookbook", "webhooks", "companion",
})


class FeatureFlags:
    """Immutable snapshot of deployment-level feature flags.

    Each flag is a boolean attribute::

        >>> features.email
        True
        >>> features.is_enabled("web_search")
        True
    """

    def __init__(self):
        self._data: dict[str, bool] = {}
        self._offline_mode = os.getenv("OFFLINE_MODE", "").lower() in ("1", "true", "yes")

        if self._offline_mode:
            logger.info("OFFLINE_MODE=true — internet-dependent features are disabled")

        for key, suffix, default, _desc in _FEATURES:
            env_val = os.getenv(f"{_PREFIX}{suffix}")
            if env_val is not None:
                # Explicit env var takes priority
                enabled = env_val.lower() in ("1", "true", "yes")
            elif self._offline_mode and key in _OFFLINE_DISABLED:
                # OFFLINE_MODE overrides default for internet features
                enabled = False
            else:
                enabled = default

            self._data[key] = enabled
            # Expose as attribute (immutable via __setattr__)
            object.__setattr__(self, key, enabled)

        # Log disabled features for operational visibility
        _disabled = [k for k, v in self._data.items() if not v]
        if _disabled:
            logger.info(
                "Disabled features (%d): %s",
                len(_disabled),
                ", ".join(sorted(_disabled)),
            )
        else:
            logger.info("All features enabled")

    def __setattr__(self, name, value):
        """Prevent mutation after initialization."""
        if name in ("_data", "_offline_mode"):
            super().__setattr__(name, value)
            return
        raise AttributeError(
            f"FeatureFlags is immutable after creation. "
            f"Cannot set '{name}'. Use environment variables."
        )

    def is_enabled(self, name: str) -> bool:
        """Check if a named feature is enabled.

        Unknown feature names default to ``True`` (safe fallback).
        """
        return self._data.get(name, True)

    def to_dict(self) -> dict[str, bool]:
        """Return all feature flags as a JSON-serializable dict."""
        return dict(self._data)

    def disabled_set(self) -> set[str]:
        """Return the set of disabled feature keys."""
        return {k for k, v in self._data.items() if not v}


# ── Singleton (import-time, shared across the process) ─────────────────
features = FeatureFlags()
