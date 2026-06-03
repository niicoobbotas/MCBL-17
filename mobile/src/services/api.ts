import axios from 'axios';
import {useAuthStore} from '../store/authStore';
import type {OptimizationMode} from '../types';

const API_BASE = 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE,
  headers: {'Content-Type': 'application/json'},
});

// Attach JWT token to every request
api.interceptors.request.use(config => {
  const token = useAuthStore.getState().accessToken;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Auto-refresh on 401
api.interceptors.response.use(
  response => response,
  async error => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;
      const refreshToken = useAuthStore.getState().refreshToken;
      if (refreshToken) {
        try {
          const res = await axios.post(`${API_BASE}/api/auth/refresh`, {
            refresh_token: refreshToken,
          });
          const {access_token, refresh_token} = res.data;
          useAuthStore.getState().setTokens(access_token, refresh_token);
          original.headers.Authorization = `Bearer ${access_token}`;
          return api(original);
        } catch {
          useAuthStore.getState().logout();
        }
      }
    }
    return Promise.reject(error);
  },
);

// Auth
export const registerUser = (email: string, password: string, name: string) =>
  api.post('/api/auth/register', {email, password, name});

export const loginUser = (email: string, password: string) =>
  api.post('/api/auth/login', {email, password});

export const getMe = () => api.get('/api/auth/me');

// Vehicles
export const getVehicles = () => api.get('/api/vehicles/');
export const createVehicle = (data: {
  name: string;
  battery_capacity_kwh: number;
  max_charge_rate_kw: number;
  current_soc_percent?: number;
  target_soc_percent?: number;
}) => api.post('/api/vehicles/', data);
export const updateVehicle = (id: string, data: Record<string, unknown>) =>
  api.put(`/api/vehicles/${id}`, data);
export const deleteVehicle = (id: string) =>
  api.delete(`/api/vehicles/${id}`);

// Chargers
export const getChargers = () => api.get('/api/chargers/');
export const createCharger = (data: {
  name: string;
  max_power_kw: number;
  pi_address?: string;
}) => api.post('/api/chargers/', data);
export const deleteCharger = (id: string) =>
  api.delete(`/api/chargers/${id}`);
export const getChargerStatus = (id: string) =>
  api.get(`/api/chargers/${id}/status`);

// Prices
export const getPrices = (area?: string, date?: string) =>
  api.get('/api/prices/', {params: {area, date}});
export const getCurrentPrice = (area?: string) =>
  api.get('/api/prices/current', {params: {area}});

// Schedules
export const createSchedule = (data: {
  vehicle_id: string;
  charger_id: string;
  available_from: string;
  needed_by: string;
  optimization_mode: OptimizationMode;
}) => api.post('/api/schedules/', data);
export const getSchedules = () => api.get('/api/schedules/');
export const getSchedule = (id: string) => api.get(`/api/schedules/${id}`);
export const cancelSchedule = (id: string) =>
  api.delete(`/api/schedules/${id}`);

// Dashboard
export const getSavings = (period?: string) =>
  api.get('/api/dashboard/savings', {params: {period}});
export const getHistory = () => api.get('/api/dashboard/history');

export default api;
