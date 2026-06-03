"""
Smart EV Charging — Team 12
Part 1: Electricity price patterns (cheap windows, volatility)

Data: Ember European wholesale day-ahead prices (daily + monthly), 2015–2025.
Why daily, not hourly: hourly Ember data wasn't provided in the package, but
we can still characterise:
  - long-run price level & volatility (the savings ceiling)
  - seasonality (monthly NL pattern)
  - day-of-week effects
  - cross-country comparison to anchor NL in the EU context
For the algorithm we synthesise a representative hourly profile shaped from
typical Dutch day-ahead behaviour, scaled to the actual daily average.
"""
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

plt.rcParams.update({
    "figure.dpi": 130,
    "savefig.dpi": 160,
    "savefig.bbox": "tight",
    "font.family": "DejaVu Sans",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "axes.titleweight": "bold",
})

PLOT_DIR = "/home/claude/work/plots"
os.makedirs(PLOT_DIR, exist_ok=True)

PRIMARY = "#1f77b4"
ACCENT = "#2ca02c"
WARN = "#d62728"
GREY = "#7f7f7f"

# ---- Load ---------------------------------------------------------------
daily = pd.read_csv("/mnt/user-data/uploads/european_wholesale_electricity_price_data_daily.csv")
daily["Date"] = pd.to_datetime(daily["Date"])
daily = daily.rename(columns={"Price (EUR/MWhe)": "price"})

nl = daily[daily["Country"] == "Netherlands"].copy().sort_values("Date").reset_index(drop=True)
nl["price_kwh"] = nl["price"] / 1000.0  # MWh -> kWh
nl["year"] = nl["Date"].dt.year
nl["month"] = nl["Date"].dt.month
nl["dow"] = nl["Date"].dt.dayofweek  # 0=Mon

print(f"NL daily rows: {len(nl)}  range: {nl['Date'].min().date()} → {nl['Date'].max().date()}")
print("\nSummary (EUR/MWh):")
print(nl["price"].describe().round(2))

# Save key stats
stats = {
    "mean_eur_mwh": nl["price"].mean(),
    "median_eur_mwh": nl["price"].median(),
    "std_eur_mwh": nl["price"].std(),
    "p10_eur_mwh": nl["price"].quantile(0.10),
    "p90_eur_mwh": nl["price"].quantile(0.90),
    "min_eur_mwh": nl["price"].min(),
    "max_eur_mwh": nl["price"].max(),
    "coef_var": nl["price"].std() / nl["price"].mean(),
    "share_negative_days": (nl["price"] < 0).mean(),
}
pd.Series(stats).to_csv("/home/claude/work/nl_price_stats.csv")
print("\nKey stats:")
for k, v in stats.items():
    print(f"  {k}: {v:.3f}")

# ---- Plot 1: NL price history with crisis annotation --------------------
fig, ax = plt.subplots(figsize=(11, 4.2))
ax.plot(nl["Date"], nl["price"], color=PRIMARY, lw=0.6, alpha=0.85)
roll = nl["price"].rolling(30, center=True).mean()
ax.plot(nl["Date"], roll, color=WARN, lw=1.6, label="30-day rolling mean")
ax.axhspan(0, stats["p10_eur_mwh"], color=ACCENT, alpha=0.12,
           label=f"Cheapest 10% (≤ €{stats['p10_eur_mwh']:.0f}/MWh)")
ax.set_title("Netherlands wholesale day-ahead price, 2015–2025")
ax.set_ylabel("EUR / MWh")
ax.set_xlabel("")
ax.legend(loc="upper left", frameon=False)
ax.annotate("Energy crisis\n(2021–2022)", xy=(pd.Timestamp("2022-08-01"), 500),
            xytext=(pd.Timestamp("2018-01-01"), 550),
            arrowprops=dict(arrowstyle="->", color=GREY), fontsize=9, color=GREY)
fig.savefig(f"{PLOT_DIR}/p1_nl_price_history.png")
plt.close(fig)

# ---- Plot 2: Annual mean & volatility -----------------------------------
ann = nl.groupby("year")["price"].agg(["mean", "std"]).reset_index()
fig, ax1 = plt.subplots(figsize=(8, 4))
ax1.bar(ann["year"], ann["mean"], color=PRIMARY, alpha=0.85, label="Annual mean")
ax1.set_ylabel("Mean price (EUR/MWh)", color=PRIMARY)
ax1.tick_params(axis="y", labelcolor=PRIMARY)
ax2 = ax1.twinx()
ax2.plot(ann["year"], ann["std"], "o-", color=WARN, lw=2, label="Std. dev. (volatility)")
ax2.set_ylabel("Std. dev. (EUR/MWh)", color=WARN)
ax2.tick_params(axis="y", labelcolor=WARN)
ax2.grid(False)
ax1.set_title("Annual price level and volatility — NL wholesale")
ax1.set_xticks(ann["year"])
fig.savefig(f"{PLOT_DIR}/p2_annual_mean_volatility.png")
plt.close(fig)

# ---- Plot 3: Monthly seasonality (post-crisis: 2023–2025) ---------------
recent = nl[nl["year"] >= 2023].copy()
mo = recent.groupby("month")["price"].agg(["mean", "std"]).reset_index()
fig, ax = plt.subplots(figsize=(8, 4))
ax.bar(mo["month"], mo["mean"], yerr=mo["std"], color=PRIMARY, alpha=0.85,
       capsize=4, ecolor=GREY)
