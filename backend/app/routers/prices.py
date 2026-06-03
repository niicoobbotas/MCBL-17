from datetime import datetime, date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import settings
from app.schemas.price import PriceResponse
from app.services.price_fetcher import cache_prices, get_prices_for_range

router = APIRouter(prefix="/api/prices", tags=["prices"])


@router.get("/", response_model=list[PriceResponse])
async def get_prices(
    area: str = Query(default=None),
    date_str: str = Query(alias="date", default=None),
    db: AsyncSession = Depends(get_db),
):
    price_area = area or settings.nordpool_price_area
    target_date = datetime.strptime(date_str, "%Y-%m-%d") if date_str else datetime.utcnow()

    prices = await cache_prices(db, price_area, target_date)
    return prices


@router.get("/current", response_model=PriceResponse | None)
async def get_current_price(
    area: str = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    price_area = area or settings.nordpool_price_area
    now = datetime.utcnow()
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    next_hour = current_hour.replace(hour=current_hour.hour + 1) if current_hour.hour < 23 else current_hour

    prices = await get_prices_for_range(db, price_area, current_hour, next_hour)
    return prices[0] if prices else None
