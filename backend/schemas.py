from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class BusinessCreate(BaseModel):
    name: str
    owner: str
    state: str
    industry: str
    employee_count: int
    annual_turnover_inr: float
    registrations: List[str] = Field(default_factory=list)
    incorporation_date: Optional[str] = None
    business_type: Optional[str] = None  # proprietorship | partnership | pvt_ltd | llp


class BusinessUpdate(BaseModel):
    """All fields optional — partial updates only modify what's set."""
    name: Optional[str] = None
    owner: Optional[str] = None
    state: Optional[str] = None
    industry: Optional[str] = None
    employee_count: Optional[int] = None
    annual_turnover_inr: Optional[float] = None
    registrations: Optional[List[str]] = None
    incorporation_date: Optional[str] = None
    business_type: Optional[str] = None


class RippleCheckRequest(BaseModel):
    business_id: str
    regulation_change: Dict[str, Any]


class ApproveDraftRequest(BaseModel):
    notes: Optional[str] = None


class ConfirmObligationsRequest(BaseModel):
    keep_ids: List[str]
    due_dates: Dict[str, str] = Field(default_factory=dict)


class ChatDiscoverRequest(BaseModel):
    business_id: str
    messages: List[Dict[str, str]]
    business_facts: Dict[str, Any] = Field(default_factory=dict)
    summarise: bool = False


class CircularInterpretRequest(BaseModel):
    business_id: str
    circular_text: str
    circular_source: str = ""


class IngestCircularRequest(BaseModel):
    source: str
    text: str
