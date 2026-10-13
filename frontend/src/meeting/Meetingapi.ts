import axios from 'axios';
import type { ApiResponse, CreateMeetingInput, Meeting, MeetingDetail, MeetingFilters, MeetingListResponse } from '@/meeting/types';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

function auth(apiKey: string) {
  return { headers: { 'X-API-Key': apiKey } };
}

export async function createMeeting(apiKey: string, input: CreateMeetingInput) {
  const response = await api.post<ApiResponse<Meeting>>('/meetings', input, auth(apiKey));
  return response.data;
}

export async function listMeetings(apiKey: string, filters: MeetingFilters, signal?: AbortSignal) {
  const response = await api.get<MeetingListResponse>('/meetings', { ...auth(apiKey), params: filters, signal });
  return response.data;
}

export async function getMeeting(apiKey: string, meetingId: string, signal?: AbortSignal) {
  const response = await api.get<ApiResponse<MeetingDetail>>(`/meetings/${encodeURIComponent(meetingId)}`, { ...auth(apiKey), signal });
  return response.data;
}

export async function leaveMeeting(apiKey: string, meetingId: string) {
  const response = await api.post<ApiResponse<Meeting>>(`/meetings/${encodeURIComponent(meetingId)}/leave`, undefined, auth(apiKey));
  return response.data;
}

export async function regenerateMinutes(apiKey: string, meetingId: string) {
  const response = await api.post<ApiResponse<Meeting>>(`/meetings/${encodeURIComponent(meetingId)}/minutes`, undefined, auth(apiKey));
  return response.data;
}

export async function checkBackend() {
  const base = new URL(api.defaults.baseURL || '/api', window.location.origin);
  const response = await axios.get<{ data?: { status?: string } }>(new URL('/health', base).toString(), { timeout: 5000 });
  return response.status === 200 && response.data?.data?.status === 'healthy';
}

export function getApiError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const body = error.response?.data as {
      error?: { message?: string; details?: { field: string; message: string }[] };
      detail?: string;
    } | undefined;
    if (error.response?.status === 401) return 'Invalid API key. Check INTERNAL_API_KEY in backend/.env.';
    const detail = body?.error?.details?.[0];
    if (detail) return `${detail.field}: ${detail.message}`;
    if (body?.error?.message) return body.error.message;
    if (body?.detail) return body.detail;
    if (!error.response) return 'Cannot reach the backend. Start it and check the frontend proxy settings.';
    if (error.response.status >= 500) return 'The backend is unavailable or returned an error. Check its server and logs.';
  }
  return 'Something went wrong. Please try again.';
}
