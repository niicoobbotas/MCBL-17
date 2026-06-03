"""
Part 2: Grid congestion in Eindhoven (where & when stressed).

Inputs:
  - eindhoven_zonal_load.csv : hourly demand per zone (Z1..Z10), 7 days
  - congestie_pc6.csv        : TenneT/Enexis congestion code per PC6 postcode
  - tennetgebieden.csv       : capacity vs. requested transport, per region
  - voedingsgebieden.csv     : feeder-area capacity, queue, resolution year
  - projecten.csv            : grid reinforcement projects
"""
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

PLOT_DIR = "/home/claude/work/plots"
os.makedirs(PLOT_DIR, exist_ok=True)

PRIMARY = "#1f77b4"; ACCENT = "#2ca02c"; WARN = "#d62728"; GREY = "#7f7f7f"
plt.rcParams.update({
    "figure.dpi": 130, "savefig.dpi": 160, "savefig.bbox": "tight",
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25, "axes.titleweight": "bold",
})

# ---- A. Hourly zonal load -----------------------------------------------
zl = pd.read_csv("/mnt/user-data/uploads/eindhoven_zonal_load.csv")
zl["timestamp"] = pd.to_datetime(zl["timestamp"], format="%m/%d/%Y %H:%M")
zl["hour"] = zl["timestamp"].dt.hour
zl["dow"] = zl["timestamp"].dt.dayofweek
print(f"Zonal load rows: {len(zl)}  period: {zl['timestamp'].min()} → {zl['timestamp'].max()}")
print("Zones:", sorted(zl["zone_id"].unique()))

# City-wide hourly profile, averaged over the week
total = zl.groupby("timestamp")["demand_MW"].sum().reset_index()
total["hour"] = total["timestamp"].dt.hour
hourly_avg = total.groupby("hour")["demand_MW"].mean()
hourly_p90 = total.groupby("hour")["demand_MW"].quantile(0.9)

fig, ax = plt.subplots(figsize=(9, 4))
ax.plot(hourly_avg.index, hourly_avg.values, "o-", color=PRIMARY, lw=2.4,
        markersize=6, label="Mean")
ax.fill_between(hourly_avg.index,
                total.groupby("hour")["demand_MW"].quantile(0.1),
                hourly_p90, color=PRIMARY, alpha=0.18, label="10–90 percentile")
peak_h = int(hourly_avg.idxmax()); trough_h = int(hourly_avg.idxmin())
ax.axvspan(17, 21, color=WARN, alpha=0.10, label="Evening peak (17–21h)")
ax.axvspan(1, 5, color=ACCENT, alpha=0.10, label="Night valley (01–05h)")
ax.set_xticks(range(0, 24, 2))
ax.set_xlabel("Hour of day")
ax.set_ylabel("Total demand (MW)")
ax.set_title(f"Eindhoven city-wide load — peak at {peak_h:02d}:00, "
             f"trough at {trough_h:02d}:00")
ax.legend(loc="upper left", frameon=False, fontsize=8)
fig.savefig(f"{PLOT_DIR}/p7_eindhoven_hourly_load.png")
plt.close(fig)

peak_mw = hourly_avg.max(); trough_mw = hourly_avg.min()
print(f"Peak: {peak_mw:.0f} MW @ {peak_h:02d}:00  |  Trough: {trough_mw:.0f} MW @ {trough_h:02d}:00")
print(f"Peak/trough ratio: {peak_mw / trough_mw:.2f}x")

# Heatmap: zone × hour
pivot = zl.groupby(["zone_id", "hour"])["demand_MW"].mean().unstack()
zone_order = sorted(pivot.index, key=lambda x: int(x[1:]))
pivot = pivot.loc[zone_order]
fig, ax = plt.subplots(figsize=(10, 4.5))
im = ax.imshow(pivot.values, aspect="auto", cmap="YlOrRd", interpolation="nearest")
ax.set_yticks(range(len(pivot.index)))
ax.set_yticklabels(pivot.index)
ax.set_xticks(range(0, 24, 2))
ax.set_xticklabels(range(0, 24, 2))
ax.set_xlabel("Hour of day")
ax.set_ylabel("Zone")
ax.set_title("Mean demand per zone × hour (MW)")
ax.grid(False)
cb = fig.colorbar(im, ax=ax)
cb.set_label("MW")
fig.savefig(f"{PLOT_DIR}/p8_zone_hour_heatmap.png")
plt.close(fig)

# Per-zone peak/trough
zsum = zl.groupby(["zone_id", "hour"])["demand_MW"].mean().unstack()
zone_peaks = zsum.max(axis=1).sort_values(ascending=False)
print("\nTop-3 zones by mean peak:")
print(zone_peaks.head(3).round(0))

# ---- B. TenneT regional headroom ---------------------------------------
tg = pd.read_csv("/mnt/user-data/uploads/tennetgebieden.csv", sep=";", decimal=",")
# Parse numeric (comma decimals already handled by decimal=",")
tg = tg.rename(columns={
    "aanwezige_transportcapaciteit_afname": "cap_demand_MW",
    "benodigde_transportcapaciteit_afname": "need_demand_MW",
    "aanwezige_transportcapaciteit_invoeding": "cap_supply_MW",
    "benodigde_transportcapaciteit_invoeding": "need_supply_MW",
    "wachtrij_afname": "queue_demand_MW",
    "wachtrij_invoeding": "queue_supply_MW",
})
tg_d = tg.dropna(subset=["cap_demand_MW", "need_demand_MW"]).copy()
tg_d["headroom_pct"] = (tg_d["cap_demand_MW"] - tg_d["need_demand_MW"]) / tg_d["cap_demand_MW"] * 100
tg_d = tg_d.sort_values("headroom_pct")

