import { useEffect, useRef, useState } from 'react';
import { ChevronDown, KeyRound, LoaderCircle, LogOut } from 'lucide-react';
import { Link, NavLink } from 'react-router-dom';

import { useAuth } from '@/auth/AuthProvider';
import type { AuthUser } from '@/auth/types';
import { checkBackend } from '@/meeting/Meetingapi';

function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join('').toUpperCase() || '?';
}

function AccountMenu({ user }: { user: AuthUser }) {
  const { signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const closeOnOutside = (event: PointerEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('pointerdown', closeOnOutside);
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.removeEventListener('pointerdown', closeOnOutside);
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, [open]);

  async function handleSignOut() {
    setSigningOut(true);
    await signOut();
  }

  return (
    <div className="account-menu" ref={menuRef}>
      <button type="button" className="account-trigger" aria-haspopup="menu" aria-expanded={open} aria-label={`Account menu for ${user.full_name}`} onClick={() => setOpen((shown) => !shown)}>
        <span className="account-avatar" aria-hidden="true">{initials(user.full_name)}</span>
        <span className="account-name">{user.full_name}</span>
        <ChevronDown size={15} aria-hidden="true" />
      </button>
      {open && (
        <div className="account-dropdown" role="menu">
          <div className="account-dropdown-head"><strong>{user.full_name}</strong><span>{user.email}</span></div>
          <Link role="menuitem" to="/account" onClick={() => setOpen(false)}><KeyRound size={16} /> Change password</Link>
          <button role="menuitem" type="button" className="account-signout" onClick={() => void handleSignOut()} disabled={signingOut}>
            {signingOut ? <LoaderCircle size={16} className="spin" /> : <LogOut size={16} />} Log out
          </button>
        </div>
      )}
    </div>
  );
}

export function StudioHeader() {
  const { user } = useAuth();
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
      {user && <nav className="header-nav" aria-label="Main navigation"><NavLink to="/" end>01 / Create</NavLink><NavLink to="/meetings">02 / Meetings</NavLink><NavLink to="/calendar">03 / Calendar</NavLink></nav>}
      <div className="header-actions">
        <div className={`connection ${backendOnline === true ? 'online' : backendOnline === false ? 'offline' : ''}`}><span className="connection-dot" />{backendOnline === null ? 'Checking backend' : backendOnline ? 'Backend online' : 'Backend offline'}</div>
        {user && <AccountMenu user={user} />}
      </div>
    </header>
  );
}
