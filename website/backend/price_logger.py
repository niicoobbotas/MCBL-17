"""
Daily price logger — NL day-ahead electricity prices for Eindhoven CACCS.

Fetches actual prices from EnergyZero (free, no API key) and writes daily files:
  live_prices/YYYY-MM-DD.json           — actual confirmed prices
  live_prices/YYYY-MM-DD_forecast.json  — forecast (overwritten when actuals arrive)

EnergyZero publishes next-day prices around 14:00-15:00 CET every day.
Run this script once in the morning (to seed today) and once in the afternoon
(to pick up tomorrow's newly-published prices). A simple cron entry:

  0 6,15 * * * python /path/to/price_logger.py

Or run manually:
  python price_logger.py               # update today + 3 days ahead
  python price_logger.py --days 5      # extend forecast window
  python price_logger.py --force       # re-fetch even if file exists
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path
from typing import Optional

try:
    import httpx as _http
    HAS_HTTP = True
except ImportError:
    try:
        import requests as _http  # type: ignore
        HAS_HTTP = True
    except ImportError:
        _http = None  # type: ignore
        HAS_HTTP = False

HERE = Path(__file__).parent
LIVE_DIR = HERE / "live_prices"

# Mean 2024 NL day-ahead hourly profile (EUR/MWh) — must match caccs.py HOURLY_WHOLESALE_MWH
# Computed from Ember Netherlands.csv genuine days only (broadcast days excluded).
HOURLY_MEAN = [
    76.0, 70.4, 67.3, 64.5, 64.2, 68.4, 81.3, 94.7,
    96.2, 82.8, 68.4, 57.0, 48.5, 43.6, 45.0, 54.3,
    69.1, 92.3, 108.5, 118.1, 115.0, 99.5, 89.8, 79.8,
]

# Seasonal scaling so forecast accounts for winter/summer price swings
_MONTH_FACTOR = [1.15, 1.10, 1.00, 0.90, 0.80, 0.75, 0.70, 0.75, 0.85, 0.95, 1.05, 1.20]
# Weekends have slightly lower industrial demand
_DOW_FACTOR = {5: 0.88, 6: 0.88}

ENERGYZERO_URL = "https://api.energyzero.nl/v1/energyprices"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
EHV_LAT, EHV_LON = 51.44, 5.48  # Eindhoven


def _local_now() -> datetime.datetime:
    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo("Europe/Amsterdam")
    except ImportError:
        tz = datetime.timezone(datetime.timedelta(hours=2))
    return datetime.datetime.now(tz)


def _get(url: str, params: dict, timeout: int = 15) -> dict:
    """GET wrapper supporting both httpx and requests."""
    resp = _http.get(url, params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def fetch_energyzero(date: datetime.date) -> Optional[list[float]]:
    """
    Fetch 24 hourly prices (EUR/MWh) from EnergyZero for the given date.
    Returns None if the day's prices are not yet published or on any error.
    EnergyZero returns EUR/kWh; we convert to EUR/MWh to match ENTSO-E convention.
    """
    if not HAS_HTTP:
        return None
    try:
        utc = datetime.timezone.utc
        from_dt = datetime.datetime.combine(date, datetime.time(0), tzinfo=utc)
        till_dt = datetime.datetime.combine(date, datetime.time(23, 59, 59), tzinfo=utc)
        data = _get(ENERGYZERO_URL, {
            "fromDate": from_dt.isoformat(),
            "tillDate": till_dt.isoformat(),
            "interval": 4,
            "usageType": 1,
            "inclBtw": "false",
        })
        raw = data.get("Prices", [])
        if len(raw) < 20:
            return None
        prices = [float(p.get("price", 0)) * 1000 for p in raw[:24]]
        while len(prices) < 24:
            prices.append(prices[-1])
        return [round(p, 2) for p in prices[:24]]
    except Exception as exc:
        print(f"  EnergyZero error ({date}): {exc}", file=sys.stderr)
        return None


def fetch_weather(date: datetime.date) -> Optional[dict]:
    """
    Fetch 24 hourly weather slots from Open-Meteo for Eindhoven (free, no key).
    Returns None on error or if date is out of the 5-day forecast window.
    """
    if not HAS_HTTP:
        return None
    try:
        today = datetime.date.today()
        days_ahead = (date - today).days
        if not (-2 <= days_ahead <= 5):
            return None
        data = _get(OPEN_METEO_URL, {
            "latitude": EHV_LAT,
            "longitude": EHV_LON,
            "hourly": "temperature_2m,windspeed_10m,direct_radiation,cloud_cover",
            "forecast_days": max(1, days_ahead + 1),
            "past_days": max(0, -days_ahead),
            "timezone": "Europe/Amsterdam",
        })
        hourly = data["hourly"]
        target = date.isoformat()
        idx = [i for i, t in enumerate(hourly["time"]) if t.startswith(target)][:24]
        if len(idx) < 24:
            return None
        return {k: [hourly[k][i] for i in idx]
                for k in ("temperature_2m", "windspeed_10m", "direct_radiation", "cloud_cover")}
    except Exception as exc:
        print(f"  Open-Meteo error ({date}): {exc}", file=sys.stderr)
        return None


def statistical_forecast(date: datetime.date, weather: Optional[dict] = None) -> list[float]:
    """
    Statistical price forecast: seasonal/weekday-adjusted profile + weather offsets.
    Wind and solar reduce prices (more renewable supply); temperature extremes raise them.
    """
    mf = _MONTH_FACTOR[date.month - 1]
    df = _DOW_FACTOR.get(date.weekday(), 1.0)
    prices = []
    for h in range(24):
        price = HOURLY_MEAN[h] * mf * df
        if weather:
            wind = weather["windspeed_10m"][h]
            solar = weather["direct_radiation"][h]
            temp = weather["temperature_2m"][h]
            price += -wind * 0.8            # wind oversupply discount
            price += -solar * 0.04          # solar oversupply discount
            price += abs(temp - 16) * 0.8  # heating/cooling demand premium
        prices.append(round(max(0.0, price), 2))
    return prices


def _actual_path(date: datetime.date) -> Path:
    return LIVE_DIR / f"{date.isoformat()}.json"


def _forecast_path(date: datetime.date) -> Path:
    return LIVE_DIR / f"{date.isoformat()}_forecast.json"


def _write(date: datetime.date, prices: list[float], is_forecast: bool, source: str) -> Path:
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    path = _forecast_path(date) if is_forecast else _actual_path(date)
    # When writing actual, delete any existing forecast file for that date
    if not is_forecast:
        fp = _forecast_path(date)
        if fp.exists():
            fp.unlink()
            print(f"  Replaced forecast → actual: {path.name}")
    payload = {
        "date": date.isoformat(),
        "source": source,
        "is_forecast": is_forecast,
        "fetched_at": _local_now().isoformat(),
        "prices_eur_mwh": prices,
    }
    path.write_text(json.dumps(payload, indent=2))
    return path


def update_date(date: datetime.date, force: bool = False) -> str:
    """
    Ensure prices exist for the given date. Tries actual first, then forecast.
    Skips writing if an actual file already exists and force=False.
    Always refreshes forecast files (they improve as the date approaches).
    """
    actual = _actual_path(date)
    if actual.exists() and not force:
        return f"{date}: actual on disk — skipped"

    prices = fetch_energyzero(date)
    if prices is not None:
        path = _write(date, prices, is_forecast=False, source="energyzero")
        return f"{date}: actual fetched from EnergyZero → {path.name}"

    # No confirmed prices yet — write/refresh forecast
    weather = fetch_weather(date)
    prices = statistical_forecast(date, weather)
    source = "statistical+weather" if weather else "statistical_profile"
    path = _write(date, prices, is_forecast=True, source=source)
    return f"{date}: forecast written ({source}) → {path.name}"


def run(days_ahead: int = 3, force: bool = False) -> None:
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    today = _local_now().date()
    print(f"Price logger — base date {today} — updating {1 + days_ahead} day(s)")
    for offset in range(days_ahead + 1):
        date = today + datetime.timedelta(days=offset)
        # Forecast files are always refreshed (better weather data as date approaches)
        do_force = force or (offset > 0 and _forecast_path(date).exists())
        msg = update_date(date, force=do_force)
        print(f"  {msg}")
    print("Done.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="NL day-ahead price logger")
    ap.add_argument("--date", help="Single date YYYY-MM-DD to update")
    ap.add_argument("--days", type=int, default=3, help="Days ahead to forecast (default 3)")
    ap.add_argument("--force", action="store_true", help="Overwrite existing files")
    args = ap.parse_args()

    if not HAS_HTTP:
        print("ERROR: pip install httpx  (or requests)", file=sys.stderr)
        sys.exit(1)

    if args.date:
        date = datetime.date.fromisoformat(args.date)
        print(update_date(date, force=args.force))
    else:
        run(days_ahead=args.days, force=args.force)
