#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Smart EV Charging — Team 12
Part 15: V2H (Vehicle-to-Home) Monte Carlo
----------------------------------------------------------------------

Reproducible: seed = 42.
----------------------------------------------------------------------
Outputs:
  - plots/p45_v2h_distribution.png
  - plots/p46_v2h_pillars.png
  - plots/p47_v2h_cliff.png
  - plots/p48_v2h_vs_battery.png
  - plots/p49_v2h_by_car.png
  - plots/p50_v2h_prognosis.png
  - results/databases/15_v2h/v2h_summary.csv
  - results/databases/15_v2h/v2h_monte_carlo.csv
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

BASE = os.path.dirname(os.path.abspath(__file__))
PLOTS = os.path.join(BASE, "..", "plots")
OUT_DIR = os.path.join(BASE, "..", "results", "databases", "15_v2h")
os.makedirs(PLOTS, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

SEED = 42
rng = np.random.default_rng(SEED)
N = 20_000

C_BLUE, C_GREEN, C_ORANGE = "#2E6FB0", "#2E9E5B", "#E08A2E"
C_GREY, C_DARK, C_RED, C_PURPLE = "#9AA3AC", "#2B2F33", "#C0504D", "#7A5BA6"
euro = FuncFormatter(lambda x, _: f"€{x:,.0f}")

# ---------------------------------------------------------------------------
# 1. V2H-CAPABLE CARS (2026, NL-relevant) — usable battery kWh, charger type
# ---------------------------------------------------------------------------
CARS = {
    "Renault 5 E-Tech":  {"kwh": 52.0, "type": "AC", "w": 0.30},
    "Hyundai Ioniq 5/6": {"kwh": 77.4, "type": "DC", "w": 0.22},
    "Kia EV6 (post-24)": {"kwh": 77.4, "type": "DC", "w": 0.15},
    "Kia EV9":           {"kwh": 99.8, "type": "DC", "w": 0.10},
    "VW ID.7 (77 kWh)":  {"kwh": 77.0, "type": "DC", "w": 0.13},
    "Nissan Leaf (new)": {"kwh": 52.0, "type": "DC", "w": 0.06},
    "Renault 4 E-Tech":  {"kwh": 52.0, "type": "AC", "w": 0.04},
}
names = list(CARS)
weights = np.array([CARS[c]["w"] for c in names])
weights /= weights.sum()

# ---------------------------------------------------------------------------
# 2. ASSUMPTIONS
# ---------------------------------------------------------------------------
HH_CONSUMPTION_MEAN = 3200         # kWh/yr (NL average)
PV_KWP_MEAN, PV_KWP_SD = 4.0, 1.3 # rooftop size (kWp)
PV_YIELD_PER_KWP = 900             # kWh/kWp/yr in NL
SURPLUS_SHARE_MEAN = 0.55          # fraction of PV that would be exported

RETAIL_EVENING = 0.40              # EUR/kWh evening grid price (post-2027)
FEEDIN_POST = 0.07                 # EUR/kWh feed-in after saldering ends
SELF_CONS_VALUE = RETAIL_EVENING - FEEDIN_POST   # ~0.33 EUR/kWh captured

DOD_V2H = 0.30                     # only cycle 30% of pack (battery care)
RT_AC, RT_DC = 0.85, 0.94         # round-trip efficiency

DAYTIME_PLUGIN_PROB = 0.45         # share of days car is home to absorb midday PV
HAS_SOLAR = 0.70                   # 70% of NL EV homes have PV

BACKUP_VALUE_MEAN = 25             # EUR/yr (NL outages are rare)
BACKUP_VALUE_SD = 15

ARB_SPREAD_MEAN = 0.15             # EUR/kWh captured night→peak (post-tax, net)
ARB_SPREAD_SD = 0.06
NIGHT_PLUGIN_PROB = 0.80           # car home overnight far more often than midday
HAS_DYNAMIC_TARIFF = 0.45         # share on a dynamic contract (rising fast)

CAPEX = {"AC": 4000, "DC": 6440}
INSTALL_MEAN, INSTALL_SD = 2200, 600
INTRO_DISCOUNT = 605               # AC only (Renault/We Drive Solar promo)
AMORTISE_YEARS = 10

STATIONARY_BATTERY_INSTALLED = 6000   # EUR for ~10 kWh installed
STATIONARY_SAVINGS = 550              # EUR/yr (mid of NL EUR 400–700 range)

PENETRATION = {2026: 0.05, 2027: 0.12, 2028: 0.22, 2029: 0.36, 2030: 0.52}

# ---------------------------------------------------------------------------
# 3. MONTE CARLO
# ---------------------------------------------------------------------------
def simulate(n=N, post_saldering=True):
    idx = rng.choice(len(names), n, p=weights)
    kwh = np.array([CARS[names[i]]["kwh"] for i in idx])
    is_dc = np.array([CARS[names[i]]["type"] == "DC" for i in idx])
    rt = np.where(is_dc, RT_DC, RT_AC)

    pv_kwp = np.clip(rng.normal(PV_KWP_MEAN, PV_KWP_SD, n), 1.0, None)
    pv_gen = pv_kwp * PV_YIELD_PER_KWP
    surplus_share = np.clip(rng.normal(SURPLUS_SHARE_MEAN, 0.1, n), 0.2, 0.85)
    pv_surplus = pv_gen * surplus_share
    has_solar = rng.random(n) < HAS_SOLAR

    daily_window = kwh * DOD_V2H * rt
    plugin = np.clip(rng.normal(DAYTIME_PLUGIN_PROB, 0.12, n), 0.1, 0.9)
    annual_absorbable = daily_window * 365 * plugin
    stored = np.minimum(pv_surplus, annual_absorbable) * has_solar

    feedin = FEEDIN_POST if post_saldering else 0.30
    capture = RETAIL_EVENING - feedin
    self_cons_value = stored * capture
    solar_kwh_per_day = np.where(annual_absorbable > 0, stored / 365.0, 0)

    has_dynamic = rng.random(n) < HAS_DYNAMIC_TARIFF
    night_plugin = np.clip(rng.normal(NIGHT_PLUGIN_PROB, 0.12, n), 0.2, 0.98)
    remaining_window = np.clip(daily_window - solar_kwh_per_day, 0, None)
    arb_kwh_yr = remaining_window * 365 * night_plugin * has_dynamic
    arb_spread = np.clip(rng.normal(ARB_SPREAD_MEAN, ARB_SPREAD_SD, n), 0.04, None)
    arbitrage_value = arb_kwh_yr * arb_spread

    backup = np.clip(rng.normal(BACKUP_VALUE_MEAN, BACKUP_VALUE_SD, n), 0, None)
    gross = self_cons_value + arbitrage_value + backup

    install = np.clip(rng.normal(INSTALL_MEAN, INSTALL_SD, n), 1200, 3500)
    capex = np.where(is_dc, CAPEX["DC"], CAPEX["AC"] - INTRO_DISCOUNT) + install
    capex_yr = capex / AMORTISE_YEARS

    net_vs_nothing = gross - capex_yr
    stationary_yr = STATIONARY_BATTERY_INSTALLED / AMORTISE_YEARS
    net_advantage_vs_battery = (gross - capex_yr) - (STATIONARY_SAVINGS - stationary_yr)

    return pd.DataFrame({
        "car": [names[i] for i in idx], "kwh": kwh, "is_dc": is_dc,
        "stored_kwh": stored, "self_cons_value": self_cons_value,
        "arbitrage_value": arbitrage_value, "backup": backup,
        "gross": gross, "capex_yr": capex_yr,
        "net_vs_nothing": net_vs_nothing,
        "net_adv_vs_battery": net_advantage_vs_battery,
    })


post = simulate(post_saldering=True)
pre = simulate(post_saldering=False)
m = lambda x: float(np.mean(x))

print("\n=== V2H RESULTS (seed=42, post-2027) ===")
print(f"  Mean solar self-consumption stored : {m(post.stored_kwh):.0f} kWh/yr")
print(f"  Mean self-consumption saving       : €{m(post.self_cons_value):.0f}/yr")
print(f"  Mean arbitrage saving (cheap→peak) : €{m(post.arbitrage_value):.0f}/yr")
print(f"  Mean backup value                  : €{m(post.backup):.0f}/yr")
print(f"  Mean GROSS V2H saving              : €{m(post.gross):.0f}/yr")
print(f"  Amortised hardware (10 yr)         : -€{m(post.capex_yr):.0f}/yr")
print(f"  Mean NET vs doing nothing          : €{m(post.net_vs_nothing):.0f}/yr")
print(f"  Mean GROSS pre-saldering-cliff     : €{m(pre.gross):.0f}/yr")
print(f"  Saldering-cliff uplift             : +€{m(post.gross)-m(pre.gross):.0f}/yr")

# Save KPI summary
summary = {
    "Mean solar stored (kWh/yr)": round(m(post.stored_kwh), 0),
    "Self-consumption saving (EUR/yr)": round(m(post.self_cons_value), 1),
    "Arbitrage saving cheap-to-peak (EUR/yr)": round(m(post.arbitrage_value), 1),
    "Backup value (EUR/yr)": round(m(post.backup), 1),
    "Gross V2H saving (EUR/yr, post-2027)": round(m(post.gross), 1),
    "Amortised hardware (EUR/yr, 10yr)": round(-m(post.capex_yr), 1),
    "Net vs doing nothing (EUR/yr)": round(m(post.net_vs_nothing), 1),
    "Gross pre-saldering-cliff (EUR/yr)": round(m(pre.gross), 1),
    "Saldering-cliff uplift (EUR/yr)": round(m(post.gross) - m(pre.gross), 1),
}
pd.Series(summary).to_csv(os.path.join(OUT_DIR, "v2h_summary.csv"), header=["value"])
post.to_csv(os.path.join(OUT_DIR, "v2h_monte_carlo.csv"), index=False)
print(f"\nData saved to {OUT_DIR}/")

# ---------------------------------------------------------------------------
# 4. PLOTS
# ---------------------------------------------------------------------------
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 11,
    "axes.edgecolor": C_DARK, "axes.linewidth": 0.8,
    "axes.grid": True, "grid.color": "#E6E9EC", "grid.linewidth": 0.8,
    "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False,
})

