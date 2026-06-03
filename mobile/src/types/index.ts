export interface User {
  id: string;
  email: string;
  name: string;
  created_at: string;
}

export interface Vehicle {
  id: string;
  name: string;
  battery_capacity_kwh: number;
  max_charge_rate_kw: number;
  current_soc_percent: number;
  target_soc_percent: number;
}

export interface Charger {
  id: string;
  name: string;
  status: 'idle' | 'charging' | 'offline';
  pi_address: string | null;
  max_power_kw: number;
}

export type OptimizationMode = 'price' | 'battery_life' | 'smart';

export interface ScheduleSlot {
  id: string;
  start_time: string;
  end_time: string;
  charge_rate_kw: number;
  estimated_cost: number;
  estimated_kwh: number;
}

export interface Schedule {
  id: string;
  vehicle_id: string;
  charger_id: string;
  available_from: string;
  needed_by: string;
  optimization_mode: OptimizationMode;
  status: 'pending' | 'active' | 'completed' | 'cancelled';
  created_at: string;
  slots: ScheduleSlot[];
}

export interface PricePoint {
  timestamp: string;
  price_area: string;
  price_eur_per_mwh: number;
}

export interface SavingsSummary {
  total_savings: number;
  total_optimized_cost: number;
  total_naive_cost: number;
  savings_percent: number;
  daily: {
    date: string;
    optimized_cost: number;
    naive_cost: number;
    savings: number;
  }[];
}

export interface ChargingSession {
  id: string;
  vehicle_name: string;
  start_time: string;
  end_time: string | null;
  energy_kwh: number;
  cost: number;
  naive_cost: number;
  savings: number;
}
