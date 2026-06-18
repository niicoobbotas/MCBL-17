"""
Smart EV Charging — Team 12
Part 11: Extended Monte Carlo Plots
----------------------------------------------------------------------

Reads:
  - results/databases/10_mc_extended/monte_carlo_extended.csv
----------------------------------------------------------------------
Outputs:
  - plots/p38_mc_ext_value_distribution.png
  - plots/p39_mc_ext_by_policy.png
  - plots/p40_mc_ext_vs_solar_size.png
  - plots/p41_mc_ext_sc_by_location.png
"""
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

plt.rcParams.update({
    "figure.dpi": 130, "savefig.dpi": 160, "savefig.bbox": "tight",
    "font.family": "DejaVu Sans",
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25, "axes.titleweight": "bold",
})

PRIMARY = "#1f77b4"; ACCENT = "#2ca02c"; WARN = "#d62728"
GREY = "#7f7f7f"; ORANGE = "#ff9900"

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_V2_DIR = os.path.join(BASE, "..", "results", "databases")
OUT = os.path.join(BASE, "..", "plots")
os.makedirs(OUT, exist_ok=True)

mc = pd.read_csv(os.path.join(DATA_V2_DIR, "10_mc_extended", "monte_carlo_extended.csv"))
n = len(mc)
print(f"Loaded MC: {n} drivers, {mc['has_solar'].sum()} solar households")

# =========================================================================
# Plot 1: Total annual value distribution — solar vs no-solar
# =========================================================================
fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))

# Left: distribution
ax = axes[0]
solar = mc[mc["has_solar"]]
nosolar = mc[~mc["has_solar"]]
ax.hist(nosolar["value_extended"], bins=40, color=GREY, alpha=0.6,
        label=f"No solar (n={len(nosolar)}, μ=€{nosolar['value_extended'].mean():.0f})")
ax.hist(solar["value_extended"], bins=40, color=ORANGE, alpha=0.65,
        label=f"With solar (n={len(solar)}, μ=€{solar['value_extended'].mean():.0f})")
ax.axvline(mc["value_extended"].mean(), color="black", ls="--", lw=1.5,
           label=f"All-driver mean: €{mc['value_extended'].mean():.0f}")
ax.set_xlabel("Total annual value per driver (€)")
ax.set_ylabel("Number of drivers")
ax.set_title("Total annual value distribution - Extended Smart CACCS")
ax.legend(loc="upper right", frameon=False, fontsize=9)

# Right: stacked composition (mean) for each group
ax = axes[1]
groups = ["No solar\n(n=" + str(len(nosolar)) + ")",
          "With solar\n(n=" + str(len(solar)) + ")",
          "All drivers\n(n=" + str(n) + ")"]
dyn_save = [(nosolar["cost_fix"] - nosolar["cost_sm_ext"]).mean(),
            (solar["cost_fix"] - solar["cost_sm_ext"]).mean(),
            (mc["cost_fix"] - mc["cost_sm_ext"]).mean()]
ere = [nosolar["ere_revenue_ext"].mean(),
       solar["ere_revenue_ext"].mean(),
       mc["ere_revenue_ext"].mean()]
sol = [nosolar["solar_value_total"].mean(),
       solar["solar_value_total"].mean(),
       mc["solar_value_total"].mean()]
x = np.arange(3)
ax.bar(x, dyn_save, color=PRIMARY, label="Dynamic-prices saving")
ax.bar(x, ere, bottom=dyn_save, color=ACCENT, label="ERE certificates")
ax.bar(x, sol, bottom=[d + e for d, e in zip(dyn_save, ere)], color=ORANGE,
       label="Solar self-consumption")
for i, total in enumerate([d + e + s for d, e, s in zip(dyn_save, ere, sol)]):
    ax.text(i, total + 8, f"€{total:.0f}", ha="center", fontweight="bold")
ax.set_xticks(x); ax.set_xticklabels(groups, fontsize=9)
ax.set_ylabel("Annual value (€)")
ax.set_title("Mean value composition by household type")
ax.legend(loc="upper left", frameon=False, fontsize=9)
ax.set_ylim(0, max([d + e + s for d, e, s in zip(dyn_save, ere, sol)]) * 1.15)
fig.tight_layout()
fig.savefig(f"{OUT}/p38_mc_ext_value_distribution.png")
plt.close(fig)
print("Saved value distribution plot")

# =========================================================================
# Plot 2: Self-consumption rate vs location
# =========================================================================
fig, ax = plt.subplots(figsize=(9, 4.5))
solar_data = solar.copy()
solar_data["pv_annual"] = solar_data["pv_kwp"] * 900
solar_data["sc_rate"] = solar_data["sc_kwh_total"] / solar_data["pv_annual"] * 100

locations = ["private", "workplace", "public"]
data_by_loc = [solar_data[solar_data["location"] == l]["sc_rate"] for l in locations]
parts = ax.boxplot(data_by_loc, labels=locations, patch_artist=True,
                    widths=0.5, medianprops=dict(color="black", lw=2))
colors = [PRIMARY, ACCENT, WARN]
for p, c in zip(parts["boxes"], colors):
    p.set_facecolor(c); p.set_alpha(0.5)
ax.set_ylabel("Solar self-consumption rate (% of PV generation)")
ax.set_xlabel("Charging location")
ax.set_title("Solar self-consumption by charging location\n"
             "(only for solar households; reflects when the car is actually plugged in)")
