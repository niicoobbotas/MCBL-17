import uuid
from pydantic import BaseModel
from app.models.charger import ChargerStatus


class ChargerCreate(BaseModel):
    name: str
    max_power_kw: float
    pi_address: str | None = None


class ChargerUpdate(BaseModel):
    name: str | None = None
    max_power_kw: float | None = None
    pi_address: str | None = None


class ChargerResponse(BaseModel):
    id: uuid.UUID
    name: str
    status: ChargerStatus
    pi_address: str | None
    max_power_kw: float

    class Config:
        from_attributes = True
