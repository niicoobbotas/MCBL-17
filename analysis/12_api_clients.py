"""
Smart EV Charging — Team 12
Part 12: API Clients for Data Refresh
----------------------------------------------------------------------
"""
from __future__ import annotations
import os
import io
import json
import time
from typing import Optional
import requests          # pip install requests
import pandas as pd


# =========================================================================
# 1) CBS Open Data — OData v3 API
# =========================================================================
# Source: https://opendata.cbs.nl/  License: CC-BY 4.0
# Documentation: https://www.cbs.nl/en-gb/our-services/open-data
#
# The OData endpoint is well-suited for incremental refresh. Example tables:
#   85237NED  Personenauto's actief; voertuigkenmerken, regio's, 1 januari
#   84709NED  Personen; vervoerwijze, motieven, regio (ODiN)
#   84710NED  Personen; ondernemen, woon-werk, mobiliteit
#   83504NED  Mobility per municipality
# =========================================================================

CBS_BASE = "https://opendata.cbs.nl/ODataApi/OData"

def fetch_cbs_table(table_id: str, query: Optional[str] = None,
                    max_pages: int = 50) -> pd.DataFrame:
    """
    Generic CBS OData fetcher with pagination. Returns the TypedDataSet.

    Args:
        table_id: e.g. "85237NED"
        query:    OData query string, e.g. "$filter=Perioden eq '2024JJ00'"
        max_pages: safety cap on paginated retrieval

    Returns:
        pandas DataFrame.
    """
    url = f"{CBS_BASE}/{table_id}/TypedDataSet"
    if query:
        url += f"?{query}"
    rows = []
    page = 0
    while url and page < max_pages:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        body = resp.json()
        rows.extend(body.get("value", []))
        url = body.get("odata.nextLink", None)
        if url and not url.startswith("http"):
            url = f"{CBS_BASE}/{table_id}/" + url
        page += 1
    return pd.DataFrame(rows)


def fetch_cbs_85237_eindhoven(year: int = 2024) -> pd.DataFrame:
    """
    Active passenger cars by fuel type for the Netherlands and provinces.
    Eindhoven (municipality) totals must be derived from provincial fuel shares
    × municipal car totals because 85237NED is published at province level.
    """
    df = fetch_cbs_table("85237NED",
                         query=f"$filter=Perioden eq '{year}JJ00'")
    df["fuel_type"] = df["Brandstofsoort"].str.strip()
    df["region_code"] = df["RegioS"].str.strip()
    return df


def fetch_cbs_metadata(table_id: str) -> pd.DataFrame:
    """Get the dimension definitions for any CBS table."""
    url = f"{CBS_BASE}/{table_id}/DataProperties"
    return pd.DataFrame(requests.get(url, timeout=30).json()["value"])


# =========================================================================
# 2) Ember — European wholesale electricity prices
# =========================================================================
# Source: https://ember-climate.org/data/data-tools/european-wholesale-electricity-price-data/
# Direct CSV download per country. License: CC-BY 4.0.
#
# The data your team already has (Netherlands.csv, hourly 2015-2025) was
# obtained from this page. To refresh:
# =========================================================================

EMBER_URL_TEMPLATE = ("https://storage.googleapis.com/emb-prod-bkt-publicdata/"
                      "public-downloads/european_wholesale_electricity_prices/"
                      "{country}.csv")

def fetch_ember_hourly(country: str = "Netherlands") -> pd.DataFrame:
    """
    Ember European wholesale electricity prices, hourly per country.
    """
    url = EMBER_URL_TEMPLATE.format(country=country)
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text))
    df["ts_utc"] = pd.to_datetime(df["Datetime (UTC)"])
    df["price_eur_mwh"] = df["Price (EUR/MWhe)"]
    return df


# =========================================================================
# 3) ENTSO-E Transparency Platform — Day-Ahead Prices (hourly)
# =========================================================================
# Source: https://transparency.entsoe.eu/
# Authoritative source for European day-ahead prices. Free with API token
# (register at https://transparency.entsoe.eu/, request token under "My Account
# Settings"). License: ENTSO-E Transparency licence (free reuse with attribution).
#
# NL bidding zone EIC code: 10YNL----------L
# =========================================================================

ENTSOE_URL = "https://web-api.tp.entsoe.eu/api"

