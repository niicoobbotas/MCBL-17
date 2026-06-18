"""
Smart EV Charging — Team 12
Part 10: Extended Monte Carlo (ERE-aware + Solar-aware CACCS)
----------------------------------------------------------------------

Reads:
  - results/databases/02_prices/nl_hourly_real_2015_2025.csv
  - results/databases/04_fleet/fleet_database.json
  - results/databases/05_behavior/arrival_distributions.csv
  - datasets/dataset6/eindhoven_zonal_load.csv
----------------------------------------------------------------------
Outputs:
  - results/databases/10_mc_extended/monte_carlo_extended.csv
  - results/databases/10_mc_extended/kpi_extended.csv
"""
import json
import os
import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "..", "results", "databases")
DIR_02   = os.path.join(DB, "02_prices")
DIR_04   = os.path.join(DB, "04_fleet")
DIR_05   = os.path.join(DB, "05_behavior")
OUT_DATA = os.path.join(DB, "10_mc_extended")
os.makedirs(OUT_DATA, exist_ok=True)

# =========================================================================
# Constants
# =========================================================================
NL_TAX = 0.10154
VAT = 0.21
ENECO_DYN_MARGIN = 0.0235
ENECO_FIXED = 0.319

# ERE (NEa 2026)
ERE_FACTOR = 183 * 3.6 / 1000  # = 0.659 ERE per kWh at 100% renewable
GRID_RENEWABLE_SHARE = 0.505
ERE_PRICE = 0.30
ERE_COMMISSION = 0.18
# Net €/kWh subsidy from ERE:
ERE_GRID_EUR_KWH = ERE_FACTOR * GRID_RENEWABLE_SHARE * ERE_PRICE * (1 - ERE_COMMISSION)
ERE_SOLAR_EUR_KWH = ERE_FACTOR * 1.000 * ERE_PRICE * (1 - ERE_COMMISSION)
print(f"ERE subsidies: grid €{ERE_GRID_EUR_KWH:.4f}/kWh, solar €{ERE_SOLAR_EUR_KWH:.4f}/kWh")

# Solar (post-saldering)
FEED_IN_TARIFF = 0.07
PV_YIELD_PER_KWP = 900  # kWh/kWp/yr in NL
PV_HOUSEHOLD_PENETRATION = 0.40  # 40% of NL households have PV
PV_KWP_RANGE = (2.0, 7.0)  # typical residential system sizes

# =========================================================================
# Solar generation profile (typical day, normalised, peaks at 13:00)
# =========================================================================
def pv_profile_hourly(kwp, day_of_year):
    """
    Returns 24-element array of expected solar kWh per hour for a kWp system
    on a given day. Accounts for seasonality (lower in winter, higher in summer).
    
    Calibrated so that annual sum = kwp × PV_YIELD_PER_KWP (=900 kWh/kWp/yr).
    """
    # Seasonal factor: peak in June (day ~170), trough in December
    seasonal = 0.4 + 0.6 * np.cos(2 * np.pi * (day_of_year - 170) / 365) ** 2
    # Mean of seasonal factor across the year is ~0.7
    SEASONAL_MEAN = 0.7
    # Hourly shape: bell curve centered at 13:00
    hours = np.arange(24)
    shape = np.exp(-((hours - 13) / 3.5) ** 2)
    shape[hours < 6] = 0
    shape[hours > 20] = 0
    # Calibrate so annual sum = kwp * PV_YIELD_PER_KWP
    daily_target = kwp * PV_YIELD_PER_KWP / 365 * seasonal / SEASONAL_MEAN
    return shape / shape.sum() * daily_target

# Verify annual yield
test_kwp = 4.0
annual = sum(pv_profile_hourly(test_kwp, d).sum() for d in range(365))
print(f"4 kWp annual yield test: {annual:.0f} kWh (target {test_kwp * PV_YIELD_PER_KWP})")

