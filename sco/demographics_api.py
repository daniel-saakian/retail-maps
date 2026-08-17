from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from sco.pull_demographics import profile_address

router = APIRouter()

AVAILABLE_RADII = [1,2,3,5,7,10]

class DemographicsRequest(BaseModel):
    address:str
    radii: list[float]

class RingProfile(BaseModel):
    population: int
    daytime_population: int
    median_age: float | None = None
    white_pct: float | None = None
    black_pct: float | None = None
    hispanic_pct: float | None = None
    asian_pct: float | None = None
    employee_count: int
    white_collar_pct: int
    white_collar_pct: float | None = None
    blue_collar_pct: float | None = None
    median_hh_income: int | None = None
    hh_discretionary_spend: int | None = None
    hh_dining_spend: int | None = None
    n_block_groups: int

class DemographicsResponse(BaseModel):
    address: str
    lat: float
    lon: float
    renter_pct: float | None = None
    wfh_pct: float | None = None
    rings: dict[str, RingProfile]

from api import require_auth

@router.post("/api/demographics", response_model=DemographicsResponse)
def get_demographics(req: DemographicsRequest, user = Depends(require_auth)):
    if not req.address.strip():
        raise HTTPException(400, "address is required")
    radii = [r for r in req.radii if r > 0]
    if not radii:
        raise HTTPException(400, "at least one radius required")
    try:
        result = profile_address(req.address.strip(), radii)
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"Demographics pull failed: {e}")

    result["rings"] = {str(k): v for k, v in result["rings"].items()}
    return result