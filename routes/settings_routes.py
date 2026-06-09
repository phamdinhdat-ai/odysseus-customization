"""Feature flag settings API — read/write feature flags from the UI."""
import os
import logging
from fastapi import APIRouter, Request, HTTPException
from core.feature_flags import features
from core.middleware import require_admin

logger = logging.getLogger(__name__)


def _offline_info():
    """Return offline mode status with source info."""
    env_offline = os.getenv("OFFLINE_MODE", "").lower() in ("1", "true", "yes")
    return {
        "active": features.offline_mode,
        "source": "env" if env_offline else ("file" if features.offline_mode else "none"),
        "env_override": env_offline,
    }


def setup_feature_settings_routes():
    """Create routes for managing feature flags from the Settings UI.

    GET  /api/settings/features        — full feature list with metadata
    PUT  /api/settings/features        — save overrides
    PUT  /api/settings/features/offline-mode — toggle offline mode
    POST /api/settings/features/reload — force reload
    """
    router = APIRouter(prefix="/api/settings", tags=["settings"])

    @router.get("/features")
    async def get_feature_flags(request: Request):
        """Return all feature flags with metadata for the Settings UI."""
        require_admin(request)
        features.reload()
        return {
            "ok": True,
            "data": features.to_detailed_dict(),
            "offline_mode": _offline_info(),
            "note": "Route-level changes require a server restart.",
        }

    @router.put("/features")
    async def save_feature_flags(request: Request, body: dict):
        """Save feature flag overrides to data/features.json."""
        require_admin(request)
        features.save_file_overrides(body)
        return {
            "ok": True,
            "data": features.to_detailed_dict(),
            "offline_mode": _offline_info(),
            "note": "Saved. Restart server for route-level changes.",
        }

    @router.put("/features/offline-mode")
    async def toggle_offline_mode(request: Request, body: dict):
        """Toggle offline mode from UI. Body: {"enabled": true/false}.

        Note: if OFFLINE_MODE=true in .env, the env var takes priority.
        """
        require_admin(request)
        enabled = bool(body.get("enabled", False))
        features.save_offline_mode(enabled)
        return {
            "ok": True,
            "offline_mode": _offline_info(),
            "data": features.to_detailed_dict(),
            "note": "Offline mode " + ("enabled" if enabled else "disabled") +
                    ". Restart server for route-level changes." +
                    (" (Note: .env OFFLINE_MODE=true overrides this)" if os.getenv("OFFLINE_MODE", "").lower() in ("1", "true", "yes") else ""),
        }

    @router.post("/features/reload")
    async def reload_feature_flags(request: Request):
        """Force reload feature flags from disk."""
        require_admin(request)
        features.reload()
        return {
            "ok": True,
            "data": features.to_detailed_dict(),
            "offline_mode": _offline_info(),
        }

    return router
