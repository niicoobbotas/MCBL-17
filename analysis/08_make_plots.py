"""
Smart EV Charging — Team 12
Part 8: Final Report Figures
----------------------------------------------------------------------

Reads:
  - results/databases/02_prices/nl_hourly_real_2015_2025.csv
  - results/databases/04_fleet/fleet_database.json
  - results/databases/06_monte_carlo/v2_monte_carlo.csv
  - datasets/dataset6/eindhoven_zonal_load.csv
----------------------------------------------------------------------
Outputs:
  - plots/p27_load_vs_price_real.png
  - plots/p28_three_policies_session.png
  - plots/p29_monte_carlo_savings.png
  - plots/p30_contract_comparison.png
  - plots/p31_ev_adoption_forecast.png
  - plots/p32_tam_funnel.png
  - plots/p33_model_market_share.png
  - results/databases/08_final_figures/single_session_real.csv
  - results/databases/08_final_figures/kpi_final.csv
  - results/databases/08_final_figures/contracts_full.csv
  - results/databases/08_final_figures/ev_forecast.csv
"""
import os, json, sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "..", "results", "databases")
DIR_02        = os.path.join(DB, "02_prices")
DIR_04        = os.path.join(DB, "04_fleet")
DIR_05        = os.path.join(DB, "05_behavior")
DIR_06        = os.path.join(DB, "06_monte_carlo")
DATA_FINAL_DIR = os.path.join(DB, "08_final_figures")
os.makedirs(DATA_FINAL_DIR, exist_ok=True)

plt.rcParams.update({
    "figure.dpi": 130, "savefig.dpi": 160, "savefig.bbox": "tight",
    "font.family": "DejaVu Sans",
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25, "axes.titleweight": "bold",
})
PRIMARY = "#1f77b4"; ACCENT = "#2ca02c"; WARN = "#d62728"
GREY = "#7f7f7f"; ORANGE = "#ff9900"; PURPLE = "#9467bd"

OUT_PLOTS = os.path.join(BASE, "..", "plots")
os.makedirs(OUT_PLOTS, exist_ok=True)
OUT_DATA = DATA_FINAL_DIR

# =========================================================================
# Load data
# =========================================================================
hourly = pd.read_csv(os.path.join(DIR_02, "nl_hourly_real_2015_2025.csv"))
hourly["ts_local"] = pd.to_datetime(hourly["ts_local"])
year2024 = hourly[hourly["year"] == 2024].sort_values("ts_local").reset_index(drop=True)
print(f"2024 hours: {len(year2024)}")

# Retail formula
NL_ENERGY_TAX_2026 = 0.10154
NL_VAT = 0.21
def retail(wholesale_eur_mwh, margin):
    return (wholesale_eur_mwh / 1000.0 + margin + NL_ENERGY_TAX_2026) * (1 + NL_VAT)

year2024["retail_eneco"]  = retail(year2024["price_eur_mwh"].values, 0.0235)
year2024["retail_essent"] = retail(year2024["price_eur_mwh"].values, 0.0220)

# Hourly profile (mean over 2024)
hour_mean = year2024.groupby("hour")["retail_eneco"].mean()
print("\n2024 hourly mean retail (Eneco €/kWh):")
print(hour_mean.round(4))

# Eindhoven zonal load
zl = pd.read_csv(os.path.join(BASE, "..", "datasets", "dataset6", "eindhoven_zonal_load.csv"))
zl["timestamp"] = pd.to_datetime(zl["timestamp"], format="%m/%d/%Y %H:%M")
total = zl.groupby("timestamp")["demand_MW"].sum().reset_index()
total["hour"] = total["timestamp"].dt.hour
load_by_hour = total.groupby("hour")["demand_MW"].mean().values
L_norm = (load_by_hour - load_by_hour.min()) / (load_by_hour.max() - load_by_hour.min())

