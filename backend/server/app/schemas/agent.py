from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ContractType


class AgentBase(BaseModel):
    contract_type: ContractType
    base_hourly_rate: Decimal = Field(..., ge=0, description="Currency per hour")
    min_monthly_pay: Decimal = Field(0, ge=0, description="Statutory or contractual floor")
    max_monthly_pay: Optional[Decimal] = Field(None, ge=0, description="Cap; null if uncapped")
    weekly_contracted_hours: int = Field(40, ge=0, le=80, description="Typically 40 (FT), 20 (PT)")
    overtime_multiplier: Decimal = Field(Decimal("1.5"), ge=1)
    holiday_multiplier: Decimal = Field(Decimal("2.0"), ge=1)
    night_differential: Decimal = Field(Decimal("0.10"), ge=0)
    currency: str = Field("INR", min_length=3, max_length=3, description="ISO code")
    primary_site: Optional[str] = None


class AgentCreate(AgentBase):
    agent_id: str = Field(..., min_length=1)


class AgentUpdate(BaseModel):
    contract_type: Optional[ContractType] = None
    base_hourly_rate: Optional[Decimal] = None
    min_monthly_pay: Optional[Decimal] = None
    max_monthly_pay: Optional[Decimal] = None
    weekly_contracted_hours: Optional[int] = None
    overtime_multiplier: Optional[Decimal] = None
    holiday_multiplier: Optional[Decimal] = None
    night_differential: Optional[Decimal] = None
    currency: Optional[str] = None
    primary_site: Optional[str] = None


class AgentOut(AgentBase):
    model_config = ConfigDict(from_attributes=True)

    agent_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
