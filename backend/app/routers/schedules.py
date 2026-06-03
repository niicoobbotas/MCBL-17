import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.charger import Charger
from app.models.schedule import Schedule, ScheduleSlot, ScheduleStatus
from app.schemas.schedule import ScheduleCreate, ScheduleResponse
from app.utils.deps import get_current_user
from app.services.optimizer import compute_schedule
from app.services.price_fetcher import cache_prices
from app.config import settings

router = APIRouter(prefix="/api/schedules", tags=["schedules"])


@router.post("/", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    req: ScheduleCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify vehicle belongs to user
    v_result = await db.execute(
        select(Vehicle).where(Vehicle.id == req.vehicle_id, Vehicle.user_id == user.id)
    )
    vehicle = v_result.scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    # Verify charger belongs to user
    c_result = await db.execute(
        select(Charger).where(Charger.id == req.charger_id, Charger.user_id == user.id)
    )
    charger = c_result.scalar_one_or_none()
    if not charger:
        raise HTTPException(status_code=404, detail="Charger not found")

    # Fetch prices for the window (cache if needed)
    # Fetch day-by-day to cover multi-day windows
    current = req.available_from.replace(hour=0, minute=0, second=0, microsecond=0)
    end_day = req.needed_by.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    all_prices = []
    while current < end_day:
        day_prices = await cache_prices(db, settings.nordpool_price_area, current)
        all_prices.extend(day_prices)
        current += timedelta(days=1)

    # Run optimizer
    slots = compute_schedule(
        prices=all_prices,
        available_from=req.available_from,
        needed_by=req.needed_by,
        current_soc=vehicle.current_soc_percent,
        target_soc=vehicle.target_soc_percent,
        battery_capacity_kwh=vehicle.battery_capacity_kwh,
        max_charge_rate_kw=vehicle.max_charge_rate_kw,
        charger_max_kw=charger.max_power_kw,
        mode=req.optimization_mode,
    )

    # Persist schedule
    schedule = Schedule(
        vehicle_id=req.vehicle_id,
        charger_id=req.charger_id,
        available_from=req.available_from,
        needed_by=req.needed_by,
        optimization_mode=req.optimization_mode,
        status=ScheduleStatus.pending,
    )
    db.add(schedule)
    await db.flush()

    for slot in slots:
        db.add(ScheduleSlot(
            schedule_id=schedule.id,
            start_time=slot.start_time,
            end_time=slot.end_time,
            charge_rate_kw=slot.charge_rate_kw,
            estimated_cost=slot.estimated_cost,
            estimated_kwh=slot.estimated_kwh,
        ))

    await db.commit()

    # Reload with slots
    result = await db.execute(
        select(Schedule).options(selectinload(Schedule.slots)).where(Schedule.id == schedule.id)
    )
    return result.scalar_one()


@router.get("/", response_model=list[ScheduleResponse])
async def list_schedules(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Schedule)
        .join(Vehicle)
        .where(Vehicle.user_id == user.id)
        .options(selectinload(Schedule.slots))
        .order_by(Schedule.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(
    schedule_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Schedule)
        .join(Vehicle)
        .where(Schedule.id == schedule_id, Vehicle.user_id == user.id)
        .options(selectinload(Schedule.slots))
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return schedule


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_schedule(
    schedule_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Schedule)
        .join(Vehicle)
        .where(Schedule.id == schedule_id, Vehicle.user_id == user.id)
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    schedule.status = ScheduleStatus.cancelled
    await db.commit()
