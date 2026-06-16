"""
CACCS — Cost-Aware Constrained Charging Scheduler
Ported from the Team 12 JavaScript implementation to Python.
Uses real Ember NL 2024 mean hourly wholesale profile.
"""
from typing import List, Tuple
import datetime
import random

# Mean 2024 NL day-ahead hourly profile (EUR/MWh, Ember data)
HOURLY_WHOLESALE_MWH = [
    66.3, 60.7, 57.5, 55.0, 55.4, 60.2, 71.6, 84.6,
    88.4, 77.0, 65.6, 53.3, 47.8, 43.3, 44.4, 53.0,
    67.0, 89.0, 105.0, 121.5, 111.4, 99.2, 88.5, 79.0,
]

# Eindhoven city-wide normalised load proxy (consistent with Enexis SJV)
L_EINDHOVEN = [
    0.18, 0.10, 0.05, 0.00, 0.01, 0.08, 0.25, 0.50,
    0.69, 0.79, 0.79, 0.77, 0.77, 0.79, 0.79, 0.85,
    0.95, 1.00, 0.86, 0.74, 0.62, 0.49, 0.35, 0.23,
]

NL_TAX = 0.10154   # energiebelasting 2026 (EUR/kWh)
VAT = 0.21

SUPPLIERS = {
    "eneco": {"dyn_margin": 0.0235, "fixed": 0.319, "name": "Eneco"},
    "essent": {"dyn_margin": 0.0220, "fixed": 0.314, "name": "Essent"},
}

# ERE constants (NEa 2026, RED III)
ERE_EMISSION_FACTOR = 183.0   # g CO2/MJ
ERE_MJ_PER_KWH = 3.6
NL_GRID_RENEWABLE = 0.505     # 50.5% renewable share, 2026
ERE_PRICE = 0.30              # EUR/ERE
ERE_COMMISSION = 0.18

# Solar
PV_YIELD_PER_KWP = 900.0     # kWh/kWp/yr NL average
FEED_IN_TARIFF = 0.07         # EUR/kWh post-saldering 2027+
SC_RATE_PASSIVE = 0.30
SC_RATE_SMART = 0.70


def retail(eur_mwh: float, margin: float) -> float:
    return (eur_mwh / 1000.0 + margin + NL_TAX) * (1 + VAT)


def get_live_wholesale_mwh() -> List[float]:
    """
    Returns today's hourly wholesale prices (EUR/MWh).
    Adds a small daily random variation (+/- 15%) to the mean profile
    to simulate day-to-day variability while remaining realistic.
    In production, replace with ENTSO-E Transparency Platform API call.
    """
    seed = datetime.date.today().toordinal()
    rng = random.Random(seed)
    factor = 1.0 + rng.uniform(-0.15, 0.15)
    # Also add per-hour noise
    return [
        max(0.0, h * factor * (1.0 + rng.uniform(-0.08, 0.08)))
        for h in HOURLY_WHOLESALE_MWH
    ]


def build_window(plugin: int, deadline: int, supplier: str, use_live: bool = True):
    """Extract price and load arrays for the charging window."""
    margin = SUPPLIERS[supplier]["dyn_margin"]
    wholesale = get_live_wholesale_mwh() if use_live else HOURLY_WHOLESALE_MWH
    win = (deadline - plugin) if deadline > plugin else (24 - plugin + deadline)
    p_win, L_win = [], []
    for i in range(win):
        h = (plugin + i) % 24
        p_win.append(retail(wholesale[h], margin))
        L_win.append(L_EINDHOVEN[h])
    return win, p_win, L_win, wholesale


def schedule_uncontrolled(E: float, Pmax: float, eta: float, win: int) -> List[float]:
    x = [0.0] * win
    rem = E
    for h in range(win):
        if rem <= 1e-9:
            break
        add = min(Pmax * eta, rem)
        x[h] = add / eta
        rem -= add
    return x


def schedule_price_only(E: float, Pmax: float, eta: float, win: int, p: List[float]) -> List[float]:
    x = [0.0] * win
    order = sorted(range(win), key=lambda i: p[i])
    rem = E
    for h in order:
        if rem <= 1e-9:
            break
        add = min(Pmax * eta, rem)
        x[h] = add / eta
        rem -= add
    return x