# =========================================================================
# FIG. 13 UPDATE — Load vs Price overlay with REAL hourly data
# =========================================================================
# Old plot used synthetic shape — now use real 2024 hourly retail
price_norm = (hour_mean - hour_mean.min()) / (hour_mean.max() - hour_mean.min())
load_norm = (load_by_hour - load_by_hour.min()) / (load_by_hour.max() - load_by_hour.min())

fig, ax = plt.subplots(figsize=(10, 4.4))
ax.plot(range(24), load_norm, "o-", color=PRIMARY, lw=2.4, markersize=6,
        label="Eindhoven load (normalised)")
ax.plot(range(24), price_norm, "s--", color=WARN, lw=2.2, markersize=5,
        label="NL retail price (normalised)")
ax.fill_between([1, 5], 0, 1.05, color=ACCENT, alpha=0.10)
ax.fill_between([17, 21], 0, 1.05, color=WARN, alpha=0.08)
ax.fill_between([11, 15], 0, 1.05, color=ORANGE, alpha=0.08)
ax.text(3, 0.10, "Cheap valley\n(overnight wind)", color=ACCENT,
        ha="center", fontweight="bold", fontsize=9)
ax.text(13, 0.10, "Solar dip\n(midday)", color="#cc8400",
        ha="center", fontweight="bold", fontsize=9)
ax.text(19, 0.10, "Stressed peak\n(commute + cook)", color=WARN,
        ha="center", fontweight="bold", fontsize=9)
ax.set_xticks(range(0, 24, 2))
ax.set_xlabel("Hour of day")
ax.set_ylabel("Normalised value (max = 1.0)")
ax.set_ylim(-0.02, 1.10)
ax.set_title("Eindhoven zonal load vs wholesale price, NL (2024)")
ax.legend(loc="upper right", frameon=False, fontsize=9)
fig.savefig(f"{OUT_PLOTS}/p27_load_vs_price_real.png")
plt.close(fig)
print("Fig 11 (load vs price, real data) saved")

# =========================================================================
# Schedulers (cleaned up)
# =========================================================================
def schedule_uncontrolled(E, P_max, eta, window):
    x = np.zeros(window); remaining = E
    for h in range(window):
        if remaining <= 0: break
        add = min(P_max * eta, remaining)
        x[h] = add / eta
        remaining -= add
    return x

def schedule_price_only(E, P_max, eta, window, p_kwh):
    x = np.zeros(window); remaining = E
    for h in np.argsort(p_kwh):
        if remaining <= 0: break
        add = min(P_max * eta, remaining)
        x[h] = add / eta
        remaining -= add
    return x

def schedule_smart(E, P_max, eta, window, p_kwh, L, L_cap=0.6,
                   alpha=1.0, beta=0.6, step=0.25):
    x = np.zeros(window); remaining = E
    while remaining > 1e-6:
        chunk = min(step, remaining)
        delta = chunk / eta
        best, best_c = -1, np.inf
        for h in range(window):
            if x[h] + delta > P_max + 1e-6: continue
            old_pen = max(0.0, L[h] + x[h]/P_max - L_cap) ** 2
            new_pen = max(0.0, L[h] + (x[h]+delta)/P_max - L_cap) ** 2
            c = alpha * p_kwh[h] * delta + beta * (new_pen - old_pen)
            if c < best_c: best_c, best = c, h
        if best < 0: break
        x[best] += delta
        remaining -= chunk
    return x

# =========================================================================
# FIG. 16 UPDATE — Single-session 30 kWh top-up with REAL prices
# =========================================================================
# 18:00 plug-in, 07:00 deadline = 14h window
# Use ONE representative day where prices look canonical (mid-winter weekday)
# Choose a Tuesday in November 2024
sample_day = year2024[(year2024["ts_local"].dt.month == 11) &
                      (year2024["ts_local"].dt.dayofweek == 1)]
