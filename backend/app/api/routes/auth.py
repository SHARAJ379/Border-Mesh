from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_officer
from app.core.security import verify_password, create_access_token
from app.models import Officer

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    badge_id: str
    password: str


class OfficerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    badge_id: str
    full_name: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    officer: OfficerOut


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """
    Real per-officer login -- replaces the old single shared OFFICER_API_KEY.
    Deliberately returns the same generic error for "no such badge_id" and
    "wrong password" (not "unknown user" vs. "wrong password" separately):
    distinguishing the two would let an attacker enumerate valid badge_ids.
    """
    officer = db.query(Officer).filter(Officer.badge_id == payload.badge_id).first()
    if not officer or not officer.is_active or not verify_password(payload.password, officer.password_hash):
        raise HTTPException(status_code=401, detail="Invalid badge ID or password.")

    token = create_access_token(officer.badge_id)
    return {"access_token": token, "officer": officer}


@router.get("/me", response_model=OfficerOut)
def get_me(current_officer: Officer = Depends(get_current_officer)):
    """Lets the frontend restore a session on page reload (it has the token
    in localStorage but not the officer's display name) and double-checks
    the token is still valid without hitting any case data."""
    return current_officer
