"""
Smart EV Charging — Team 12 — REVISION
Part 1B: Real Ember hourly NL day-ahead prices, 2015–2025.

Replaces the synthetic hourly profile from the v1 report.
Data source: Ember Climate (https://ember-climate.org/data/data-tools/european-wholesale-electricity-price-data/)
File: Netherlands.csv (~96k hourly rows, UTC + Local timestamps).

Tasks:
  1. Load & sanity-check the data (duplicates, missing hours, value-broadcast).
  2. Compute realised hourly profile per year and 2023–2025 mean.
  3. Compare to v1 synthetic profile (validation).
  4. Identify cheap windows by season, weekday/weekend.
  5. Quantify "savings ceiling" — best 25% of hours vs daily mean.
  6. Export real_hourly_profile_v2.csv for downstream simulation.
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
PLOT_DIR = "/home/claude/work/plots_v2"
os.makedirs(PLOT_DIR, exist_ok=True)
PRIMARY = "#1f77b4"; ACCENT = "#2ca02c"; WARN = "#d62728"; GREY = "#7f7f7f"; ORANGE = "#ff9900"

# ---- Load -----------------------------------------------------------
df = pd.read_csv("/mnt/user-data/uploads/Netherlands.csv")
df["ts_utc"] = pd.to_datetime(df["Datetime (UTC)"])
df["ts_local"] = pd.to_datetime(df["Datetime (Local)"])
df = df.rename(columns={"Price (EUR/MWhe)": "price_eur_mwh"})
df["price_eur_kwh"] = df["price_eur_mwh"] / 1000.0
df["hour"] = df["ts_local"].dt.hour
df["dow"] = df["ts_local"].dt.dayofweek  # 0=Mon
df["month"] = df["ts_local"].dt.month
df["year"] = df["ts_local"].dt.year
df["date"] = df["ts_local"].dt.date

print(f"Rows: {len(df):,}")
print(f"Date range: {df['ts_local'].min()} → {df['ts_local'].max()}")
print(f"Unique years: {sorted(df['year'].unique())}")

# ---- Sanity check: detect "broadcast" days (same price 24h in a row) ----
day_var = df.groupby("date")["price_eur_mwh"].std()
broadcast_days = (day_var == 0).sum()
total_days = len(day_var)
print(f"\nDays where all 24 hours have identical price (broadcast): "
      f"{broadcast_days:,} of {total_days:,} ({broadcast_days/total_days*100:.1f}%)")
years_per_year = df[df["date"].isin(day_var[day_var == 0].index)].groupby("year").size() / 24
print("Broadcast days per year:")
print(years_per_year.round(0).astype(int))

# Conclusion: Early years (2015-2018) likely have many broadcast days because Ember
# back-filled them from daily data. For the *hourly profile* we should focus on
# years where sub-daily variation is genuine — typically 2019 onwards.
genuine = df[~df["date"].isin(day_var[day_var == 0].index)]
print(f"\nRows with genuine intra-day variation: {len(genuine):,} ({len(genuine)/len(df)*100:.1f}%)")

# ---- Year-by-year hourly profile -----------------------------------
years_to_plot = [2019, 2020, 2021, 2022, 2023, 2024, 2025]
fig, ax = plt.subplots(figsize=(10, 5))
cmap = plt.cm.viridis(np.linspace(0.15, 0.92, len(years_to_plot)))
for c, yr in zip(cmap, years_to_plot):
    sub = genuine[genuine["year"] == yr]
    if len(sub) == 0:
        continue
    prof = sub.groupby("hour")["price_eur_mwh"].mean()
    ax.plot(prof.index, prof.values, "o-", color=c, lw=2,
            markersize=4, label=f"{yr} (n={len(sub):,}h)")
ax.set_xticks(range(0, 24, 2))
ax.set_xlabel("Hour of day (local)")
ax.set_ylabel("Mean price (EUR / MWh)")
ax.set_title("NL day-ahead hourly profile by year — Ember real data")
ax.legend(loc="upper left", frameon=False, fontsize=9)
fig.savefig(f"{PLOT_DIR}/v2_p1_hourly_by_year.png")
plt.close(fig)

# ---- 2023-2025 representative profile (normalized + absolute) -----
recent = genuine[genuine["year"] >= 2023]
print(f"\n2023-2025 genuine hours: {len(recent):,}")
hour_mean = recent.groupby("hour")["price_eur_mwh"].mean()
hour_median = recent.groupby("hour")["price_eur_mwh"].median()
hour_p25 = recent.groupby("hour")["price_eur_mwh"].quantile(0.25)
hour_p75 = recent.groupby("hour")["price_eur_mwh"].quantile(0.75)
print("\nRecent hourly mean (EUR/MWh):")
print(hour_mean.round(1).to_string())

# Plot with IQR band
fig, ax = plt.subplots(figsize=(10, 4.4))
ax.fill_between(hour_mean.index, hour_p25, hour_p75, color=PRIMARY, alpha=0.18,
                label="25–75 percentile band")
ax.plot(hour_mean.index, hour_mean, "o-", color=PRIMARY, lw=2.4, label="Mean")
ax.plot(hour_median.index, hour_median, "s--", color=WARN, lw=1.6, label="Median")

# Mark cheap and peak quartiles
overall_mean = hour_mean.mean()
ax.axhline(overall_mean, color=GREY, ls=":", lw=1, alpha=0.7, label=f"24h average")
cheap_thr = hour_mean.quantile(0.25); peak_thr = hour_mean.quantile(0.75)
ax.axhspan(0, cheap_thr, color=ACCENT, alpha=0.06)
ax.axhspan(peak_thr, hour_mean.max() * 1.1, color=WARN, alpha=0.06)

ax.set_xticks(range(0, 24, 2))
ax.set_xlabel("Hour of day (Europe/Amsterdam)")
ax.set_ylabel("Price (EUR / MWh)")
ax.set_title("NL real hourly price profile, 2023–2025 (Ember data, genuine days only)")
ax.legend(loc="upper left", frameon=False, fontsize=9)
fig.savefig(f"{PLOT_DIR}/v2_p2_recent_profile.png")
plt.close(fig)

# Cheapest / most-expensive hours
sorted_hours = hour_mean.sort_values()
print(f"\n6 cheapest hours: {sorted_hours.head(6).index.tolist()}  "
      f"(mean €{sorted_hours.head(6).mean():.1f}/MWh)")
print(f"6 most expensive: {sorted_hours.tail(6).index.tolist()}  "
      f"(mean €{sorted_hours.tail(6).mean():.1f}/MWh)")
print(f"Peak/trough ratio (mean): {hour_mean.max() / hour_mean.min():.2f}×")

# ---- Compare real vs synthetic v1 profile -------------------------
synth = pd.read_csv("/home/claude/work/synthetic_hourly_profile.csv")
# Re-normalise both to mean = 1.0 for shape comparison
real_norm = hour_mean / hour_mean.mean()
synth_norm = (synth["eur_per_mwh"] / synth["eur_per_mwh"].mean()).values

fig, ax = plt.subplots(figsize=(10, 4.4))
ax.plot(range(24), real_norm, "o-", color=PRIMARY, lw=2.4, markersize=6,
        label=f"Real (Ember 2023–25, n={len(recent):,}h)")
ax.plot(range(24), synth_norm, "s--", color=WARN, lw=2, markersize=5,
        label="Synthetic (v1 report shape)")
ax.axhline(1.0, color=GREY, ls=":", lw=1)
ax.set_xticks(range(0, 24, 2))
ax.set_xlabel("Hour of day")
ax.set_ylabel("Price ratio (mean = 1.0)")
ax.set_title("Validation: synthetic profile vs. real Ember data")
ax.legend(loc="upper left", frameon=False)
# Annotate the agreement
mae = np.mean(np.abs(real_norm.values - synth_norm))
ax.text(0.98, 0.05, f"Mean abs. error = {mae:.3f}",
        transform=ax.transAxes, ha="right", fontsize=9,
        bbox=dict(facecolor="white", edgecolor="grey", alpha=0.85))
fig.savefig(f"{PLOT_DIR}/v2_p3_real_vs_synth.png")
plt.close(fig)
print(f"\nReal vs synthetic shape — mean abs error: {mae:.3f} (lower = better match)")

# ---- Seasonality: hourly profile by season ------------------------
def season(month):
    return ("DJF" if month in (12, 1, 2) else
            "MAM" if month in (3, 4, 5) else
            "JJA" if month in (6, 7, 8) else "SON")

recent2 = recent.copy()
recent2["season"] = recent2["month"].map(season)
fig, ax = plt.subplots(figsize=(10, 4.4))
season_colors = {"DJF": "#1f77b4", "MAM": "#2ca02c", "JJA": "#d62728", "SON": "#ff9900"}
for s, col in season_colors.items():
    sub = recent2[recent2["season"] == s]
    prof = sub.groupby("hour")["price_eur_mwh"].mean()
    ax.plot(prof.index, prof.values, "o-", color=col, lw=2, markersize=5,
            label=f"{s} (n={len(sub):,}h)")
ax.set_xticks(range(0, 24, 2))
ax.set_xlabel("Hour of day")
ax.set_ylabel("Mean price (EUR / MWh)")
ax.set_title("Hourly profile by season, 2023–2025")
ax.legend(loc="upper left", frameon=False, fontsize=9)
fig.savefig(f"{PLOT_DIR}/v2_p4_seasonal_profile.png")
plt.close(fig)

# Print solar-driven midday dip emergence
summer = recent2[recent2["season"] == "JJA"].groupby("hour")["price_eur_mwh"].mean()
winter = recent2[recent2["season"] == "DJF"].groupby("hour")["price_eur_mwh"].mean()
print(f"\nSummer midday (12-14h) mean: €{summer.loc[12:14].mean():.1f}/MWh")
print(f"Winter midday (12-14h) mean: €{winter.loc[12:14].mean():.1f}/MWh")
print(f"Summer evening (18-20h) mean: €{summer.loc[18:20].mean():.1f}/MWh")
print(f"Winter evening (18-20h) mean: €{winter.loc[18:20].mean():.1f}/MWh")
print("⇒ Summer shows much more pronounced midday solar dip.")

# ---- Negative-price hours ------------------------------------------
neg = df[df["price_eur_mwh"] < 0]
print(f"\nNegative-price hours total: {len(neg):,} ({len(neg)/len(df)*100:.2f}%)")
neg_yr = neg.groupby("year").size()
print("By year:")
print(neg_yr.to_string())

fig, ax = plt.subplots(figsize=(8, 4))
ax.bar(neg_yr.index, neg_yr.values, color=ACCENT)
ax.set_xlabel("Year")
ax.set_ylabel("Hours with price < €0/MWh")
ax.set_title("Negative-price hours per year — the smart-charging gift")
fig.savefig(f"{PLOT_DIR}/v2_p5_negative_hours.png")
plt.close(fig)

# ---- Day-of-week × hour heatmap ------------------------------------
dow_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
pivot = recent.groupby(["dow", "hour"])["price_eur_mwh"].mean().unstack()
fig, ax = plt.subplots(figsize=(10, 4))
im = ax.imshow(pivot.values, aspect="auto", cmap="YlOrRd")
ax.set_yticks(range(7)); ax.set_yticklabels(dow_labels)
ax.set_xticks(range(0, 24, 2)); ax.set_xticklabels(range(0, 24, 2))
ax.set_xlabel("Hour of day")
ax.set_title("Mean price (EUR/MWh) — Day-of-week × Hour, 2023–2025")
ax.grid(False)
cb = fig.colorbar(im, ax=ax); cb.set_label("EUR/MWh")
fig.savefig(f"{PLOT_DIR}/v2_p6_dow_hour_heatmap.png")
plt.close(fig)

# ---- Savings ceiling: best 25% of hours vs daily mean -------------
# For each day, compute the mean price of its cheapest 6 hours vs the full day mean.
def cheap_vs_full(grp):
    if len(grp) < 24:
        return np.nan
    return grp.nsmallest(6).mean() / grp.mean()

per_day = genuine.groupby("date")["price_eur_mwh"].apply(cheap_vs_full).dropna()
print(f"\nSavings ceiling — ratio of cheapest 6 hours to daily mean:")
print(per_day.describe().round(3))
print(f"Mean: shifting all charging to the 6 cheapest hours saves "
      f"{(1 - per_day.mean())*100:.1f}% relative to flat-rate charging.")

# Export the real recent profile for the simulation
out = pd.DataFrame({
    "hour": hour_mean.index,
    "price_eur_mwh_mean": hour_mean.values,
    "price_eur_mwh_median": hour_median.values,
    "price_eur_kwh_mean": (hour_mean / 1000).values,
})
out.to_csv("/home/claude/work/real_hourly_profile_v2.csv", index=False)

# Also export the full hourly history for the new Monte Carlo
hist = genuine[["ts_local", "year", "month", "dow", "hour", "price_eur_mwh", "price_eur_kwh"]]
hist.to_csv("/home/claude/work/nl_hourly_real_2015_2025.csv", index=False)

print(f"\n✓ Part 1B done. Plots in {PLOT_DIR}")
print(f"  Real hourly profile saved to /home/claude/work/real_hourly_profile_v2.csv")
print(f"  Full hourly history saved to /home/claude/work/nl_hourly_real_2015_2025.csv")
