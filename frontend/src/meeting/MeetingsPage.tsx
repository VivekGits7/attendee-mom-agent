import { useEffect, useState } from 'react';
import { ArrowLeft, ArrowRight, ArrowUpRight, CircleAlert, ListFilter, LoaderCircle, RefreshCw, Search } from 'lucide-react';
import { Link } from 'react-router-dom';

import { Select, type SelectOption } from '@/components/Select';
import { StudioHeader } from '@/components/StudioHeader';
import { getApiError, listMeetings } from '@/meeting/Meetingapi';
import { MeetingStatusBadge } from '@/meeting/MeetingStatusBadge';
import type { Meeting, MeetingFilters, MeetingListResponse, MeetingStatus } from '@/meeting/types';
import './pages.css';

const PAGE_SIZE = 12;
type SortOrder = NonNullable<MeetingFilters['sort_order']>;

const STATUS_OPTIONS: SelectOption<MeetingStatus | ''>[] = [
  { value: '', label: 'All statuses' },
  { value: 'scheduled', label: 'Scheduled' },
  { value: 'joining', label: 'Joining' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'processing', label: 'Processing' },
  { value: 'completed', label: 'Completed' },
  { value: 'failed', label: 'Failed' },
];
const PLATFORM_OPTIONS: SelectOption<Meeting['platform'] | ''>[] = [
  { value: '', label: 'All platforms' },
  { value: 'google_meet', label: 'Google Meet' },
  { value: 'teams', label: 'Microsoft Teams' },
];
const SORT_OPTIONS: SelectOption<SortOrder>[] = [
  { value: 'latest', label: 'Latest first' },
  { value: 'oldest', label: 'Oldest first' },
  { value: 'a_to_z', label: 'Title A–Z' },
  { value: 'z_to_a', label: 'Title Z–A' },
];

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));
}

