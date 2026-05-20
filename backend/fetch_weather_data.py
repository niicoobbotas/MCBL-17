"""
fetch_weather_data.py
=====================
Downloads and saves historical hourly weather data for the Netherlands
(Eindhoven + 3 supplementary NL grid points) from Open-Meteo's ERA5 archive.

Coverage : 2015-01-01 → 2025-12-08  (matches Netherlands.csv)
Output   : weather_netherlands_2015_2025.parquet  (~2 MB)
           weather_netherlands_2015_2025.csv      (~5 MB, optional)

Run once:
    pip install requests pandas pyarrow tqdm
    python fetch_weather_data.py

After that, the Python backend reads the Parquet file — no re-download needed.
Daily top-ups use the live Open-Meteo Forecast API (also in this script).
"""

import time
import sys
from datetime import datetime, date, timedelta
from pathlib import Path

import requests
import pandas as pd

# ── Configuration ────────────────────────────────────────────────────────────

START_DATE = "2015-01-01"
END_DATE   = "2025-12-08"   # matches your Netherlands.csv

OUTPUT_PARQUET = Path("weather_netherlands_2015_2025.parquet")
OUTPUT_CSV     = Path("weather_netherlands_2015_2025.csv")   # set to None to skip

# Hourly variables to pull from ERA5 via Open-Meteo
# Chosen for electricity price modelling; see comments for rationale.
HOURLY_VARIABLES = [
    "temperature_2m",           # °C  – heating/cooling demand driver
    "windspeed_10m",            # m/s – standard meteorological height
    "windspeed_100m",           # m/s – turbine hub-height, better for wind power
    "winddirection_10m",        # °   – North Sea SW wind = high NL generation
    "direct_radiation",         # W/m² – solar PV generation proxy
    "diffuse_radiation",        # W/m² – complements direct for flat panels
    "cloudcover",               # %   – correlated with solar & demand behaviour
    "precipitation",            # mm  – weak feature but correlated with cloud
    "pressure_msl",             # hPa – synoptic weather regime signal
    "relativehumidity_2m",      # %   – comfort-based cooling demand
]

# Sampling points across NL: Eindhoven + Rotterdam + Amsterdam + Groningen
# Area-averaging gives a national demand/supply signal, not just local
LOCATIONS = {
    "eindhoven":  {"lat": 51.44, "lon": 5.48},   # primary (Eindhoven load zone)
    "rotterdam":  {"lat": 51.92, "lon": 4.48},   # large industrial load
    "amsterdam":  {"lat": 52.37, "lon": 4.90},   # north Holland demand
    "groningen":  {"lat": 53.22, "lon": 6.57},   # north NL, near wind farms
}

BASE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# ── Helpers ──────────────────────────────────────────────────────────────────

def fetch_location(name: str, lat: float, lon: float,
                   start: str, end: str, retries: int = 3) -> pd.DataFrame:
    """
    Fetch hourly ERA5 weather from Open-Meteo for one location.
    Returns a DataFrame with a UTC DatetimeIndex.
    Column names are prefixed with the location name, e.g. 'eindhoven_temperature_2m'.
    """
    params = {
        "latitude":  lat,
        "longitude": lon,
        "start_date": start,
        "end_date":   end,
        "hourly":     ",".join(HOURLY_VARIABLES),
        "wind_speed_unit": "ms",       # metres per second
        "timezone":   "UTC",
    }

    for attempt in range(1, retries + 1):
        try:
            print(f"  [{name}] Fetching ERA5 {start} → {end} (attempt {attempt})…")
            resp = requests.get(BASE_URL, params=params, timeout=60)
            resp.raise_for_status()
            data = resp.json()

            df = pd.DataFrame(data["hourly"])
            df["time"] = pd.to_datetime(df["time"], utc=True)
            df = df.set_index("time")
            df.columns = [f"{name}_{c}" for c in df.columns]
            print(f"  [{name}] ✓  {len(df):,} rows, {df.shape[1]} variables")
            return df

        except requests.HTTPError as e:
            print(f"  [{name}] HTTP error: {e}  — waiting 10s…")
            time.sleep(10)
        except Exception as e:
            print(f"  [{name}] Error: {e}  — waiting 5s…")
            time.sleep(5)

    raise RuntimeError(f"Failed to fetch data for {name} after {retries} attempts")


