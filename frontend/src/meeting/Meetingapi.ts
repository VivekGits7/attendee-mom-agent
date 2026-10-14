import axios from 'axios';
import type { ApiResponse, CreateMeetingInput, Meeting, MeetingDetail, MeetingFilters, MeetingListResponse } from '@/meeting/types';

const api = axios.create({
  baseURL: import.meta.env.API_BASE_URL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

export async function createMeeting(input: CreateMeetingInput) {
  const response = await api.post<ApiResponse<Meeting>>('/meetings', input);
  return response.data;
}

export async function listMeetings(filters: MeetingFilters, signal?: AbortSignal) {
  const response = await api.get<MeetingListResponse>('/meetings', { params: filters, signal });
  return response.data;
}

export async function getMeeting(meetingId: string, signal?: AbortSignal) {
  const response = await api.get<ApiResponse<MeetingDetail>>(`/meetings/${encodeURIComponent(meetingId)}`, { signal });
  return response.data;
}

export async function leaveMeeting(meetingId: string) {
  const response = await api.post<ApiResponse<Meeting>>(`/meetings/${encodeURIComponent(meetingId)}/leave`);
  return response.data;
}

export async function regenerateMinutes(meetingId: string) {
  const response = await api.post<ApiResponse<Meeting>>(`/meetings/${encodeURIComponent(meetingId)}/minutes`);
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
    if (error.response?.status === 401) return 'The backend rejected the API key. Make BACKEND_API_KEY in frontend/.env match INTERNAL_API_KEY in backend/.env, then restart the frontend.';
    const detail = body?.error?.details?.[0];
    if (detail) return `${detail.field}: ${detail.message}`;
    if (body?.error?.message) return body.error.message;
    if (body?.detail) return body.detail;
    if (!error.response) return 'Cannot reach the backend. Start it and check the frontend proxy settings.';
    if (error.response.status >= 500) return 'The backend is unavailable or returned an error. Check its server and logs.';
  }
  return 'Something went wrong. Please try again.';
}
