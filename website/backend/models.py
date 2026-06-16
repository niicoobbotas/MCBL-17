from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from database import Base
import datetime


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    address = Column(String, nullable=True)
    supplier = Column(String, default="eneco")
    plugin_time = Column(Integer, default=18)
    deadline = Column(Integer, default=7)
    ere_enabled = Column(Boolean, default=True)
    solar_enabled = Column(Boolean, default=False)
    solar_kwp = Column(Float, default=4.0)
    # saver = β 0.0 (cost only) | balance = β 0.5 (default) | eco = β 1.0 (max grid)
    charging_profile = Column(String, default="balance")
    gdpr_consent = Column(Boolean, default=False)
    gdpr_consent_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    vehicles = relationship("Vehicle", back_populates="owner", cascade="all, delete-orphan")
    sessions = relationship("ChargingSession", back_populates="user", cascade="all, delete-orphan")


class Vehicle(Base):
    __tablename__ = "vehicles"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    brand = Column(String, nullable=True)
    year = Column(Integer, nullable=True)
    model_name = Column(String, nullable=False)
    battery_kwh = Column(Float, nullable=False)
    wltp_km = Column(Integer, nullable=False)
    ac_power_kw = Column(Float, nullable=False)
    efficiency_kwh_100km = Column(Float, nullable=False)
    is_default = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    owner = relationship("User", back_populates="vehicles")


class ChargingSession(Base):
    __tablename__ = "charging_sessions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=True)
    session_date = Column(DateTime, default=datetime.datetime.utcnow)
    kwh_delivered = Column(Float, nullable=False)
    cost_eur = Column(Float, nullable=False)
    savings_vs_uncontrolled = Column(Float, default=0.0)
    savings_vs_fixed = Column(Float, default=0.0)
    policy = Column(String, default="smart")
    plugin_hour = Column(Integer, nullable=False)
    deadline_hour = Column(Integer, nullable=False)
    supplier = Column(String, default="eneco")
    schedule_json = Column(Text, nullable=True)

    user = relationship("User", back_populates="sessions")
