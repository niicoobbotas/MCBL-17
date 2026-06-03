import uuid
from sqlalchemy import String, Float, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.database import Base


class ChargerStatus(str, enum.Enum):
    idle = "idle"
    charging = "charging"
    offline = "offline"


class Charger(Base):
    __tablename__ = "chargers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[ChargerStatus] = mapped_column(SAEnum(ChargerStatus), default=ChargerStatus.idle)
    pi_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    max_power_kw: Mapped[float] = mapped_column(Float, nullable=False)

    user = relationship("User", back_populates="chargers")
    schedules = relationship("Schedule", back_populates="charger", cascade="all, delete-orphan")
    charging_sessions = relationship("ChargingSession", back_populates="charger", cascade="all, delete-orphan")