sample_day_start = sample_day["ts_local"].min()  # first Tuesday in Nov 2024
# Find the index in the year2024 array for 18:00 on that day
day_18 = year2024[(year2024["ts_local"].dt.date == sample_day_start.date()) &
                  (year2024["hour"] == 18)].index[0]
# 48-hour window from 18:00 to next-next day 18:00
p48 = year2024.iloc[day_18:day_18 + 48]["retail_eneco"].values
L48 = np.concatenate([np.roll(L_norm, -18), np.roll(L_norm, -18)])  # rotate so slot 0 = 18:00

# Actually a cleaner approach — just use the L_norm rolled to clock hour 18 at slot 0
def rotate(arr, by):
    return np.concatenate([arr[by:], arr[:by]])
L_rot = rotate(L_norm, 18)  # now L_rot[0] is clock hour 18
L48 = np.concatenate([L_rot, L_rot])

# Window: slot 0 = 18:00, slot 13 = 07:00 next morning
window = 14
P_max = 11.0
eta = 0.92
E_req = 30.0

p_win = p48[:window]
L_win = L48[:window]

x_unc = schedule_uncontrolled(E_req, P_max, eta, window)
x_po  = schedule_price_only(E_req, P_max, eta, window, p_win)
x_sm  = schedule_smart(E_req, P_max, eta, window, p_win, L_win, beta=0.6)

# Map onto 48h timeline for plotting
def to_48(x_local):
    full = np.zeros(48)
    full[:window] = x_local
    return full

x_unc_48 = to_48(x_unc); x_po_48 = to_48(x_po); x_sm_48 = to_48(x_sm)

# Cost — use the full 48h price array
def cost(x_full): return float(np.sum(x_full * p48))
def peak_kw(x_full): return float(max(x_full[:window]))

# Save results
results = pd.DataFrame({
    "policy": ["Uncontrolled", "Price-only", "Smart (CACCS)"],
    "cost_EUR": [cost(x_unc_48), cost(x_po_48), cost(x_sm_48)],
    "peak_kW": [peak_kw(x_unc_48), peak_kw(x_po_48), peak_kw(x_sm_48)],
})
results["savings_vs_unc_pct"] = (1 - results["cost_EUR"] / results.loc[0, "cost_EUR"]) * 100
print("\nSingle-session results (real Eneco dynamic, Nov 2024 weekday):")
print(results.round(3).to_string(index=False))
results.to_csv(f"{OUT_DATA}/single_session_real.csv", index=False)

# Plot — match v1 style with bars + price overlay
fig, axes = plt.subplots(3, 1, figsize=(11, 7.5), sharex=True)
labels = ["Uncontrolled", "Price-only", "Smart (CACCS)"]
colors = [WARN, ORANGE, ACCENT]
data = [x_unc_48, x_po_48, x_sm_48]
for ax, lab, c, x in zip(axes, labels, colors, data):
    ax.bar(range(48), x, color=c, alpha=0.85, width=0.9)
    ax2 = ax.twinx()
    ax2.plot(range(48), p48, color=GREY, lw=1.3, alpha=0.85)
    ax2.set_ylabel("€/kWh", fontsize=8, color=GREY)
    ax2.tick_params(axis="y", labelsize=7, colors=GREY)
    ax2.grid(False)
    ax.set_ylabel("Charging\npower (kW)")
    c_val = cost(x); pk = peak_kw(x)
    ax.set_title(f"{lab}   |   Cost €{c_val:.2f}   |   peak draw {pk:.1f} kW",
                 fontsize=10)
    ax.set_ylim(0, P_max * 1.15)
    ax.axvspan(window - 0.5, 48, color=GREY, alpha=0.08)
