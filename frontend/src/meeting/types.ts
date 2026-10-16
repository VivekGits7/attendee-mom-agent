export type MeetingStatus = 'scheduled' | 'joining' | 'in_progress' | 'processing' | 'completed' | 'failed';
export type EmailStatus = 'pending' | 'sent' | 'sent_to_fallback' | 'failed';

export interface CreateMeetingInput {
  meeting_url: string;
  title: string;
  recipient_email: string | null;
  join_at: string | null;
}

export interface Meeting {
  meeting_id: string;
  title: string;
  meeting_url: string;
  platform: 'google_meet' | 'teams';
  bot_id: string | null;
  bot_state: string | null;
  status: MeetingStatus;
  recipient_email: string | null;
  join_at: string | null;
  ends_at: string | null;
  calendar_synced: boolean;
  email_status: EmailStatus;
  email_sent_to: string | null;
  error_message: string | null;
  created_at: string;
}

export interface Utterance {
  utterance_id: string;
  speaker_name: string;
  speaker_is_host: boolean;
  timestamp_ms: number;
  duration_ms: number;
  text: string;
}

export interface Minutes {
  summary: string;
  outcomes: { item: string; owner: string | null; due_date: string | null }[];
  open_questions: string[];
}

export interface MeetingDetail extends Meeting {
  utterances: Utterance[];
  minutes: Minutes | null;
}

export type LiveMessage =
  | { type: 'snapshot'; data: { meeting: Meeting; utterances: Utterance[] } }
  | { type: 'utterance'; data: Utterance }
  | { type: 'status'; data: Meeting }
  | { type: 'ping' }
  | { type: 'failed'; message: string };

export interface ApiResponse<T> {
  success: boolean;
  message: string;
  data: T;
}

export interface MeetingListResponse extends ApiResponse<Meeting[]> {
  total: number;
  limit: number;
  offset: number;
}

export interface MeetingFilters {
  search?: string;
  status?: MeetingStatus;
  platform?: Meeting['platform'];
  join_from?: string;
  join_until?: string;
  sort_by?: 'title' | 'status' | 'created_at' | 'join_at';
  sort_order?: 'latest' | 'oldest' | 'a_to_z' | 'z_to_a';
  limit?: number;
  offset?: number;
}