export default function MeetingsPage() {
  const [query, setQuery] = useState('');
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<MeetingStatus | ''>('');
  const [platform, setPlatform] = useState<Meeting['platform'] | ''>('');
  const [sortOrder, setSortOrder] = useState<SortOrder>('latest');
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<MeetingListResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);

  useEffect(() => {
    const timer = window.setTimeout(() => { setSearch(query.trim()); setOffset(0); }, 350);
    return () => window.clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    let active = true;
    let inFlight = false;
    const controller = new AbortController();
    const filters: MeetingFilters = {
      search: search || undefined,
      status: status || undefined,
      platform: platform || undefined,
      sort_by: 'title',
      sort_order: sortOrder,
      limit: PAGE_SIZE,
      offset,
    };
    const load = async (showLoading: boolean) => {
      if (inFlight) return;
      inFlight = true;
      if (showLoading) setLoading(true);
      try {
        const result = await listMeetings(filters, controller.signal);
        if (active) { setPage(result); setError(''); setLastUpdated(new Date()); }
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
    }, 15000);
    return () => { active = false; controller.abort(); window.clearInterval(timer); };
  }, [search, status, platform, sortOrder, offset, refreshToken]);

  const pageNumber = Math.floor(offset / PAGE_SIZE) + 1;
  const pageCount = page ? Math.max(1, Math.ceil(page.total / PAGE_SIZE)) : 1;

  return (
    <div className="site-shell overflow-x-hidden">
      <a className="skip-link" href="#main">Skip to main content</a>
      <StudioHeader />
      <main id="main">
        <section className="collection-hero">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="section-index"><span className="index-line" /> THE ARCHIVE <span className="index-number">/ 002</span></div>
            <div className="collection-hero-row"><div><h1>All your<br /><em>conversations.</em></h1><p>Every bot session, live transcript, and finished MOM in one place.</p></div><Link className="collection-cta" to="/">New meeting <ArrowUpRight size={19} /></Link></div>
          </div>
        </section>

        <section className="collection-body">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="collection-toolbar"><div><span className="eyebrow">MEETING LIBRARY</span><h2>{page ? `${page.total} meeting${page.total === 1 ? '' : 's'}` : 'Meetings'}</h2></div><div className="refresh-meta"><span>{lastUpdated ? `Updated ${lastUpdated.toLocaleTimeString()}` : 'Refreshes every 15 seconds'}</span><button type="button" onClick={() => setRefreshToken((token) => token + 1)} disabled={loading} aria-label="Refresh meetings"><RefreshCw size={18} className={loading ? 'spin' : ''} /></button></div></div>
            <div className="filter-bar"><div className="filter-search"><Search size={19} /><label className="sr-only" htmlFor="meeting-search">Search meetings</label><input id="meeting-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search title or recipient..." maxLength={100} /></div><Select className="filter-select" label="Status" icon={<ListFilter size={17} />} value={status} options={STATUS_OPTIONS} onChange={(next) => { setStatus(next); setOffset(0); }} /><Select className="filter-select" label="Platform" value={platform} options={PLATFORM_OPTIONS} onChange={(next) => { setPlatform(next); setOffset(0); }} /><Select className="filter-select" label="Sort order" value={sortOrder} options={SORT_OPTIONS} onChange={(next) => { setSortOrder(next); setOffset(0); }} /></div>

            {error && !page ? <div className="library-empty error-empty"><CircleAlert size={28} /><h3>Could not load meetings.</h3><p>{error}</p><button className="secondary-button" type="button" onClick={() => setRefreshToken((token) => token + 1)}>Try again <ArrowRight size={18} /></button></div> : loading && !page ? <div className="library-empty"><LoaderCircle size={30} className="spin" /><h3>Loading meetings...</h3></div> : <>
              {error && <div className="inline-error" role="alert"><CircleAlert size={18} />{error}</div>}
              <div className="meeting-list-heading"><span>MEETING</span><span>CREATED</span><span>STATUS</span><span>EMAIL</span><span /></div>
              {page?.data.length ? <div className="meeting-list">{page.data.map((meeting, index) => <Link className="meeting-row" to={`/meetings/${meeting.meeting_id}`} key={meeting.meeting_id}><div className="meeting-row-title"><span className="row-index">{String(offset + index + 1).padStart(2, '0')}</span><div><strong>{meeting.title}</strong><small>{meeting.platform === 'google_meet' ? 'Google Meet' : 'Microsoft Teams'} <span>·</span> {meeting.recipient_email || 'Default recipient'}</small></div></div><span className="row-date">{formatDate(meeting.created_at)}</span><MeetingStatusBadge status={meeting.status} /><span className="row-email">{meeting.email_status.replace(/_/g, ' ')}</span><ArrowUpRight size={20} className="row-arrow" /></Link>)}</div> : <div className="library-empty"><span className="eyebrow">NO RESULTS</span><h3>No meetings found.</h3><p>{search || status || platform ? 'Try clearing the search or filters.' : 'Create your first meeting to see it here.'}</p><Link to="/">Create a meeting <ArrowUpRight size={17} /></Link></div>}
              {page && page.total > 0 && <div className="pagination"><span>Showing {offset + 1}–{Math.min(offset + PAGE_SIZE, page.total)} of {page.total}</span><div><button type="button" onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))} disabled={offset === 0 || loading}><ArrowLeft size={18} /> Previous</button><span>Page {pageNumber} / {pageCount}</span><button type="button" onClick={() => setOffset(offset + PAGE_SIZE)} disabled={offset + PAGE_SIZE >= page.total || loading}>Next <ArrowRight size={18} /></button></div></div>}
            </>}
          </div>
        </section>
      </main>
      <footer className="site-footer"><div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8"><span>ATTENDEE / STUDIO</span><p>Meetings, made useful.</p><Link to="/">New meeting <ArrowUpRight size={16} /></Link></div></footer>
    </div>
  );
}