axes[-1].set_xlabel("Hours from plug-in (slot 0 = 18:00; deadline 07:00 next day)")
axes[-1].set_xticks(range(0, 48, 4))
axes[-1].set_xticklabels([f"{(18 + i) % 24:02d}:00" for i in range(0, 48, 4)])
fig.suptitle("Three charging policies on 30 kWh chaarge\n"
             "(Tue Nov 2024, plug-in 18:00, deadline 07:00)",
             y=1.00, fontsize=12, fontweight="bold")
fig.tight_layout()
fig.savefig(f"{OUT_PLOTS}/p28_three_policies_session.png")
plt.close(fig)
print("Fig 16 (3-policy single session with real prices) saved")

# =========================================================================
# FIG. 17 UPDATE — Monte Carlo in 3-policy v1 format
# =========================================================================
# Pull the v2 MC results but render as 3 policies (drop "Fixed")
mc = pd.read_csv(os.path.join(DIR_06, "v2_monte_carlo.csv"))
print(f"\nMC rows: {len(mc)}")
print(f"Mean costs (unc/po/sm): €{mc['cost_unc'].mean():.0f} / "
      f"€{mc['cost_po'].mean():.0f} / €{mc['cost_sm'].mean():.0f}")

# Plot in v1 style: left = savings distribution, right = peak power
fig, axes = plt.subplots(1, 2, figsize=(12, 4.4))

mc["save_po_eur"] = mc["cost_unc"] - mc["cost_po"]
mc["save_sm_eur"] = mc["cost_unc"] - mc["cost_sm"]

axes[0].hist(mc["save_po_eur"], bins=40, color=ORANGE, alpha=0.65,
             label=f"Price-only (μ=€{mc['save_po_eur'].mean():.0f})")
axes[0].hist(mc["save_sm_eur"], bins=40, color=ACCENT, alpha=0.65,
             label=f"Smart (μ=€{mc['save_sm_eur'].mean():.0f})")
axes[0].axvline(0, color="black", lw=0.8)
axes[0].set_xlabel("Annual savings vs uncontrolled (€)")
axes[0].set_ylabel("Number of drivers")
axes[0].set_title(f"Distribution of annual € savings (N={len(mc)})")
axes[0].legend(frameon=False)

# Peak-hour charging
axes[1].hist(mc["peak_kwh_unc"], bins=40, color=WARN, alpha=0.6,
             label=f"Uncontrolled (μ={mc['peak_kwh_unc'].mean():.0f} kWh/yr)")
axes[1].hist(mc["peak_kwh_sm"], bins=40, color=ACCENT, alpha=0.6,
             label=f"Smart (μ={mc['peak_kwh_sm'].mean():.0f} kWh/yr)")
axes[1].set_xlabel("Annual peak-hour (17–21h) charging (kWh)")
axes[1].set_ylabel("Number of drivers")
axes[1].set_title("Peak-hour grid pressure: Smart vs Uncontrolled")
axes[1].legend(frameon=False)
fig.tight_layout()
fig.savefig(f"{OUT_PLOTS}/p29_monte_carlo_savings.png")
plt.close(fig)
print("Fig 17 (Monte Carlo, 3-policy v1-style) saved")

# Save KPIs for the report
mc["save_po_pct"] = mc["save_po_eur"] / mc["cost_unc"] * 100
mc["save_sm_pct"] = mc["save_sm_eur"] / mc["cost_unc"] * 100
mc["peak_drop_pct"] = (1 - mc["peak_kwh_sm"] / mc["peak_kwh_unc"]).where(
    mc["peak_kwh_unc"] > 0.1, np.nan) * 100