def schedule_smart(
    E: float,
    Pmax: float,
    eta: float,
    win: int,
    p: List[float],
    L: List[float],
    L_cap: float = 0.6,
    beta: float = 0.6,
    step: float = 0.25,
) -> List[float]:
    x = [0.0] * win
    rem = E
    iterations = 0
    while rem > 1e-6 and iterations < 20000:
        iterations += 1
        chunk = min(step, rem)
        delta = chunk / eta
        best_h, best_cost = -1, float("inf")
        for h in range(win):
            if x[h] + delta > Pmax + 1e-6:
                continue
            old_pen = max(0.0, L[h] + x[h] / Pmax - L_cap) ** 2
            new_pen = max(0.0, L[h] + (x[h] + delta) / Pmax - L_cap) ** 2
            c = p[h] * delta + beta * (new_pen - old_pen)
            if c < best_cost:
                best_cost, best_h = c, h
        if best_h < 0:
            break
        x[best_h] += delta
        rem -= chunk
    return x


def session_cost(x: List[float], p: List[float]) -> float:
    return sum(v * p[h] for h, v in enumerate(x))


def peak_kwh(x: List[float], plugin: int, win: int) -> float:
    total = 0.0
    for i, v in enumerate(x):
        h = (plugin + i) % 24
        if 17 <= h <= 21:
            total += v
    return total


def run_caccs(
    energy_kwh: float,
    pmax_kw: float,
    plugin_hour: int,
    deadline_hour: int,
    supplier: str = "eneco",
    beta: float = 0.6,
    eta: float = 0.92,
) -> dict:
    win, p_win, L_win, wholesale = build_window(plugin_hour, deadline_hour, supplier)

    x_unc = schedule_uncontrolled(energy_kwh, pmax_kw, eta, win)
    x_po = schedule_price_only(energy_kwh, pmax_kw, eta, win, p_win)
    x_sm = schedule_smart(energy_kwh, pmax_kw, eta, win, p_win, L_win, 0.6, beta)

    cost_unc = session_cost(x_unc, p_win)
    cost_po = session_cost(x_po, p_win)
    cost_sm = session_cost(x_sm, p_win)
    cost_fix = energy_kwh * SUPPLIERS[supplier]["fixed"]

    pk_unc = peak_kwh(x_unc, plugin_hour, win)
    pk_sm = peak_kwh(x_sm, plugin_hour, win)
    peak_drop = (1.0 - pk_sm / pk_unc) * 100.0 if pk_unc > 0.1 else 0.0

    schedule = []
    for i in range(win):
        h = (plugin_hour + i) % 24
        schedule.append({
            "hour": h,
            "slot": i,
            "price": round(p_win[i], 4),
            "wholesale": round(wholesale[(plugin_hour + i) % 24], 1),
            "load": round(L_win[i], 3),
            "uncontrolled_kw": round(x_unc[i], 3),
            "price_only_kw": round(x_po[i], 3),
            "smart_kw": round(x_sm[i], 3),
        })

    return {
        "energy_kwh": round(energy_kwh, 2),
        "window_hours": win,
        "plugin_hour": plugin_hour,
        "deadline_hour": deadline_hour,
        "supplier": supplier,
        "costs": {
            "uncontrolled": round(cost_unc, 2),
            "price_only": round(cost_po, 2),
            "smart": round(cost_sm, 2),
            "fixed": round(cost_fix, 2),
        },
        "savings": {
            "vs_uncontrolled_eur": round(cost_unc - cost_sm, 2),
            "vs_fixed_eur": round(cost_fix - cost_sm, 2),
            "vs_uncontrolled_pct": round((cost_unc - cost_sm) / cost_unc * 100, 1) if cost_unc > 0 else 0,
            "vs_fixed_pct": round((cost_fix - cost_sm) / cost_fix * 100, 1) if cost_fix > 0 else 0,
        },
        "peak_drop_pct": round(peak_drop, 1),
        "schedule": schedule,
    }


