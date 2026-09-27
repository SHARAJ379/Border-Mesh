import hmac
from typing import Optional

from fastapi import Header, HTTPException

from app.core.config import settings
from app.core.database import get_db


def require_officer_auth(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> None:
    """
    Minimal API-key gate for the most sensitive, irreversible actions (case
    deletion, biometric purge) -- see the OFFICER_API_KEY setting for the
    scope and limits of what this actually protects against. Any request
    missing the header, or presenting the wrong value, is rejected before
    the route body ever runs.

    hmac.compare_digest, not `!=`: a plain string comparison short-circuits
    on the first mismatched byte, so its running time leaks how many
    leading characters of a guess were correct -- a real, well-known
    timing side-channel (CWE-208) against a shared-secret comparison like
    this one. compare_digest runs in constant time with respect to the
    content of both inputs.
    """
    if not x_api_key or not hmac.compare_digest(x_api_key, settings.OFFICER_API_KEY):
        raise HTTPException(status_code=401, detail="Missing or invalid X-API-Key for this action.")


# Re-export get_db
__all__ = ["get_db", "require_officer_auth"]