# ---- p45: distribution of gross annual V2H saving ----
fig, ax = plt.subplots(figsize=(7.4, 3.9))
v = post["gross"].clip(0, np.percentile(post["gross"], 99))
ax.hist(v, bins=55, color=C_GREEN, alpha=0.85, edgecolor="white", linewidth=0.4)
ax.axvline(m(post.gross), color=C_ORANGE, lw=2,
           label=f"Mean €{m(post.gross):.0f}/yr")
ax.axvline(float(np.median(v)), color=C_BLUE, lw=2, ls="--",
           label=f"Median €{float(np.median(v)):.0f}/yr")
ax.set_xlabel("Annual gross V2H saving (€/yr)")
ax.set_ylabel("Households")
ax.xaxis.set_major_formatter(euro)
ax.set_title("Distribution of total annual V2H saving\n"
             f"(20 000 households, post-2027, Eindhoven)", fontsize=11)
ax.legend(frameon=False, fontsize=9)
fig.tight_layout()
fig.savefig(os.path.join(PLOTS, "p45_v2h_distribution.png"), dpi=150)
plt.close(fig)

# ---- p46: the two savings pillars ----
fig, ax = plt.subplots(figsize=(7.6, 4.0))
pillars = ["Solar self-\nconsumption", "Arbitrage\n(cheap-to-peak)", "Backup\nresilience"]
vals = [m(post.self_cons_value), m(post.arbitrage_value), m(post.backup)]
bars = ax.bar(pillars, vals, color=[C_GREEN, C_BLUE, C_GREY], width=0.6, edgecolor="white")
for b, val in zip(bars, vals):
    ax.text(b.get_x() + b.get_width() / 2, val + 4, f"€{val:.0f}",
            ha="center", fontweight="bold")