def get_current_price(supplier: str = "eneco") -> dict:
    now = datetime.datetime.now()
    h = now.hour
    margin = SUPPLIERS[supplier]["dyn_margin"]
    wholesale = get_live_wholesale_mwh()
    price = retail(wholesale[h], margin)
    avg = sum(retail(w, margin) for w in wholesale) / 24.0
    pct_vs_avg = (price - avg) / avg * 100.0

    # Find cheapest window (3-hour block)
    best_start, best_avg = 0, float("inf")
    for start in range(24):
        block = [retail(wholesale[(start + i) % 24], margin) for i in range(3)]
        ba = sum(block) / 3.0
        if ba < best_avg:
            best_avg, best_start = ba, start

    return {
        "hour": h,
        "price": round(price, 4),
        "avg_today": round(avg, 4),
        "pct_vs_avg": round(pct_vs_avg, 1),
        "cheapest_window_start": best_start,
        "cheapest_window_end": (best_start + 3) % 24,
        "supplier": supplier,
        "timestamp": now.isoformat(),
    }


def get_today_hourly(supplier: str = "eneco") -> List[dict]:
    margin = SUPPLIERS[supplier]["dyn_margin"]
    wholesale = get_live_wholesale_mwh()
    return [
        {
            "hour": h,
            "wholesale": round(wholesale[h], 1),
            "retail": round(retail(wholesale[h], margin), 4),
            "load": L_EINDHOVEN[h],
        }
        for h in range(24)
    ]


def compute_annual_value(
    annual_km: float,
    efficiency: float,
    supplier: str,
    plugin_hour: int,
    deadline_hour: int,
    pmax_kw: float,
    ere_enabled: bool = True,
    solar_enabled: bool = False,
    solar_kwp: float = 4.0,
    eta: float = 0.92,
) -> dict:
    annual_kwh = annual_km * efficiency / 100.0 / eta
    effective_range = 300.0  # simplified for annual calc
    sessions = max(1, round(annual_km / effective_range))
    kwh_session = annual_kwh / sessions

    win, p_win, L_win, _ = build_window(plugin_hour, deadline_hour, supplier)
    x_sm = schedule_smart(kwh_session, pmax_kw, eta, win, p_win, L_win)
    cost_sm_session = session_cost(x_sm, p_win)
    cost_sm_annual = cost_sm_session * sessions
    cost_fixed_annual = annual_kwh * SUPPLIERS[supplier]["fixed"]
    dynamic_saving = cost_fixed_annual - cost_sm_annual

    ere_value = 0.0
    if ere_enabled:
        if solar_enabled:
            pv_kwh = solar_kwp * PV_YIELD_PER_KWP
            solar_kwh = min(pv_kwh * SC_RATE_SMART, annual_kwh)
            grid_kwh = annual_kwh - solar_kwh
            ere_value = (
                solar_kwh * 1.0 * ERE_EMISSION_FACTOR * ERE_MJ_PER_KWH / 1000 * ERE_PRICE * (1 - ERE_COMMISSION)
                + grid_kwh * NL_GRID_RENEWABLE * ERE_EMISSION_FACTOR * ERE_MJ_PER_KWH / 1000 * ERE_PRICE * (1 - ERE_COMMISSION)
            )
        else:
            ere_value = (
                annual_kwh * NL_GRID_RENEWABLE * ERE_EMISSION_FACTOR * ERE_MJ_PER_KWH / 1000
                * ERE_PRICE * (1 - ERE_COMMISSION)
            )

    solar_value = 0.0
    if solar_enabled:
        pv_kwh = solar_kwp * PV_YIELD_PER_KWP
        smart_match = min(pv_kwh * SC_RATE_SMART, annual_kwh)
        passive_match = min(pv_kwh * SC_RATE_PASSIVE, annual_kwh)
        retail_price = SUPPLIERS[supplier]["fixed"]
        solar_value = (smart_match - passive_match) * (retail_price - FEED_IN_TARIFF)

    return {
        "annual_kwh": round(annual_kwh, 1),
        "sessions": sessions,
        "dynamic_saving": round(dynamic_saving, 2),
        "ere_value": round(ere_value, 2),
        "solar_value": round(solar_value, 2),
        "total": round(dynamic_saving + ere_value + solar_value, 2),
    }
