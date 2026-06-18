"""
Smart EV Charging — Team 12
Part 9: ERE & Solar Revenue Plots
----------------------------------------------------------------------

Reads:
  - ere_solar_model.py  (imported from the same directory)
----------------------------------------------------------------------
Outputs:
  - plots/p34_ere_value_stack.png
  - plots/p35_solar_matching.png
  - plots/p36_ere_value_landscape.png
  - plots/p37_ere_per_kwh.png
"""
import os
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ere_solar_model import (
    calc_ere_revenue, calc_solar_self_consumption_value, estimate_pv_generation,
    total_value_stack, ERE_PER_KWH_GRID, ERE_PER_KWH_SOLAR,
    NL_GRID_RENEWABLE_SHARE_2026, ERE_PRICE_EUR_PER_UNIT, INBOEKER_COMMISSION,
    SC_RATE_PASSIVE, SC_RATE_SMART, FEED_IN_TARIFF_2026
)

plt.rcParams.update({
    "figure.dpi": 130, "savefig.dpi": 160, "savefig.bbox": "tight",
    "font.family": "DejaVu Sans",
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25, "axes.titleweight": "bold",
})

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "..", "plots")
os.makedirs(OUT, exist_ok=True)

DB = os.path.join(BASE, "..", "results", "databases")
DIR_04 = os.path.join(DB, "04_fleet")
DIR_06 = os.path.join(DB, "06_monte_carlo")

# Tesla Model Y efficiency from fleet database (kWh/100km)
with open(os.path.join(DIR_04, "fleet_database.json")) as _f:
    _fleet = json.load(_f)
MODEL_Y_EFF = next(m["kWh_per_100km"] for m in _fleet["ev_models"]
                   if m["model"] == "Tesla Model Y")

# Smart saving ratio from Monte Carlo kpi_summary
_kpi = pd.read_csv(os.path.join(DIR_06, "kpi_summary.csv"), index_col=0).squeeze()
ENECO_FIXED_TARIFF = 0.319  # EUR/kWh
_save_pct = _kpi["mean_save_sm_vs_fix_pct"]
SMART_COST_RATIO = (1 - _save_pct / 100) * ENECO_FIXED_TARIFF  # EUR/kWh smart

PRIMARY = "#1f77b4"; ACCENT = "#2ca02c"; WARN = "#d62728"
GREY = "#7f7f7f"; ORANGE = "#ff9900"; PURPLE = "#9467bd"

# =========================================================================
# Plot 1: Value-stack comparison — no-solar vs solar driver
# =========================================================================
# Typical Eindhoven driver, Tesla Model Y, 12k km/yr, Eneco dynamic+smart
TYPICAL_KM = 12_000
annual_kwh = TYPICAL_KM * MODEL_Y_EFF / 100 / 0.92
fixed_cost = annual_kwh * ENECO_FIXED_TARIFF
smart_cost = annual_kwh * SMART_COST_RATIO

stack_no_solar = total_value_stack(annual_kwh, fixed_cost, smart_cost,
                                     has_solar=False)
stack_solar = total_value_stack(annual_kwh, fixed_cost, smart_cost,
                                  has_solar=True, pv_kwp=4.0)

fig, axes = plt.subplots(1, 2, figsize=(12, 5))
labels = ["Dynamic-prices\nsaving", "ERE\ncertificates",
          "Solar self-\nconsumption", "Total\n(combined)"]
colors_stack = [PRIMARY, ACCENT, ORANGE, "#444444"]

for ax, stack, title in [(axes[0], stack_no_solar, "Driver WITHOUT solar PV"),
                          (axes[1], stack_solar, "Driver WITH 4 kWp solar PV")]:
    vals = [stack["dynamic_save_eur"], stack["ere_revenue_eur"],
            stack["solar_value_eur"], stack["total_eur"]]
    bars = ax.bar(range(4), vals, color=colors_stack, alpha=0.88,
                   edgecolor="black", linewidth=0.5)
    ax.set_xticks(range(4))
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylabel("Annual value (€)")
    ax.set_title(title)
    ax.set_ylim(0, 900)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width()/2, v + 15,
                f"€{v:.0f}", ha="center", fontweight="bold", fontsize=10)
fig.suptitle("Total annual value to a Smart EV Charging customer\n"
             "(Tesla Model Y, 12 000 km/yr, Eneco dynamic + smart cable)",
             fontsize=12, fontweight="bold", y=1.02)
fig.tight_layout()
fig.savefig(f"{OUT}/p34_ere_value_stack.png")
plt.close(fig)
print(f"Saved value-stack plot")

