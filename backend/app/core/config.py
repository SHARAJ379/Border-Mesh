import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

# Root project directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

class Settings(BaseSettings):
    PROJECT_NAME: str = "BorderMesh — AI-Based Fake Identity & Document Screening System"
    API_V1_STR: str = "/api"
    ENVIRONMENT: str = "development"
    DEMO_MODE: bool = True
    
    # Database
    DATABASE_URL: str = "sqlite:///./border_mesh.db"
    
    # Uploads
    UPLOAD_DIR: str = str(BASE_DIR / "uploads")
    
    # Security
    SECRET_KEY: str = "bordermesh-sih2026-demo-secret-key-change-in-production"

    # Minimal API-key gate (X-API-Key header) required for the two most
    # sensitive, irreversible actions: permanent case deletion and the
    # biometric purge protocol. This is NOT a full auth/session system --
    # there is no per-user identity behind it, and since the frontend has to
    # embed this key to call those two endpoints, it's a shared secret
    # visible in the frontend bundle, not a real access-control boundary
    # against a determined attacker. What it does close: neither endpoint
    # can currently be triggered by a bare, credential-free request (e.g. a
    # stray script, a scanner, an unauthenticated curl) -- which is the gap
    # this was added to close before SIH judging. Revisit with real
    # per-officer auth before any non-demo deployment.
    OFFICER_API_KEY: str = "bordermesh-sih2026-officer-key-change-in-production"
    # No wildcard here: FastAPI/Starlette combines allow_credentials=True with
    # a "*" entry by reflecting whatever Origin header the request actually
    # sent, rather than a literal "*" -- which makes this list into a no-op
    # allowlist that accepts every origin with credentials attached. The
    # deployed frontend never needs a third-party origin anyway: nginx proxies
    # /api and /uploads under the same origin the page was loaded from, so
    # this list only matters for local dev tooling hitting the API directly.
    ALLOWED_ORIGINS: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    
    # Risk Engine Weights (Sum to 1.0)
    WEIGHT_MRZ: float = 0.25
    WEIGHT_TAMPER: float = 0.30
    WEIGHT_FACE: float = 0.30
    WEIGHT_CONSISTENCY: float = 0.10
    WEIGHT_WATCHLIST: float = 0.05
    
    # Risk Thresholds
    THRESHOLD_LOW: int = 24
    THRESHOLD_MEDIUM: int = 49
    THRESHOLD_HIGH: int = 74
    
    # Tamper AI -- per-region forensic-CNN reporting threshold (see
    # tamper_service.py's analyze(), which samples the portrait/center/mrz
    # regions independently). This is a REPORTING cut point only -- it
    # decides whether an individual region's CNN probability shows as its
    # own PASS or FAIL risk-check entry. It does NOT change
    # _aggregate_tamper_score's existing math, which still folds the raw
    # max(region_probs) into the overall tamper_risk exactly as before.
    # 0.5 is an unvalidated default, not a calibrated number -- there is no
    # labeled forged-document set behind it (see tamper_cnn's own
    # synthetic-only-training disclosure in SESSION_SUMMARY.md). Kept here,
    # named, so it's trivially findable/tunable once real tampered-sample
    # evaluation exists, instead of buried inline in tamper_service.py.
    TAMPER_REGION_THRESHOLD: float = 0.5

    # OCR Settings
    OCR_ENGINE: str = "pytesseract"
    # Empty by default: ocr_service.py only overrides pytesseract's tesseract_cmd
    # when this path actually exists, otherwise it falls back to pytesseract's
    # own PATH search -- which is what works across machines/OSes as long as
    # tesseract-ocr is installed. A hardcoded Homebrew-only default here
    # (previously "/opt/homebrew/bin/tesseract") silently only worked on
    # Apple Silicon Macs; set this explicitly if your tesseract binary isn't
    # already on PATH.
    TESSERACT_PATH: str = ""
    
    # Blockchain audit-chain anchoring (Ethereum Sepolia testnet) -- see
    # app/services/blockchain_anchor_service.py. On-demand only, triggered by
    # an officer action -- never called from AuditService.log()/verify_chain()'s
    # hot path, so an RPC outage or a drained faucet wallet can never affect
    # the core (already-working) local hash-chain audit trail.
    ANCHOR_RPC_URL: str = "https://ethereum-sepolia-rpc.publicnode.com"
    ANCHOR_CHAIN_ID: int = 11155111  # Ethereum Sepolia
    ANCHOR_NETWORK_NAME: str = "Ethereum Sepolia"
    ANCHOR_EXPLORER_TX_URL: str = "https://sepolia.etherscan.io/tx/"
    # Throwaway testnet-only wallet key -- holds no real-world value. Empty
    # by default, which disables the feature (see AnchorConfigurationError)
    # rather than silently failing on first use.
    ANCHOR_PRIVATE_KEY: str = ""

    # Symmetric key (Fernet/AES-128-CBC+HMAC) encrypting every biometric
    # artifact at rest -- document scans, live face captures, extracted
    # face crops, tamper heatmaps, and cross-case face embeddings (see
    # app.core.encryption). This is a real key from an environment
    # variable, not a hardcoded literal, but it is NOT production-grade key
    # management: one static key, no rotation, no envelope
    # encryption/per-record data keys, no HSM/KMS -- generated once via
    # `Fernet.generate_key()` the same way ANCHOR_PRIVATE_KEY/SECRET_KEY
    # already are for this demo. Override via env var in any real
    # deployment; this default exists purely so the app works out of the
    # box.
    BIOMETRIC_ENCRYPTION_KEY: str = "GIdlRJ4jkqQin6vgx8uDRtGQ2EXnGhbd_jIXGEjS848="

    # Privacy & Disclaimer
    DISCLAIMER_TEXT: str = (
        "PROTOTYPE SYSTEM — Smart India Hackathon 2026 Demo. "
        "Simulated watchlist and demo risk indicators. "
        "Requires human officer review; never makes definitive legal assertions."
    )
    
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

