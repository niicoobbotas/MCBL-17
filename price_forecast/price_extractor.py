import requests
from datetime import datetime, timedelta
import pytz 

def fetch_eindhoven_prices():
    url = "https://api.energyzero.nl/v1/energyprices"
    tz = pytz.timezone('Europe/Amsterdam')
    
    tomorrow = datetime.now(tz) + timedelta(days=1)
    start_dt = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
    end_dt = tomorrow.replace(hour=23, minute=59, second=59, microsecond=0)

    params = {
        "fromDate": start_dt.astimezone(pytz.UTC).strftime('%Y-%m-%dT%H:%M:%S.000Z'),
        "tillDate": end_dt.astimezone(pytz.UTC).strftime('%Y-%m-%dT%H:%M:%S.000Z'),
        "interval": 4,
        "usageType": 1,
        "inclBtw": "true"
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        return data.get('Prices', [])
    except requests.exceptions.RequestException as e:
        print(f"Hardware Buffer Error: Could not fetch data - {e}")
        return []

if __name__ == "__main__":
    prices = fetch_eindhoven_prices()
    for entry in prices:
        utc_time = datetime.fromisoformat(entry['readingDate'].replace('Z', '+00:00'))
        local_time = utc_time.astimezone(pytz.timezone('Europe/Amsterdam'))
        
        print(f"Time: {local_time.strftime('%H:%M')} | Price: €{entry['price']:.4f}/kWh")