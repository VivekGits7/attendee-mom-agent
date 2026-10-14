import { useEffect, useMemo, useState } from 'react';
import { ArrowUpRight, CalendarClock, Check, ChevronLeft, ChevronRight, CircleAlert, Clock3, LoaderCircle, RefreshCw, Video } from 'lucide-react';
import { Link } from 'react-router-dom';

import { StudioHeader } from '@/components/StudioHeader';
import { getApiError, listMeetings } from '@/meeting/Meetingapi';
import type { Meeting } from '@/meeting/types';
import './calendar.css';

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const PAGE_SIZE = 100;

function monthStart(date: Date, offset = 0) {
  return new Date(date.getFullYear(), date.getMonth() + offset, 1);
}

function dayKey(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' }).format(new Date(value));
}

function formatDate(value: string | Date) {
  return new Intl.DateTimeFormat(undefined, { weekday: 'long', month: 'long', day: 'numeric' }).format(typeof value === 'string' ? new Date(value) : value);
}

function sourceLabel(meeting: Meeting) {
  return meeting.calendar_synced ? 'Teams calendar' : 'Scheduled in studio';
}

export default function CalendarPage() {
  const [viewMonth, setViewMonth] = useState(() => monthStart(new Date()));
  const [selectedDay, setSelectedDay] = useState(() => dayKey(new Date()));
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [nextMeeting, setNextMeeting] = useState<Meeting | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);

  useEffect(() => {
    let active = true;
    let inFlight = false;
    const controller = new AbortController();
    setMeetings([]);
    setLastUpdated(null);
    const load = async (showLoading: boolean) => {
      if (inFlight) return;
      inFlight = true;
      if (showLoading) setLoading(true);
      try {
        const now = new Date();
        const start = monthStart(viewMonth);
        const end = monthStart(viewMonth, 1);
        const joinFrom = new Date(Math.max(start.getTime(), now.getTime())).toISOString();
        const upcoming = await listMeetings({
          status: 'scheduled', join_from: now.toISOString(), sort_by: 'join_at',
          sort_order: 'oldest', limit: 1, offset: 0,
        }, controller.signal);
        const monthMeetings: Meeting[] = [];
        if (start < end && new Date(joinFrom) < end) {
          let offset = 0;
          let total = 0;
          do {
            const page = await listMeetings({
              status: 'scheduled', join_from: joinFrom, join_until: end.toISOString(),
              sort_by: 'join_at', sort_order: 'oldest', limit: PAGE_SIZE, offset,
            }, controller.signal);
            monthMeetings.push(...page.data);
            offset += page.data.length;
            total = page.total;
          } while (offset < total && monthMeetings.length < total);
        }
        if (active) {
          setMeetings(monthMeetings);
          setNextMeeting(upcoming.data[0] ?? null);
          setLastUpdated(new Date());
          setError('');
        }
      } catch (requestError) {
        if (active) setError(getApiError(requestError));
      } finally {
        inFlight = false;
        if (active) setLoading(false);
      }
    };
    void load(true);
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') void load(false);
    }, 30000);
    return () => { active = false; controller.abort(); window.clearInterval(timer); };
  }, [viewMonth, refreshToken]);

  const eventsByDay = useMemo(() => {
    const grouped = new Map<string, Meeting[]>();
    for (const meeting of meetings) {
      if (!meeting.join_at) continue;
      const key = dayKey(new Date(meeting.join_at));
      grouped.set(key, [...(grouped.get(key) ?? []), meeting]);
    }
    return grouped;
  }, [meetings]);

  const days = useMemo(() => {
    const first = monthStart(viewMonth);
    const mondayOffset = (first.getDay() + 6) % 7;
    const count = Math.ceil((mondayOffset + new Date(first.getFullYear(), first.getMonth() + 1, 0).getDate()) / 7) * 7;
    return Array.from({ length: count }, (_, index) => new Date(first.getFullYear(), first.getMonth(), index - mondayOffset + 1));
  }, [viewMonth]);

  const today = dayKey(new Date());
  const selectedMeetings = eventsByDay.get(selectedDay) ?? [];
  const canGoBack = viewMonth.getTime() > monthStart(new Date()).getTime();
  const monthLabel = new Intl.DateTimeFormat(undefined, { month: 'long', year: 'numeric' }).format(viewMonth);
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

  function changeMonth(offset: number) {
    const next = monthStart(viewMonth, offset);
    setViewMonth(next);
    setSelectedDay(dayKey(next.getTime() === monthStart(new Date()).getTime() ? new Date() : next));
  }

  function goToday() {
    setViewMonth(monthStart(new Date()));
    setSelectedDay(dayKey(new Date()));
  }

  return (
    <div className="site-shell overflow-x-hidden">
      <a className="skip-link" href="#main">Skip to main content</a>
      <StudioHeader />
      <main id="main">
        <section className="schedule-hero">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 schedule-hero-inner">
            <div className="schedule-hero-copy">
              <div className="section-index"><span className="index-line" /> YOUR BOT SCHEDULE <span className="index-number">/ 003</span></div>
              <h1>Every meeting.<br /><em>Right on time.</em></h1>
              <p>See when the notetaker joins next. Teams invitations and meetings scheduled in the studio appear here together.</p>
              <div className="schedule-hero-links"><Link to="/">Schedule a bot <ArrowUpRight size={18} /></Link><Link to="/meetings">All meetings <ArrowUpRight size={18} /></Link></div>
            </div>
            <div className="next-bot-card" aria-live="polite">
              <div className="next-bot-top"><span><span className="next-pulse" /> NEXT BOT JOIN</span><CalendarClock size={23} /></div>
              {loading && !lastUpdated ? <div className="next-bot-loading"><LoaderCircle size={25} className="spin" /> Finding your next meeting...</div> : error && !lastUpdated ? <div className="next-bot-empty"><h2>Schedule unavailable.</h2><p>Check the connection and try refreshing the calendar.</p></div> : nextMeeting?.join_at ? <>
                <div className="next-bot-date"><strong>{new Date(nextMeeting.join_at).getDate()}</strong><span>{new Intl.DateTimeFormat(undefined, { month: 'short', year: 'numeric' }).format(new Date(nextMeeting.join_at))}</span></div>
                <h2>{nextMeeting.title}</h2>
                <p><Clock3 size={16} /> {formatDate(nextMeeting.join_at)} · {formatTime(nextMeeting.join_at)}{nextMeeting.ends_at ? ` – ${formatTime(nextMeeting.ends_at)}` : ''}</p>
                <div className="next-bot-footer"><span>{sourceLabel(nextMeeting)}</span><Link to={`/meetings/${nextMeeting.meeting_id}`}>View meeting <ArrowUpRight size={17} /></Link></div>
              </> : <div className="next-bot-empty"><h2>Open space ahead.</h2><p>No upcoming bot joins are scheduled yet.</p><Link to="/">Create a meeting <ArrowUpRight size={17} /></Link></div>}
            </div>
          </div>
        </section>

        <section className="schedule-body">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="schedule-section-top"><div><span className="eyebrow">PLAN AHEAD</span><h2>The calendar<span>.</span></h2><p>Times shown in {timezone}. Calendar updates every 30 seconds while this page is open.</p></div><div className="schedule-actions"><span>{lastUpdated ? `Updated ${lastUpdated.toLocaleTimeString()}` : 'Loading schedule'}</span><button type="button" onClick={() => setRefreshToken((value) => value + 1)} disabled={loading} aria-label="Refresh schedule"><RefreshCw size={18} className={loading ? 'spin' : ''} /></button></div></div>
            {error && <div className="inline-error" role="alert"><CircleAlert size={18} />{error}<button type="button" onClick={() => setRefreshToken((value) => value + 1)}>Retry</button></div>}
            <div className="schedule-layout">
              <section className="month-panel" aria-label="Bot calendar">
                <div className="month-panel-top"><div><span className="eyebrow">UPCOMING / {String(viewMonth.getMonth() + 1).padStart(2, '0')}</span><h3>{monthLabel}</h3></div><div className="month-controls"><button type="button" className="month-today" onClick={goToday}>Today</button><button type="button" onClick={() => changeMonth(-1)} disabled={!canGoBack} aria-label="Previous month"><ChevronLeft size={20} /></button><button type="button" onClick={() => changeMonth(1)} aria-label="Next month"><ChevronRight size={20} /></button></div></div>
                <div className="month-weekdays" aria-hidden="true">{WEEKDAYS.map((day) => <span key={day}>{day}</span>)}</div>
                <div className="month-grid">{days.map((date) => {
                  const key = dayKey(date);
                  const items = eventsByDay.get(key) ?? [];
                  const outside = date.getMonth() !== viewMonth.getMonth();
                  const past = key < today;
                  return <button type="button" key={key} className={`month-cell${outside ? ' outside' : ''}${past ? ' past' : ''}${key === today ? ' today' : ''}${key === selectedDay ? ' selected' : ''}`} onClick={() => { if (outside) setViewMonth(monthStart(date)); setSelectedDay(key); }} disabled={past} aria-pressed={key === selectedDay} aria-label={`${formatDate(date)}${items.length ? `, ${items.length} scheduled bot${items.length === 1 ? '' : 's'}` : ', no scheduled bots'}`}>
                    <span className="month-day-number">{date.getDate()}</span>
                    {items.length > 0 && <span className="month-event-markers"><span className="month-event-title">{items[0].title}</span><span className="month-event-dots" aria-hidden="true">{items.slice(0, 3).map((item) => <i key={item.meeting_id} />)}</span>{items.length > 1 && <small>+{items.length - 1}</small>}</span>}
                  </button>;
                })}</div>
                <div className="month-panel-footer"><span><i /> Scheduled bot join</span><span>{meetings.length} this month</span></div>
              </section>

              <section className="agenda-panel" aria-label="Selected day schedule">
                <div className="agenda-top"><span className="eyebrow">DAY VIEW</span><h3>{new Intl.DateTimeFormat(undefined, { weekday: 'long' }).format(new Date(`${selectedDay}T12:00:00`))}<span>.</span></h3><p>{new Intl.DateTimeFormat(undefined, { month: 'long', day: 'numeric', year: 'numeric' }).format(new Date(`${selectedDay}T12:00:00`))}</p></div>
                <div className="agenda-count"><span>{selectedMeetings.length} bot join{selectedMeetings.length === 1 ? '' : 's'}</span><span>{timezone}</span></div>
                {loading ? <div className="agenda-empty"><LoaderCircle size={23} className="spin" /><p>Loading this day...</p></div> : error && !lastUpdated ? <div className="agenda-empty"><CircleAlert size={29} /><h4>Schedule unavailable.</h4><p>Use Refresh to try again.</p></div> : selectedMeetings.length ? <div className="agenda-list">{selectedMeetings.map((meeting) => <Link className="agenda-item" key={meeting.meeting_id} to={`/meetings/${meeting.meeting_id}`}><div className="agenda-time"><strong>{meeting.join_at ? formatTime(meeting.join_at) : '—'}</strong>{meeting.ends_at && <small>to {formatTime(meeting.ends_at)}</small>}</div><div className="agenda-copy"><span className="agenda-source"><Video size={13} /> {sourceLabel(meeting)}</span><h4>{meeting.title}</h4><p>{meeting.recipient_email ? `MOM to ${meeting.recipient_email}` : 'Default MOM recipient'}</p><span className="agenda-status"><Check size={13} /> Bot scheduled</span></div><ArrowUpRight size={18} className="agenda-arrow" /></Link>)}</div> : <div className="agenda-empty"><CalendarClock size={32} /><h4>Nothing on this day.</h4><p>When you invite the bot to a Teams meeting or schedule it here, its join time will show up on this calendar.</p><Link to="/">Schedule a bot <ArrowUpRight size={16} /></Link></div>}
              </section>
            </div>
          </div>
        </section>
      </main>
      <footer className="site-footer"><div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8"><span>ATTENDEE / STUDIO</span><p>Meetings, made useful.</p><Link to="/meetings">All meetings <ArrowUpRight size={16} /></Link></div></footer>
    </div>
  );
}