kpis = {
    "n_drivers": len(mc),
    "mean_cost_unc": mc["cost_unc"].mean(),
    "mean_cost_po": mc["cost_po"].mean(),
    "mean_cost_sm": mc["cost_sm"].mean(),
    "median_cost_unc": mc["cost_unc"].median(),
    "median_cost_po": mc["cost_po"].median(),
    "median_cost_sm": mc["cost_sm"].median(),
    "mean_save_po_eur": mc["save_po_eur"].mean(),
    "mean_save_sm_eur": mc["save_sm_eur"].mean(),
    "median_save_sm_eur": mc["save_sm_eur"].median(),
    "mean_save_po_pct": mc["save_po_pct"].mean(),
    "mean_save_sm_pct": mc["save_sm_pct"].mean(),
    "mean_peak_kwh_unc": mc["peak_kwh_unc"].mean(),
    "mean_peak_kwh_sm": mc["peak_kwh_sm"].mean(),
    "mean_peak_drop_pct": mc["peak_drop_pct"].mean(skipna=True),
    "share_drivers_save": (mc["save_sm_eur"] > 0).mean() * 100,
}
print("\nKPIs:")
for k, v in kpis.items():
    print(f"  {k}: {v:.2f}")
pd.Series(kpis).to_csv(f"{OUT_DATA}/kpi_final.csv")

# =========================================================================
# NEW PLOT — Eneco vs Essent five-contract comparison
# =========================================================================
# Full contract menu for both suppliers (Jan-May 2026 published rates)
# Sources: eneco.nl, essent.nl official tariff cards, energievergelijk.nl
contracts = pd.DataFrame([
    # supplier, contract, type, rate_eur_kwh, standing_eur_mo, notes
    ["Eneco",  "HollandseWind & Zon Variabel",  "variable", 0.293, 6.95, "Indefinite term, quarterly adjustments"],
    ["Eneco",  "Stroom Vast 1 jaar",            "fixed-1y",  0.319, 6.95, "12-mo lock; ~€60-150 cashback bonus"],
    ["Eneco",  "Stroom Vast 3 jaar",            "fixed-3y",  0.348, 6.95, "36-mo lock"],
    ["Eneco",  "Dynamische Stroom",             "dynamic",   None,  6.95, "Hourly EPEX + €0.0235/kWh margin"],
    ["Eneco",  "Modelcontract",                 "model",     0.305, 6.95, "Standardised regulator-defined product"],
    ["Essent", "Variabel",                      "variable", 0.269, 7.10, "Q1-Q2 2026, quarterly adjustments"],
    ["Essent", "Vast 1 jaar",                   "fixed-1y",  0.314, 7.10, "12-mo lock; cashback bonus"],
    ["Essent", "Vast 3 jaar",                   "fixed-3y",  0.342, 7.10, "36-mo lock"],
    ["Essent", "Dynamisch",                     "dynamic",   None,  7.10, "Hourly EPEX + €0.0220/kWh margin"],
    ["Essent", "Modelcontract",                 "model",     0.301, 7.10, "Standardised regulator-defined product"],
], columns=["supplier", "contract", "type", "rate_eur_kwh",
            "standing_eur_mo", "notes"])

# For dynamic, compute the 2024-mean equivalent
mean_eneco_dyn = year2024["retail_eneco"].mean()
mean_essent_dyn = year2024["retail_essent"].mean()
contracts.loc[(contracts["supplier"] == "Eneco") & (contracts["type"] == "dynamic"),
              "rate_eur_kwh"] = mean_eneco_dyn
contracts.loc[(contracts["supplier"] == "Essent") & (contracts["type"] == "dynamic"),
              "rate_eur_kwh"] = mean_essent_dyn

# Annual EV-only kWh for the bill calculation: 1,533 kWh
# (Eindhoven driver 10,950 km × 14 kWh/100km ÷ 0.92 charger eff)
EV_KWH = 10_950 * 14/100 / 0.92
print(f"\nAnnual EV-only kWh: {EV_KWH:.0f}")

# Compute annual EV-charging cost per contract (kWh × rate; standing charge is shared with household)
contracts["ev_annual_cost"] = contracts["rate_eur_kwh"] * EV_KWH
contracts.to_csv(f"{OUT_DATA}/contracts_full.csv", index=False)
print("\nFull contract menu (2026):")
print(contracts[["supplier", "contract", "type", "rate_eur_kwh", "ev_annual_cost"]].round(3).to_string(index=False))

