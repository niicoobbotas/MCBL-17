import uuid
from datetime import datetime

from sqlalchemy import Float, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ChargingSession(Base):
    __tablename__ = "charging_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("schedules.id"), nullable=True)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=False)
    charger_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chargers.id"), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    energy_kwh: Mapped[float] = mapped_column(Float, default=0.0)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    avg_price_per_kwh: Mapped[float] = mapped_column(Float, default=0.0)
    naive_cost: Mapped[float] = mapped_column(Float, default=0.0)

    schedule = relationship("Schedule", back_populates="charging_sessions")
    vehicle = relationship("Vehicle", back_populates="charging_sessions")
    charger = relationship("Charger", back_populates="charging_sessions")