ax.set_ylabel("Mean saving (€/yr)")
ax.yaxis.set_major_formatter(euro)
ax.set_ylim(0, max(vals) * 1.25)
ax.set_title("The two V2H savings pillars (+ backup). Arbitrage works\n"
             "without solar and whenever the car is home overnight", fontsize=11)
fig.tight_layout()
fig.savefig(os.path.join(PLOTS, "p46_v2h_pillars.png"), dpi=150)
plt.close(fig)

# ---- p47: saldering cliff before/after ----
fig, ax = plt.subplots(figsize=(7.0, 3.8))
cats = ["Before cliff\n(saldering, up to 2026)", "After cliff\n(no saldering, 2027 and later)"]
g = [m(pre.gross), m(post.gross)]
bars = ax.bar(cats, g, color=[C_GREY, C_ORANGE], width=0.55, edgecolor="white")
for b, val in zip(bars, g):
    ax.text(b.get_x() + b.get_width() / 2, val + 3, f"€{val:.0f}",
            ha="center", fontweight="bold")
ax.annotate("", xy=(1, g[1]), xytext=(1, g[0]),
            arrowprops=dict(arrowstyle="->", color=C_RED, lw=2))
ax.text(1.12, (g[0] + g[1]) / 2,
        f"+€{g[1]-g[0]:.0f}\n(×{g[1]/max(g[0], 1):.1f})",
        color=C_RED, fontsize=10, fontweight="bold", va="center")
