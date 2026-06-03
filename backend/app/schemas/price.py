from datetime import datetime
from pydantic import BaseModel


class PriceResponse(BaseModel):
    timestamp: datetime
    price_area: str
    price_eur_per_mwh: float

    class Config:
        from_attributes = True


class DailySavings(BaseModel):
    date: str
    optimized_cost: float
    naive_cost: float
    savings: float


class SavingsSummary(BaseModel):
    total_savings: float
    total_optimized_cost: float
    total_naive_cost: float
    savings_percent: float
    daily: list[DailySavings]


class SessionResponse(BaseModel):
    id: str
    vehicle_name: str
    start_time: datetime
    end_time: datetime | None
    energy_kwh: float
    cost: float
    naive_cost: float
    savings: float

    class Config:
        from_attributes = True
