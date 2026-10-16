import { useEffect, useRef, useState } from 'react';

import { clearSession, getSession, subscribeSession } from '@/auth/session';
import type { LiveMessage, Meeting, Utterance } from '@/meeting/types';

const LOGIN_ENDED = 4001;
const GIVE_UP_CODES = new Set([4002, 4004]);
const MAX_RETRY_MS = 15000;

export type LiveMeetingReason = 'snapshot' | 'status';

export function liveTranscriptUrl(meetingId: string): string {
  const url = new URL(import.meta.env.API_BASE_URL, window.location.origin);
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  url.pathname = `${url.pathname.replace(/\/$/, '')}/ws/meetings/${encodeURIComponent(meetingId)}/transcript`;
  return url.toString();
}

function upsertLine(lines: Utterance[], line: Utterance): Utterance[] {
  const index = lines.findIndex((current) => current.utterance_id === line.utterance_id);
  if (index >= 0) return lines.map((current, position) => (position === index ? line : current));
  const last = lines[lines.length - 1];
  if (!last || last.timestamp_ms <= line.timestamp_ms) return [...lines, line];
  return [...lines, line].sort((a, b) => a.timestamp_ms - b.timestamp_ms);
}

// Returns the streamed transcript while the socket is live, and null whenever the page should fall back to polling.
export function useLiveTranscript(
  meetingId: string | undefined,
  enabled: boolean,
  onMeeting: (meeting: Meeting, reason: LiveMeetingReason) => void,
): Utterance[] | null {
  const [token, setToken] = useState(() => getSession()?.accessToken ?? null);
  const [stream, setStream] = useState<{ key: string; lines: Utterance[] } | null>(null);
  const onMeetingRef = useRef(onMeeting);
  const key = meetingId && enabled && token ? `${meetingId}|${token}` : null;

  useEffect(() => {
    onMeetingRef.current = onMeeting;
  }, [onMeeting]);

  useEffect(() => subscribeSession((session) => setToken(session?.accessToken ?? null)), []);

  useEffect(() => {
    if (!key || !meetingId || !token) return;
    let socket: WebSocket | null = null;
    let retryTimer: number | undefined;
    let attempt = 0;
    let stopped = false;

    const connect = () => {
      const ws = new WebSocket(liveTranscriptUrl(meetingId));
      socket = ws;
      ws.onopen = () => ws.send(JSON.stringify({ token }));
      ws.onmessage = (event) => {
        let message: LiveMessage;
        try {
          message = JSON.parse(String(event.data)) as LiveMessage;
        } catch {
          return;
        }
        if (message.type === 'snapshot') {
          attempt = 0;
          setStream({ key, lines: message.data.utterances });
          onMeetingRef.current(message.data.meeting, 'snapshot');
        } else if (message.type === 'utterance') {
          setStream((current) => (current?.key === key ? { key, lines: upsertLine(current.lines, message.data) } : current));
        } else if (message.type === 'status') {
          onMeetingRef.current(message.data, 'status');
        }
      };
      ws.onclose = (event) => {
        socket = null;
        if (stopped) return;
        setStream(null);
        if (event.code === LOGIN_ENDED) {
          // A socket opened before a password change must not wipe the fresh session.
          if (getSession()?.accessToken === token) clearSession();
          return;
        }
        if (GIVE_UP_CODES.has(event.code)) return;
        retryTimer = window.setTimeout(connect, Math.min(1000 * 2 ** attempt, MAX_RETRY_MS));
        attempt += 1;
      };
    };

    connect();
    return () => {
      stopped = true;
      window.clearTimeout(retryTimer);
      socket?.close(1000);
      setStream(null);
    };
  }, [key, meetingId, token]);

  return stream && stream.key === key ? stream.lines : null;
}