# =========================================================================
# Plot 2: Solar matching — passive vs smart self-consumption
# =========================================================================
# Show a typical sunny day: PV generation curve + EV charging window
hours = np.arange(24)

# PV generation profile (April-September average, 4 kWp system)
def pv_profile(kwp):
    """kWh/h profile, peaks around 13:00."""
    p = np.zeros(24)
    for h in range(24):
        # Bell curve centered at 13:00 with 5-hour width
        p[h] = max(0, np.exp(-((h - 13) / 3.5) ** 2))
    return p * kwp * 0.7  # scale to realistic kWh

pv_4kwp = pv_profile(4.0)
print(f"PV daily total: {pv_4kwp.sum():.2f} kWh on a sunny day")

# Two EV charging policies
ev_uncontrolled = np.zeros(24)
ev_uncontrolled[18:21] = 5.0  # plug-in 18:00, 5 kW for 3h
ev_uncontrolled[21] = 3.0

ev_smart = np.zeros(24)
# Smart shifts charging to midday IF the car is home, plus night fill
ev_smart[12:15] = 4.5  # midday solar match
ev_smart[2:5] = 3.0    # overnight wind

fig, axes = plt.subplots(2, 1, figsize=(11, 6.5), sharex=True)

# Top: passive (no smart) — solar exports, EV charges in evening
ax = axes[0]
ax.fill_between(hours, 0, pv_4kwp, color=ORANGE, alpha=0.55, label="Solar generation (4 kWp)")
ax.bar(hours, ev_uncontrolled, color=WARN, alpha=0.85, width=0.85,
       label="Uncontrolled EV charging")
ax.fill_between(hours, 0, np.minimum(pv_4kwp, ev_uncontrolled),
                color=ACCENT, alpha=0.55, label="Solar to EV (self-consumed)")
ax.set_ylabel("kW / kWh per hour")
ax.set_title("Without smart schedule: 30% of solar reaches the EV\n"
             "(rest is exported to the grid at low feed-in tariff)")
ax.legend(loc="upper left", frameon=False, fontsize=9)
ax.set_ylim(0, 6)
sc_passive = min(pv_4kwp.sum(), np.minimum(pv_4kwp, ev_uncontrolled).sum())
ax.text(0.98, 0.85, f"Self-consumed: {sc_passive:.1f} kWh\n"
        f"Exported: {pv_4kwp.sum() - sc_passive:.1f} kWh",
        transform=ax.transAxes, ha="right",
        bbox=dict(facecolor="white", edgecolor="grey", alpha=0.9), fontsize=9)

# Bottom: smart — EV shifted to midday + overnight cheap
ax = axes[1]
ax.fill_between(hours, 0, pv_4kwp, color=ORANGE, alpha=0.55, label="Solar generation (4 kWp)")
ax.bar(hours, ev_smart, color=ACCENT, alpha=0.85, width=0.85,
       label="Smart EV charging (CACCS)")
ax.fill_between(hours, 0, np.minimum(pv_4kwp, ev_smart),
                color="#0a5d2e", alpha=0.65, label="Solar to EV (self-consumed)")
ax.set_xlabel("Hour of day")
ax.set_ylabel("kW / kWh per hour")
ax.set_title("With smart schedule: 70% of solar reaches the EV\n"
             "(midday match avoids export loss; overnight fill at cheap-wind prices)")
ax.legend(loc="upper left", frameon=False, fontsize=9)
ax.set_xticks(range(0, 24, 2))
ax.set_ylim(0, 6)
sc_smart = min(pv_4kwp.sum(), np.minimum(pv_4kwp, ev_smart).sum())
ax.text(0.98, 0.85, f"Self-consumed: {sc_smart:.1f} kWh\n"
        f"Exported: {pv_4kwp.sum() - sc_smart:.1f} kWh",
        transform=ax.transAxes, ha="right",
        bbox=dict(facecolor="white", edgecolor="grey", alpha=0.9), fontsize=9)
fig.suptitle("Solar self-consumption: matching EV charging to PV generation",
             fontsize=12, fontweight="bold", y=1.00)
fig.tight_layout()
fig.savefig(f"{OUT}/p35_solar_matching.png")
plt.close(fig)
print(f"Saved solar-matching plot")

# =========================================================================
# Plot 3: Total earnings landscape across mileage
# =========================================================================
mileages = np.arange(2000, 30001, 1000)
no_solar_total = []
solar_total = []
ere_only = []
dyn_only = []

