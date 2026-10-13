import { useEffect, useState } from 'react';
import { Link, NavLink } from 'react-router-dom';

import { checkBackend } from '@/meeting/Meetingapi';

export function StudioHeader() {
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);

  useEffect(() => {
    let mounted = true;
    const check = () => void checkBackend()
      .then((online) => { if (mounted) setBackendOnline(online); })
      .catch(() => { if (mounted) setBackendOnline(false); });
    check();
    const timer = window.setInterval(check, 30000);
    return () => { mounted = false; window.clearInterval(timer); };
  }, []);

  return (
    <header className="site-header">
      <Link className="brand" to="/" aria-label="Meeting Console home"><span className="brand-mark"><span /><span /><span /></span><span>ATTENDEE<span className="brand-light"> / STUDIO</span></span></Link>
      <nav className="header-nav" aria-label="Main navigation"><NavLink to="/" end>01 / Create</NavLink><NavLink to="/meetings">02 / Meetings</NavLink></nav>
      <div className={`connection ${backendOnline === true ? 'online' : backendOnline === false ? 'offline' : ''}`}><span className="connection-dot" />{backendOnline === null ? 'Checking backend' : backendOnline ? 'Backend online' : 'Backend offline'}</div>
    </header>
  );
}