ax.set_xticks(range(1, 13))
ax.set_xticklabels(["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
ax.set_title("Monthly price seasonality, NL (2023–2025)")
ax.set_ylabel("EUR / MWh (mean ± 1σ)")
fig.savefig(f"{PLOT_DIR}/p3_monthly_seasonality.png")
plt.close(fig)

# ---- Plot 4: Day-of-week pattern ----------------------------------------
dow_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
dw = recent.groupby("dow")["price"].mean().reset_index()
fig, ax = plt.subplots(figsize=(7, 3.8))
colors = [ACCENT if i >= 5 else PRIMARY for i in dw["dow"]]
ax.bar(dw["dow"], dw["price"], color=colors)
ax.set_xticks(range(7))
ax.set_xticklabels(dow_labels)
ax.set_title("Day-of-week average price, NL (2023–2025)")
ax.set_ylabel("EUR / MWh")
ax.text(5.5, dw["price"].max() * 0.95, "Weekend\n(cheaper)",
        ha="center", color=ACCENT, fontsize=9, fontweight="bold")
fig.savefig(f"{PLOT_DIR}/p4_dow_pattern.png")
plt.close(fig)

# ---- Plot 5: Cross-country comparison, recent ---------------------------
recent_eu = daily[daily["Date"] >= "2023-01-01"]
cc = recent_eu.groupby("Country")["price"].mean().sort_values()
focus = ["Netherlands", "Germany", "Belgium", "France",
         "Denmark", "Spain", "Italy", "Sweden", "Norway", "Poland"]
cc_focus = cc.reindex(focus).dropna()
fig, ax = plt.subplots(figsize=(8, 4))
colors = [WARN if c == "Netherlands" else PRIMARY for c in cc_focus.index]
ax.barh(cc_focus.index, cc_focus.values, color=colors)
ax.set_title("Mean wholesale price by country (2023–2025)")
ax.set_xlabel("EUR / MWh")
ax.invert_yaxis()
fig.savefig(f"{PLOT_DIR}/p5_country_comparison.png")
plt.close(fig)

# ---- Synthesise a representative NL hourly profile ----------------------
# Anchored to typical ENTSO-E / Dutch day-ahead shape:
#   - night trough ~02:00–05:00
#   - morning ramp peak ~07:00–09:00
#   - solar-driven midday dip ~12:00–15:00
#   - sharp evening peak ~17:00–20:00
# Shape multipliers (mean = 1.0), then scaled to the actual daily NL mean.
hour_shape = np.array([
    0.78, 0.72, 0.68, 0.66, 0.68, 0.78,  # 00–05
    0.95, 1.18, 1.30, 1.20, 1.05, 0.92,  # 06–11
    0.82, 0.75, 0.74, 0.80, 0.95, 1.25,  # 12–17
    1.45, 1.40, 1.20, 1.00, 0.88, 0.82,  # 18–23
])
hour_shape = hour_shape / hour_shape.mean()  # normalise to mean = 1

recent_mean = recent["price"].mean()
hourly_typ = hour_shape * recent_mean
hourly_df = pd.DataFrame({"hour": range(24), "eur_per_mwh": hourly_typ,
                          "eur_per_kwh": hourly_typ / 1000.0})
hourly_df.to_csv("/home/claude/work/synthetic_hourly_profile.csv", index=False)

fig, ax = plt.subplots(figsize=(9, 4))
ax.plot(range(24), hourly_typ, "o-", color=PRIMARY, lw=2.4, markersize=6)
ax.fill_between(range(24), hourly_typ, alpha=0.15, color=PRIMARY)
cheap_thr = np.percentile(hourly_typ, 25)
peak_thr = np.percentile(hourly_typ, 75)
ax.axhline(cheap_thr, color=ACCENT, ls="--", lw=1.2,
           label=f"Cheap quartile (≤ €{cheap_thr:.0f})")
ax.axhline(peak_thr, color=WARN, ls="--", lw=1.2,
           label=f"Peak quartile (≥ €{peak_thr:.0f})")
for h in range(24):
    if hourly_typ[h] <= cheap_thr:
        ax.scatter(h, hourly_typ[h], color=ACCENT, s=80, zorder=5)
    elif hourly_typ[h] >= peak_thr:
        ax.scatter(h, hourly_typ[h], color=WARN, s=80, zorder=5)
ax.set_xticks(range(0, 24, 2))
ax.set_xlabel("Hour of day")
ax.set_ylabel("EUR / MWh")
ax.set_title("Representative NL day-ahead price profile (scaled to 2023–2025 mean)")
ax.legend(loc="upper left", frameon=False)
fig.savefig(f"{PLOT_DIR}/p6_hourly_profile.png")
plt.close(fig)

print("\nCheapest 6 hours (synthetic profile):",
      sorted(np.argsort(hourly_typ)[:6].tolist()))
print("Most expensive 6 hours:",
      sorted(np.argsort(hourly_typ)[-6:].tolist()))
print(f"Peak/trough ratio: {hourly_typ.max() / hourly_typ.min():.2f}x")

print("\n✓ Part 1 done. Plots in", PLOT_DIR)
