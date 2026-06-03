from dataclasses import dataclass
from datetime import datetime, timedelta

from app.models.price import Price
from app.models.schedule import OptimizationMode


# Normalised (0-1) Eindhoven grid-load profile by clock hour, used as a
# congestion proxy by the grid-aware "smart" scheduler. Derived from the
# team's research dataset (eindhoven_zonal_load.csv, MCBL-17): hourly mean
# total demand min-max scaled. Note the clear evening peak (17:00-21:00).
EINDHOVEN_LOAD_NORM = [
    0.181, 0.106, 0.047, 0.000, 0.011, 0.083, 0.252, 0.499,
    0.691, 0.789, 0.788, 0.770, 0.767, 0.792, 0.793, 0.851,
    0.943, 1.000, 0.864, 0.737, 0.619, 0.496, 0.356, 0.229,
]
# Congestion threshold: above this normalised load the grid is "stressed"
# (~60th percentile of the profile). Charging above it is penalised.
CONGESTION_CAP = 0.60


@dataclass
class ChargingSlot:
    start_time: datetime
    end_time: datetime
    charge_rate_kw: float
    estimated_kwh: float
    estimated_cost: float


def compute_schedule(
    prices: list[Price],
    available_from: datetime,
    needed_by: datetime,
    current_soc: float,
    target_soc: float,
    battery_capacity_kwh: float,
    max_charge_rate_kw: float,
    charger_max_kw: float,
    mode: OptimizationMode,
) -> list[ChargingSlot]:
    """Compute optimal charging schedule given prices and constraints.

    Args:
        prices: Hourly price data for the available window.
        available_from: Earliest time charging can start.
        needed_by: Time by which the car must be ready.
        current_soc: Current state of charge (0-100).
        target_soc: Desired state of charge (0-100).
        battery_capacity_kwh: Total battery capacity.
        max_charge_rate_kw: Max charge rate the vehicle supports.
        charger_max_kw: Max power the charger can deliver.
        mode: Optimization mode — price, battery_life, or smart (grid-aware).

    Returns:
        List of ChargingSlot with the optimal schedule.
    """
    effective_target = target_soc
    if mode == OptimizationMode.battery_life:
        # Cap at 80% unless user explicitly wants more
        effective_target = min(target_soc, 80.0)

    energy_needed = (effective_target - current_soc) / 100.0 * battery_capacity_kwh
    if energy_needed <= 0:
        return []

    max_rate = min(max_charge_rate_kw, charger_max_kw)

    # Filter prices to our available window (each entry covers 1 hour)
    window_prices = [
        p for p in prices
        if p.timestamp >= available_from and p.timestamp < needed_by
    ]
    if not window_prices:
        return []

    if mode == OptimizationMode.smart:
        return _compute_smart(window_prices, energy_needed, max_rate)

    if mode == OptimizationMode.battery_life:
        # Use a gentler charge rate (60% of max) for battery longevity
        charge_rate = max_rate * 0.6
    else:
        charge_rate = max_rate

    # Each price entry covers 1 hour; energy per slot at chosen rate
    kwh_per_slot = charge_rate  # charge_rate_kw * 1 hour

    # Sort by price (ascending for price mode, with battery_life penalty)
    if mode == OptimizationMode.price:
        sorted_prices = sorted(window_prices, key=lambda p: p.price_eur_per_mwh)
    else:
        # Battery life: prefer spreading out, slight penalty for late-night vs early slots
        # Still sort by price but bias toward consecutive low-rate slots
        sorted_prices = sorted(window_prices, key=lambda p: p.price_eur_per_mwh)

    # Greedily pick cheapest slots until energy need is met
    selected = []
    remaining_kwh = energy_needed
    for price in sorted_prices:
        if remaining_kwh <= 0:
            break
        slot_kwh = min(kwh_per_slot, remaining_kwh)
        cost = slot_kwh * (price.price_eur_per_mwh / 1000.0)  # EUR/MWh -> EUR/kWh
        selected.append(ChargingSlot(
            start_time=price.timestamp,
            end_time=price.timestamp.replace(hour=price.timestamp.hour + 1)
            if price.timestamp.hour < 23
            else price.timestamp.replace(hour=0, day=price.timestamp.day + 1),
            charge_rate_kw=charge_rate if slot_kwh == kwh_per_slot else slot_kwh,
            estimated_kwh=slot_kwh,
            estimated_cost=round(cost, 4),
        ))
        remaining_kwh -= slot_kwh

    # Sort selected slots chronologically
    selected.sort(key=lambda s: s.start_time)

    # Merge consecutive slots
    merged: list[ChargingSlot] = []
    for slot in selected:
        if merged and merged[-1].end_time == slot.start_time and merged[-1].charge_rate_kw == slot.charge_rate_kw:
            merged[-1].end_time = slot.end_time
            merged[-1].estimated_kwh += slot.estimated_kwh
            merged[-1].estimated_cost += slot.estimated_cost
        else:
            merged.append(slot)

    return merged


