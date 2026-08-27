import apiClient from './client';

export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export async function login(data: LoginRequest): Promise<TokenResponse> {
  const res = await apiClient.post<TokenResponse>('/auth/login', data);
  return res.data;
}

export async function register(data: LoginRequest): Promise<TokenResponse> {
  const res = await apiClient.post<TokenResponse>('/auth/register', data);
  return res.data;
}