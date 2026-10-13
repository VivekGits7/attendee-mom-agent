import { useEffect, useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  CalendarClock,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  Clock3,
  Copy,
  ExternalLink,
  FileText,
  Link2,
  LoaderCircle,
  Mail,
  Mic2,
  Play,
  RefreshCw,
  Search,
  Send,
  Square,
} from 'lucide-react';

import {
  createMeeting,
  getApiError,
  getMeeting,
  leaveMeeting,
  regenerateMinutes,
} from '@/meeting/Meetingapi';
import { StudioHeader } from '@/components/StudioHeader';
import { ApiKeyField } from '@/meeting/ApiKeyField';
import { useApiKey } from '@/meeting/ApiKeyContext';
import type { MeetingDetail, MeetingStatus, Minutes } from '@/meeting/types';

type PendingAction = 'create' | 'lookup' | 'refresh' | 'leave' | 'minutes' | null;
type Notice = { kind: 'success' | 'error'; text: string } | null;
type DetailTab = 'minutes' | 'transcript';

const RECENT_KEY = 'meeting-console-recent-ids';
const finalBotStates = new Set(['ended', 'fatal_error']);

function readRecent(): string[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(RECENT_KEY) || '[]');
    return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string').slice(0, 5) : [];
  } catch {
    return [];
  }
}