# =========================================================================
# Extended schedulers
# =========================================================================
def schedule_uncontrolled(E, P_max, eta, window):
    x = np.zeros(window); rem = E
    for h in range(window):
        if rem <= 0: break
        add = min(P_max * eta, rem)
        x[h] = add / eta
        rem -= add
    return x

def schedule_price_only(E, P_max, eta, window, p_kwh):
    x = np.zeros(window); rem = E
    for h in np.argsort(p_kwh):
        if rem <= 0: break
        add = min(P_max * eta, rem)
        x[h] = add / eta
        rem -= add
    return x

def schedule_smart(E, P_max, eta, window, p_kwh, L_norm,
                   L_cap=0.6, alpha=1.0, beta=0.6, step=0.25):
    """Baseline CACCS (price + congestion penalty)."""
    x = np.zeros(window); rem = E
    while rem > 1e-6:
        chunk = min(step, rem)
        delta = chunk / eta
        best, best_c = -1, np.inf
        for h in range(window):
            if x[h] + delta > P_max + 1e-6: continue
            old_pen = max(0.0, L_norm[h] + x[h]/P_max - L_cap) ** 2
            new_pen = max(0.0, L_norm[h] + (x[h]+delta)/P_max - L_cap) ** 2
            c = alpha * p_kwh[h] * delta + beta * (new_pen - old_pen)
            if c < best_c: best_c, best = c, h
        if best < 0: break
        x[best] += delta
        rem -= chunk
    return x

def schedule_smart_extended(E, P_max, eta, window, p_kwh, L_norm, pv_kwh, retail_price,
                            L_cap=0.6, alpha=1.0, beta=0.6, step=0.25):
    """
    Solar-aware + ERE-aware CACCS.
    
    The effective price seen by the scheduler for each hour h is:
        p_eff[h] = p_kwh[h] - solar_match_value[h] - ere_subsidy[h]
    where:
      solar_match_value[h] = (retail - feed_in) per kWh, capped by available solar
      ere_subsidy[h] = ERE_GRID (or ERE_SOLAR if charging from solar) per kWh
    
    The scheduler then picks the lowest p_eff hours, naturally preferring
    midday-solar hours and high-renewable-share hours.
    """
    x = np.zeros(window); rem = E
    solar_remaining = pv_kwh.copy()  # how much solar is still available per hour
    
    while rem > 1e-6:
        chunk = min(step, rem)
        delta = chunk / eta
        best, best_c = -1, np.inf
        
        for h in range(window):
            if x[h] + delta > P_max + 1e-6: continue
            
            # Solar value: each kWh charged that overlaps with solar earns the gap
            solar_available_h = min(solar_remaining[h], delta)
            solar_credit = solar_available_h * (retail_price - FEED_IN_TARIFF)
            
            # ERE subsidy: solar-matched portion at higher rate, rest at grid rate
            ere_solar_part = solar_available_h * ERE_SOLAR_EUR_KWH
            ere_grid_part = (delta - solar_available_h) * ERE_GRID_EUR_KWH
            ere_credit = ere_solar_part + ere_grid_part
            
            # Congestion penalty (unchanged)
            old_pen = max(0.0, L_norm[h] + x[h]/P_max - L_cap) ** 2
            new_pen = max(0.0, L_norm[h] + (x[h]+delta)/P_max - L_cap) ** 2
            
            # Effective marginal cost
            c = alpha * p_kwh[h] * delta - solar_credit - ere_credit \
                + beta * (new_pen - old_pen)
            
            if c < best_c: best_c, best = c, h
        
        if best < 0: break
        # Commit the chunk
        solar_used = min(solar_remaining[best], delta)
        solar_remaining[best] -= solar_used
        x[best] += delta
        rem -= chunk
    
    return x

