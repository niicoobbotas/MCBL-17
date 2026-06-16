from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


class UserCreate(BaseModel):
    email: EmailStr
    name: str
    password: str
    supplier: str = "eneco"
    charging_profile: str = "balance"
    gdpr_consent: bool = False


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    supplier: Optional[str] = None
    plugin_time: Optional[int] = None
    deadline: Optional[int] = None
    ere_enabled: Optional[bool] = None
    solar_enabled: Optional[bool] = None
    solar_kwp: Optional[float] = None
    charging_profile: Optional[str] = None


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    address: Optional[str] = None
    supplier: str
    plugin_time: int
    deadline: int
    ere_enabled: bool
    solar_enabled: bool
    solar_kwp: float
    charging_profile: str
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserOut


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class VehicleCreate(BaseModel):
    model_name: str
    brand: Optional[str] = None
    year: Optional[int] = None
    battery_kwh: float
    wltp_km: int
    ac_power_kw: float
    efficiency_kwh_100km: float
    is_default: bool = True


class VehicleUpdate(BaseModel):
    is_default: Optional[bool] = None
    model_name: Optional[str] = None


class VehicleOut(BaseModel):
    id: int
    model_name: str
    brand: Optional[str] = None
    year: Optional[int] = None
    battery_kwh: float
    wltp_km: int
    ac_power_kw: float
    efficiency_kwh_100km: float
    is_default: bool

    class Config:
        from_attributes = True


class CACCSRequest(BaseModel):
    energy_kwh: float
    pmax_kw: float
    plugin_hour: int
    deadline_hour: int
    supplier: str = "eneco"
    beta: float = 0.5
    eta: float = 0.92


class ScheduleSlot(BaseModel):
    hour: int
    slot: int
    price: float
    load: float
    uncontrolled_kw: float
    price_only_kw: float
    smart_kw: float


class CACCSResult(BaseModel):
    energy_kwh: float
    window_hours: int
    plugin_hour: int
    deadline_hour: int
    costs: dict
    savings: dict
    schedule: List[ScheduleSlot]
    peak_drop_pct: float


class SessionCreate(BaseModel):
    vehicle_id: Optional[int] = None
    kwh_delivered: float
    cost_eur: float
    savings_vs_uncontrolled: float = 0.0
    savings_vs_fixed: float = 0.0
    policy: str = "smart"
    plugin_hour: int
    deadline_hour: int
    supplier: str = "eneco"
    schedule_json: Optional[str] = None


class SessionOut(SessionCreate):
    id: int
    user_id: int
    session_date: datetime

    class Config:
        from_attributes = True


class MonthlyBill(BaseModel):
    month: str
    total_kwh: float
    total_cost: float
    total_savings_vs_fixed: float
    session_count: int
