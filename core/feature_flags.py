"""
core/feature_flags.py

Centralized feature-flag system for deployment-level feature gating.

Reads from ``data/features.json`` first (user-editable via Settings UI),
then applies environment variable overrides from ``.env`` on top.
Environment variables always take highest priority.

Feature flags control whether entire backend routes are registered /
frontend panels are shown.

Convenience shortcuts:
    ``OFFLINE_MODE=true``  disables ALL internet-dependent features at once.
    ``OFFLINE_MODE=false`` (or unset) lets individual flags take over.

Usage:
    from core.feature_flags import features

    if features.email:
        app.include_router(email_router)

    if features.is_enabled("web_search"):
        # same as features.web_search

    features.reload()        # re-read from disk (after Settings UI save)
    features.to_dict()
    # {"email": false, "web_search": false, "calendar": true, ...}
"""

import os
import json
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

# ── File-based feature storage path ────────────────────────────────────
_FEATURES_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "features.json",
)

# Map of feature keys → their default values (for file merging)
_FEATURE_DEFAULTS: dict[str, bool] = {key: default for key, _suffix, default, _desc in _FEATURES}


def _load_features_from_file() -> dict[str, bool]:
    """Load feature flag overrides from data/features.json.

    Returns a dict of feature_key → bool, or empty dict if the file
    doesn't exist / is invalid. Special key '_offline_mode' (bool)
    provides a UI-driven OFFLINE_MODE override.
    """
    try:
        with open(_FEATURES_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        if not isinstance(saved, dict):
            logger.warning("features.json is not a dict, ignoring")
            return {}
        result = {}
        for k, v in saved.items():
            if k == "_offline_mode":
                result[k] = bool(v)
            elif k in _FEATURE_DEFAULTS:
                result[k] = bool(v)
        return result
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"Failed to load features.json: {e}")
        return {}


def _save_features_to_file(features: dict[str, bool]) -> None:
    """Persist feature flag overrides to data/features.json (atomic)."""
    from core.atomic_io import atomic_write_json
    os.makedirs(os.path.dirname(_FEATURES_FILE), exist_ok=True)
    atomic_write_json(_FEATURES_FILE, features, indent=2)


class FeatureFlags:
    """Snapshot of deployment-level feature flags.

    Resolution order (highest priority wins):
        1. ``ODYSSEUS_FEATURE_*`` environment variables (``.env``)
        2. ``OFFLINE_MODE`` environment variable
        3. ``data/features.json`` user overrides (from Settings UI)
        4. Hardcoded defaults

    Each flag is a boolean attribute::

        >>> features.email
        True
        >>> features.is_enabled("web_search")
        True

    Call ``features.reload()`` after saving to ``data/features.json``
    to refresh the in-memory state (used by Settings UI save flow).
    """

    def __init__(self):
        self._data: dict[str, bool] = {}
        self._offline_mode = False
        self._file_overrides: dict[str, bool] = {}
        self._env_overrides: dict[str, bool] = {}
        self._resolve()

    def _resolve(self):
        """Rebuild the flag state from all sources."""
        # 1. Start with hardcoded defaults
        resolved = dict(_FEATURE_DEFAULTS)

        # 2. Apply file-based overrides (from Settings UI)
        self._file_overrides = _load_features_from_file()
        resolved.update({k: v for k, v in self._file_overrides.items() if k != "_offline_mode"})

        # 3. Check OFFLINE_MODE — env var takes priority, file override as fallback
        env_offline = os.getenv("OFFLINE_MODE", "").lower() in ("1", "true", "yes")
        file_offline = self._file_overrides.get("_offline_mode", False)
        self._offline_mode = env_offline or file_offline
        if self._offline_mode:
            source = "env" if env_offline else "settings UI"
            logger.info(f"OFFLINE_MODE=true ({source}) — internet-dependent features are disabled")

        # 4. Apply env var overrides (highest priority)
        self._env_overrides = {}
        for key, suffix, _default, _desc in _FEATURES:
            env_val = os.getenv(f"{_PREFIX}{suffix}")
            if env_val is not None:
                enabled = env_val.lower() in ("1", "true", "yes")
                self._env_overrides[key] = enabled
                resolved[key] = enabled
            elif self._offline_mode and key in _OFFLINE_DISABLED:
                resolved[key] = False

        self._data = resolved

        # Expose as attributes
        for key, value in resolved.items():
            object.__setattr__(self, key, value)

        # Log disabled features for operational visibility
        _disabled = [k for k, v in resolved.items() if not v]
        if _disabled:
            logger.info(
                "Disabled features (%d): %s",
                len(_disabled),
                ", ".join(sorted(_disabled)),
            )
        else:
            logger.info("All features enabled")

    def reload(self):
        """Re-read feature flags from disk and env vars.

        Call this after saving to ``data/features.json`` via the Settings UI.
        Note: route registration happens at startup, so route-level changes
        still require a server restart.
        """
        self._resolve()

    def __setattr__(self, name, value):
        """Prevent accidental mutation after initialization.

        Use ``reload()`` to refresh from disk, or environment variables
        for deployment-level overrides.
        """
        if name in ("_data", "_offline_mode", "_file_overrides", "_env_overrides"):
            super().__setattr__(name, value)
            return
        raise AttributeError(
            f"FeatureFlags is immutable after creation. "
            f"Cannot set '{name}'. Use data/features.json (Settings UI) "
            f"or environment variables."
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

    def get_source(self, key: str) -> str:
        """Return which source determined a feature's value.

        Returns one of: 'env', 'offline_mode', 'file', 'default'.
        """
        if key in self._env_overrides:
            return "env"
        if self._offline_mode and key in _OFFLINE_DISABLED:
            return "offline_mode"
        if key in self._file_overrides:
            return "file"
        return "default"

    @property
    def offline_mode(self) -> bool:
        """Whether OFFLINE_MODE is currently active (env or file override)."""
        return self._offline_mode

    def to_detailed_dict(self) -> dict:
        """Return feature flags with source metadata for the Settings UI."""
        details = {}
        for key, _suffix, default, desc in _FEATURES:
            details[key] = {
                "enabled": self._data.get(key, default),
                "source": self.get_source(key),
                "default": default,
                "description": desc,
                "offline_affected": key in _OFFLINE_DISABLED,
            }
        return details

    def save_file_overrides(self, overrides: dict[str, bool]) -> dict:
        """Save feature overrides to data/features.json and reload.

        Only keys present in overrides are updated; others keep their
        current file value. Env vars still take priority on next reload.
        Special key '_offline_mode' toggles offline mode from the UI.

        Returns the new full feature state.
        """
        current_file = dict(self._file_overrides)
        for k, v in overrides.items():
            if k == "_offline_mode":
                current_file["_offline_mode"] = bool(v)
            elif k in _FEATURE_DEFAULTS:
                current_file[k] = bool(v)
        _save_features_to_file(current_file)
        self.reload()
        return self.to_dict()

    def save_offline_mode(self, enabled: bool) -> dict:
        """Toggle offline mode from the Settings UI.

        Saves to data/features.json. Note: if OFFLINE_MODE=true in .env,
        that env var takes priority and this has no effect.
        """
        return self.save_file_overrides({"_offline_mode": enabled})


# ── Singleton (import-time, shared across the process) ─────────────────
features = FeatureFlags()