# =========================================================================
# Cost-tracking helpers
# =========================================================================
def session_metrics(x, p_kwh, pv_kwh, retail_price):
    """
    For a schedule x (array of grid draws by hour), compute:
      - grid_cost: € paid for grid kWh
      - solar_self_consumed_kwh: kWh that came from PV instead of grid
      - solar_value: € value of self-consumed solar (vs export)
      - ere_kwh_grid: kWh that earn grid ERE (charged from grid)
      - ere_kwh_solar: kWh that earn solar ERE (charged from PV)
    """
    grid_cost = 0.0
    sc_kwh = 0.0
    ere_grid = 0.0
    ere_solar = 0.0
    
    for h in range(len(x)):
        draw = x[h]
        if draw <= 0: continue
        # How much of this hour's draw comes from solar?
        from_solar = min(draw, pv_kwh[h])
        from_grid = draw - from_solar
        # Cost is only for grid portion
        grid_cost += from_grid * p_kwh[h]
        sc_kwh += from_solar
        ere_grid += from_grid
        ere_solar += from_solar
    
    solar_value = sc_kwh * (retail_price - FEED_IN_TARIFF)
    
    return {
        "grid_cost": grid_cost,
        "sc_kwh": sc_kwh,
        "solar_value": solar_value,
        "ere_kwh_grid": ere_grid,
        "ere_kwh_solar": ere_solar,
    }

