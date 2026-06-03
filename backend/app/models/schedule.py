import uuid
from datetime import datetime
import enum

from sqlalchemy import String, Float, ForeignKey, DateTime, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class OptimizationMode(str, enum.Enum):
    price = "price"
    battery_life = "battery_life"
    smart = "smart"  # grid-aware: cost + congestion (CACCS, see optimizer.py)


class ScheduleStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    completed = "completed"
    cancelled = "cancelled"


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=False)
    charger_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chargers.id"), nullable=False)
    available_from: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    needed_by: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    optimization_mode: Mapped[OptimizationMode] = mapped_column(SAEnum(OptimizationMode), nullable=False)
    status: Mapped[ScheduleStatus] = mapped_column(SAEnum(ScheduleStatus), default=ScheduleStatus.pending)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    vehicle = relationship("Vehicle", back_populates="schedules")
    charger = relationship("Charger", back_populates="schedules")
    slots = relationship("ScheduleSlot", back_populates="schedule", cascade="all, delete-orphan")
    charging_sessions = relationship("ChargingSession", back_populates="schedule")


class ScheduleSlot(Base):
    __tablename__ = "schedule_slots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    schedule_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("schedules.id"), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    charge_rate_kw: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_cost: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_kwh: Mapped[float] = mapped_column(Float, nullable=False)

    schedule = relationship("Schedule", back_populates="slots")
