import { api } from '@/lib/http';
import type { ChangePasswordInput, LoginResponse, TokenResponse } from '@/auth/types';

export async function login(email: string, password: string) {
  const form = new URLSearchParams({ username: email, password });
  const response = await api.post<LoginResponse>('/auth/login', form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  return response.data;
}

export async function logout() {
  await api.post('/auth/logout');
}

export async function changePassword(input: ChangePasswordInput) {
  const response = await api.post<TokenResponse>('/auth/change-password', input);
  return response.data;
}
