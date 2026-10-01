from typing import Optional

from fastapi import Header, HTTPException, Query, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models import Officer


def get_current_officer(
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
) -> Officer:
    """
    Resolves the real, logged-in Officer behind this request -- replaces the
    old single shared OFFICER_API_KEY, which gated exactly 2 endpoints and
    carried no per-user identity at all. Every data-reading and data-writing
    route in this app now depends on this (see each router), so an
    unauthenticated request can no longer read a case file or stream a
    biometric image, not just be blocked from deleting one.

    Accepts the token two ways:
    - `Authorization: Bearer <token>` header -- every normal JSON API call.
    - `?token=<token>` query parameter -- the one exception is the
      decrypt-and-stream /uploads/{file_path} route (main.py): an <img
      src="..."> tag has no way to attach a custom header, so the frontend
      appends the token to the URL there instead. A query-string token is a
      real, if minor, exposure (it can end up in server access logs or a
      Referer header) -- acceptable here given the short token lifetime
      (ACCESS_TOKEN_EXPIRE_MINUTES) and that this is a decision-support demo,
      not a hardened production deployment; a real deployment should swap
      this for short-lived, per-resource signed URLs instead.
    """
    raw_token = token
    if authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer" and value:
            raw_token = value

    if not raw_token:
        raise HTTPException(status_code=401, detail="Not authenticated. Log in and retry with a valid session.")

    badge_id = decode_access_token(raw_token)
    if not badge_id:
        raise HTTPException(status_code=401, detail="Session expired or invalid. Please log in again.")

    officer = db.query(Officer).filter(Officer.badge_id == badge_id).first()
    if not officer or not officer.is_active:
        raise HTTPException(status_code=401, detail="Session expired or invalid. Please log in again.")

    return officer


# Re-export get_db
__all__ = ["get_db", "get_current_officer"]