function formatDate(value: string | null): string {
  if (!value) return 'Not set';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

function formatOffset(milliseconds: number): string {
  const seconds = Math.floor(Math.max(milliseconds, 0) / 1000);
  return `${String(Math.floor(seconds / 3600)).padStart(2, '0')}:${String(Math.floor((seconds % 3600) / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
}

function readable(value: string): string {
  return value.replace(/_/g, ' ');
}

function StatusPill({ status }: { status: MeetingStatus }) {
  const tone = status === 'completed' ? 'success' : status === 'failed' ? 'danger' : 'live';
  return <span className={`status-pill ${tone}`}><span className="status-dot" />{readable(status)}</span>;
}

function EmptyMinutes() {
  return (
    <div className="empty-content">
      <div className="empty-icon"><FileText size={25} strokeWidth={1.6} /></div>
      <h3>Minutes are on their way.</h3>
      <p>After the bot leaves and the transcript is processed, the summary, decisions, and action items will appear here.</p>
    </div>
  );
}

function MinutesView({ minutes }: { minutes: Minutes }) {
  return (
    <div className="minutes-content">
      <div className="summary-block">
        <span className="eyebrow">THE SUMMARY</span>
        <p>{minutes.summary}</p>
      </div>
      <div className="minutes-columns">
        <section>
          <h3>Key points <span>{String(minutes.key_points.length).padStart(2, '0')}</span></h3>
          {minutes.key_points.length ? <ul className="plain-list">{minutes.key_points.map((point, index) => <li key={`${point}-${index}`}>{point}</li>)}</ul> : <p className="muted-copy">No key points recorded.</p>}
        </section>
        <section>
          <h3>Decisions <span>{String(minutes.decisions.length).padStart(2, '0')}</span></h3>
          {minutes.decisions.length ? <ul className="plain-list">{minutes.decisions.map((item, index) => <li key={`${item.decision}-${index}`}>{item.decision}<small>Decided by {item.made_by}</small></li>)}</ul> : <p className="muted-copy">No decisions recorded.</p>}
        </section>
      </div>
      <section className="action-section">
        <h3>Action items <span>{String(minutes.action_items.length).padStart(2, '0')}</span></h3>
        {minutes.action_items.length ? (
          <div className="action-list">
            {minutes.action_items.map((item, index) => (
              <div className="action-item" key={`${item.task}-${index}`}>
                <div className="action-number">{String(index + 1).padStart(2, '0')}</div>
                <div><strong>{item.task}</strong><p>{item.owner} <span>·</span> Due {item.due_date}</p></div>
                <span className="priority">{item.priority}</span>
              </div>
            ))}
          </div>
        ) : <p className="muted-copy">No action items recorded.</p>}
      </section>
      <div className="minutes-columns bottom-columns">
        <section>
          <h3>Open questions <span>{String(minutes.open_questions.length).padStart(2, '0')}</span></h3>
          {minutes.open_questions.length ? <ul className="plain-list">{minutes.open_questions.map((question, index) => <li key={`${question}-${index}`}>{question}</li>)}</ul> : <p className="muted-copy">No open questions.</p>}
        </section>
        <section>
          <h3>Attendees <span>{String(minutes.attendees.length).padStart(2, '0')}</span></h3>
          {minutes.attendees.length ? <div className="attendee-list">{minutes.attendees.map((name, index) => <span key={`${name}-${index}`}>{name}</span>)}</div> : <p className="muted-copy">No attendees identified.</p>}
        </section>
      </div>
    </div>
  );
}

function App() {
  const { apiKey } = useApiKey();
  const navigate = useNavigate();
  const [title, setTitle] = useState('');
  const [meetingUrl, setMeetingUrl] = useState('');
  const [recipientEmail, setRecipientEmail] = useState('');
  const [joinMode, setJoinMode] = useState<'now' | 'later'>('now');
  const [joinAt, setJoinAt] = useState('');
  const [lookupId, setLookupId] = useState('');
  const [recent, setRecent] = useState(readRecent);
  const [meeting, setMeeting] = useState<MeetingDetail | null>(null);
  const [pending, setPending] = useState<PendingAction>(null);
  const [notice, setNotice] = useState<Notice>(null);
  const [activeTab, setActiveTab] = useState<DetailTab>('minutes');
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!meeting || !apiKey || meeting.status === 'completed' || meeting.status === 'failed') return;
    const timer = window.setInterval(() => {
      void getMeeting(apiKey, meeting.meeting_id).then((response) => setMeeting((current) => current?.meeting_id === response.data.meeting_id ? response.data : current)).catch(() => undefined);
    }, 10000);
    return () => window.clearInterval(timer);
  }, [meeting?.meeting_id, meeting?.status, apiKey]);

  function remember(id: string) {
    setRecent((current) => {
      const next = [id, ...current.filter((item) => item !== id)].slice(0, 5);
      try { localStorage.setItem(RECENT_KEY, JSON.stringify(next)); } catch { /* Recent IDs still work for this tab. */ }
      return next;
    });
  }

  async function loadMeeting(id: string, action: PendingAction = 'lookup') {
    if (!apiKey.trim()) { setNotice({ kind: 'error', text: 'Enter the backend API key first.' }); return; }
    if (!id.trim()) { setNotice({ kind: 'error', text: 'Enter a meeting ID to look it up.' }); return; }
    setPending(action);
    setNotice(null);
    try {
      const response = await getMeeting(apiKey.trim(), id.trim());
      setMeeting(response.data);
      setLookupId(response.data.meeting_id);
      remember(response.data.meeting_id);
      setNotice({ kind: 'success', text: 'Meeting details are up to date.' });
    } catch (error) {
      setNotice({ kind: 'error', text: getApiError(error) });
    } finally {
      setPending(null);
    }
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!apiKey.trim()) { setNotice({ kind: 'error', text: 'Enter the backend API key first.' }); return; }
    if (title.trim().length < 2) { setNotice({ kind: 'error', text: 'Meeting title needs at least 2 characters.' }); return; }
    try {
      const url = new URL(meetingUrl.trim());
      const host = url.hostname.toLowerCase();
      if (!['meet.google.com', 'teams.microsoft.com', 'teams.live.com'].includes(host) && !host.endsWith('.teams.microsoft.com')) throw new Error();
    } catch {
      setNotice({ kind: 'error', text: 'Use a full Google Meet or Microsoft Teams URL.' });
      return;
    }
    if (joinMode === 'later' && (!joinAt || !Number.isFinite(new Date(joinAt).getTime()) || new Date(joinAt).getTime() <= Date.now())) {
      setNotice({ kind: 'error', text: 'Choose a future date and time for the scheduled join.' });
      return;
    }
    setPending('create');
    setNotice(null);
    try {
      const response = await createMeeting(apiKey.trim(), {
        title: title.trim(),
        meeting_url: meetingUrl.trim(),
        recipient_email: recipientEmail.trim() || null,
        join_at: joinMode === 'later' ? new Date(joinAt).toISOString() : null,
      });
      const created = response.data;
      setMeeting({ ...created, utterances: [], minutes: null });
      setLookupId(created.meeting_id);
      remember(created.meeting_id);
      navigate(`/meetings/${created.meeting_id}`);
    } catch (error) {
      setNotice({ kind: 'error', text: getApiError(error) });
    } finally {
      setPending(null);
    }
  }

  async function handleAction(action: 'leave' | 'minutes') {
    if (!meeting) return;
    const message = action === 'leave'
      ? 'Make the bot leave this meeting now? Minutes will be generated after it ends.'
      : 'Regenerate minutes and send the email again?';
    if (!window.confirm(message)) return;
    setPending(action);
    setNotice(null);
    try {
      const response = action === 'leave'
        ? await leaveMeeting(apiKey.trim(), meeting.meeting_id)
        : await regenerateMinutes(apiKey.trim(), meeting.meeting_id);
      setMeeting((current) => current ? { ...current, ...response.data } : current);
      setNotice({ kind: 'success', text: response.message });
    } catch (error) {
      setNotice({ kind: 'error', text: getApiError(error) });
    } finally {
      setPending(null);
    }
  }

  async function copyId() {
    if (!meeting) return;
    try {
      await navigator.clipboard.writeText(meeting.meeting_id);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setNotice({ kind: 'error', text: 'Could not copy the meeting ID.' });
    }
  }

  const canLeave = Boolean(meeting?.bot_id && !new Set(['leaving', 'post_processing', ...finalBotStates]).has(meeting.bot_state || '') && meeting.status !== 'completed' && meeting.status !== 'failed');
  const canRegenerate = Boolean(meeting && finalBotStates.has(meeting.bot_state || ''));

  return (
    <div className="site-shell overflow-x-hidden">
      <a className="skip-link" href="#main">Skip to main content</a>
      <StudioHeader />
      {notice && <div className={`global-notice ${notice.kind}`} role="alert">{notice.kind === 'success' ? <CheckCircle2 size={19} /> : <CircleAlert size={19} />}<span>{notice.text}</span><button type="button" onClick={() => setNotice(null)} aria-label="Dismiss message">×</button></div>}

      <main id="main">
        <section className="hero-section" id="top">
          <div className="hero-inner max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="hero-copy">
              <div className="section-index"><span className="index-line" /> THE MEETING WORKSPACE <span className="index-number">/ 001</span></div>
              <h1>Every word,<br /><em>worth keeping.</em></h1>
              <p className="hero-subtitle">Send a notetaker to your meeting. Follow the conversation live. Leave with clear minutes and next steps.</p>
              <div className="hero-meta"><span><span className="meta-square" /> GOOGLE MEET</span><span><span className="meta-square" /> MICROSOFT TEAMS</span></div>
              <div className="hero-art" aria-hidden="true"><div className="orbit orbit-one" /><div className="orbit orbit-two" /><div className="orbit orbit-three" /><div className="art-core"><Mic2 size={42} strokeWidth={1.15} /></div><span className="art-label label-one">RECORD</span><span className="art-label label-two">TRANSCRIBE</span><span className="art-label label-three">SUMMARIZE</span></div>
            </div>

            <div className="create-panel" id="create">
              <div className="panel-heading"><div><span className="eyebrow">01 / NEW SESSION</span><h2>Start a meeting<span className="blue-period">.</span></h2></div><ArrowUpRight size={24} strokeWidth={1.5} /></div>
              <form onSubmit={handleCreate}>
                <ApiKeyField id="api-key" />
                <div className="field"><label htmlFor="meeting-title">Meeting title <span>REQUIRED</span></label><input id="meeting-title" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="e.g. Product planning" minLength={2} maxLength={255} required /></div>
                <div className="field"><label htmlFor="meeting-url">Meeting link <span>REQUIRED</span></label><div className="input-icon"><Link2 size={18} /><input id="meeting-url" type="url" value={meetingUrl} onChange={(event) => setMeetingUrl(event.target.value)} placeholder="https://meet.google.com/..." required /></div></div>
                <div className="field"><label htmlFor="recipient-email">Minutes recipient <span>OPTIONAL</span></label><div className="input-icon"><Mail size={18} /><input id="recipient-email" type="email" value={recipientEmail} onChange={(event) => setRecipientEmail(event.target.value)} placeholder="you@company.com" /></div><p className="field-help">Use an allowed domain. Otherwise the backend sends to its default address.</p></div>
                <fieldset className="schedule-field"><legend>When should the bot join?</legend><div className="choice-group"><label className={joinMode === 'now' ? 'choice active' : 'choice'}><input type="radio" name="join-mode" checked={joinMode === 'now'} onChange={() => setJoinMode('now')} /><Play size={16} fill="currentColor" /> Join now</label><label className={joinMode === 'later' ? 'choice active' : 'choice'}><input type="radio" name="join-mode" checked={joinMode === 'later'} onChange={() => setJoinMode('later')} /><CalendarClock size={17} /> Schedule</label></div>{joinMode === 'later' && <input className="schedule-input" aria-label="Scheduled join time" type="datetime-local" value={joinAt} onChange={(event) => setJoinAt(event.target.value)} required />}</fieldset>
                <button className="primary-button" type="submit" disabled={pending !== null}>{pending === 'create' ? <><LoaderCircle size={19} className="spin" /> Creating meeting...</> : <><Send size={18} /> Send the bot <ArrowUpRight size={19} /></>}</button>
                <p className="form-footnote">The bot joins your call and leaves automatically after everyone else.</p>
              </form>
            </div>
          </div>
          <div className="marquee" aria-hidden="true"><div className="marquee-track">CAPTURE THE CONVERSATION <span>✳</span> TURN TALK INTO ACTION <span>✳</span> MAKE EVERY MINUTE COUNT <span>✳</span> CAPTURE THE CONVERSATION <span>✳</span> TURN TALK INTO ACTION <span>✳</span> MAKE EVERY MINUTE COUNT <span>✳</span></div></div>
        </section>

        <section className="workspace-section" id="workspace">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="workspace-heading"><div><div className="section-index dark-index"><span className="index-line" /> YOUR CONTROL ROOM <span className="index-number">/ 002</span></div><h2>Stay in the <em>loop.</em></h2></div><div><p>Open any saved meeting, follow its live transcript, and see the finished MOM.</p><Link className="all-meetings-link" to="/meetings">Browse all meetings <ArrowUpRight size={18} /></Link></div></div>
            <div className="workspace-grid">
              <aside className="side-column">
                <section className="side-card lookup-card"><span className="eyebrow">FIND A SESSION</span><h3>Meeting ID</h3><form onSubmit={(event) => { event.preventDefault(); void loadMeeting(lookupId); }}><label className="sr-only" htmlFor="meeting-id">Meeting ID</label><div className="lookup-input"><Search size={18} /><input id="meeting-id" value={lookupId} onChange={(event) => setLookupId(event.target.value)} placeholder="Paste meeting UUID" /></div><button className="secondary-button" type="submit" disabled={pending !== null}>{pending === 'lookup' ? <LoaderCircle size={17} className="spin" /> : <ArrowRight size={17} />} Open meeting</button></form></section>
                <section className="side-card recent-card"><div className="small-card-heading"><span className="eyebrow">RECENT SESSIONS</span><span>{String(recent.length).padStart(2, '0')}</span></div>{recent.length ? <ul>{recent.map((id) => <li key={id}><button type="button" onClick={() => void loadMeeting(id)} disabled={pending !== null}><span className="recent-icon"><Clock3 size={17} /></span><span>{id.slice(0, 8)}<small>{id.slice(8, 18)}...</small></span><ChevronRight size={17} /></button></li>)}</ul> : <p className="muted-copy">Meetings you create or open will appear here.</p>}</section>
                <div className="side-note"><div className="note-symbol">✳</div><p>One meeting. Every important moment, in one place.</p><span>ATTENDEE / STUDIO</span></div>
              </aside>

              <div className="detail-column">
                {meeting ? <>
                  <article className="meeting-card"><div className="meeting-top"><span className="eyebrow">CURRENT SESSION <span>/ {meeting.platform === 'google_meet' ? 'GOOGLE MEET' : 'MICROSOFT TEAMS'}</span></span><StatusPill status={meeting.status} /></div><h3>{meeting.title}</h3><div className="meeting-id"><span>{meeting.meeting_id}</span><button type="button" onClick={() => void copyId()} aria-label="Copy meeting ID">{copied ? <Check size={17} /> : <Copy size={17} />}</button></div><div className="meeting-facts"><div><span>BOT STATUS</span><strong>{readable(meeting.bot_state || 'pending')}</strong></div><div><span>JOIN TIME</span><strong>{meeting.join_at ? formatDate(meeting.join_at) : 'Joined immediately'}</strong></div><div><span>MINUTES EMAIL</span><strong>{readable(meeting.email_status)}{meeting.email_sent_to ? ` · ${meeting.email_sent_to}` : ''}</strong></div></div>{meeting.error_message && <div className="meeting-error"><CircleAlert size={18} />{meeting.error_message}</div>}<div className="meeting-actions"><Link className="action-button" to={`/meetings/${meeting.meeting_id}`}><ArrowUpRight size={17} /> Open live page</Link><button className="action-button" type="button" onClick={() => void loadMeeting(meeting.meeting_id, 'refresh')} disabled={pending !== null}>{pending === 'refresh' ? <LoaderCircle size={17} className="spin" /> : <RefreshCw size={17} />} Refresh details</button><a className="action-button" href={meeting.meeting_url} target="_blank" rel="noopener noreferrer"><ExternalLink size={17} /> Open call</a><button className="action-button danger-button" type="button" onClick={() => void handleAction('leave')} disabled={pending !== null || !canLeave}>{pending === 'leave' ? <LoaderCircle size={17} className="spin" /> : <Square size={16} />} Make bot leave</button></div></article>
                  <article className="output-card"><div className="output-top"><div><span className="eyebrow">THE OUTPUT</span><h3>What happened<span className="blue-period">.</span></h3></div><button className="regenerate-button" type="button" onClick={() => void handleAction('minutes')} disabled={pending !== null || !canRegenerate}>{pending === 'minutes' ? <LoaderCircle size={17} className="spin" /> : <RefreshCw size={17} />} Regenerate & resend</button></div><div className="tabs" role="tablist" aria-label="Meeting output"><button role="tab" aria-selected={activeTab === 'minutes'} className={activeTab === 'minutes' ? 'selected' : ''} onClick={() => setActiveTab('minutes')}><FileText size={17} /> Meeting minutes</button><button role="tab" aria-selected={activeTab === 'transcript'} className={activeTab === 'transcript' ? 'selected' : ''} onClick={() => setActiveTab('transcript')}><Mic2 size={17} /> Transcript <span>{meeting.utterances.length}</span></button></div><div className="output-body" role="tabpanel">{activeTab === 'minutes' ? (meeting.minutes ? <MinutesView minutes={meeting.minutes} /> : <EmptyMinutes />) : (meeting.utterances.length ? <div className="transcript-list">{meeting.utterances.map((line, index) => <div className="transcript-line" key={`${line.timestamp_ms}-${index}`}><span className="transcript-time">{formatOffset(line.timestamp_ms)}</span><div><strong>{line.speaker_name}{line.speaker_is_host && <span className="host-tag">HOST</span>}</strong><p>{line.text}</p></div></div>)}</div> : <div className="empty-content"><div className="empty-icon"><Mic2 size={25} strokeWidth={1.6} /></div><h3>Waiting for the conversation.</h3><p>Transcript lines will appear here as the bot captures them.</p></div>)}</div></article>
                </> : <article className="workspace-empty"><div className="empty-emblem"><span>01</span><ArrowDownRight size={56} strokeWidth={1} /></div><div className="workspace-empty-copy"><span className="eyebrow">READY WHEN YOU ARE</span><h3>Your next meeting<br /><em>starts here.</em></h3><p>Create a session above or open one by ID. The transcript, minutes, and bot controls will appear in this workspace.</p><a href="#create">Create a meeting <ArrowUpRight size={18} /></a></div></article>}
              </div>
            </div>
          </div>
        </section>
      </main>
      <footer className="site-footer"><div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8"><span>ATTENDEE / STUDIO</span><p>Meetings, made useful.</p><a href="#top">Back to top <ArrowUpRight size={16} /></a></div></footer>
    </div>
  );
}

export default App;
