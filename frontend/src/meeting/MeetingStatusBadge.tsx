import type { MeetingStatus } from '@/meeting/types';

export function MeetingStatusBadge({ status }: { status: MeetingStatus }) {
  const tone = status === 'completed' ? 'success' : status === 'failed' ? 'danger' : 'live';
  return <span className={`status-pill ${tone}`}><span className="status-dot" />{status.replace(/_/g, ' ')}</span>;
}
