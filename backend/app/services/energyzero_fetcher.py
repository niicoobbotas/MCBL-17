"""EnergyZero price source — real Dutch consumer electricity prices.

Adapted from the team's research script `Price extractor.py` (MCBL-17).
The EnergyZero API returns the dynamic day-ahead tariff that Dutch
consumers actually pay in EUR/kWh, *including* energy tax + BTW (VAT).

We convert to EUR/MWh on the way in so it shares the same storage unit
as the rest of the price pipeline (`Price.price_eur_per_mwh`).
"""
from datetime import datetime, timedelta, timezone

import httpx

ENERGYZERO_URL = "https://api.energyzero.nl/v1/energyprices"


async def fetch_energyzero_prices(date: datetime) -> list[dict]:
    """Fetch hourly consumer prices for a single day from EnergyZero.

    Args:
        date: Any datetime within the desired day (interpreted in UTC).

    Returns:
        List of dicts: {timestamp (UTC), price_area, price_eur_per_mwh}.
    """
    day = date.astimezone(timezone.utc) if date.tzinfo else date.replace(tzinfo=timezone.utc)
    start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1) - timedelta(seconds=1)

    params = {
        "fromDate": start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "tillDate": end.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "interval": 4,      # 4 = hourly
        "usageType": 1,     # 1 = electricity
        "inclBtw": "true",  # include VAT so it matches the real bill
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(ENERGYZERO_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    prices = []
    for entry in data.get("Prices", []):
        reading = entry.get("readingDate")
        price_kwh = entry.get("price")
        if reading is None or price_kwh is None:
            continue
        ts = datetime.fromisoformat(reading.replace("Z", "+00:00"))
        prices.append({
            # Store naive UTC to match the rest of the pipeline (DateTime column)
            "timestamp": ts.astimezone(timezone.utc).replace(tzinfo=None),
            "price_area": "NL",
            "price_eur_per_mwh": float(price_kwh) * 1000.0,  # EUR/kWh -> EUR/MWh
        })
    return prices
