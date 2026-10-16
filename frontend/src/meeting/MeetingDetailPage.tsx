import { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowLeft, ArrowUpRight, Check, CircleAlert, Clock3, Copy, ExternalLink, FileText, LoaderCircle, Mic2, RefreshCw, Square } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';

import { StudioHeader } from '@/components/StudioHeader';
import { getApiError, getMeeting, leaveMeeting, regenerateMinutes } from '@/meeting/Meetingapi';
import { MeetingStatusBadge } from '@/meeting/MeetingStatusBadge';
import { formatClock, formatElapsed, transcriptStart } from '@/meeting/transcript';
import type { Meeting, MeetingDetail, Minutes } from '@/meeting/types';
import { type LiveMeetingReason, useLiveTranscript } from '@/meeting/useLiveTranscript';
import './pages.css';

type Action = 'leave' | 'minutes' | null;
const finalBotStates = new Set(['ended', 'fatal_error']);
const stoppedBotStates = new Set(['leaving', 'post_processing', 'ended', 'fatal_error']);
const activeStatuses = new Set(['scheduled', 'joining', 'in_progress', 'processing']);
const POLL_MS = 5000;
const LIVE_REFRESH_MS = 30000;

function formatDate(value: string | null) {
  if (!value) return 'Not scheduled';
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));
}

