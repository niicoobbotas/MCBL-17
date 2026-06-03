import {create} from 'zustand';
import type {User} from '../types';

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: User | null;
  isAuthenticated: boolean;
  isDemo: boolean;
  setTokens: (access: string, refresh: string) => void;
  setUser: (user: User) => void;
  loginDemo: () => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>(set => ({
  accessToken: null,
  refreshToken: null,
  user: null,
  isAuthenticated: false,
  isDemo: false,
  setTokens: (access, refresh) =>
    set({accessToken: access, refreshToken: refresh, isAuthenticated: true}),
  setUser: (user) => set({user}),
  loginDemo: () =>
    set({
      accessToken: 'demo',
      refreshToken: 'demo',
      isAuthenticated: true,
      isDemo: true,
      user: {
        id: 'demo-user-001',
        email: 'demo@evcharger.app',
        name: 'Andrei',
        created_at: new Date().toISOString(),
      },
    }),
  logout: () =>
    set({
      accessToken: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,
      isDemo: false,
    }),
}));