# Highlight Noord-Brabant
fig, ax = plt.subplots(figsize=(8.5, 5))
colors = [WARN if "Noord-Brabant" in str(r) else
          (ACCENT if h >= 0 else GREY)
          for r, h in zip(tg_d["congestiegebied"], tg_d["headroom_pct"])]
ax.barh(tg_d["congestiegebied"], tg_d["headroom_pct"], color=colors)
ax.axvline(0, color="black", lw=0.8)
ax.set_xlabel("Demand transport headroom (%)")
ax.set_title("TenneT regional headroom — demand side\n"
             "(red = Noord-Brabant; negative = structural shortage)")
ax.invert_yaxis()
fig.savefig(f"{PLOT_DIR}/p9_tennet_headroom.png")
plt.close(fig)

nb_row = tg[tg["congestiegebied"].str.contains("Noord-Brabant", na=False)]
print("\nNoord-Brabant TenneT region:")
print(nb_row[["congestiegebied", "cap_demand_MW", "need_demand_MW",
              "queue_demand_MW", "jaartal_opgelost_afname"]].to_string(index=False))

# ---- C. PC6 congestion status, Eindhoven (PC6 starting with 56xx) ------
pc6 = pd.read_csv("/mnt/user-data/uploads/congestie_pc6.csv", sep=";", decimal=",")
pc6["pc4"] = pc6["postcode"].str[:4]
ehv = pc6[pc6["pc4"].str.startswith("56")].copy()
print(f"\nEindhoven (5600-range) PC6 entries: {len(ehv):,}")

# Distribution of afname code per PC4 (afname = demand-side congestion code 0..3)
ehv_pc4 = ehv.groupby("pc4")["afname"].agg(["mean", "max", "count"]).reset_index()
ehv_pc4 = ehv_pc4.sort_values("mean", ascending=False)
print("\nTop-10 Eindhoven PC4 by mean demand-congestion code:")
print(ehv_pc4.head(10).to_string(index=False))

fig, ax = plt.subplots(figsize=(10, 4))
top = ehv_pc4.head(20)
colors = [WARN if v >= 2.5 else ("orange" if v >= 1.5 else ACCENT) for v in top["mean"]]
ax.bar(top["pc4"], top["mean"], color=colors)
ax.set_xlabel("Postcode-4")
ax.set_ylabel("Mean demand-congestion code (0=free → 3=fully congested)")
ax.set_title("Demand-side congestion across Eindhoven postcodes (top-20)")
ax.set_xticklabels(top["pc4"], rotation=45)
fig.savefig(f"{PLOT_DIR}/p10_ehv_pc4_congestion.png")
plt.close(fig)

# Share of Eindhoven entries per code
code_share = ehv["afname"].value_counts(normalize=True).sort_index() * 100
print("\nShare of Eindhoven PC6 by demand-congestion code (%):")
print(code_share.round(1))

# ---- D. Combine: when does congestion hit hardest? ---------------------
# Overlay city-wide hourly load with the synthetic price profile
hp = pd.read_csv("/home/claude/work/synthetic_hourly_profile.csv")
fig, ax1 = plt.subplots(figsize=(10, 4.4))
ax1.plot(hourly_avg.index, hourly_avg.values / hourly_avg.max(),
         "o-", color=PRIMARY, lw=2.4, label="Load (normalised)")
ax1.plot(hp["hour"], hp["eur_per_mwh"] / hp["eur_per_mwh"].max(),
         "s--", color=WARN, lw=2.0, label="Price (normalised)")
ax1.fill_between([17, 21], 0, 1.05, color=WARN, alpha=0.08)
ax1.fill_between([1, 5], 0, 1.05, color=ACCENT, alpha=0.10)
ax1.text(19, 0.4, "Stressed", color=WARN, ha="center", fontweight="bold")
ax1.text(3, 0.4, "Cheap & clean", color=ACCENT, ha="center", fontweight="bold")
ax1.set_xticks(range(0, 24, 2))
ax1.set_xlabel("Hour of day")
ax1.set_ylabel("Normalised value (max = 1.0)")
ax1.set_ylim(0, 1.1)
ax1.set_title("Load and price move together — the smart-charging opportunity")
ax1.legend(loc="lower right", frameon=False)
fig.savefig(f"{PLOT_DIR}/p11_load_vs_price.png")
plt.close(fig)

# Save congestion summary stats
summary = {
    "peak_load_MW": peak_mw,
    "trough_load_MW": trough_mw,
    "peak_hour": peak_h,
    "trough_hour": trough_h,
    "peak_to_trough_ratio": peak_mw / trough_mw,
    "share_ehv_pc6_congestion_code_2_or_3": (ehv["afname"] >= 2).mean(),
    "share_ehv_pc6_fully_congested": (ehv["afname"] == 3).mean(),
}
pd.Series(summary).to_csv("/home/claude/work/congestion_stats.csv")
print("\nKey congestion stats:")
for k, v in summary.items():
    print(f"  {k}: {v:.3f}")
print("\n✓ Part 2 done.")
