import axios from 'axios';

import { clearSession, getSession } from '@/auth/session';

export const api = axios.create({
  baseURL: import.meta.env.API_BASE_URL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config) => {
  const session = getSession();
  if (session && !config.headers.Authorization) config.headers.Authorization = `Bearer ${session.accessToken}`;
  return config;
});

api.interceptors.response.use(undefined, (error) => {
  if (axios.isAxiosError(error) && error.response?.status === 401) {
    const sentToken = error.config?.headers?.Authorization;
    const session = getSession();
    // A request that left before a password change must not wipe the fresh session.
    if (session && sentToken === `Bearer ${session.accessToken}`) clearSession();
  }
  return Promise.reject(error);
});

export function getApiError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const body = error.response?.data as {
      error?: { message?: string; details?: { field: string; message: string }[] };
      detail?: string;
    } | undefined;
    const detail = body?.error?.details?.[0];
    if (detail) return `${detail.field}: ${detail.message}`;
    if (body?.error?.message) return body.error.message;
    if (body?.detail) return body.detail;
    if (!error.response) return 'Cannot reach the backend. Start it and check the frontend proxy settings.';
    if (error.response.status === 401) return 'Your session has ended. Please log in again.';
    if (error.response.status === 429) return 'Too many attempts. Please wait a minute and try again.';
    if (error.response.status >= 500) return 'The backend is unavailable or returned an error. Check its server and logs.';
  }
  return 'Something went wrong. Please try again.';
}
