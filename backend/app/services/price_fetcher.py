from datetime import datetime, timedelta
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.config import settings
from app.models.price import Price
from app.services.energyzero_fetcher import fetch_energyzero_prices


NORDPOOL_DAY_AHEAD_URL = "https://dataportal-api.nordpoolgroup.com/api/DayAheadPrices"


async def fetch_prices(area: str, date: datetime) -> list[dict]:
    """Fetch raw prices for a day from the configured source.

    EnergyZero gives real Dutch consumer prices (incl. BTW); Nordpool gives
    wholesale day-ahead prices. Both return EUR/MWh dicts.
    """
    if settings.price_source == "energyzero":
        return await fetch_energyzero_prices(date)
    return await fetch_nordpool_prices(area, date)


async def fetch_nordpool_prices(area: str, date: datetime) -> list[dict]:
    """Fetch day-ahead prices from Nordpool for a given area and date."""
    date_str = date.strftime("%Y-%m-%d")
    params = {
        "date": date_str,
        "market": "DayAhead",
        "deliveryArea": area,
        "currency": "EUR",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(NORDPOOL_DAY_AHEAD_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    prices = []
    for row in data.get("multiAreaEntries", []):
        delivery_start = row.get("deliveryStart")
        entry_prices = row.get("entryPerArea", {})
        price_value = entry_prices.get(area)
        if delivery_start is not None and price_value is not None:
            prices.append({
                "timestamp": datetime.fromisoformat(delivery_start.replace("Z", "+00:00")),
                "price_area": area,
                "price_eur_per_mwh": float(price_value),
            })
    return prices


async def cache_prices(db: AsyncSession, area: str, date: datetime) -> list[Price]:
    """Fetch prices from Nordpool and cache in DB. Returns cached prices."""
    day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    # Check if already cached
    result = await db.execute(
        select(Price).where(
            and_(
                Price.price_area == area,
                Price.timestamp >= day_start,
                Price.timestamp < day_end,
            )
        ).order_by(Price.timestamp)
    )
    existing = result.scalars().all()
    if len(existing) >= 23:  # Most of a day is cached
        return list(existing)

    # Fetch and store
    raw_prices = await fetch_prices(area, date)
    price_objects = []
    for p in raw_prices:
        price = Price(
            timestamp=p["timestamp"],
            price_area=p["price_area"],
            price_eur_per_mwh=p["price_eur_per_mwh"],
            fetched_at=datetime.utcnow(),
        )
        db.add(price)
        price_objects.append(price)

    await db.commit()
    return price_objects


async def get_prices_for_range(
    db: AsyncSession, area: str, start: datetime, end: datetime
) -> list[Price]:
    """Get cached prices for a time range."""
    result = await db.execute(
        select(Price).where(
            and_(
                Price.price_area == area,
                Price.timestamp >= start,
                Price.timestamp < end,
            )
        ).order_by(Price.timestamp)
    )
    return list(result.scalars().all())