function NotesSection({ title, items }: { title: string; items: string[] }) {
  return <section className="report-section"><div className="report-section-heading"><h3>{title}</h3><span>{String(items.length).padStart(2, '0')}</span></div>{items.length ? <ul className="report-list">{items.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul> : <p className="muted-copy">Nothing recorded.</p>}</section>;
}

function MinutesReport({ minutes }: { minutes: Minutes }) {
  return <div className="report-content">
    <div className="report-summary"><span className="eyebrow">SUMMARY</span><p>{minutes.summary}</p></div>
    <section className="report-section">
      <div className="report-section-heading"><h3>Outcomes</h3><span>{String(minutes.outcomes.length).padStart(2, '0')}</span></div>
      {minutes.outcomes.length ? <div className="report-actions">{minutes.outcomes.map((outcome, index) => <div className="report-action" key={`${outcome.item}-${index}`}><span>{String(index + 1).padStart(2, '0')}</span><div><strong>{outcome.item}</strong>{(outcome.owner || outcome.due_date) && <p>{[outcome.owner, outcome.due_date && `Due ${outcome.due_date}`].filter(Boolean).join(' · ')}</p>}</div></div>)}</div> : <p className="muted-copy">Nothing recorded.</p>}
    </section>
    <NotesSection title="Open questions" items={minutes.open_questions} />
  </div>;
}

export default function MeetingDetailPage() {
  const { meetingId } = useParams();
  const [meeting, setMeeting] = useState<MeetingDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [lastSynced, setLastSynced] = useState<Date | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);
  const [action, setAction] = useState<Action>(null);
  const [copied, setCopied] = useState(false);
  const watching = !meeting || activeStatuses.has(meeting.status) || (meeting.status === 'completed' && meeting.email_status === 'pending');
  const pollNeeded = useRef(true);
  pollNeeded.current = watching;
  const reloadRef = useRef<(() => void) | null>(null);

  const handleLiveMeeting = useCallback((data: Meeting, reason: LiveMeetingReason) => {
    setMeeting((current) => (current ? { ...current, ...data } : current));
    setLastSynced(new Date());
    // Status events can mean new minutes or an email result, which only the REST detail carries.
    if (reason === 'status') reloadRef.current?.();
  }, []);

  const liveLines = useLiveTranscript(meetingId, Boolean(meeting) && watching, handleLiveMeeting);
  const isLive = liveLines !== null;
  const liveRef = useRef(false);
  liveRef.current = isLive;

  useEffect(() => {
    if (!meetingId) { setMeeting(null); setError(''); return; }
    let active = true;
    let inFlight = false;
    let lastLoadedAt = 0;
    const controller = new AbortController();
    const load = async (showLoading: boolean) => {
      if (inFlight) return;
      inFlight = true;
      if (showLoading) setLoading(true);
      try {
        const response = await getMeeting(meetingId, controller.signal);
        lastLoadedAt = Date.now();
        if (active) { setMeeting(response.data); setError(''); setLastSynced(new Date()); }
      } catch (requestError) {
        if (active) setError(getApiError(requestError));
      } finally {
        inFlight = false;
        if (active) setLoading(false);
      }
    };
    reloadRef.current = () => void load(false);
    void load(true);
    const timer = window.setInterval(() => {
      if (document.visibilityState !== 'visible' || !pollNeeded.current) return;
      if (liveRef.current && Date.now() - lastLoadedAt < LIVE_REFRESH_MS) return;
      void load(false);
    }, POLL_MS);
    return () => { active = false; reloadRef.current = null; controller.abort(); window.clearInterval(timer); };
  }, [meetingId, refreshToken]);

  async function handleAction(nextAction: Exclude<Action, null>) {
    if (!meeting) return;
    const prompt = nextAction === 'leave'
      ? 'Make the bot leave now? Minutes will be generated when the meeting ends.'
      : 'Regenerate the minutes and send the email again?';
    if (!window.confirm(prompt)) return;
    setAction(nextAction);
    setError('');
    setNotice('');
    try {
      const response = nextAction === 'leave'
        ? await leaveMeeting(meeting.meeting_id)
        : await regenerateMinutes(meeting.meeting_id);
      setMeeting((current) => current ? { ...current, ...response.data } : current);
      setNotice(response.message);
      setRefreshToken((token) => token + 1);
    } catch (requestError) {
      setError(getApiError(requestError));
    } finally {
      setAction(null);
    }
  }

  async function copyId() {
    if (!meeting) return;
    try {
      await navigator.clipboard.writeText(meeting.meeting_id);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setError('Could not copy the meeting ID.');
    }
  }

  const lines = liveLines ?? meeting?.utterances ?? [];
  const startMs = transcriptStart(lines);
  const canLeave = Boolean(meeting?.bot_id && !stoppedBotStates.has(meeting.bot_state || '') && meeting.status !== 'failed');
  const canRegenerate = Boolean(meeting && finalBotStates.has(meeting.bot_state || '') && meeting.status !== 'processing');

  return <div className="site-shell overflow-x-hidden"><a className="skip-link" href="#main">Skip to main content</a><StudioHeader /><main id="main"><section className="detail-hero"><div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8"><Link className="back-link" to="/meetings"><ArrowLeft size={17} /> All meetings</Link><div className="section-index"><span className="index-line" /> LIVE SESSION <span className="index-number">/ 003</span></div><div className="detail-hero-title"><div><h1>{meeting?.title || 'Meeting details'}<span className="blue-period">.</span></h1><p>{meeting ? (meeting.platform === 'google_meet' ? 'Google Meet' : 'Microsoft Teams') : 'Transcript and meeting minutes'}</p></div>{meeting && <MeetingStatusBadge status={meeting.status} />}</div></div></section><section className="detail-body"><div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8"><div className="detail-toolbar"><span className="eyebrow">MEETING WORKSPACE</span><div><span className="sync-indicator"><span className={watching ? 'sync-dot active' : 'sync-dot'} />{isLive ? 'Live · real time' : watching ? 'Live sync · every 5s' : 'Up to date'}</span>{lastSynced && <span className="last-synced">Last update {lastSynced.toLocaleTimeString()}</span>}<button type="button" className="icon-refresh" onClick={() => setRefreshToken((token) => token + 1)} disabled={loading} aria-label="Refresh meeting"><RefreshCw size={19} className={loading ? 'spin' : ''} /></button></div></div>{error && <div className="inline-error" role="alert"><CircleAlert size={18} />{error}</div>}{notice && <div className="inline-success" role="status"><Check size={18} />{notice}</div>}{loading && !meeting ? <div className="library-empty"><LoaderCircle size={30} className="spin" /><h2>Loading the meeting...</h2></div> : meeting ? <><div className="detail-overview"><div className="detail-overview-main"><div className="meeting-id"><span>{meeting.meeting_id}</span><button type="button" onClick={() => void copyId()} aria-label="Copy meeting ID">{copied ? <Check size={17} /> : <Copy size={17} />}</button></div><p>{meeting.status === 'completed' ? 'The transcript and MOM are ready.' : meeting.status === 'failed' ? 'This meeting needs attention.' : 'The bot and transcript update as the meeting progresses.'}</p></div><div className="detail-overview-facts"><div><span>BOT STATE</span><strong>{(meeting.bot_state || 'pending').replace(/_/g, ' ')}</strong></div><div><span>STARTED</span><strong>{formatDate(meeting.created_at)}</strong></div><div><span>SCHEDULED JOIN</span><strong>{meeting.join_at ? formatDate(meeting.join_at) : 'Joined now'}</strong></div><div><span>MINUTES EMAIL</span><strong>{meeting.email_status.replace(/_/g, ' ')}</strong><small>{meeting.email_sent_to || meeting.recipient_email || 'Default recipient'}</small></div></div></div>{meeting.error_message && <div className="inline-error" role="alert"><CircleAlert size={18} />{meeting.error_message}</div>}<div className="detail-actions"><a href={meeting.meeting_url} target="_blank" rel="noopener noreferrer"><ExternalLink size={17} /> Open meeting link</a><button type="button" onClick={() => void handleAction('leave')} disabled={!canLeave || action !== null}>{action === 'leave' ? <LoaderCircle size={17} className="spin" /> : <Square size={16} />} Make bot leave</button><button type="button" onClick={() => void handleAction('minutes')} disabled={!canRegenerate || action !== null}>{action === 'minutes' ? <LoaderCircle size={17} className="spin" /> : <RefreshCw size={17} />} Regenerate & resend MOM</button></div><div className="live-columns"><section className="live-transcript"><div className="live-panel-heading"><div><span className="eyebrow">01 / THE CONVERSATION</span><h2>Live transcript<span className="blue-period">.</span></h2></div><span className="count-label"><Mic2 size={15} /> {lines.length} lines</span></div>{lines.length ? <ol className="live-transcript-list" aria-live="polite">{lines.map((line) => <li key={line.utterance_id}><time dateTime={new Date(line.timestamp_ms).toISOString()} title={formatClock(line.timestamp_ms)}>{formatElapsed(line.timestamp_ms, startMs)}</time><div><strong>{line.speaker_name}{line.speaker_is_host && <small>HOST</small>}</strong><p>{line.text}</p></div></li>)}</ol> : <div className="panel-empty"><Mic2 size={27} /><h3>No transcript yet.</h3><p>Lines appear here as Attendee captures speech from the meeting.</p></div>}</section><section className="live-report"><div className="live-panel-heading"><div><span className="eyebrow">02 / THE TAKEAWAYS</span><h2>Meeting minutes<span className="blue-period">.</span></h2></div><FileText size={23} className="panel-heading-icon" /></div>{meeting.minutes ? <><div className="report-meta"><Clock3 size={15} /> {meeting.status === 'processing' ? 'Showing the last saved MOM while new minutes are generated' : 'Generated from the meeting transcript'}</div><MinutesReport minutes={meeting.minutes} /></> : <div className="panel-empty"><FileText size={27} /><h3>Minutes are on their way.</h3><p>After the bot leaves, the backend builds the summary, outcomes, and open questions.</p></div>}</section></div></> : <div className="library-empty"><h2>Meeting not available.</h2><p>This meeting may have been removed. Pick another one from the list.</p><Link to="/meetings">Back to all meetings <ArrowUpRight size={17} /></Link></div>}</div></section></main><footer className="site-footer"><div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8"><span>ATTENDEE / STUDIO</span><p>Meetings, made useful.</p><Link to="/meetings">All meetings <ArrowUpRight size={16} /></Link></div></footer></div>;
}