ax.set_ylabel("Mean gross V2H saving (€/yr)")
ax.yaxis.set_major_formatter(euro)
ax.set_ylim(0, max(g) * 1.35)
ax.set_title("The 2027 net-metering cliff is the trigger:\n"
             "self-consumption barely pays today, but jumps once saldering ends",
             fontsize=11)
fig.tight_layout()
fig.savefig(os.path.join(PLOTS, "p47_v2h_cliff.png"), dpi=150)
plt.close(fig)

# ---- p48: V2H car vs stationary home battery ----
fig, ax = plt.subplots(figsize=(7.6, 4.0))
labels = ["Stationary\n10 kWh battery", "V2H car\n(AC charger)", "V2H car\n(DC charger)"]
stat_net = STATIONARY_SAVINGS - STATIONARY_BATTERY_INSTALLED / AMORTISE_YEARS
ac_mask = ~post["is_dc"]
dc_mask = post["is_dc"]
ac_net = m(post.loc[ac_mask, "net_vs_nothing"])
dc_net = m(post.loc[dc_mask, "net_vs_nothing"])
gross_vals = [STATIONARY_SAVINGS, m(post.loc[ac_mask, "gross"]),
              m(post.loc[dc_mask, "gross"])]
capex_vals = [STATIONARY_BATTERY_INSTALLED / AMORTISE_YEARS,
              m(post.loc[ac_mask, "capex_yr"]),
              m(post.loc[dc_mask, "capex_yr"])]
net_vals = [stat_net, ac_net, dc_net]
x = np.arange(3)
w = 0.35
ax.bar(x - w / 2, gross_vals, w, label="Gross saving", color=C_GREEN)
ax.bar(x + w / 2, capex_vals, w, label="Amortised hardware", color=C_RED, alpha=0.8)
for i, nv in enumerate(net_vals):
    ax.text(i, max(gross_vals[i], capex_vals[i]) + 8,
            f"net €{nv:+.0f}", ha="center", fontsize=9, fontweight="bold",
            color=C_BLUE if nv >= 0 else C_RED)
