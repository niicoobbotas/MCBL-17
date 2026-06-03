import uuid
from datetime import datetime
from pydantic import BaseModel
from app.models.schedule import OptimizationMode, ScheduleStatus


class ScheduleCreate(BaseModel):
    vehicle_id: uuid.UUID
    charger_id: uuid.UUID
    available_from: datetime
    needed_by: datetime
    optimization_mode: OptimizationMode


class ScheduleSlotResponse(BaseModel):
    id: uuid.UUID
    start_time: datetime
    end_time: datetime
    charge_rate_kw: float
    estimated_cost: float
    estimated_kwh: float

    class Config:
        from_attributes = True


class ScheduleResponse(BaseModel):
    id: uuid.UUID
    vehicle_id: uuid.UUID
    charger_id: uuid.UUID
    available_from: datetime
    needed_by: datetime
    optimization_mode: OptimizationMode
    status: ScheduleStatus
    created_at: datetime
    slots: list[ScheduleSlotResponse] = []

    class Config:
        from_attributes = True