# Plot — grouped bar
fig, ax = plt.subplots(figsize=(11, 4.8))
order = ["variable", "fixed-1y", "fixed-3y", "dynamic", "model"]
order_labels = ["Variabel", "Vast 1 jaar", "Vast 3 jaar", "Dynamisch", "Modelcontract"]
eneco = contracts[contracts["supplier"] == "Eneco"].set_index("type").loc[order]
essent = contracts[contracts["supplier"] == "Essent"].set_index("type").loc[order]
x = np.arange(len(order))
w = 0.38
b1 = ax.bar(x - w/2, eneco["rate_eur_kwh"], w, color=PRIMARY, label="Eneco")
b2 = ax.bar(x + w/2, essent["rate_eur_kwh"], w, color=ACCENT, label="Essent")
ax.set_xticks(x); ax.set_xticklabels(order_labels)
ax.set_ylabel("Headline rate (€/kWh, incl. taxes & BTW)")
ax.set_title("Eneco vs Essent, five contract types compared (May 2026 published rates)")
ax.legend(frameon=False, loc="upper left")
# Annotate bars
for bars in (b1, b2):
    for r in bars:
        ax.text(r.get_x() + r.get_width()/2, r.get_height() + 0.005,
                f"€{r.get_height():.3f}", ha="center", fontsize=8)
ax.set_ylim(0, max(contracts["rate_eur_kwh"]) * 1.15)
fig.savefig(f"{OUT_PLOTS}/p30_contract_comparison.png")
plt.close(fig)
print("Fig 30 (full contract menu) saved")

# =========================================================================
# NEW PLOT — EV adoption forecast 2020-2030 with scenarios
# =========================================================================
# Sources:
#  - Historical: EAFO/RVO 2020-2025 BEV stock
#  - Climate Agreement (2019): 100% ZEV new sales 2030 (aspirational)
#  - NKL projection: ~3M EVs by 2030
#  - CODEC model (Hoen et al. 2023): 26-40% BEV in new sales by 2030
#
# Build three scenarios for NL BEV stock and apply Eindhoven 1.02% share

years = np.arange(2020, 2031)

# Historical — read from fleet database (04_fleet/nl_fleet_yearly.csv)
_nl_fleet = pd.read_csv(os.path.join(DIR_04, "nl_fleet_yearly.csv"))
hist_stock = dict(zip(_nl_fleet["year"].astype(int), _nl_fleet["BEV_stock"].astype(int)))

# Forecast scenarios (NL stock by 2030)
# Low: CODEC realistic — extrapolate 2025 trajectory with declining growth
# Central: ElaadNL Outlook + EAFO — ~1.9M BEVs by 2030
# High: Climate Agreement — 3M EVs (BEV+PHEV) → ~2.6M BEVs by 2030
forecast_low = {2026: 720_000, 2027: 830_000, 2028: 960_000, 2029: 1_100_000, 2030: 1_250_000}
forecast_central = {2026: 770_000, 2027: 950_000, 2028: 1_180_000, 2029: 1_440_000, 2030: 1_750_000}
forecast_high = {2026: 820_000, 2027: 1_080_000, 2028: 1_440_000, 2029: 1_950_000, 2030: 2_600_000}

# Combine
stock = pd.DataFrame({"year": years})
stock["historical"] = [hist_stock.get(y) for y in years]
stock["low"] = [hist_stock.get(y, forecast_low.get(y)) for y in years]
stock["central"] = [hist_stock.get(y, forecast_central.get(y)) for y in years]
stock["high"] = [hist_stock.get(y, forecast_high.get(y)) for y in years]

# Eindhoven (1.02% of NL fleet)
EHV_SHARE = 0.0102
for col in ["historical", "low", "central", "high"]:
    stock[f"ehv_{col}"] = (stock[col] * EHV_SHARE).round(0)
