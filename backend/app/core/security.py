import hashlib
import re
import os
import uuid
import io
from pathlib import Path
from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError

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