# =========================================================================
# Load data
# =========================================================================
def run():
    print("\nLoading data…")
    hourly = pd.read_csv(os.path.join(DIR_02, "nl_hourly_real_2015_2025.csv"))
    hourly["ts_local"] = pd.to_datetime(hourly["ts_local"])
    year2024 = hourly[hourly["year"] == 2024].sort_values("ts_local").reset_index(drop=True)
    year2024["retail_eneco"] = (year2024["price_eur_mwh"]/1000.0 + ENECO_DYN_MARGIN + NL_TAX) * (1 + VAT)
    year2024_hours = year2024["retail_eneco"].values
    print(f"  2024 retail hours: {len(year2024_hours)}")

    with open(os.path.join(DIR_04, "fleet_database.json")) as f:
        fdb = json.load(f)
    bev = pd.DataFrame(fdb["ev_models"])
    bev = bev[bev["type"] == "BEV"].reset_index(drop=True)
    bev["sample_p"] = bev["new_2024_2025"] / bev["new_2024_2025"].sum()

    arrivals = pd.read_csv(os.path.join(DIR_05, "arrival_distributions.csv"))

    zl = pd.read_csv(os.path.join(BASE, "..", "datasets", "dataset6", "eindhoven_zonal_load.csv"))
    zl["timestamp"] = pd.to_datetime(zl["timestamp"], format="%m/%d/%Y %H:%M")
    total = zl.groupby("timestamp")["demand_MW"].sum().reset_index()
    total["hour"] = total["timestamp"].dt.hour
    load_by_hour = total.groupby("hour")["demand_MW"].mean().values
    L_norm_24 = (load_by_hour - load_by_hour.min()) / (load_by_hour.max() - load_by_hour.min())
    
    # Pre-compute PV profiles for all 366 days (full year)
    print("  Pre-computing PV profiles for all days…")
    pv_profiles_per_kwp = {}  # day -> 24-hour profile (kWh per hour for 1 kWp)
    for d in range(366):
        pv_profiles_per_kwp[d] = pv_profile_hourly(1.0, d)
    
    rng = np.random.default_rng(42)
    N = 1000
    
    # Sample drivers
    driver_models = rng.choice(bev.index, size=N, p=bev["sample_p"].values, replace=True)
    df = bev.loc[driver_models].reset_index(drop=True).copy()
    df["driver_id"] = range(N)
    
    EHV_ANNUAL_KM = 10_950
    df["annual_km"] = rng.normal(EHV_ANNUAL_KM, EHV_ANNUAL_KM * 0.20, N).clip(5000, 30000)
    df["annual_kWh"] = df["annual_km"] * df["kWh_per_100km"] / 100
    df["effective_range"] = df["wltp_km"] * 0.85 * 0.70
    df["sessions_per_year"] = (df["annual_km"] / df["effective_range"]).round().astype(int).clip(40, 250)
    df["kWh_per_session"] = df["annual_kWh"] / df["sessions_per_year"]
    
    # Solar assignment
    df["has_solar"] = rng.random(N) < PV_HOUSEHOLD_PENETRATION
    df["pv_kwp"] = np.where(df["has_solar"],
                              rng.uniform(PV_KWP_RANGE[0], PV_KWP_RANGE[1], N),
                              0.0)
    print(f"  Solar households: {df['has_solar'].sum()} / {N}  ({df['has_solar'].mean()*100:.0f}%)")
    print(f"  Mean PV size (solar households): {df.loc[df['has_solar'], 'pv_kwp'].mean():.2f} kWp")
    
    # Location & arrival
    df["location"] = rng.choice(["private", "workplace", "public"],
                                  size=N, p=[0.60, 0.15, 0.25])
    plugin_hours = []
    for loc in df["location"]:
        p = arrivals[f"{loc}_p"].values
        plugin_hours.append(rng.choice(24, p=p))
    df["plugin_hour"] = plugin_hours
    df["window_h"] = df["location"].map(
        lambda l: rng.choice({"private": [12, 13, 14, 15],
                              "workplace": [7, 8, 9],
                              "public": [3, 4, 5, 6]}[l])
    )
    
    # =====================================================================
    # Run simulation
    # =====================================================================
    eta = 0.92
    records = []
    
    print(f"\nRunning Monte Carlo over {N} drivers…")
    for i, row in df.iterrows():
        if i % 50 == 0: print(f"  driver {i}/{N}…", end="\r")
        sessions = int(row["sessions_per_year"])
        P_max = float(row["ac_kW"])
        E_req = float(row["kWh_per_session"])
        tp = int(row["plugin_hour"])
        win = int(row["window_h"])
        pv_kwp = float(row["pv_kwp"])
        
        # Local-load window (rotate so slot 0 = plug-in hour)
        L_full = np.concatenate([L_norm_24, L_norm_24])
        L_win = L_full[tp:tp + win]
        
        days = rng.choice(364, size=sessions, replace=True)
        
        cost_unc = cost_po = cost_sm = cost_sm_ext = 0.0
        cost_fix = 0.0
        peak_unc = peak_sm = peak_sm_ext = 0.0
        sc_kwh_total = 0.0
        solar_value_total = 0.0
        ere_grid_kwh = 0.0
        ere_solar_kwh = 0.0
        grid_kwh_baseline = 0.0  # grid kWh under uncontrolled
        
        for d in days:
            start = d * 24 + tp
            end = start + win
            if end > len(year2024_hours): continue
            p_win = year2024_hours[start:end]
            
            # PV in the charging window — rotate to start at plug-in hour
            pv_day = pv_profiles_per_kwp[d % 366] * pv_kwp
            pv_full = np.concatenate([pv_day, pv_day])
            pv_win = pv_full[tp:tp + win]
            
            retail_now = ENECO_FIXED  # retail price for solar self-consumption value
            
            # Feasibility
            max_dlv = win * P_max * eta
            E_use = min(E_req, max_dlv * 0.99)
            
            # Schedules
            x_unc = schedule_uncontrolled(E_use, P_max, eta, win)
            x_po = schedule_price_only(E_use, P_max, eta, win, p_win)
            x_sm = schedule_smart(E_use, P_max, eta, win, p_win, L_win)
            x_sm_ext = schedule_smart_extended(E_use, P_max, eta, win, p_win, L_win,
                                                 pv_win, retail_now)
            
            # Baseline costs (no solar credit, no ERE) — money paid to grid only
            cost_unc += float(np.sum(x_unc * p_win))
            cost_po += float(np.sum(x_po * p_win))
            cost_sm += float(np.sum(x_sm * p_win))
            
            # Extended scheduler — track solar self-consumption properly
            m_ext = session_metrics(x_sm_ext, p_win, pv_win, retail_now)
            cost_sm_ext += m_ext["grid_cost"]
            sc_kwh_total += m_ext["sc_kwh"]
            solar_value_total += m_ext["solar_value"]
            ere_grid_kwh += m_ext["ere_kwh_grid"]
            ere_solar_kwh += m_ext["ere_kwh_solar"]
            
            # Fixed-tariff baseline (charging full required energy at fixed rate)
            cost_fix += float(np.sum(x_unc)) * ENECO_FIXED
            
            # Peaks (clock hours 17-21)
            for slot in range(win):
                clock = (tp + slot) % 24
                if 17 <= clock <= 21:
                    peak_unc += x_unc[slot]
                    peak_sm += x_sm[slot]
                    peak_sm_ext += x_sm_ext[slot]
        
        # ERE revenue (annual)
        ere_revenue = (ere_grid_kwh * ERE_GRID_EUR_KWH +
                        ere_solar_kwh * ERE_SOLAR_EUR_KWH)
        
        # For drivers without solar, also compute ERE for the baseline smart schedule
        ere_baseline_smart = (cost_sm / year2024["retail_eneco"].mean()
                                if cost_sm > 0 else 0) * ERE_GRID_EUR_KWH
        # Actually clearer: just count the kWh delivered
        # Approximation: the smart schedule delivers ~annual_kwh kWh, all from grid
        ere_grid_only = row["annual_kWh"] * ERE_GRID_EUR_KWH
        
        records.append({
            "driver_id": i, "model": row["model"], "ac_kW": P_max,
            "annual_km": row["annual_km"], "annual_kWh": row["annual_kWh"],
            "sessions": sessions, "location": row["location"],
            "plugin_hour": tp, "window_h": win,
            "has_solar": bool(row["has_solar"]), "pv_kwp": pv_kwp,
            "cost_fix": cost_fix, "cost_unc": cost_unc,
            "cost_po": cost_po, "cost_sm": cost_sm, "cost_sm_ext": cost_sm_ext,
            "peak_kwh_unc": peak_unc, "peak_kwh_sm": peak_sm,
            "peak_kwh_sm_ext": peak_sm_ext,
            "sc_kwh_total": sc_kwh_total,
            "solar_value_total": solar_value_total,
            "ere_revenue_ext": ere_revenue,
            "ere_revenue_grid_only": ere_grid_only,
        })
    
    mc = pd.DataFrame(records)
    print(f"\n\nN drivers: {len(mc)}")
    
    # Compute combined value
    # Baseline smart: only dynamic-price savings + ERE on all grid kWh
    mc["value_baseline_smart"] = (mc["cost_fix"] - mc["cost_sm"]) + mc["ere_revenue_grid_only"]
    
    # Extended: dynamic savings (cost_sm_ext < cost_sm) + ERE + solar value
    mc["value_extended"] = ((mc["cost_fix"] - mc["cost_sm_ext"])
                              + mc["ere_revenue_ext"]
                              + mc["solar_value_total"])
    
    # Save
    mc.to_csv(f"{OUT_DATA}/monte_carlo_extended.csv", index=False)
    print(f"  Saved {OUT_DATA}/monte_carlo_extended.csv")
    
    # =====================================================================
    # Summary
    # =====================================================================
    print("\n" + "=" * 70)
    print("EXTENDED MONTE CARLO — RESULTS")
    print("=" * 70)
    
    print("\nAnnual cost per driver (€):")
    for col, label in [("cost_fix", "Fixed tariff"),
                         ("cost_unc", "Dynamic — uncontrolled"),
                         ("cost_po", "Dynamic — price-only"),
                         ("cost_sm", "Dynamic — Smart (baseline CACCS)"),
                         ("cost_sm_ext", "Dynamic — Smart EXTENDED (solar+ERE-aware)")]:
        print(f"  {label:<48}  €{mc[col].mean():>6.0f}  (median €{mc[col].median():.0f})")
    
    print(f"\nValue add to driver (annual €):")
    print(f"  Mean ERE revenue (extended):         €{mc['ere_revenue_ext'].mean():.0f}")
    print(f"  Mean solar self-consumption value:   €{mc['solar_value_total'].mean():.0f}")
    print(f"  Mean total value (Smart vs Fixed + ERE + Solar): €{mc['value_extended'].mean():.0f}")
    
    print(f"\nSolar households (n={mc['has_solar'].sum()}):")
    sd = mc[mc["has_solar"]]
    print(f"  Mean self-consumed kWh/yr: {sd['sc_kwh_total'].mean():.0f}")
    print(f"  Mean solar value (€/yr):   €{sd['solar_value_total'].mean():.0f}")
    print(f"  Mean total value (€/yr):   €{sd['value_extended'].mean():.0f}")
    
    nsd = mc[~mc["has_solar"]]
    print(f"\nNo-solar households (n={(~mc['has_solar']).sum()}):")
    print(f"  Mean total value (€/yr):   €{nsd['value_extended'].mean():.0f}")
    
    # Compare extended vs baseline smart
    delta = mc["cost_sm"] - mc["cost_sm_ext"]
    print(f"\nExtension vs baseline Smart (€/driver/yr):")
    print(f"  Mean Δ cost (solar-aware saves on bill):     €{delta.mean():.0f}")
    print(f"  Of which from solar households:               €{delta[mc['has_solar']].mean():.0f}")
    print(f"  Of which from non-solar households:           €{delta[~mc['has_solar']].mean():.0f}")
    
    # Peak relief
    peak_drop_sm = (1 - mc["peak_kwh_sm"] / mc["peak_kwh_unc"]).where(mc["peak_kwh_unc"] > 0.1, np.nan) * 100
    peak_drop_ext = (1 - mc["peak_kwh_sm_ext"] / mc["peak_kwh_unc"]).where(mc["peak_kwh_unc"] > 0.1, np.nan) * 100
    print(f"\nPeak-hour drop (Smart vs Uncontrolled):")
    print(f"  Baseline:   {peak_drop_sm.mean(skipna=True):.1f}%")
    print(f"  Extended:   {peak_drop_ext.mean(skipna=True):.1f}%")
    
    # KPI summary
    kpis = pd.Series({
        "n_drivers": len(mc),
        "n_solar_households": int(mc["has_solar"].sum()),
        "mean_cost_fix": mc["cost_fix"].mean(),
        "mean_cost_unc": mc["cost_unc"].mean(),
        "mean_cost_sm": mc["cost_sm"].mean(),
        "mean_cost_sm_ext": mc["cost_sm_ext"].mean(),
        "mean_ere_revenue_ext": mc["ere_revenue_ext"].mean(),
        "mean_solar_value": mc["solar_value_total"].mean(),
        "mean_total_value_baseline": mc["value_baseline_smart"].mean(),
        "mean_total_value_extended": mc["value_extended"].mean(),
        "mean_total_value_solar_households": sd["value_extended"].mean(),
        "mean_total_value_nonsolar_households": nsd["value_extended"].mean(),
        "mean_sc_kwh_solar_households": sd["sc_kwh_total"].mean(),
        "mean_peak_drop_baseline_pct": peak_drop_sm.mean(skipna=True),
        "mean_peak_drop_extended_pct": peak_drop_ext.mean(skipna=True),
    })
    kpis.to_csv(f"{OUT_DATA}/kpi_extended.csv")
    print(f"\n✓ Saved {OUT_DATA}/kpi_extended.csv")


if __name__ == "__main__":
    run()
