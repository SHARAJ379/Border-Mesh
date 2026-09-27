import logging
import mimetypes
import os
import sys
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings, default_secrets_still_in_use

logger = logging.getLogger("bordermesh.startup")
from app.core.database import Base, engine, SessionLocal
from app.core.encryption import decrypt_bytes
from app.api.routes import health, screening, cases, dashboard, demo, audit, settings as settings_routes, compliance

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes database tables and auto-seeds synthetic cases if empty."""
    offenders = default_secrets_still_in_use()
    if offenders:
        message = (
            f"[BorderMesh] Using checked-in DEMO default value(s) for: {', '.join(offenders)}. "
            "These are publicly known (they're in the repo's own source) and provide no real "
            "security -- override via environment variables before any non-demo use."
        )
        if settings.ENVIRONMENT != "development":
            # A non-development ENVIRONMENT is this app's own explicit claim
            # that this isn't just someone's local demo run -- refuse to
            # boot with a publicly-known secret in that case rather than
            # only logging a warning nobody may read before traffic starts.
            raise RuntimeError(
                message + f" Refusing to start with ENVIRONMENT='{settings.ENVIRONMENT}'."
            )
        logger.warning(message)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        from app.services.watchlist_service import ensure_seeded
        ensure_seeded(db)

        from app.models import Case
        case_count = db.query(Case).count()
        if case_count == 0:
            print("[BorderMesh] Empty database detected. Seeding initial synthetic screening cases...")
            # `scripts/` lives alongside `backend/`, not inside it, so it isn't on
            # sys.path when running via `--app-dir backend` / PYTHONPATH=backend
            # (locally) or WORKDIR /app (Docker). Add the repo root explicitly.
            repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            if repo_root not in sys.path:
                sys.path.insert(0, repo_root)
            from scripts.seed_cases import seed_initial_cases
            seed_initial_cases(db)
            print("[BorderMesh] Seed completed successfully.")
    except Exception as e:
        print(f"[BorderMesh] Startup seed note: {e}")
    finally:
        db.close()
    yield

app = FastAPI(
    title="BorderMesh API",
    description=(
        "AI-Based Fake Identity & Document Screening System — SIH 2026 Prototype.\n\n"
        "Integrates OCR, ICAO 9303 MRZ Checksums, Multi-Signal Tamper AI (ELA, Splicing, Seams), "
        "Biometric Face Verification, and an Explainable Risk Engine for border immigration officers."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS configuration. allow_credentials is False because nothing in this
# app uses cookies or session auth -- every request is a plain, credential-
# free fetch -- and keeping it True alongside any future loosening of
# ALLOWED_ORIGINS would silently re-open the origin-reflection issue this
# was fixed for.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Every file under UPLOAD_DIR (document scans, live face captures, face
# crops, tamper heatmaps) is encrypted at rest -- see app.core.encryption --
# so this can no longer be a raw StaticFiles mount serving bytes straight
# off disk. This route decrypts in memory and streams the plaintext back,
# at the exact same URL shape (`/uploads/<subdir>/<filename>`) the old
# mount used, so no frontend code needed to change.
uploads_path = os.path.abspath(settings.UPLOAD_DIR)
os.makedirs(uploads_path, exist_ok=True)


@app.get("/uploads/{file_path:path}")
def serve_encrypted_upload(file_path: str):
    requested_path = os.path.normpath(os.path.join(uploads_path, file_path))
    # Path-traversal guard StaticFiles handled for free -- a "../" segment
    # must never resolve outside uploads_path.
    if os.path.commonpath([requested_path, uploads_path]) != uploads_path:
        raise HTTPException(status_code=404, detail="Not found.")
    if not os.path.isfile(requested_path):
        raise HTTPException(status_code=404, detail="Not found.")

    with open(requested_path, "rb") as f:
        ciphertext = f.read()
    plaintext = decrypt_bytes(ciphertext)

    media_type, _ = mimetypes.guess_type(requested_path)
    return Response(content=plaintext, media_type=media_type or "application/octet-stream")

# Standalone public case-verification page (plain HTML/JS, no React/build step,
# no login) -- backed by the no-auth GET /api/audit/anchor-proof/{case_number}
# endpoint. html=True serves static/verify/index.html at both /verify and
# /verify/, and lets ?case=... be read client-side without any server routing.
verify_page_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "static", "verify"))
app.mount("/verify", StaticFiles(directory=verify_page_path, html=True), name="verify-page")

# Include Routers
app.include_router(health.router, prefix=settings.API_V1_STR)
app.include_router(screening.router, prefix=settings.API_V1_STR)
app.include_router(cases.router, prefix=settings.API_V1_STR)
app.include_router(dashboard.router, prefix=settings.API_V1_STR)
app.include_router(demo.router, prefix=settings.API_V1_STR)
app.include_router(audit.router, prefix=settings.API_V1_STR)
app.include_router(settings_routes.router, prefix=settings.API_V1_STR)
app.include_router(compliance.router, prefix=settings.API_V1_STR)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
