#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Smart EV Charging — Team 12
Part 14: Middleware Market Segmentation
----------------------------------------------------------------------

All proportions are explicit, defensible knobs grounded in 2026 NL data.
Reproducible: seed = 42.
----------------------------------------------------------------------
Outputs:
  - plots/p42_mw_segments.png
  - plots/p43_mw_funnel.png
  - plots/p44_mw_sensitivity.png
  - results/databases/14_middleware/middleware_summary.csv
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
OUT_DIR = os.path.join(BASE, "..", "results", "databases", "14_middleware")
os.makedirs(PLOTS, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

rng = np.random.default_rng(42)
N = 50_000

C_BLUE, C_GREEN, C_ORANGE = "#2E6FB0", "#2E9E5B", "#E08A2E"
C_GREY, C_DARK, C_RED, C_PURPLE = "#9AA3AC", "#2B2F33", "#C0504D", "#7A5BA6"
pct = FuncFormatter(lambda x, _: f"{x:.0f}%")

# ---------------------------------------------------------------------------
# 1. EINDHOVEN EV BASE (grounded estimate)
# ---------------------------------------------------------------------------
# NL ~1.2M BEVs registered 2025. Eindhoven ~248k people (~1.4% of NL pop),
# but above-average urban EV adoption. Public chargers in Eindhoven ~3,000.
EINDHOVEN_BEVS = 14_000

# ---------------------------------------------------------------------------
# 2. LAYER PROBABILITIES (defensible knobs)
# ---------------------------------------------------------------------------
P_HOME_CHARGING = 0.62   # share with access to home/private charging
P_CAR_API = 0.45         # share whose car has usable native charging API
P_SMART_WALLBOX = 0.40   # share with a natively smart wallbox
RHO = 0.35               # positive correlation (smart car buyers buy smart wallbox)


def simulate(n=N, p_home=P_HOME_CHARGING, p_api=P_CAR_API, p_box=P_SMART_WALLBOX):
    home = rng.random(n) < p_home
    z1 = rng.normal(size=n)
    z2 = RHO * z1 + np.sqrt(1 - RHO**2) * rng.normal(size=n)
    car_api = z1 < np.quantile(z1, p_api)
    smart_box = z2 < np.quantile(z2, p_box)
    car_api &= home
    smart_box &= home
    already_smart = home & (car_api | smart_box)
    needs_mw = home & ~(car_api | smart_box)
    public_only = ~home
    return pd.DataFrame({
        "home": home, "car_api": car_api, "smart_box": smart_box,
        "already_smart": already_smart, "needs_mw": needs_mw,
        "public_only": public_only,
    })


df = simulate()
shares = {
    "Home/private charging": df.home.mean(),
    "  - already smart (car API or smart box)": df.already_smart.mean(),
    "  - needs middleware (neither)": df.needs_mw.mean(),
    "Public-only (not addressable)": df.public_only.mean(),
    "Car has native API (of all)": df.car_api.mean(),
    "Smart wallbox (of all)": df.smart_box.mean(),
}
print("=== EINDHOVEN MIDDLEWARE SEGMENTATION (seed=42) ===")
for k, v in shares.items():
    print(f"  {k:46s}: {v*100:5.1f}%")
print(f"\n  Base BEVs (est.)                : {EINDHOVEN_BEVS:,}")
print(f"  Home-charging EVs               : {int(df.home.mean()*EINDHOVEN_BEVS):,}")
print(f"  -> NEEDS MIDDLEWARE             : {int(df.needs_mw.mean()*EINDHOVEN_BEVS):,}")
print(f"  -> already smart (connector app): {int(df.already_smart.mean()*EINDHOVEN_BEVS):,}")
print(f"  -> public-only (skip)           : {int(df.public_only.mean()*EINDHOVEN_BEVS):,}")

summary = {
    "Eindhoven BEVs (est)": EINDHOVEN_BEVS,
    "Home-charging share %": round(df.home.mean() * 100, 1),
    "Needs middleware share %": round(df.needs_mw.mean() * 100, 1),
    "Already smart share %": round(df.already_smart.mean() * 100, 1),
    "Public-only share %": round(df.public_only.mean() * 100, 1),
    "Needs-middleware EVs (count)": int(df.needs_mw.mean() * EINDHOVEN_BEVS),
    "Already-smart EVs (count)": int(df.already_smart.mean() * EINDHOVEN_BEVS),
}
pd.Series(summary).to_csv(os.path.join(OUT_DIR, "middleware_summary.csv"), header=["value"])
print(f"\nSummary saved to {OUT_DIR}/middleware_summary.csv")

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 11,
    "axes.edgecolor": C_DARK, "axes.linewidth": 0.8,
    "axes.grid": True, "grid.color": "#E6E9EC", "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False,
})

