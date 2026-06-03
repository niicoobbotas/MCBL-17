import type {Vehicle, Charger, Schedule, PricePoint, ChargingSession} from '../types';

export const demoVehicles: Vehicle[] = [
  {
    id: 'v-001',
    name: 'Tesla Model 3',
    battery_capacity_kwh: 75,
    max_charge_rate_kw: 11,
    current_soc_percent: 35,
    target_soc_percent: 80,
  },
];

export const demoChargers: Charger[] = [
  {
    id: 'c-001',
    name: 'Home Charger',
    status: 'idle',
    pi_address: '192.168.1.50',
    max_power_kw: 11,
  },
];

function todayAt(hour: number): string {
  const d = new Date();
  d.setHours(hour, 0, 0, 0);
  return d.toISOString();
}

export const demoSchedule: Schedule = {
  id: 's-001',
  vehicle_id: 'v-001',
  charger_id: 'c-001',
  available_from: todayAt(22),
  needed_by: todayAt(7),
  optimization_mode: 'price',
  status: 'active',
  created_at: new Date().toISOString(),
  slots: [
    {
      id: 'sl-001',
      start_time: todayAt(1),
      end_time: todayAt(3),
      charge_rate_kw: 11,
      estimated_cost: 1.32,
      estimated_kwh: 22,
    },
    {
      id: 'sl-002',
      start_time: todayAt(4),
      end_time: todayAt(6),
      charge_rate_kw: 11,
      estimated_cost: 1.08,
      estimated_kwh: 22,
    },
  ],
};

export function generateDemoPrices(): PricePoint[] {
  const prices: PricePoint[] = [];
  // Realistic NL day-ahead price curve (EUR/MWh)
  const hourlyPrices = [
    62, 58, 52, 48, 45, 42, 55, 78, 120, 135, 128, 115,
    98, 88, 82, 85, 95, 145, 168, 155, 130, 105, 85, 70,
  ];
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  for (let h = 0; h < 24; h++) {
    const ts = new Date(today);
    ts.setHours(h);
    prices.push({
      timestamp: ts.toISOString(),
      price_area: 'NL',
      price_eur_per_mwh: hourlyPrices[h],
    });
  }
  return prices;
}

export const demoSessions: ChargingSession[] = [
  {
    id: 'cs-001',
    vehicle_name: 'Tesla Model 3',
    start_time: daysAgo(1, 1),
    end_time: daysAgo(1, 5),
    energy_kwh: 24,
    cost: 2.88,
    naive_cost: 4.56,
    savings: 1.68,
  },
  {
    id: 'cs-002',
    vehicle_name: 'Tesla Model 3',
    start_time: daysAgo(4, 2),
    end_time: daysAgo(4, 6),
    energy_kwh: 18,
    cost: 2.10,
    naive_cost: 3.42,
    savings: 1.32,
  },
  {
    id: 'cs-003',
    vehicle_name: 'Tesla Model 3',
    start_time: daysAgo(8, 23),
    end_time: daysAgo(7, 4),
    energy_kwh: 30,
    cost: 3.60,
    naive_cost: 5.70,
    savings: 2.10,
  },
];

function daysAgo(days: number, hour: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  d.setHours(hour, 0, 0, 0);
  return d.toISOString();
}
