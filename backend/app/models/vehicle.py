import uuid
from sqlalchemy import String, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    battery_capacity_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    max_charge_rate_kw: Mapped[float] = mapped_column(Float, nullable=False)
    current_soc_percent: Mapped[float] = mapped_column(Float, default=50.0)
    target_soc_percent: Mapped[float] = mapped_column(Float, default=80.0)

    user = relationship("User", back_populates="vehicles")
    schedules = relationship("Schedule", back_populates="vehicle", cascade="all, delete-orphan")
    charging_sessions = relationship("ChargingSession", back_populates="vehicle", cascade="all, delete-orphan")