# Sample counts
for i, l in enumerate(locations):
    n = (solar_data["location"] == l).sum()
    ax.text(i + 1, ax.get_ylim()[1] * 0.95, f"n={n}", ha="center", fontsize=9, color=GREY)
fig.savefig(f"{OUT}/p41_mc_ext_sc_by_location.png")
plt.close(fig)
print("Saved self-consumption-by-location plot")

# =========================================================================
# Plot 3: Cost comparison — all five policies
# =========================================================================
fig, ax = plt.subplots(figsize=(10, 4.5))
policies = ["Fixed", "Uncontrolled\n(dynamic)", "Price-only", "Smart",
            "Smart extended\n(solar + ERE)"]
means = [mc["cost_fix"].mean(), mc["cost_unc"].mean(), mc["cost_po"].mean(),
          mc["cost_sm"].mean(), mc["cost_sm_ext"].mean()]
colors_p = [GREY, WARN, ORANGE, ACCENT, "#0a5d2e"]
bars = ax.bar(range(5), means, color=colors_p, alpha=0.85)
for b, v in zip(bars, means):
    ax.text(b.get_x() + b.get_width()/2, v + 8, f"€{v:.0f}",
            ha="center", fontweight="bold")
# Annotate savings vs Fixed
for i in range(1, 5):
    saving = means[0] - means[i]
    pct = saving / means[0] * 100
    ax.text(i, means[i] / 2, f"−€{saving:.0f}\n(−{pct:.0f}%)",
            ha="center", color="white", fontweight="bold", fontsize=10)
ax.set_xticks(range(5))
ax.set_xticklabels(policies, fontsize=10)
ax.set_ylabel("Mean annual charging cost (€)")
ax.set_title(f"Mean annual cost of five policies, N={len(mc)} Eindhoven drivers (2024)")
ax.set_ylim(0, max(means) * 1.18)
fig.savefig(f"{OUT}/p39_mc_ext_by_policy.png")
plt.close(fig)
print("Saved five-policy comparison plot")

# =========================================================================
# Plot 4: Total value vs PV size (solar households only)
# =========================================================================
fig, ax = plt.subplots(figsize=(10, 4.5))
sd = solar.sort_values("pv_kwp")
ax.scatter(sd["pv_kwp"], sd["value_extended"], color=ORANGE, alpha=0.55,
           s=30, label="Per driver")
# Trend line
from numpy.polynomial import Polynomial
p = Polynomial.fit(sd["pv_kwp"], sd["value_extended"], 1)
x_trend = np.linspace(2, 7, 50)
ax.plot(x_trend, p(x_trend), "-", color="black", lw=2, label="Linear trend")
ax.set_xlabel("PV system size (kWp)")
ax.set_ylabel("Total annual value (€)")
ax.set_title("Total annual value vs PV system size for solar households")
ax.legend(loc="upper left", frameon=False)
fig.savefig(f"{OUT}/p40_mc_ext_vs_solar_size.png")
plt.close(fig)
print("Saved value-vs-kWp plot")

# =========================================================================
# Summary table for the report
# =========================================================================
print("\n--- Summary KPIs to embed in §11.5 ---")
summary = {
    "All drivers (N=1000)": {
        "Cost Fixed":           mc["cost_fix"].mean(),
        "Cost Smart baseline":  mc["cost_sm"].mean(),
        "Cost Smart EXTENDED":  mc["cost_sm_ext"].mean(),
        "Dynamic save":         (mc["cost_fix"] - mc["cost_sm_ext"]).mean(),
        "ERE revenue":          mc["ere_revenue_ext"].mean(),
        "Solar value":          mc["solar_value_total"].mean(),
        "TOTAL value":          mc["value_extended"].mean(),
    },
    "Solar households (n=406)": {
        "Cost Fixed":           solar["cost_fix"].mean(),
        "Cost Smart EXTENDED":  solar["cost_sm_ext"].mean(),
        "Dynamic save":         (solar["cost_fix"] - solar["cost_sm_ext"]).mean(),
        "ERE revenue":          solar["ere_revenue_ext"].mean(),
        "Solar value":          solar["solar_value_total"].mean(),
        "TOTAL value":          solar["value_extended"].mean(),
        "Self-consumed kWh":    solar["sc_kwh_total"].mean(),
    },
    "No-solar households (n=594)": {
        "Cost Fixed":           nosolar["cost_fix"].mean(),
        "Cost Smart EXTENDED":  nosolar["cost_sm_ext"].mean(),
        "Dynamic save":         (nosolar["cost_fix"] - nosolar["cost_sm_ext"]).mean(),
        "ERE revenue":          nosolar["ere_revenue_ext"].mean(),
        "TOTAL value":          nosolar["value_extended"].mean(),
    },
}
for grp, vals in summary.items():
    print(f"\n{grp}:")
    for k, v in vals.items():
        print(f"  {k:<30}  €{v:>6.0f}")

print(f"\nPeak-hour relief: baseline {(1 - mc['peak_kwh_sm'] / mc['peak_kwh_unc']).where(mc['peak_kwh_unc'] > 0.1, np.nan).mean(skipna=True)*100:.0f}%, "
      f"extended {(1 - mc['peak_kwh_sm_ext'] / mc['peak_kwh_unc']).where(mc['peak_kwh_unc'] > 0.1, np.nan).mean(skipna=True)*100:.0f}%")