def fetch_topup(name: str, lat: float, lon: float, past_days: int = 7) -> pd.DataFrame:
    """
    Fetch the most recent `past_days` days + 5-day forecast from the live
    Open-Meteo Forecast API. Used for daily top-up after the historical
    baseline is saved.
    """
    params = {
        "latitude":  lat,
        "longitude": lon,
        "hourly":    ",".join(HOURLY_VARIABLES),
        "past_days": past_days,
        "forecast_days": 5,
        "wind_speed_unit": "ms",
        "timezone": "UTC",
    }
    resp = requests.get(FORECAST_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    df = pd.DataFrame(data["hourly"])
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.set_index("time")
    df.columns = [f"{name}_{c}" for c in df.columns]
    return df


def add_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute derived features from raw weather that directly improve
    electricity price prediction:
      - national averages across all 4 NL locations
      - heating/cooling degree hours (base 15°C / 22°C)
      - wind ramp rate (3h change in wind speed → sudden drop = price spike)
      - clear-sky index (actual radiation / theoretical maximum)
      - hour, day-of-week, month, weekend flag (calendar features)
    """
    locs = list(LOCATIONS.keys())

    # ── National averages (area-weighted; equal weights here) ──────────────
    for var in HOURLY_VARIABLES:
        cols = [f"{loc}_{var}" for loc in locs if f"{loc}_{var}" in df.columns]
        if cols:
            df[f"nl_avg_{var}"] = df[cols].mean(axis=1)

    # ── Heating / Cooling degree-hours (base 15°C, 22°C) ──────────────────
    t = df["nl_avg_temperature_2m"]
    df["hdh"] = (15 - t).clip(lower=0)   # heating demand
    df["cdh"] = (t - 22).clip(lower=0)   # cooling demand

    # ── Wind ramp rate: 3-hour change in national average wind speed ───────
    df["wind_ramp_3h"] = df["nl_avg_windspeed_100m"].diff(3)

    # ── Clear-sky index (solar actual / max possible for that hour) ─────────
    # Theoretical max at 51.4°N: peak ~850 W/m² in June noon
    # Approximate by hour-of-day * monthly envelope
    hour = df.index.hour
    month = df.index.month
    # Simple clear-sky envelope (W/m²)
    max_rad = pd.Series(
        [max(0, 850 * max(0, (hour[i] - 5.5) * (18.5 - hour[i])) / 42.25
             * (0.6 + 0.4 * abs(month[i] - 6.5) / 5.5 * -1 + 0.4))
         for i in range(len(df))],
        index=df.index
    )
    df["clearsky_index"] = (df["nl_avg_direct_radiation"] / max_rad.clip(lower=10)).clip(0, 2)

    # ── Calendar features ──────────────────────────────────────────────────
    df["hour"]       = df.index.hour
    df["dayofweek"]  = df.index.dayofweek      # 0=Monday, 6=Sunday
    df["month"]      = df.index.month
    df["is_weekend"] = (df.index.dayofweek >= 5).astype(int)

    # Cyclical encodings (avoid ordinal distance artefacts)
    import numpy as np
    df["hour_sin"]  = np.sin(2 * np.pi * df["hour"]  / 24)
    df["hour_cos"]  = np.cos(2 * np.pi * df["hour"]  / 24)
    df["dow_sin"]   = np.sin(2 * np.pi * df["dayofweek"] / 7)
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)

    return df


# ── Main download ─────────────────────────────────────────────────────────────

def download_historical():
    print("=" * 60)
    print("Open-Meteo ERA5 Historical Weather Download")
    print(f"Period  : {START_DATE} → {END_DATE}")
    print(f"Points  : {', '.join(LOCATIONS.keys())}")
    print(f"Vars    : {len(HOURLY_VARIABLES)} hourly variables per point")
    print(f"Expected: ~87,852 rows | ~2 MB Parquet | ~5 MB CSV")
    print("=" * 60)

    # Open-Meteo recommends splitting long requests into yearly chunks
    # to stay within their 1-year-per-request guideline for the archive API.
    years = list(range(2015, 2026))
    all_chunks = []

    for loc_name, coords in LOCATIONS.items():
        print(f"\n▶ Location: {loc_name} ({coords['lat']}°N, {coords['lon']}°E)")
        loc_chunks = []

        for year in years:
            s = f"{year}-01-01"
            # End of year, but don't go past END_DATE
            e_raw = date(year, 12, 31)
            e_cap = date(2025, 12, 8)
            e = str(min(e_raw, e_cap))

            if s > str(e_cap):
                break

            chunk = fetch_location(loc_name, coords["lat"], coords["lon"], s, e)
            loc_chunks.append(chunk)
            time.sleep(0.5)   # be polite to the API

        loc_df = pd.concat(loc_chunks).sort_index()
        # Remove any duplicate timestamps (year boundary overlap)
        loc_df = loc_df[~loc_df.index.duplicated(keep="first")]
        all_chunks.append(loc_df)
        print(f"  [{loc_name}] Total rows: {len(loc_df):,}")

    print("\n▶ Merging all locations…")
    df = pd.concat(all_chunks, axis=1)
    df = df.sort_index()

    print("▶ Computing derived features…")
    df = add_derived_features(df)

    print(f"\n▶ Final shape: {df.shape[0]:,} rows × {df.shape[1]} columns")
    print(f"   Date range : {df.index[0]} → {df.index[-1]}")
    print(f"   Missing    : {df.isnull().sum().sum():,} cells")

    # ── Save ──────────────────────────────────────────────────────────────
    print(f"\n▶ Saving Parquet → {OUTPUT_PARQUET}")
    df.to_parquet(OUTPUT_PARQUET, compression="snappy", index=True)
    size_mb = OUTPUT_PARQUET.stat().st_size / 1e6
    print(f"   Parquet size : {size_mb:.2f} MB")

    if OUTPUT_CSV is not None:
        print(f"▶ Saving CSV    → {OUTPUT_CSV}")
        df.to_csv(OUTPUT_CSV)
        size_mb_csv = OUTPUT_CSV.stat().st_size / 1e6
        print(f"   CSV size     : {size_mb_csv:.2f} MB")

    print("\n✓ Done. Run daily_topup() to extend with recent + forecast data.")
    return df


# ── Daily top-up ─────────────────────────────────────────────────────────────

def daily_topup(parquet_path: Path = OUTPUT_PARQUET, past_days: int = 7):
    """
    Call this once per day (e.g. via cron or APScheduler in your backend).
    Fetches the last `past_days` days of actuals + 5-day forecast,
    merges into the stored Parquet, deduplicates, and overwrites.

    Returns a DataFrame of NEW rows (for feeding straight into inference).
    """
    print(f"▶ Daily top-up: loading existing data from {parquet_path}…")
    existing = pd.read_parquet(parquet_path)
    last_ts  = existing.index.max()
    print(f"   Existing coverage ends: {last_ts}")

    all_new = []
    for loc_name, coords in LOCATIONS.items():
        new_chunk = fetch_topup(loc_name, coords["lat"], coords["lon"], past_days)
        all_new.append(new_chunk)

    new_df = pd.concat(all_new, axis=1).sort_index()
    new_df = add_derived_features(new_df)

    # Merge: new rows take priority (actuals overwrite forecast rows)
    combined = pd.concat([existing, new_df])
    combined = combined[~combined.index.duplicated(keep="last")]
    combined = combined.sort_index()

    combined.to_parquet(parquet_path, compression="snappy", index=True)
    added = combined.index.max() - last_ts
    print(f"   ✓ Extended by {added}  | New end: {combined.index.max()}")

    # Return only rows newer than yesterday (for immediate inference use)
    cutoff = pd.Timestamp.utcnow() - pd.Timedelta(days=1)
    return combined[combined.index >= cutoff]


# ── Column reference ──────────────────────────────────────────────────────────

COLUMN_REFERENCE = """
COLUMN REFERENCE — weather_netherlands_2015_2025.parquet
=========================================================
Per-location columns (4 locations × 10 variables = 40 raw columns):
  {loc}_temperature_2m       °C      2m air temperature
  {loc}_windspeed_10m        m/s     wind at 10m height
  {loc}_windspeed_100m       m/s     wind at 100m (turbine hub height)
  {loc}_winddirection_10m    °       wind direction (0–360, met convention)
  {loc}_direct_radiation      W/m²   direct solar radiation at surface
  {loc}_diffuse_radiation     W/m²   diffuse (sky) radiation
  {loc}_cloudcover           %       total cloud cover
  {loc}_precipitation        mm/h    liquid precipitation
  {loc}_pressure_msl         hPa     mean sea level pressure
  {loc}_relativehumidity_2m  %       relative humidity at 2m

National-average columns (mean of all 4 points):
  nl_avg_{variable}           same units as above

Derived feature columns:
  hdh                         heating degree-hours (base 15°C)
  cdh                         cooling degree-hours (base 22°C)
  wind_ramp_3h               m/s     3-hour change in nl_avg_windspeed_100m
  clearsky_index             —       actual / theoretical max solar radiation
  hour, dayofweek, month     int     calendar components
  is_weekend                 0/1     Saturday or Sunday
  hour_sin, hour_cos         float   cyclical hour encoding
  dow_sin                    float   cyclical day-of-week encoding
  month_sin                  float   cyclical month encoding

Index:
  UTC DatetimeIndex, hourly, no gaps (ERA5 is gap-free by construction)

Locations pulled:
  eindhoven  51.44°N  5.48°E   primary point; NL south load centre
  rotterdam  51.92°N  4.48°E   major industrial load
  amsterdam  52.37°N  4.90°E   north Holland demand
  groningen  53.22°N  6.57°E   near North Sea wind farms
"""


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--topup" in sys.argv:
        daily_topup()
    else:
        df = download_historical()
        print(COLUMN_REFERENCE)
        print("\nColumn list:")
        for c in df.columns:
            print(f"  {c}")