def _slot_end(start: datetime) -> datetime:
    """End of the one-hour slot beginning at `start`."""
    return start + timedelta(hours=1)


def _compute_smart(
    window_prices: list[Price],
    energy_needed: float,
    max_rate: float,
    beta: float = 0.5,
    step: float = 0.25,
) -> list[ChargingSlot]:
    """Grid-aware scheduler (CACCS — Cost-Aware Constrained Charging Scheduler).

    Ported from the team's research (MCBL-17, more_code/03_simulation.py). The
    plain price optimizer minimises cost alone; CACCS additionally penalises
    charging during local grid congestion, minimising:

        J = Σ_h [ price_h · x_h  +  β · max(0, load_h + x_h − cap)² ]

    subject to Σ x_h = energy_needed and 0 ≤ x_h ≤ max_rate, where load_h is the
    normalised Eindhoven congestion proxy for that clock hour and x_h is the
    charger draw normalised to [0, 1]. Solved with the same fast greedy-with-
    penalty heuristic as the research code: repeatedly add a small `step` of
    energy to the hour with the lowest marginal (price + congestion) cost.
    """
    hours = sorted(window_prices, key=lambda p: p.timestamp)
    # Per-hour state: grid draw allocated so far (kW, == kWh over a 1h slot)
    allocated = {p.timestamp: 0.0 for p in hours}

    def congestion_penalty(load_norm: float, draw_kw: float) -> float:
        x_norm = draw_kw / max_rate if max_rate > 0 else 0.0
        overshoot = max(0.0, load_norm + x_norm - CONGESTION_CAP)
        return beta * overshoot * overshoot

    remaining = energy_needed
    while remaining > 1e-6:
        chunk = min(step, remaining)
        best_p, best_cost = None, float("inf")
        for p in hours:
            current = allocated[p.timestamp]
            if current + chunk > max_rate + 1e-9:
                continue  # hour already at the charger's max rate
            price_kwh = p.price_eur_per_mwh / 1000.0
            load = EINDHOVEN_LOAD_NORM[p.timestamp.hour]
            old_pen = congestion_penalty(load, current)
            new_pen = congestion_penalty(load, current + chunk)
            marginal = price_kwh * chunk + (new_pen - old_pen)
            if marginal < best_cost:
                best_cost, best_p = marginal, p
        if best_p is None:
            break  # window too short to deliver the energy at this rate
        allocated[best_p.timestamp] += chunk
        remaining -= chunk

    # Build chronological slots for the hours that received charge
    slots = [
        ChargingSlot(
            start_time=p.timestamp,
            end_time=_slot_end(p.timestamp),
            charge_rate_kw=round(allocated[p.timestamp], 3),
            estimated_kwh=round(allocated[p.timestamp], 3),
            estimated_cost=round(allocated[p.timestamp] * (p.price_eur_per_mwh / 1000.0), 4),
        )
        for p in hours
        if allocated[p.timestamp] > 1e-6
    ]
    return slots


def compute_naive_cost(prices: list[Price], energy_kwh: float, available_from: datetime) -> float:
    """Compute cost of naive charging (start immediately, charge at max rate)."""
    window = sorted(
        [p for p in prices if p.timestamp >= available_from],
        key=lambda p: p.timestamp,
    )
    remaining = energy_kwh
    cost = 0.0
    for price in window:
        if remaining <= 0:
            break
        slot_kwh = min(remaining, energy_kwh)  # 1 hour max at full rate
        cost += slot_kwh * (price.price_eur_per_mwh / 1000.0)
        remaining -= slot_kwh
    return round(cost, 4)
