from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.charging_session import ChargingSession
from app.schemas.price import SavingsSummary, DailySavings, SessionResponse
from app.utils.deps import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/savings", response_model=SavingsSummary)
async def get_savings(
    period: str = Query(default="month"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.utcnow()
    if period == "week":
        start = now - timedelta(weeks=1)
    elif period == "month":
        start = now - timedelta(days=30)
    elif period == "year":
        start = now - timedelta(days=365)
    else:
        start = now - timedelta(days=30)

    result = await db.execute(
        select(ChargingSession)
        .join(Vehicle)
        .where(Vehicle.user_id == user.id, ChargingSession.start_time >= start)
        .order_by(ChargingSession.start_time)
    )
    sessions = result.scalars().all()

    total_optimized = sum(s.cost for s in sessions)
    total_naive = sum(s.naive_cost for s in sessions)
    total_savings = total_naive - total_optimized
    savings_pct = (total_savings / total_naive * 100) if total_naive > 0 else 0.0

    # Group by day
    daily_map: dict[str, DailySavings] = {}
    for s in sessions:
        day = s.start_time.strftime("%Y-%m-%d")
        if day not in daily_map:
            daily_map[day] = DailySavings(date=day, optimized_cost=0, naive_cost=0, savings=0)
        daily_map[day].optimized_cost += s.cost
        daily_map[day].naive_cost += s.naive_cost
        daily_map[day].savings += (s.naive_cost - s.cost)

    return SavingsSummary(
        total_savings=round(total_savings, 2),
        total_optimized_cost=round(total_optimized, 2),
        total_naive_cost=round(total_naive, 2),
        savings_percent=round(savings_pct, 1),
        daily=list(daily_map.values()),
    )


@router.get("/history", response_model=list[SessionResponse])
async def get_history(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChargingSession)
        .join(Vehicle)
        .where(Vehicle.user_id == user.id)
        .options(selectinload(ChargingSession.vehicle))
        .order_by(ChargingSession.start_time.desc())
        .limit(50)
    )
    sessions = result.scalars().all()

    return [
        SessionResponse(
            id=str(s.id),
            vehicle_name=s.vehicle.name,
            start_time=s.start_time,
            end_time=s.end_time,
            energy_kwh=s.energy_kwh,
            cost=s.cost,
            naive_cost=s.naive_cost,
            savings=round(s.naive_cost - s.cost, 2),
        )
        for s in sessions
    ]