stock.to_csv(f"{OUT_DATA}/ev_forecast.csv", index=False)
print("\nEV forecast (Eindhoven BEV stock):")
print(stock[["year", "ehv_historical", "ehv_low", "ehv_central", "ehv_high"]].to_string(index=False))

# Plot
fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))
# Left — NL BEV stock
ax = axes[0]
hist_yrs = [y for y in years if y <= 2025]
hist_vals = [hist_stock[y] for y in hist_yrs]
ax.plot(hist_yrs, hist_vals, "o-", color="black", lw=2.5, markersize=8,
        label="Historical (EAFO/RVO)")
fc_yrs = [y for y in years if y >= 2025]
ax.plot(fc_yrs, [stock[stock["year"] == y]["low"].values[0] for y in fc_yrs],
        "--", color=GREY, lw=1.8, label="Low (CODEC realistic)")
ax.plot(fc_yrs, [stock[stock["year"] == y]["central"].values[0] for y in fc_yrs],
        "-", color=PRIMARY, lw=2.5, label="Central (ElaadNL Outlook)")
ax.plot(fc_yrs, [stock[stock["year"] == y]["high"].values[0] for y in fc_yrs],
        "--", color=ACCENT, lw=1.8, label="High (Climate Agreement 100% ZEV)")
ax.fill_between(fc_yrs,
                [stock[stock["year"] == y]["low"].values[0] for y in fc_yrs],
                [stock[stock["year"] == y]["high"].values[0] for y in fc_yrs],
                color=PRIMARY, alpha=0.10)
ax.set_xlabel("Year")
ax.set_ylabel("NL BEV stock")
ax.set_title("Netherlands BEV stock - historical and 2030 scenarios")
ax.set_xticks(range(2020, 2031, 2))
ax.yaxis.set_major_formatter(plt.matplotlib.ticker.StrMethodFormatter('{x:,.0f}'))
ax.legend(loc="upper left", frameon=False, fontsize=9)
ax.set_ylim(0, 3_000_000)

# Right — Eindhoven addressable market
ax = axes[1]
hist_ehv = [hist_stock[y] * EHV_SHARE for y in hist_yrs]
ax.plot(hist_yrs, hist_ehv, "o-", color="black", lw=2.5, markersize=8,
        label="Historical")
ax.plot(fc_yrs, [stock[stock["year"] == y]["ehv_low"].values[0] for y in fc_yrs],
        "--", color=GREY, lw=1.8, label="Low")
ax.plot(fc_yrs, [stock[stock["year"] == y]["ehv_central"].values[0] for y in fc_yrs],
        "-", color=PRIMARY, lw=2.5, label="Central")
ax.plot(fc_yrs, [stock[stock["year"] == y]["ehv_high"].values[0] for y in fc_yrs],
        "--", color=ACCENT, lw=1.8, label="High")
ax.fill_between(fc_yrs,
                [stock[stock["year"] == y]["ehv_low"].values[0] for y in fc_yrs],
                [stock[stock["year"] == y]["ehv_high"].values[0] for y in fc_yrs],
                color=PRIMARY, alpha=0.10)
# Annotate central 2030
y2030_c = stock[stock["year"] == 2030]["ehv_central"].values[0]
ax.annotate(f"{int(y2030_c):,} BEVs\nin Eindhoven", xy=(2030, y2030_c),
            xytext=(2028, y2030_c + 4000),
            arrowprops=dict(arrowstyle="->", color="black"),
            fontsize=10, fontweight="bold")
ax.set_xlabel("Year")
ax.set_ylabel("Eindhoven BEV stock")
ax.set_title("Eindhoven BEV stock (1.02% NL share) - addressable market")
ax.set_xticks(range(2020, 2031, 2))
ax.yaxis.set_major_formatter(plt.matplotlib.ticker.StrMethodFormatter('{x:,.0f}'))
ax.legend(loc="upper left", frameon=False, fontsize=9)
fig.tight_layout()
fig.savefig(f"{OUT_PLOTS}/p31_ev_adoption_forecast.png")
plt.close(fig)
print("New plot (EV forecast) saved")

