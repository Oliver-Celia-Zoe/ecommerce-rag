import { create } from 'zustand';
import { login as loginApi, register as registerApi, type LoginRequest, type TokenResponse } from '../api/auth';

interface AuthState {
  isAuthenticated: boolean;
  username: string | null;
  login: (data: LoginRequest) => Promise<void>;
  register: (data: LoginRequest) => Promise<void>;
  logout: () => void;
  checkAuth: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  isAuthenticated: false,
  username: null,

  login: async (data) => {
    const res: TokenResponse = await loginApi(data);
    localStorage.setItem('access_token', res.access_token);
    set({ isAuthenticated: true, username: data.username });
  },

  register: async (data) => {
    const res: TokenResponse = await registerApi(data);
    localStorage.setItem('access_token', res.access_token);
    set({ isAuthenticated: true, username: data.username });
  },

  logout: () => {
    localStorage.removeItem('access_token');
    set({ isAuthenticated: false, username: null });
  },

  checkAuth: () => {
    const token = localStorage.getItem('access_token');
    set({ isAuthenticated: !!token, username: localStorage.getItem('username') });
  },
}));