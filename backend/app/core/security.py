import hashlib
import re
import os
import uuid
import io
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import bcrypt
import jwt
from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError

from app.core.config import settings

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024 # 10 MB

# Pillow format names for each allowed extension -- checked against what
# Image.open() actually decoded the bytes as, not what the filename claims.
# A mismatch (e.g. an .svg, an HTML/script polyglot, or any non-image blob
# renamed to "x.jpg") is rejected here rather than trusted on extension
# alone.
_ALLOWED_PIL_FORMATS = {"JPEG", "PNG", "WEBP"}

def hash_identifier(identifier: str) -> str:
    """Hashes a document number or sensitive identity attribute using SHA-256 for privacy."""
    if not identifier:
        return ""
    clean = re.sub(r"[^A-Za-z0-9]", "", identifier).upper()
    return hashlib.sha256(clean.encode("utf-8")).hexdigest()

def sanitize_filename(filename: str) -> str:
    """Generates a secure, non-colliding filename preventing directory traversal attacks."""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        ext = ".jpg"
    return f"{uuid.uuid4().hex}{ext}"

def validate_image_upload(filename: str, file_size: int, contents: bytes = None):
    """
    Rejects the request unless the upload is both a plausibly-named and
    genuinely-decodable image, within the size limit.

    `contents` is optional only for backward compatibility with any other
    caller that hasn't been updated to pass the actual bytes yet -- every
    call site in this codebase (screening.py, demo.py's file-upload paths)
    does, since extension/size alone previously let any file renamed to
    ".jpg" (a script, an HTML/SVG polyglot, an executable) straight onto
    disk and into every later stage of the pipeline (OCR, tamper analysis,
    face detection) as if it were real image data.
    """
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file extension: {ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds maximum allowed limit of {MAX_FILE_SIZE // (1024*1024)}MB"
        )
    if file_size == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if contents is not None:
        try:
            with Image.open(io.BytesIO(contents)) as img:
                img.verify()  # structural check: catches truncated/corrupt data
            # verify() leaves the file object unusable for anything further
            # (Pillow's own documented behavior) -- re-open on a fresh
            # stream to read the format it actually decoded as.
            with Image.open(io.BytesIO(contents)) as img:
                detected_format = img.format
        except (UnidentifiedImageError, OSError, ValueError):
            raise HTTPException(
                status_code=400,
                detail="Uploaded file is not a valid, decodable image."
            )
        if detected_format not in _ALLOWED_PIL_FORMATS:
            raise HTTPException(
                status_code=400,
                detail=f"Uploaded file's actual content ({detected_format}) does not match an allowed image type."
            )


# --- Officer authentication (password hashing + JWT) -----------------------
# Replaces the old single shared OFFICER_API_KEY (see config.py's own
# comment on ACCESS_TOKEN_EXPIRE_MINUTES) with real per-officer login.

JWT_ALGORITHM = "HS256"


def hash_password(plain_password: str) -> str:
    """bcrypt, not a faster general-purpose hash (SHA-256 etc.) -- bcrypt's
    deliberate slowness and built-in per-hash salt are exactly what a
    password hash needs and a generic hash doesn't provide; hash_identifier
    above is for document numbers (needs to be fast and must not be
    salted, since it's used as a lookup/index key), a completely different
    requirement from a credential."""
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # Malformed/legacy hash -- fail closed, not a 500.
        return False


def create_access_token(badge_id: str) -> str:
    """Signs a JWT with SECRET_KEY (HS256) carrying the officer's badge_id
    as `sub` and an expiry -- see app.api.deps.get_current_officer for the
    verifying half."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": badge_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[str]:
    """Returns the badge_id (`sub` claim) from a valid, unexpired token, or
    None for anything invalid/expired/malformed -- callers turn None into
    a 401, never an exception bubbling out of a dependency."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    return payload.get("sub")
