"""
End-to-end tests for real per-officer authentication (app.api.routes.auth,
app.api.deps.get_current_officer) -- these deliberately do NOT use
test_api.py's dependency_overrides shortcut, since the whole point here is
to prove the real login -> JWT -> protected-route chain actually works,
not just that routes declare the dependency.

Uses its own TestClient/app instance (not test_api.py's shared one) so it
never touches that module's dependency override.
"""
import io

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.core.config import settings

_client_cm = TestClient(app)
client = _client_cm.__enter__()


def teardown_module(module):
    _client_cm.__exit__(None, None, None)


def test_login_with_the_seeded_demo_officer_succeeds():
    res = client.post("/api/auth/login", json={
        "badge_id": "OFFICER-DEMO-01",
        "password": settings.DEFAULT_OFFICER_PASSWORD,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["token_type"] == "bearer"
    assert data["officer"]["badge_id"] == "OFFICER-DEMO-01"
    assert isinstance(data["access_token"], str) and len(data["access_token"]) > 20


def test_login_with_wrong_password_is_rejected():
    res = client.post("/api/auth/login", json={
        "badge_id": "OFFICER-DEMO-01",
        "password": "definitely-the-wrong-password",
    })
    assert res.status_code == 401


def test_login_with_unknown_badge_id_is_rejected_the_same_way_as_wrong_password():
    """Same error/status for 'no such officer' and 'wrong password' -- a
    different response for each would let a caller enumerate valid
    badge_ids (see auth.py's login docstring)."""
    unknown_res = client.post("/api/auth/login", json={
        "badge_id": "NOT-A-REAL-BADGE",
        "password": "anything",
    })
    wrong_pw_res = client.post("/api/auth/login", json={
        "badge_id": "OFFICER-DEMO-01",
        "password": "also-not-right",
    })
    assert unknown_res.status_code == wrong_pw_res.status_code == 401
    assert unknown_res.json()["detail"] == wrong_pw_res.json()["detail"]


def test_protected_route_rejects_no_token_and_a_garbage_token():
    assert client.get("/api/cases").status_code == 401
    assert client.get("/api/cases", headers={"Authorization": "Bearer not-a-real-jwt"}).status_code == 401


def test_a_real_token_from_login_authenticates_a_protected_route():
    login_res = client.post("/api/auth/login", json={
        "badge_id": "OFFICER-DEMO-01",
        "password": settings.DEFAULT_OFFICER_PASSWORD,
    })
    token = login_res.json()["access_token"]

    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["badge_id"] == "OFFICER-DEMO-01"

    cases_res = client.get("/api/cases", headers={"Authorization": f"Bearer {token}"})
    assert cases_res.status_code == 200


def test_uploads_route_accepts_the_token_as_a_query_param_not_just_a_header():
    """
    The decrypt-and-stream /uploads/{file_path} route is the one route an
    <img src="..."> tag has to hit without a custom Authorization header --
    see get_current_officer's own docstring for why it also accepts
    `?token=`. Confirms both paths actually work against a real uploaded
    file, and that an unauthenticated request to it is rejected.
    """
    login_res = client.post("/api/auth/login", json={
        "badge_id": "OFFICER-DEMO-01",
        "password": settings.DEFAULT_OFFICER_PASSWORD,
    })
    token = login_res.json()["access_token"]

    buf = io.BytesIO()
    Image.new("RGB", (32, 32), "white").save(buf, format="JPEG")
    buf.seek(0)

    upload_res = client.post(
        "/api/screening/upload",
        files={"file": ("specimen.jpg", buf, "image/jpeg")},
        data={"document_type": "Passport", "country": "Unknown"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert upload_res.status_code == 200
    image_url = upload_res.json()["document_image_url"]

    assert client.get(image_url).status_code == 401  # no token at all
    assert client.get(f"{image_url}?token=garbage").status_code == 401
    assert client.get(f"{image_url}?token={token}").status_code == 200
    assert client.get(image_url, headers={"Authorization": f"Bearer {token}"}).status_code == 200
