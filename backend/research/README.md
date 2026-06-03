# Research (MCBL-17)

Data-science and modelling work from the team (originally the `MCBL-17` repo),
merged into this project. The **live app** reuses the key results from here;
the scripts below remain as reference, reproducibility and report material.

## What was integrated into the running backend

| Research artifact | Integrated as | Notes |
|---|---|---|
| `Price extractor.py` (EnergyZero API) | `app/services/energyzero_fetcher.py` | Real Dutch consumer prices (€/kWh incl. BTW). Now the default `price_source`. |
| `more_code/03_simulation.py` — CACCS scheduler | `app/services/optimizer.py` → `_compute_smart()` | The grid-aware "smart" optimization mode (cost **+** congestion). |
| `eindhoven_zonal_load.csv` hourly load profile | `optimizer.EINDHOVEN_LOAD_NORM` | Normalised 24h congestion proxy embedded as a constant. |

Selecting **Smart Grid** mode in the app now runs the team's CACCS algorithm.

## Scripts (reference only)

These were written for a notebook/sandbox environment and use absolute paths
(`/home/claude`, `/mnt/user-data`, OneDrive) — they are kept for provenance and
are **not** wired into the API. Re-point the paths to `./data` / `./more_data`
to re-run them.

- `Price extractor.py` — EnergyZero day-ahead price fetcher (Eindhoven).
- `EDA/EDA.py` — exploratory plots (prices, load, congestion, zonal demand).
- `more_code/01_price_analysis.py` — price statistics & hourly profile.
- `more_code/02_congestion_analysis.py` — TenneT / PC6 congestion analysis.
- `more_code/03_simulation.py` — CACCS algorithm + 1000-driver Monte Carlo.
- `weather_pipeline/fetch_weather_data.py` — Open-Meteo ERA5 weather pull for
  price-forecasting features (run once to build a Parquet cache).
- `frontend/eindhoven_price_forecast.html` — standalone price-forecast dashboard.

## Data

`data/`, `more_data/`, `more_plots/` hold the input CSVs/PDFs and generated
figures. Some files are large (the two `congestie_pc6.csv` are ~34 MB each and
identical duplicates) — see the repo root if you'd rather keep raw data out of
version control.
