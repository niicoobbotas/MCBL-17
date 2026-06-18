"""
Smart EV Charging — Team 12
Module: ERE & Solar Revenue Model  (imported by Parts 9 and 10)
----------------------------------------------------------------------
"""

# =========================================================================
# Constants
# =========================================================================
ERE_EMISSION_FACTOR_G_MJ = 183.0      # g CO2 / MJ — NEa reference factor
ERE_MJ_PER_KWH = 3.6                   # MJ / kWh — energy conversion
NL_GRID_RENEWABLE_SHARE_2026 = 0.505   # 50.5% — NEa-fixed for 2026

# ERE per kWh, by source of electricity
ERE_PER_KWH_GRID = (NL_GRID_RENEWABLE_SHARE_2026
                    * ERE_EMISSION_FACTOR_G_MJ
                    * ERE_MJ_PER_KWH / 1000.0)   # ≈ 0.333
ERE_PER_KWH_SOLAR = (1.000
                     * ERE_EMISSION_FACTOR_G_MJ
                     * ERE_MJ_PER_KWH / 1000.0)  # ≈ 0.659

# Market parameters (early 2026)
ERE_PRICE_EUR_PER_UNIT = 0.30          # €/ERE = €/kg CO2 (Groenbalans Mar 2026)
INBOEKER_COMMISSION = 0.18             # 18% — mid-range of 15-25%

# Solar parameters (NL household scale)
PV_SYSTEM_KWP_TYPICAL = 4.0            # 4 kWp average rooftop in NL
PV_YIELD_KWH_PER_KWP = 900             # kWh/kWp/year in NL (CBS 2023-2024 avg)
FEED_IN_TARIFF_2026 = 0.07             # €/kWh paid for export (down from full retail)
SC_RATE_PASSIVE = 0.30                 # 30% default self-consumption without smart matching
SC_RATE_SMART = 0.70                   # 70% with smart algorithm matching EV charging to solar


def calc_ere_per_kwh(renewable_share=NL_GRID_RENEWABLE_SHARE_2026):
    """ERE certificates earned per kWh charged."""
    return renewable_share * ERE_EMISSION_FACTOR_G_MJ * ERE_MJ_PER_KWH / 1000.0


def calc_ere_revenue(annual_kwh, ere_price=ERE_PRICE_EUR_PER_UNIT,
                     renewable_share=NL_GRID_RENEWABLE_SHARE_2026,
                     commission=INBOEKER_COMMISSION):
    """
    Annual ERE revenue (net of inboeker commission) for a home charger.
    
    Args:
        annual_kwh: kWh delivered through the MID-certified charger per year
        ere_price: market price per ERE (€/kg CO2)
        renewable_share: renewable share of input electricity (0.505 for grid, 1.0 for solar)
        commission: inboekdienstverlener share (0.15-0.25)
    
    Returns:
        net annual ERE revenue (€/yr)
    """
    ere_count = annual_kwh * calc_ere_per_kwh(renewable_share)
    gross = ere_count * ere_price
    net = gross * (1 - commission)
    return net


def calc_solar_self_consumption_value(annual_solar_kwh, sc_rate,
                                       retail_price, feed_in=FEED_IN_TARIFF_2026):
    """
    Value gained by self-consuming solar instead of exporting.
    
    Each self-consumed kWh:
        - Avoids buying from grid at retail_price
        - Forgoes feed-in revenue of feed_in
        - Net value: (retail_price - feed_in)
    
    Args:
        annual_solar_kwh: yearly solar generation routed to the EV
        sc_rate: fraction self-consumed by EV (vs exported to grid)
        retail_price: €/kWh retail (used for direct-consumption opportunity cost)
        feed_in: €/kWh paid for export
    
    Returns:
        annual € value of self-consumed solar (post-2027 saldering rules)
    """
    self_consumed = annual_solar_kwh * sc_rate
    value_per_kwh = retail_price - feed_in
    return self_consumed * value_per_kwh


def estimate_pv_generation(kwp=PV_SYSTEM_KWP_TYPICAL,
                            yield_per_kwp=PV_YIELD_KWH_PER_KWP):
    """Annual solar PV generation in kWh."""
    return kwp * yield_per_kwp


