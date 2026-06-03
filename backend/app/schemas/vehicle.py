import uuid
from pydantic import BaseModel


class VehicleCreate(BaseModel):
    name: str
    battery_capacity_kwh: float
    max_charge_rate_kw: float
    current_soc_percent: float = 50.0
    target_soc_percent: float = 80.0


class VehicleUpdate(BaseModel):
    name: str | None = None
    battery_capacity_kwh: float | None = None
    max_charge_rate_kw: float | None = None
    current_soc_percent: float | None = None
    target_soc_percent: float | None = None


class VehicleResponse(BaseModel):
    id: uuid.UUID
    name: str
    battery_capacity_kwh: float
    max_charge_rate_kw: float
    current_soc_percent: float
    target_soc_percent: float

    class Config:
        from_attributes = True