for km in mileages:
    # Approximate annual_kwh and costs (linear scaling for illustration)
    annual_kwh = km * MODEL_Y_EFF / 100 / 0.92
    fixed = annual_kwh * ENECO_FIXED_TARIFF
    smart = annual_kwh * SMART_COST_RATIO
    
    no_solar = total_value_stack(annual_kwh, fixed, smart, has_solar=False)
    yes_solar = total_value_stack(annual_kwh, fixed, smart, has_solar=True, pv_kwp=4.0)
    no_solar_total.append(no_solar["total_eur"])
    solar_total.append(yes_solar["total_eur"])
    ere_only.append(no_solar["ere_revenue_eur"])
    dyn_only.append(no_solar["dynamic_save_eur"])

fig, ax = plt.subplots(figsize=(11, 5))
ax.plot(mileages, dyn_only, "-", color=PRIMARY, lw=2.2, label="Dynamic-prices saving (smart schedule)")
ax.plot(mileages, ere_only, "-", color=ACCENT, lw=2.2, label="ERE certificates")
ax.plot(mileages, no_solar_total, "-", color="#444", lw=2.8,
        label="Total: without solar")
ax.plot(mileages, solar_total, "-", color=ORANGE, lw=2.8,
        label="Total: with 4 kWp solar")
ax.fill_between(mileages, no_solar_total, solar_total, color=ORANGE, alpha=0.10)
ax.axvline(10950, color=GREY, ls=":", lw=1.5, alpha=0.7)
ax.text(10950, 50, " Eindhoven\n avg (10 950 km)", fontsize=9, color=GREY)
ax.axvline(14500, color=GREY, ls=":", lw=1.5, alpha=0.7)
ax.text(14500, 50, " NL avg\n (14 500 km)", fontsize=9, color=GREY)
ax.set_xlabel("Annual mileage (km)")
ax.set_ylabel("Total annual € value to driver")
ax.set_title("Total smart schedule value vs annual mileage\n"
             "(Tesla Model Y, Eneco dynamic, MID-registered ERE, optional 4 kWp solar)")
ax.legend(loc="upper left", frameon=False, fontsize=9)
ax.set_xlim(0, 30000)
ax.set_ylim(0, max(solar_total) * 1.1)
ax.xaxis.set_major_formatter(plt.matplotlib.ticker.StrMethodFormatter('{x:,.0f}'))
ax.yaxis.set_major_formatter(plt.matplotlib.ticker.StrMethodFormatter('€{x:,.0f}'))
fig.savefig(f"{OUT}/p36_ere_value_landscape.png")
plt.close(fig)
print(f"Saved value-landscape plot")

# =========================================================================
# Plot 4: ERE formula breakdown — visual primer
# =========================================================================
fig, ax = plt.subplots(figsize=(11, 5))

# Horizontal bar chart showing how ERE per kWh is built up
categories = ["Grid electricity\n(NL net average,\n50.5% renewable)",
              "Verified green-power\ncontract\n(100% renewable)",
              "Own rooftop solar\nused directly\n(100% renewable + bonus)"]
ere_kwh = [
    NL_GRID_RENEWABLE_SHARE_2026 * 183 * 3.6 / 1000,
    1.0 * 183 * 3.6 / 1000,
    1.0 * 183 * 3.6 / 1000,
]
prices_per_kwh = [
    NL_GRID_RENEWABLE_SHARE_2026 * 183 * 3.6 / 1000 * ERE_PRICE_EUR_PER_UNIT * (1 - INBOEKER_COMMISSION),
    1.0 * 183 * 3.6 / 1000 * ERE_PRICE_EUR_PER_UNIT * (1 - INBOEKER_COMMISSION),
    1.0 * 183 * 3.6 / 1000 * ERE_PRICE_EUR_PER_UNIT * (1 - INBOEKER_COMMISSION),
]

y = np.arange(len(categories))
bars = ax.barh(y, prices_per_kwh, color=[GREY, ACCENT, ORANGE], alpha=0.85,
                edgecolor="black", linewidth=0.5)
ax.set_yticks(y)
ax.set_yticklabels(categories, fontsize=10)
ax.invert_yaxis()
ax.set_xlabel("Net ERE revenue per kWh charged (€)")
ax.set_title("ERE revenue per kWh of EV charging by source of electricity")
for b, p, e in zip(bars, prices_per_kwh, ere_kwh):
    ax.text(p + 0.001, b.get_y() + b.get_height()/2,
            f"  €{p:.4f}/kWh  ({e:.3f} ERE/kWh)",
            va="center", fontsize=10, fontweight="bold")
ax.set_xlim(0, max(prices_per_kwh) * 1.5)
fig.savefig(f"{OUT}/p37_ere_per_kwh.png")
plt.close(fig)
print(f"Saved ERE-formula plot")