# ---- p42: three segments ----
fig, ax = plt.subplots(figsize=(7.8, 4.2))
seg = ["Needs middleware\n(core market)", "Already smart\n(connector app)",
       "Public-only\n(not addressable)"]
vals = [df.needs_mw.mean() * 100, df.already_smart.mean() * 100,
        df.public_only.mean() * 100]
colors = [C_ORANGE, C_GREEN, C_GREY]
bars = ax.bar(seg, vals, color=colors, width=0.6, edgecolor="white")
for b, v in zip(bars, vals):
    ax.text(b.get_x() + b.get_width() / 2, v + 0.6,
            f"{v:.0f}%\n({int(v/100*EINDHOVEN_BEVS):,})",
            ha="center", fontweight="bold", fontsize=9.5)
ax.set_ylabel("Share of Eindhoven BEVs")
ax.yaxis.set_major_formatter(pct)
ax.set_ylim(0, max(vals) * 1.3)
ax.set_title(f"Eindhoven EV segments for the stop/resume middleware\n"
             f"(estimated base of{EINDHOVEN_BEVS:,} BEVs)", fontsize=11)
fig.tight_layout()
fig.savefig(os.path.join(PLOTS, "p42_mw_segments.png"), dpi=150)
plt.close(fig)

# ---- p43: addressable-market funnel ----
fig, ax = plt.subplots(figsize=(7.8, 4.0))
stages = ["All BEVs", "Home/private\ncharging", "Not already\nsmart",
          "Core middleware\nmarket"]
counts = [EINDHOVEN_BEVS, int(df.home.mean() * EINDHOVEN_BEVS),
          int(df.needs_mw.mean() * EINDHOVEN_BEVS),
          int(df.needs_mw.mean() * EINDHOVEN_BEVS)]
ax.barh(range(len(stages)), counts,
        color=[C_GREY, C_BLUE, C_ORANGE, C_ORANGE], edgecolor="white")
ax.set_yticks(range(len(stages)))
ax.set_yticklabels(stages, fontsize=9.5)
for i, c in enumerate(counts):
    ax.text(c + 150, i, f"{c:,}", va="center", fontweight="bold", fontsize=9.5)
ax.set_xlabel("Number of EVs")
ax.invert_yaxis()
ax.set_title("Addressable-market funnel for the middleware", fontsize=11)
fig.tight_layout()
fig.savefig(os.path.join(PLOTS, "p43_mw_funnel.png"), dpi=150)
plt.close(fig)

# ---- p44: sensitivity — needs-middleware vs smart-wallbox adoption ----
fig, ax = plt.subplots(figsize=(7.6, 4.0))
box_grid = np.linspace(0.2, 0.8, 13)
need_share = []
for pb in box_grid:
    d = simulate(p_box=pb)
    need_share.append(d.needs_mw.mean() * 100)
ax.plot(box_grid * 100, need_share, color=C_ORANGE, lw=2.5, marker="o")
ax.axvline(P_SMART_WALLBOX * 100, color=C_RED, ls="--", lw=1.5,
           label=f"Base case: {P_SMART_WALLBOX*100:.0f}% smart wallbox")
ax.set_xlabel("Smart-wallbox adoption among home chargers (%)")
ax.set_ylabel("Needs-middleware share (%)")
ax.yaxis.set_major_formatter(pct)
ax.set_title("As smart wallboxes spread, the middleware market\n"
             "shrinks, hence the connector-app market grows. Both need our software.",
             fontsize=11)
ax.legend(frameon=False, fontsize=9)
fig.tight_layout()
fig.savefig(os.path.join(PLOTS, "p44_mw_sensitivity.png"), dpi=150)
plt.close(fig)

print("\nPlots saved:")
print(f"  {PLOTS}/p42_mw_segments.png")
print(f"  {PLOTS}/p43_mw_funnel.png")
print(f"  {PLOTS}/p44_mw_sensitivity.png")
