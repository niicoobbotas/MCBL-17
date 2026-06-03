"""
Part 3: Smart vs uncontrolled charging — algorithm + simulation.

ALGORITHM (Cost-Aware Constrained Charging Scheduler, CACCS)
============================================================
Given:
    H ∈ {0..23}            hours of a 24h scheduling window
    p_h                    forecast €/kWh price for hour h
    L_h                    forecast grid load (or congestion proxy) for hour h
    L_cap                  local grid cap (kW) beyond which we throttle
    P_max                  charger max power (kW)
    η                      charger efficiency (≈ 0.92)
    E_req                  energy needed to reach target SoC (kWh)
    [t_plug, t_dead]       plug-in and deadline hours
    α, β                   weights for cost vs congestion penalty

Find x_h ∈ [0, P_max] (charging power for hour h, kW) that minimise:
    J = Σ_h [ α · p_h · x_h / η  +  β · max(0, L_h + x_h − L_cap)² ]
subject to:
    Σ_h x_h ≥ E_req           (energy must be delivered)
    x_h = 0  for h ∉ [t_plug, t_dead]
    0 ≤ x_h ≤ P_max

IMPLEMENTATION
==============
For β = 0 the problem is a linear knapsack: rank eligible hours by price,
fill from cheapest until E_req is met. With β > 0 it becomes a small
quadratic program; we solve it with a fast greedy-with-penalty heuristic
that adds power to the (price + marginal congestion penalty)-cheapest hour
in 0.25 kWh increments. For a 24h window this terminates in <1 ms.

Three policies compared:
    UNCONTROLLED  — start charging at plug-in, full power until done
    PRICE-ONLY    — α=1, β=0 (current "smart" status quo)
    SMART (CACCS) — α=1, β>0  (our proposal)
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

# ---- Inputs from earlier analyses --------------------------------------
hp = pd.read_csv("/home/claude/work/synthetic_hourly_profile.csv")
price_kwh = hp["eur_per_kwh"].values  # 24 values
# Add typical retail markup so numbers reflect what users pay
# Dutch dynamic-tariff retail = wholesale + energy-tax + supplier margin
RETAIL_MARKUP = 0.18  # €/kWh, roughly 2025 Dutch dyn-tariff overhead
retail_kwh = price_kwh + RETAIL_MARKUP

# Eindhoven aggregate load (mean over week, by hour, in MW)
zl = pd.read_csv("/mnt/user-data/uploads/eindhoven_zonal_load.csv")
zl["timestamp"] = pd.to_datetime(zl["timestamp"], format="%m/%d/%Y %H:%M")
zl["hour"] = zl["timestamp"].dt.hour
total = zl.groupby("timestamp")["demand_MW"].sum().reset_index()
total["hour"] = total["timestamp"].dt.hour
load_MW = total.groupby("hour")["demand_MW"].mean().values  # 24 values

# Use load as a congestion proxy normalised to [0,1]
L_norm = (load_MW - load_MW.min()) / (load_MW.max() - load_MW.min())


# =========================================================================
# Scheduler implementations
# =========================================================================
def schedule_uncontrolled(E_req, P_max, eta, t_plug, t_dead):
    """Start at plug-in, charge at P_max until E_req delivered."""
    n = t_dead + 1
    x = np.zeros(n)
    remaining = E_req
    for h in range(t_plug, t_dead + 1):
        if remaining <= 0:
            break
        battery_add = min(P_max * eta, remaining)
        x[h] = battery_add / eta  # grid draw
        remaining -= battery_add
    return x


def schedule_price_only(E_req, P_max, eta, t_plug, t_dead, p):
    """Greedy fill from cheapest eligible hour."""
    n = t_dead + 1
    x = np.zeros(n)
    hours = list(range(t_plug, t_dead + 1))
    order = sorted(hours, key=lambda h: p[h])
    remaining = E_req
    for h in order:
        if remaining <= 0:
            break
        battery_add = min(P_max * eta, remaining)
        x[h] = battery_add / eta
        remaining -= battery_add
    return x


def schedule_smart(E_req, P_max, eta, t_plug, t_dead, p, L, L_cap,
                   alpha=1.0, beta=0.6, step=0.25):
    """
    Greedy heuristic for J = Σ [α·p_h·x_h/η + β·max(0, L_h + x_h − L_cap)²].
    Add `step` kWh of battery energy at a time to the hour with the
    lowest marginal cost (price + congestion penalty derivative).
    """
    n = t_dead + 1
    x = np.zeros(n)  # kW per hour (= kWh per hour since Δt = 1h)
    hours = np.array(range(t_plug, t_dead + 1))
    remaining = E_req
    while remaining > 1e-6:
        chunk = min(step, remaining)
        delta_grid = chunk / eta  # extra grid draw to add this chunk
        best_h, best_cost = None, np.inf
        for h in hours:
            new_x = x[h] + delta_grid
            if new_x > P_max + 1e-6:
                continue
            # marginal cost = price·delta_grid + β·[penalty(L+new_x) − penalty(L+x_h)]
            old_pen = max(0.0, L[h] + x[h] - L_cap) ** 2
            new_pen = max(0.0, L[h] + new_x - L_cap) ** 2
            cost = alpha * p[h] * delta_grid + beta * (new_pen - old_pen)
            if cost < best_cost:
                best_cost, best_h = cost, h
        if best_h is None:
            break  # infeasible (window too short)
        x[best_h] += delta_grid
        remaining -= chunk
    return x


def cost_kwh_to_user(x, p):
    """User pays grid draw × price per kWh."""
    return float(np.sum(x * p))


def peak_added(x, L):
    """Max grid load addition during peak (17–21h)."""
    peak_hours = [17, 18, 19, 20, 21]
    return float(max(x[h] for h in peak_hours))


# =========================================================================
# Single-session demo (one driver, one night)
# =========================================================================
E_req = 30.0   # kWh — typical commuter top-up
P_max = 11.0   # kW — Dutch 3-phase home wallbox
eta = 0.92
t_plug, t_dead = 18, 7 + 24  # plug in at 18:00, deadline 07:00 next day

# Build a 24h-extended price/load array (repeat for simplicity, evening + morning)
p_ext = np.concatenate([retail_kwh, retail_kwh])  # 48 hours
L_ext = np.concatenate([load_MW, load_MW]) / 1000.0  # GW

# For the schedulers we use 24-slot arrays that span hours 18..(24+7)=31
# Easier: shift so the window starts at 0
window_len = t_dead - t_plug + 1  # = 14 hours
p_win = p_ext[t_plug:t_plug + window_len]
L_win = L_ext[t_plug:t_plug + window_len]
L_cap_GW = np.percentile(L_ext, 60)  # cap = 60th percentile of load
# Schedule on a 24h frame with the window remapped to [0, window_len-1]
# The 48-slot timeline starts at plug-in (slot 0 = plug-in hour = 18:00),
# so we just copy the local schedule into the first `window_len` slots.
def reframe(scheduler, **kw):
    x_local = scheduler(E_req, P_max, eta, 0, window_len - 1,
                        p=p_win, **kw) if scheduler is not schedule_uncontrolled \
              else scheduler(E_req, P_max, eta, 0, window_len - 1)
    full = np.zeros(48)
    full[:window_len] = x_local
    return full

x_unc = reframe(schedule_uncontrolled)
x_po  = reframe(schedule_price_only)
x_sm  = reframe(lambda *a, **kw: schedule_smart(*a, **kw, L=L_win, L_cap=L_cap_GW,
                                                alpha=1.0, beta=0.6))

# Build a 48h price/load timeline that ALSO starts at plug-in (18:00).
# retail[] is indexed by clock hour 0..23; shift so index 0 = clock hour 18.
def rotate(arr, by):
    return np.concatenate([arr[by:], arr[:by]])

retail_from_plug = rotate(retail_kwh, t_plug)            # 24-vec starting at 18:00
load_from_plug   = rotate(load_MW / 1000.0, t_plug)      # GW, starting at 18:00
p_timeline = np.concatenate([retail_from_plug, retail_from_plug])  # 48 h
L_timeline = np.concatenate([load_from_plug, load_from_plug])

# Costs & peak metrics — aligned to plug-in
def total_cost(x_full): return float(np.sum(x_full * p_timeline))
# Evening peak in CLOCK time 17..21 == slots [-1, 0, 1, 2, 3] (slot 0 is 18:00,
# slot -1 wraps around). Drivers plug in at 18 so they can't charge at 17;
# practically the peak window we care about is clock 18..21 = slots 0..3.
def peak_evening(x_full): return float(max(x_full[0:4]))

results = pd.DataFrame({
    "policy": ["Uncontrolled", "Price-only", "Smart (CACCS)"],
    "cost_EUR": [total_cost(x_unc), total_cost(x_po), total_cost(x_sm)],
    "kWh_drawn": [float(x_unc.sum()), float(x_po.sum()), float(x_sm.sum())],
    "peak_kW_evening": [peak_evening(x_unc), peak_evening(x_po), peak_evening(x_sm)],
})
results["EUR_per_kWh"] = results["cost_EUR"] / (E_req)  # cost per kWh delivered to battery
results["savings_vs_unc_%"] = (1 - results["cost_EUR"] / results.loc[0, "cost_EUR"]) * 100
print("\nSingle-session results (30 kWh top-up, plug-in 18:00, deadline 07:00):")
print(results.round(3).to_string(index=False))
results.to_csv("/home/claude/work/single_session_results.csv", index=False)

# Plot the three schedules — timeline starts at plug-in (slot 0 = 18:00)
fig, axes = plt.subplots(3, 1, figsize=(10, 7), sharex=True)
labels = ["Uncontrolled", "Price-only", "Smart (CACCS)"]
colors = [WARN, "#ff9900", ACCENT]
data = [x_unc, x_po, x_sm]
for ax, lab, c, x in zip(axes, labels, colors, data):
    ax.bar(range(48), x, color=c, alpha=0.85, width=0.9)
    ax2 = ax.twinx()
    ax2.plot(range(48), p_timeline, color=GREY, lw=1.2, alpha=0.8, label="Price")
    ax2.set_ylabel("€/kWh", fontsize=8, color=GREY)
    ax2.tick_params(axis="y", labelsize=7, colors=GREY)
    ax2.grid(False)
    ax.set_ylabel("Charging\npower (kW)")
    cost = total_cost(x); pk = peak_evening(x)
    ax.set_title(f"{lab}   |   Cost €{cost:.2f}   |   evening peak {pk:.1f} kW",
                 fontsize=10)
    ax.set_ylim(0, P_max * 1.15)
    # Shade the deadline window (after slot 13 = after 07:00 the car must be ready)
    ax.axvspan(13.5, 48, color=GREY, alpha=0.08)
axes[-1].set_xlabel("Hours from plug-in (slot 0 = 18:00; deadline 07:00 next day)")
axes[-1].set_xticks(range(0, 48, 4))
axes[-1].set_xticklabels([f"{(t_plug + i) % 24:02d}:00" for i in range(0, 48, 4)])
fig.suptitle("Three charging policies on the same 30 kWh top-up "
             "(plug-in 18:00, deadline 07:00)", y=1.00,
             fontsize=12, fontweight="bold")
fig.tight_layout()
fig.savefig(f"{PLOT_DIR}/p12_three_policies.png")
plt.close(fig)


# =========================================================================
# Monte Carlo: 1000 drivers across a year
# =========================================================================
rng = np.random.default_rng(42)
N = 1000
# Sample per-driver:
#   - annual km: 12,000–18,000 (CBS NL mean ~13k)
#   - efficiency: 17–21 kWh/100km
#   - charging frequency: 1.5–3 sessions/week → ~78–156 / year
#   - per-session energy: drawn so it matches yearly km × efficiency
annual_km = rng.uniform(12_000, 18_000, N)
eff_kwh100 = rng.uniform(17, 21, N)
annual_kwh = annual_km * eff_kwh100 / 100.0
sessions = rng.integers(78, 157, N)
energy_per_session = annual_kwh / sessions  # kWh per plug-in

# Plug-in distribution — most weekday evenings 17–20, some daytime fleet users
plugin_hours = rng.choice([16, 17, 18, 19, 20, 21, 22, 7, 8],
                          size=N, p=[0.05, 0.18, 0.25, 0.20, 0.12, 0.08, 0.05, 0.04, 0.03])
# Deadline: typical 06:30–08:00, give 7 to keep integer hours
deadlines = rng.choice([6, 7, 8, 9], size=N, p=[0.20, 0.50, 0.20, 0.10])

# Price scenario: 365 days of NL realised daily mean, broadcast through hourly shape
nl = pd.read_csv("/mnt/user-data/uploads/european_wholesale_electricity_price_data_daily.csv")
nl["Date"] = pd.to_datetime(nl["Date"])
nl = nl[(nl["Country"] == "Netherlands") & (nl["Date"] >= "2024-01-01") & (nl["Date"] < "2025-01-01")]
nl_daily = nl["Price (EUR/MWhe)"].values  # ~365 days, EUR/MWh
hour_shape = (np.array([
    0.78, 0.72, 0.68, 0.66, 0.68, 0.78,
    0.95, 1.18, 1.30, 1.20, 1.05, 0.92,
    0.82, 0.75, 0.74, 0.80, 0.95, 1.25,
    1.45, 1.40, 1.20, 1.00, 0.88, 0.82,
]))
hour_shape = hour_shape / hour_shape.mean()

# Pre-build a 365×24 hourly price matrix in €/kWh (incl markup)
n_days = len(nl_daily)
hourly_year = np.outer(nl_daily, hour_shape) / 1000.0 + RETAIL_MARKUP  # EUR/kWh

# Driver-day cost simulation: each driver does `sessions[i]` random days
def simulate_driver(i, policy):
    E = energy_per_session[i]
    tp = int(plugin_hours[i])
    td = int(deadlines[i]) + 24 if int(deadlines[i]) < tp else int(deadlines[i])
    window = td - tp + 1
    if window < int(np.ceil(E / (P_max * eta))):
        # infeasible window for slow charger; skip (rare with these params)
        return np.nan, np.nan
    days = rng.choice(n_days, size=sessions[i], replace=True)
    total_cost = 0.0
    total_peak_add = 0.0
    for d in days:
        # Two-day price slice starting at plug-in
        d2 = d + 1 if d + 1 < n_days else d
        p2 = np.concatenate([hourly_year[d], hourly_year[d2]])  # 48 h
        L2 = np.concatenate([load_MW, load_MW]) / 1000.0
        p_win = p2[tp:tp + window]; L_win = L2[tp:tp + window]
        if policy == "unc":
            x_local = schedule_uncontrolled(E, P_max, eta, 0, window - 1)
        elif policy == "po":
            x_local = schedule_price_only(E, P_max, eta, 0, window - 1, p_win)
        else:
            x_local = schedule_smart(E, P_max, eta, 0, window - 1,
                                     p_win, L_win, L_cap_GW,
                                     alpha=1.0, beta=0.6)
        full = np.zeros(48); full[tp:tp + window] = x_local
        total_cost += np.sum(full * p2)
        total_peak_add += float(max(full[17:22]))  # evening peak power
    return total_cost, total_peak_add / sessions[i]  # avg evening peak per session

print(f"\nRunning Monte Carlo: {N} drivers × ~120 sessions each…")
records = []
for i in range(N):
    c_u, pk_u = simulate_driver(i, "unc")
    c_p, pk_p = simulate_driver(i, "po")
    c_s, pk_s = simulate_driver(i, "smart")
    if np.isnan(c_u): continue
    records.append({
        "driver": i, "annual_kWh": annual_kwh[i], "sessions": sessions[i],
        "cost_unc": c_u, "cost_po": c_p, "cost_smart": c_s,
        "peak_unc": pk_u, "peak_po": pk_p, "peak_smart": pk_s,
    })
mc = pd.DataFrame(records)
mc["savings_po_eur"] = mc["cost_unc"] - mc["cost_po"]
mc["savings_smart_eur"] = mc["cost_unc"] - mc["cost_smart"]
mc["savings_po_pct"] = mc["savings_po_eur"] / mc["cost_unc"] * 100
mc["savings_smart_pct"] = mc["savings_smart_eur"] / mc["cost_unc"] * 100
# Peak-drop only meaningful for drivers who would have charged during peak hours
peak_mask = mc["peak_unc"] > 0.1
mc["peak_drop_smart_pct"] = np.where(
    peak_mask,
    (1 - mc["peak_smart"] / mc["peak_unc"]) * 100,
    np.nan,
)

print("\nAnnual cost per driver (€):")
print(mc[["cost_unc", "cost_po", "cost_smart"]].describe().round(0))
print("\nSavings vs uncontrolled (%):")
print(mc[["savings_po_pct", "savings_smart_pct"]].describe().round(2))
print("\nEvening-peak charging power per session (kW):")
print(mc[["peak_unc", "peak_po", "peak_smart"]].describe().round(2))
print("\nMean evening-peak drop, Smart vs Unc: "
      f"{mc['peak_drop_smart_pct'].mean():.1f}%")

mc.to_csv("/home/claude/work/monte_carlo_results.csv", index=False)

# Histogram of annual savings
fig, axes = plt.subplots(1, 2, figsize=(12, 4))
axes[0].hist(mc["savings_po_eur"], bins=40, color="#ff9900", alpha=0.7,
             label=f"Price-only (μ=€{mc['savings_po_eur'].mean():.0f})")
axes[0].hist(mc["savings_smart_eur"], bins=40, color=ACCENT, alpha=0.7,
             label=f"Smart (μ=€{mc['savings_smart_eur'].mean():.0f})")
axes[0].axvline(0, color="black", lw=0.8)
axes[0].set_xlabel("Annual savings vs uncontrolled (€)")
axes[0].set_ylabel("Number of drivers")
axes[0].set_title("Distribution of annual € savings (N=1000)")
axes[0].legend(frameon=False)

axes[1].hist(mc["peak_unc"], bins=30, color=WARN, alpha=0.6,
             label=f"Uncontrolled (μ={mc['peak_unc'].mean():.1f} kW)")
axes[1].hist(mc["peak_smart"], bins=30, color=ACCENT, alpha=0.6,
             label=f"Smart (μ={mc['peak_smart'].mean():.1f} kW)")
axes[1].set_xlabel("Avg evening-peak charging power per session (kW)")
axes[1].set_ylabel("Number of drivers")
axes[1].set_title("Peak-hour grid pressure: Smart vs Uncontrolled")
axes[1].legend(frameon=False)
fig.tight_layout()
fig.savefig(f"{PLOT_DIR}/p13_monte_carlo.png")
plt.close(fig)

# Aggregate KPI summary
kpis = {
    "n_drivers_simulated": len(mc),
    "mean_annual_cost_unc_EUR": mc["cost_unc"].mean(),
    "mean_annual_cost_po_EUR": mc["cost_po"].mean(),
    "mean_annual_cost_smart_EUR": mc["cost_smart"].mean(),
    "mean_savings_po_pct": mc["savings_po_pct"].mean(),
    "mean_savings_smart_pct": mc["savings_smart_pct"].mean(),
    "mean_savings_smart_EUR": mc["savings_smart_eur"].mean(),
    "median_savings_smart_EUR": mc["savings_smart_eur"].median(),
    "mean_peak_drop_smart_pct": mc["peak_drop_smart_pct"].mean(skipna=True),
    "n_evening_pluggers": int(peak_mask.sum()),
    "share_drivers_save_smart": (mc["savings_smart_eur"] > 0).mean(),
}
pd.Series(kpis).to_csv("/home/claude/work/kpi_summary.csv")
print("\n=== Headline KPIs for the report ===")
for k, v in kpis.items():
    print(f"  {k}: {v:.2f}")
print("\n✓ Part 3 done.")
