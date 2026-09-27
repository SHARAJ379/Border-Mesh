"""
Tests for the security-hardening pass: real image-content validation on
upload (not just filename extension), and the demo-default-secret startup
guard. See app.core.security.validate_image_upload and
app.core.config.default_secrets_still_in_use.
"""
import io
import pytest
from fastapi import HTTPException
from PIL import Image

from app.core.security import validate_image_upload
from app.core import config as config_module


def _real_jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), "white").save(buf, format="JPEG")
    return buf.getvalue()


def test_validate_image_upload_accepts_a_genuine_jpeg():
    contents = _real_jpeg_bytes()
    # Must not raise.
    validate_image_upload("specimen.jpg", len(contents), contents)


def test_validate_image_upload_rejects_a_non_image_renamed_to_jpg():
    """
    The exact gap this was added for: before this fix, only the filename
    extension and byte count were checked -- any file (a script, an HTML/
    SVG polyglot, plain garbage) renamed to end in ".jpg" was accepted and
    written straight to disk, then handed to OCR/tamper/face analysis as if
    it were real image data.
    """
    fake_contents = b"not a real image, just bytes claiming to be one" * 5

    with pytest.raises(HTTPException) as exc_info:
        validate_image_upload("payload.jpg", len(fake_contents), fake_contents)
    assert exc_info.value.status_code == 400


def test_validate_image_upload_rejects_empty_file():
    with pytest.raises(HTTPException) as exc_info:
        validate_image_upload("empty.jpg", 0, b"")
    assert exc_info.value.status_code == 400


def test_validate_image_upload_still_enforces_extension_allowlist():
    contents = _real_jpeg_bytes()
    with pytest.raises(HTTPException) as exc_info:
        validate_image_upload("specimen.exe", len(contents), contents)
    assert exc_info.value.status_code == 400


def test_validate_image_upload_still_enforces_size_limit():
    contents = _real_jpeg_bytes()
    with pytest.raises(HTTPException) as exc_info:
        validate_image_upload("specimen.jpg", 999_999_999, contents)
    assert exc_info.value.status_code == 400


def test_default_secrets_still_in_use_flags_the_checked_in_demo_values(monkeypatch):
    monkeypatch.setattr(config_module.settings, "SECRET_KEY", config_module._DEFAULT_SECRET_KEY)
    monkeypatch.setattr(config_module.settings, "OFFICER_API_KEY", config_module._DEFAULT_OFFICER_API_KEY)
    monkeypatch.setattr(config_module.settings, "BIOMETRIC_ENCRYPTION_KEY", config_module._DEFAULT_BIOMETRIC_ENCRYPTION_KEY)

    offenders = config_module.default_secrets_still_in_use()
    assert set(offenders) == {"SECRET_KEY", "OFFICER_API_KEY", "BIOMETRIC_ENCRYPTION_KEY"}


def test_default_secrets_still_in_use_is_clean_once_all_are_overridden(monkeypatch):
    monkeypatch.setattr(config_module.settings, "SECRET_KEY", "a-real-override-value")
    monkeypatch.setattr(config_module.settings, "OFFICER_API_KEY", "another-real-override-value")
    monkeypatch.setattr(config_module.settings, "BIOMETRIC_ENCRYPTION_KEY", "yet-another-real-override-value")

    assert config_module.default_secrets_still_in_use() == []
