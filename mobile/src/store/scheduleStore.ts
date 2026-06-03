import {create} from 'zustand';
import type {Schedule, Vehicle, Charger} from '../types';

interface ScheduleState {
  schedules: Schedule[];
  vehicles: Vehicle[];
  chargers: Charger[];
  setSchedules: (s: Schedule[]) => void;
  setVehicles: (v: Vehicle[]) => void;
  setChargers: (c: Charger[]) => void;
  addSchedule: (s: Schedule) => void;
}

export const useScheduleStore = create<ScheduleState>(set => ({
  schedules: [],
  vehicles: [],
  chargers: [],
  setSchedules: (schedules) => set({schedules}),
  setVehicles: (vehicles) => set({vehicles}),
  setChargers: (chargers) => set({chargers}),
  addSchedule: (s) => set(state => ({schedules: [s, ...state.schedules]})),
}));