ax.set_xticks(x)
ax.set_xticklabels(labels, fontsize=9)
ax.set_ylabel("EUR / yr")
ax.yaxis.set_major_formatter(euro)
ax.set_title("Car-as-battery (V2H) vs a stationary\n"
             "home battery. V2H avoids a separate €6,000 battery purchase",
             fontsize=11)
ax.legend(frameon=False, fontsize=9)
fig.tight_layout()
fig.savefig(os.path.join(PLOTS, "p48_v2h_vs_battery.png"), dpi=150)
plt.close(fig)

# ---- p49: net saving by car model ----
fig, ax = plt.subplots(figsize=(7.8, 4.0))
by_car = post.groupby("car")["net_vs_nothing"].mean().reindex(names)
colors2 = [C_BLUE if CARS[c]["type"] == "DC" else C_GREEN for c in names]
ax.barh(range(len(names)), by_car.values, color=colors2, edgecolor="white")
ax.set_yticks(range(len(names)))
ax.set_yticklabels(
    [f"{c}\n({CARS[c]['kwh']:.0f} kWh, {CARS[c]['type']})" for c in names],
    fontsize=8.5)
for i, val in enumerate(by_car.values):
    ax.text(val + (2 if val >= 0 else -2), i, f"€{val:.0f}", va="center",
            ha="left" if val >= 0 else "right", fontsize=9, fontweight="bold")
ax.axvline(0, color=C_DARK, lw=0.8)
ax.set_xlabel("Mean NET V2H saving vs doing nothing (€/yr)")
ax.xaxis.set_major_formatter(euro)
ax.set_title("Net V2H saving by car (green=AC, blue=DC).\n"
             "Larger packs store more midday surplus; AC hardware is cheaper",
             fontsize=11)
ax.invert_yaxis()
fig.tight_layout()
fig.savefig(os.path.join(PLOTS, "p49_v2h_by_car.png"), dpi=150)
plt.close(fig)

# ---- p50: 2030 prognosis ----
fig, ax = plt.subplots(figsize=(7.6, 5.0))
yrs = list(PENETRATION)
pen = [PENETRATION[y] for y in yrs]
ax.bar([str(y) for y in yrs], [p * 100 for p in pen], color=C_PURPLE, alpha=0.45,
       label="V2H-capable share of EV fleet (%)")
ax2 = ax.twinx()
gross_year = [(m(pre.gross) if y < 2027 else m(post.gross)) for y in yrs]
ax2.plot([str(y) for y in yrs], gross_year, color=C_ORANGE, marker="o", lw=2.5,
         label="Mean gross saving/household (€/yr)")
ax.axvline(1, color=C_RED, ls="--", lw=1.5)
ax.text(0.93, 0.58, "saldering ends in\n(2027)",
        color=C_RED, fontsize=8.5, ha="right",
        transform=ax.transAxes,
        bbox=dict(facecolor="white", edgecolor="none", alpha=0.85, pad=2))
ax.set_ylabel("V2H-capable share of EV fleet (%)")
ax2.set_ylim(0, 1100)
ax2.set_ylabel("Gross saving (€/yr)")
ax2.yaxis.set_major_formatter(euro)
ax.set_title("Prognosis to 2030: V2H-capable EVs rise as the 2030 zero-\n"
             "emission new-car mandate comes into effect; the 2027 cliff steps up per-home value",
             fontsize=11)
lines = ax.get_legend_handles_labels()[0] + ax2.get_legend_handles_labels()[0]
labs = ax.get_legend_handles_labels()[1] + ax2.get_legend_handles_labels()[1]
ax.legend(lines, labs, frameon=False, fontsize=8.5, loc="upper left")
fig.tight_layout()
fig.savefig(os.path.join(PLOTS, "p50_v2h_prognosis.png"), dpi=150)
plt.close(fig)

print("\nPlots saved:")
for p in ["p45_v2h_distribution", "p46_v2h_pillars", "p47_v2h_cliff",
          "p48_v2h_vs_battery", "p49_v2h_by_car", "p50_v2h_prognosis"]:
    print(f"  {PLOTS}/{p}.png")
