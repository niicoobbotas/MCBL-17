import pandas as pd
import matplotlib.pyplot as plt

plt.style.use('bmh')

df_price = pd.read_csv(r"C:\Users\nicol\OneDrive - TU Eindhoven\Desktop\Year 2\Q4\Urban Mobility Startups For Liveable Cities 4CBLW017\Data_Set\Data_Set\Dataset 7 – Electricity Prices\european_wholesale_electricity_price_data_hourly\Netherlands.csv")
df_price['Datetime (Local)'] = pd.to_datetime(df_price['Datetime (Local)'])

df_load = pd.read_excel(r"C:\Users\nicol\OneDrive - TU Eindhoven\Desktop\Year 2\Q4\Urban Mobility Startups For Liveable Cities 4CBLW017\Data_Set\Data_Set\Dataset 6 – Electricity Load (Demand)\GUI_TOTAL_LOAD_DAYAHEAD_202412312300-202501072300.xlsx", skiprows=7)
df_load.columns = ['MTU', 'Actual_Load', 'Forecast_Load']
df_load['Timestamp'] = pd.to_datetime(df_load['MTU'].str.split(' - ').str[0], dayfirst=True)

df_congestie = pd.read_csv(r"C:\Users\nicol\OneDrive - TU Eindhoven\Desktop\Year 2\Q4\Urban Mobility Startups For Liveable Cities 4CBLW017\Data_Set\Data_Set\Dataset 5 – Grid Congestion & Constraints\tennetcongestie.csv", sep=";")

df_ehv_load = pd.read_csv(r"C:\Users\nicol\OneDrive - TU Eindhoven\Desktop\Year 2\Q4\Urban Mobility Startups For Liveable Cities 4CBLW017\Data_Set\Data_Set\Dataset 6 – Electricity Load (Demand)\eindhoven_zonal_load.csv")
df_ehv_load['timestamp'] = pd.to_datetime(df_ehv_load['timestamp'])


plt.figure(figsize=(12, 6))
latest_date = df_price['Datetime (Local)'].max()
mask = (df_price['Datetime (Local)'] > (latest_date - pd.Timedelta(days=30)))
data_p1 = df_price[mask]
plt.plot(data_p1['Datetime (Local)'], data_p1['Price (EUR/MWhe)'], color='blue', linewidth=1.5)
plt.title('Netherlands Wholesale Electricity Prices (Last 30 Days)')
plt.ylabel('Price (EUR/MWh)')
plt.grid(True, alpha=0.3)
plt.savefig('nl_electricity_prices.png')

plt.figure(figsize=(12, 6))
plt.plot(df_load['Timestamp'], df_load['Actual_Load'], label='Actual Load', alpha=0.8)
plt.plot(df_load['Timestamp'], df_load['Forecast_Load'], label='Day-Ahead Forecast', linestyle='--', alpha=0.8)
plt.title('National Grid Load Analysis')
plt.ylabel('Load (MW)')
plt.legend()
plt.savefig('national_load_analysis.png')

plt.figure(figsize=(10, 5))
congestie_counts = df_congestie['afname'].value_counts().sort_index()
# Converting index to string for the X-axis labels
plt.bar(congestie_counts.index.astype(str), congestie_counts.values, color='salmon', edgecolor='black')
plt.title('Distribution of Congestion Level (0=None, 3=Full) at TenneT Stations')
plt.xlabel('Congestion Level (Afname/Demand)')
plt.ylabel('Number of Stations')
plt.savefig('congestion_summary.png')

plt.figure(figsize=(12, 6))
subset_zones = ['Z1', 'Z2', 'Z5', 'Z10']
for zone in subset_zones:
    zone_data = df_ehv_load[df_ehv_load['zone_id'] == zone]
    plt.plot(zone_data['timestamp'], zone_data['demand_MW'], label=zone)
plt.title('Eindhoven Local Demand: Comparing Top Zones')
plt.ylabel('Demand (MW)')
plt.legend(title='Zone ID')
plt.savefig('eindhoven_zonal_demand.png')

print(f"Average Electricity Price: {df_price['Price (EUR/MWhe)'].mean():.2f} EUR/MWh")
print(f"Max Recorded Price: {df_price['Price (EUR/MWhe)'].max():.2f} EUR/MWh")
print(f"Percentage of Stations with Full Congestion: {(len(df_congestie[df_congestie['afname'] == 3]) / len(df_congestie) * 100):.1f}%")