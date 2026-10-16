import type { Utterance } from '@/meeting/types';

const clockFormat = new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit', second: '2-digit' });

export function transcriptStart(utterances: Utterance[]): number {
  return utterances.reduce((earliest, line) => Math.min(earliest, line.timestamp_ms), Infinity);
}

// Attendee sends Unix time in ms, so lines are shown as time elapsed since the first one.
export function formatElapsed(timestampMs: number, startMs: number): string {
  const seconds = Math.floor(Math.max(timestampMs - startMs, 0) / 1000);
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${pad(Math.floor(seconds / 3600))}:${pad(Math.floor((seconds % 3600) / 60))}:${pad(seconds % 60)}`;
}

export function formatClock(timestampMs: number): string {
  return clockFormat.format(new Date(timestampMs));
}

export interface SpeakerTurn {
  key: string;
  speakerName: string;
  isHost: boolean;
  lines: Utterance[];
}

export function groupTranscript(lines: Utterance[]): SpeakerTurn[] {
  const turns: SpeakerTurn[] = [];
  for (const line of lines) {
    const turn = turns[turns.length - 1];
    if (turn && turn.speakerName === line.speaker_name && turn.isHost === line.speaker_is_host) turn.lines.push(line);
    else turns.push({ key: line.utterance_id, speakerName: line.speaker_name, isHost: line.speaker_is_host, lines: [line] });
  }
  return turns;
}