def fetch_entsoe_dayahead(start: str, end: str, token: str,
                           area_code: str = "10YNL----------L") -> pd.DataFrame:
    """
    Hourly day-ahead price for an ENTSO-E bidding zone.

    Args:
        start, end: 'YYYY-MM-DD' (UTC)
        token:      ENTSO-E security token (free, register on platform)
        area_code:  default Netherlands

    Returns:
        DataFrame with columns ts_utc, price_eur_mwh
    """
    # ENTSO-E uses YYYYMMDDhhmm format
    s = start.replace("-", "") + "0000"
    e = end.replace("-", "") + "2300"
    params = {
        "securityToken": token,
        "documentType": "A44",          # day-ahead prices
        "in_Domain": area_code,
        "out_Domain": area_code,
        "periodStart": s,
        "periodEnd": e,
    }
    resp = requests.get(ENTSOE_URL, params=params, timeout=60)
    resp.raise_for_status()
    # ENTSO-E returns XML — for full parsing use the `entsoe-py` package
    # https://github.com/EnergieID/entsoe-py
    return resp.text  # raw XML; parsing left to entsoe-py for brevity


# =========================================================================
# 4) OpenChargeMap — public charging point locations
# =========================================================================
# Source: https://openchargemap.org/  License: ODbL (Open Database License)
# Register at https://openchargemap.org/site/develop/api for a free API key.
#
# Reference: https://openchargemap.org/site/develop/api#api-poi
# =========================================================================

OCM_URL = "https://api.openchargemap.io/v3/poi/"

def fetch_chargers_eindhoven(api_key: str, distance_km: int = 10) -> pd.DataFrame:
    """
    Public charging-point POIs in a 10-km radius around Eindhoven centre.
    """
    params = {
        "output": "json",
        "key": api_key,
        "latitude": 51.4416,
        "longitude": 5.4697,
        "distance": distance_km,
        "distanceunit": "KM",
        "maxresults": 5000,
        "compact": True,
        "verbose": False,
    }
    resp = requests.get(OCM_URL, params=params, timeout=30)
    resp.raise_for_status()
    items = resp.json()
    rows = []
    for it in items:
        addr = it.get("AddressInfo", {})
        rows.append({
            "id": it.get("ID"),
            "name": addr.get("Title"),
            "lat": addr.get("Latitude"),
            "lon": addr.get("Longitude"),
            "postcode": addr.get("Postcode"),
            "n_connections": len(it.get("Connections", []) or []),
            "max_power_kw": max(
                (c.get("PowerKW") or 0 for c in (it.get("Connections", []) or [])),
                default=0,
            ),
            "operator": (it.get("OperatorInfo") or {}).get("Title"),
        })
    return pd.DataFrame(rows)


# =========================================================================
# 5) PDOK / Kadaster — addresses & buildings (BAG)
# =========================================================================
# Source: https://www.pdok.nl/
# License: CC-0 (public domain)
# WFS endpoint:
#   https://service.pdok.nl/lv/bag/wfs/v2_0?service=WFS&request=GetCapabilities
#
# For aggregated dwelling counts per PC4, the CBS table 84799NED is easier than
# the raw BAG WFS — it has dwellings per postcode-4 per year.
# =========================================================================

def fetch_dwellings_per_pc4(year: int = 2024) -> pd.DataFrame:
    """CBS 84799NED — Kerncijfers wijken en buurten, per gemeente."""
    return fetch_cbs_table("84799NED",
                           query=f"$filter=Perioden eq '{year}JJ00'")


# =========================================================================
# 6) Eneco / Essent dynamic tariff archive — third-party scrapers
# =========================================================================
# Eneco and Essent do not publish a public historical-rate API. The cleanest
# proxy is `nordpool` or `entsoe-py` for wholesale (above), then apply the
# documented retail formula:
#     consumer_eur_kwh = (wholesale + supplier_margin + energy_tax) * (1 + BTW)
#
# Documented Jan-2026 values:
#     supplier_margin: Eneco €0.0235/kWh, Essent €0.0220/kWh
#     energy_tax (energiebelasting + ODE merged): €0.10154/kWh (2026)
#     BTW (VAT): 21%
# =========================================================================

def apply_retail(wholesale_eur_mwh: float, supplier: str = "eneco") -> float:
    """Convert wholesale €/MWh to consumer €/kWh under NL dynamic tariff rules."""
    NL_TAX_2026 = 0.10154
    NL_VAT = 0.21
    margin = {"eneco": 0.0235, "essent": 0.0220}[supplier]
    return (wholesale_eur_mwh / 1000.0 + margin + NL_TAX_2026) * (1 + NL_VAT)


# =========================================================================
# 7) NDW / DOT-NL — Dutch traffic flow open data
# =========================================================================
# Source: https://opendata.ndw.nu/
# License: CC0 (public domain)
# Useful for validating Eindhoven trip-length distribution.
# =========================================================================


if __name__ == "__main__":
    print("Demo: applying retail formula to sample wholesale price:")
    for p in [0.020, 0.050, 0.100, 0.200]:
        ws_mwh = p * 1000
        en = apply_retail(ws_mwh, "eneco")
        es = apply_retail(ws_mwh, "essent")
        print(f"  Wholesale €{ws_mwh:>6.1f}/MWh → "
              f"Eneco €{en:.4f}/kWh   Essent €{es:.4f}/kWh")