# Ensure required upload directories exist
os.makedirs(os.path.join(settings.UPLOAD_DIR, "documents"), exist_ok=True)
os.makedirs(os.path.join(settings.UPLOAD_DIR, "faces"), exist_ok=True)
os.makedirs(os.path.join(settings.UPLOAD_DIR, "heatmaps"), exist_ok=True)
os.makedirs(os.path.join(settings.UPLOAD_DIR, "crops"), exist_ok=True)

# Every one of these ships with a real, working default so the app runs
# out of the box for a demo -- see each field's own comment above for why
# that's an accepted tradeoff here. The one thing that must never happen
# silently is one of these checked-in demo values reaching a deployment
# that ENVIRONMENT itself claims is not "development": that's the exact
# gap that turns a known, disclosed demo credential into a real one.
# _DEFAULT_* below are this module's own literals duplicated intentionally
# (not imported back from the Settings field defaults) so this check keeps
# working even if a future edit changes a default -- it should start
# failing loudly then, not silently stop checking anything.
_DEFAULT_SECRET_KEY = "bordermesh-sih2026-demo-secret-key-change-in-production"
_DEFAULT_OFFICER_API_KEY = "bordermesh-sih2026-officer-key-change-in-production"
_DEFAULT_BIOMETRIC_ENCRYPTION_KEY = "GIdlRJ4jkqQin6vgx8uDRtGQ2EXnGhbd_jIXGEjS848="


def default_secrets_still_in_use() -> list[str]:
    """
    Returns the names of every setting still holding its checked-in demo
    value. Called from main.py's startup lifespan, which logs the result
    loudly (and, when ENVIRONMENT is not "development", refuses to start) --
    see that call site for the enforcement half of this. Pure/side-effect-
    free here so it can also be asserted against directly in tests.
    """
    offenders = []
    if settings.SECRET_KEY == _DEFAULT_SECRET_KEY:
        offenders.append("SECRET_KEY")
    if settings.OFFICER_API_KEY == _DEFAULT_OFFICER_API_KEY:
        offenders.append("OFFICER_API_KEY")
    if settings.BIOMETRIC_ENCRYPTION_KEY == _DEFAULT_BIOMETRIC_ENCRYPTION_KEY:
        offenders.append("BIOMETRIC_ENCRYPTION_KEY")
    return offenders