# =========================================================================
# NEW PLOT — TAM funnel (Eindhoven 2030)
# =========================================================================
y2030_central = stock[stock["year"] == 2030]["ehv_central"].values[0]
phev_share_2030 = 0.18  # roughly stable through 2030
ehv_phev_2030 = int(y2030_central * phev_share_2030 / 0.82)  # BEV/(BEV+PHEV)=0.82

# Funnel: TAM → SAM → SOM
_hcs = pd.read_csv(os.path.join(DIR_05, "ehv_home_charging_share.csv"))
home_charging_share = _hcs["home_charging_share_pct"].mean() / 100
target_segments = {
    "Eindhoven plug-in vehicles 2030 (TAM)": y2030_central + ehv_phev_2030,
    f"Home-charging-capable ({home_charging_share*100:.0f}%, SAM)": int((y2030_central + ehv_phev_2030) * home_charging_share),
    "On dynamic tariff (35% by 2030)": int((y2030_central + ehv_phev_2030) * home_charging_share * 0.35),
    "Realistic capture (15% of SAM by 2030)": int((y2030_central + ehv_phev_2030) * home_charging_share * 0.15),
}
print(f"\nTAM funnel 2030 (Eindhoven):")
for k, v in target_segments.items():
    print(f"  {k}: {v:,}")

fig, ax = plt.subplots(figsize=(10, 4.5))
labels = list(target_segments.keys())
values = list(target_segments.values())
colors_fnl = [PRIMARY, ACCENT, ORANGE, WARN]
y_pos = np.arange(len(labels))
bars = ax.barh(y_pos, values, color=colors_fnl, alpha=0.85)
ax.set_yticks(y_pos); ax.set_yticklabels(labels, fontsize=9)
ax.invert_yaxis()
ax.set_xlabel("Number of vehicles / users in Eindhoven")
ax.set_title("Eindhoven 2030 - Smart EV Charging market funnel")
for i, v in enumerate(values):
    ax.text(v + max(values) * 0.01, i, f"{v:,}", va="center",
            fontsize=10, fontweight="bold")
ax.set_xlim(0, max(values) * 1.20)
fig.savefig(f"{OUT_PLOTS}/p32_tam_funnel.png")
plt.close(fig)
print("New plot (TAM funnel) saved")

# =========================================================================
# NEW PLOT — Top 15 EV model market share (sales-weighted pie/bar)
# =========================================================================
with open(os.path.join(DIR_04, "fleet_database.json")) as f:
    fdb = json.load(f)
ev_models = pd.DataFrame(fdb["ev_models"])
bev = ev_models[ev_models["type"] == "BEV"].copy().sort_values("new_2024_2025", ascending=True)

fig, ax = plt.subplots(figsize=(10, 5))
ax.barh(bev["model"], bev["new_2024_2025"], color=PRIMARY)
for i, (m, v, b, r) in enumerate(zip(bev["model"], bev["new_2024_2025"],
                                       bev["battery_kWh"], bev["wltp_km"])):
    ax.text(v + max(bev["new_2024_2025"]) * 0.01, i,
            f"  {b:.0f} kWh · {r:.0f} km", va="center", fontsize=8, color="#444")
ax.set_xlabel("New registrations, NL 2024-2025")
ax.set_title("Top-15 BEV models in the Netherlands (2024-2025 combined)\n"
             "Specs shown: battery capacity · WLTP range")
fig.savefig(f"{OUT_PLOTS}/p33_model_market_share.png")
plt.close(fig)
print("Fig 33 (model share) saved")

print(f"\nAll final plots saved to {OUT_PLOTS}")