def total_value_stack(annual_charging_kwh,
                       fixed_cost_eur,
                       smart_cost_eur,
                       has_solar=False,
                       pv_kwp=PV_SYSTEM_KWP_TYPICAL,
                       retail_price=0.319,
                       ere_price=ERE_PRICE_EUR_PER_UNIT,
                       commission=INBOEKER_COMMISSION,
                       smart_solar_match=SC_RATE_SMART):
    """
    Stack the three independent revenue streams that a smart-cable user
    can earn:
    
      1. Dynamic-prices saving  = fixed_cost - smart_cost   (always available)
      2. ERE certificates       = annual_kwh × 0.333 × ERE_price × (1 - commission)
                                  (requires MID-certified charger + registration)
      3. Solar self-consumption = matched_solar_kwh × (retail - feed_in)
                                  (only if household has PV)
    
    Returns: dict with each stream + total
    """
    # 1. Dynamic-prices saving
    dynamic_save = fixed_cost_eur - smart_cost_eur
    
    # 2. ERE revenue
    if has_solar:
        # PV-matched portion earns the higher 'own renewables' ERE rate
        solar_kwh = min(estimate_pv_generation(pv_kwp) * smart_solar_match,
                        annual_charging_kwh)
        grid_kwh = annual_charging_kwh - solar_kwh
        ere_solar = calc_ere_revenue(solar_kwh, ere_price, 1.000, commission)
        ere_grid = calc_ere_revenue(grid_kwh, ere_price,
                                     NL_GRID_RENEWABLE_SHARE_2026, commission)
        ere_total = ere_solar + ere_grid
    else:
        ere_total = calc_ere_revenue(annual_charging_kwh, ere_price,
                                      NL_GRID_RENEWABLE_SHARE_2026, commission)
    
    # 3. Solar self-consumption value
    if has_solar:
        annual_pv = estimate_pv_generation(pv_kwp)
        solar_to_ev = min(annual_pv * smart_solar_match, annual_charging_kwh)
        passive_to_ev = min(annual_pv * SC_RATE_PASSIVE, annual_charging_kwh)
        # Incremental value of SMART matching vs passive baseline
        delta_self_consumed = solar_to_ev - passive_to_ev
        solar_value = delta_self_consumed * (retail_price - FEED_IN_TARIFF_2026)
    else:
        solar_value = 0.0
    
    return {
        "dynamic_save_eur": dynamic_save,
        "ere_revenue_eur": ere_total,
        "solar_value_eur": solar_value,
        "total_eur": dynamic_save + ere_total + solar_value,
    }


# =========================================================================
# Self-test
# =========================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("ERE + Solar revenue model — self test")
    print("=" * 70)
    print(f"\nOfficial ERE rates:")
    print(f"  Grid electricity (50.5% renewable): {ERE_PER_KWH_GRID:.4f} ERE/kWh")
    print(f"  Own solar (100% renewable):         {ERE_PER_KWH_SOLAR:.4f} ERE/kWh")
    print(f"  Market price:                       €{ERE_PRICE_EUR_PER_UNIT}/ERE")
    
    print("\nExample 1: Eindhoven driver, 12,000 km/yr, NO solar")
    print("-" * 70)
    annual_kwh = 2152  # from Tesla Model Y at 12k km
    out = total_value_stack(annual_kwh, 687, 523, has_solar=False)
    for k, v in out.items():
        print(f"  {k:<22} €{v:>7.0f}")
    
    print("\nExample 2: Same driver, WITH 4 kWp solar PV (post-saldering)")
    print("-" * 70)
    out = total_value_stack(annual_kwh, 687, 523, has_solar=True, pv_kwp=4.0)
    for k, v in out.items():
        print(f"  {k:<22} €{v:>7.0f}")
    
    print("\nExample 3: High-mileage driver, 25,000 km/yr, 6 kWp solar")
    print("-" * 70)
    out = total_value_stack(4480, 1430, 1090, has_solar=True, pv_kwp=6.0)
    for k, v in out.items():
        print(f"  {k:<22} €{v:>7.0f}")
    
    print("\nERE per kWh at different market prices:")
    for p in [0.18, 0.30, 0.36]:
        ere = calc_ere_revenue(1000, ere_price=p) / 1000
        print(f"  €{p:.2f}/ERE → €{ere:.4f}/kWh (net of {INBOEKER_COMMISSION:.0%} commission)")
