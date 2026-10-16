import axios from 'axios';

import { api } from '@/lib/http';
import type { ApiResponse, CreateMeetingInput, Meeting, MeetingDetail, MeetingFilters, MeetingListResponse } from '@/meeting/types';

export { getApiError } from '@/lib/http';

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
