from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict

from app.api.deps import get_db, get_current_officer
from app.models import Officer
from app.services.policy_service import get_policy, update_policy, PolicyValidationError

router = APIRouter(prefix="/settings", tags=["settings"])


class PolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    weight_mrz: float
    weight_tamper: float
    weight_face: float
    weight_consistency: float
    weight_watchlist: float
    threshold_low: float
    threshold_medium: float
    threshold_high: float


class PolicyUpdate(BaseModel):
    weight_mrz: float
    weight_tamper: float
    weight_face: float
    weight_consistency: float
    weight_watchlist: float
    threshold_low: float
    threshold_medium: float
    threshold_high: float


@router.get("/policy", response_model=PolicyOut)
def get_policy_settings(db: Session = Depends(get_db), _officer: Officer = Depends(get_current_officer)):
    """The risk engine's live weights/thresholds -- what the Settings page's
    sliders actually control."""
    return get_policy(db)


@router.post("/policy", response_model=PolicyOut)
def update_policy_settings(
    payload: PolicyUpdate,
    db: Session = Depends(get_db),
    _officer: Officer = Depends(get_current_officer),
):
    # Risk-engine weights/thresholds directly drive every case's
    # LOW/MEDIUM/HIGH/CRITICAL classification (see risk_engine.py) --
    # comparable in impact to case deletion or biometric purge, so this
    # requires real officer login the same as those two routes (see
    # app.api.deps.get_current_officer).
    #
    # The weights-sum-to-100% / ascending-thresholds invariant is enforced
    # inside update_policy itself (see policy_service.py) so it holds no
    # matter what calls it -- this just translates that into an HTTP error.
    try:
        return update_policy(db, **payload.model_dump())
    except PolicyValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
