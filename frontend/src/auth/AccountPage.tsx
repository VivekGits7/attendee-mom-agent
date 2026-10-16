import { useState, type FormEvent } from 'react';
import { ArrowUpRight, CheckCircle2, CircleAlert, KeyRound, LoaderCircle } from 'lucide-react';

import { useAuth } from '@/auth/AuthProvider';
import { PasswordInput } from '@/auth/PasswordInput';
import { StudioHeader } from '@/components/StudioHeader';
import { getApiError } from '@/lib/http';
import './auth.css';

const MIN_PASSWORD = 8;

type Notice = { kind: 'success' | 'error'; text: string } | null;

function formatDate(value: string | null) {
  if (!value) return 'Not yet';
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));
}

export default function AccountPage() {
  const { user, updatePassword } = useAuth();
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState<Notice>(null);

  const tooShort = newPassword.length > 0 && newPassword.length < MIN_PASSWORD;
  const mismatch = confirmPassword.length > 0 && newPassword !== confirmPassword;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!oldPassword || !newPassword || !confirmPassword) { setNotice({ kind: 'error', text: 'Fill in all three password fields.' }); return; }
    if (newPassword.length < MIN_PASSWORD) { setNotice({ kind: 'error', text: `Your new password needs at least ${MIN_PASSWORD} characters.` }); return; }
    if (newPassword !== confirmPassword) { setNotice({ kind: 'error', text: 'The new passwords do not match.' }); return; }
    if (newPassword === oldPassword) { setNotice({ kind: 'error', text: 'Pick a new password that is different from the current one.' }); return; }
    setPending(true);
    setNotice(null);
    try {
      await updatePassword({ old_password: oldPassword, new_password: newPassword, confirm_new_password: confirmPassword });
      setOldPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setNotice({ kind: 'success', text: 'Password updated. Any other device using this account has been signed out.' });
    } catch (requestError) {
      setNotice({ kind: 'error', text: getApiError(requestError) });
    } finally {
      setPending(false);
    }
  }

  if (!user) return null;

  return (
    <div className="site-shell overflow-x-hidden">
      <a className="skip-link" href="#main">Skip to main content</a>
      <StudioHeader />
      <main id="main">
        <section className="hero-section auth-hero" id="top">
          <div className="hero-inner max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="hero-copy">
              <div className="section-index"><span className="index-line" /> YOUR ACCOUNT <span className="index-number">/ 004</span></div>
              <h1>Keep it<br /><em>locked.</em></h1>
              <p className="hero-subtitle">Change your password any time. Signing in somewhere else will need the new one.</p>
              <dl className="account-facts">
                <div><dt>NAME</dt><dd>{user.full_name}</dd></div>
                <div><dt>EMAIL</dt><dd>{user.email}</dd></div>
                <div><dt>MEMBER SINCE</dt><dd>{formatDate(user.created_at)}</dd></div>
                <div><dt>LAST LOGIN</dt><dd>{formatDate(user.last_login_at)}</dd></div>
              </dl>
            </div>

            <div className="create-panel auth-panel">
              <div className="panel-heading"><div><span className="eyebrow">SECURITY</span><h2>Change password<span className="blue-period">.</span></h2></div><KeyRound size={24} strokeWidth={1.5} /></div>
              <form onSubmit={handleSubmit} noValidate>
                {notice && <div className={`auth-alert ${notice.kind}`} role={notice.kind === 'error' ? 'alert' : 'status'}>{notice.kind === 'success' ? <CheckCircle2 size={18} /> : <CircleAlert size={18} />}<span>{notice.text}</span></div>}
                <div className="field">
                  <label htmlFor="old-password">Current password <span>REQUIRED</span></label>
                  <PasswordInput id="old-password" autoComplete="current-password" value={oldPassword} onChange={(event) => setOldPassword(event.target.value)} required />
                </div>
                <div className="field">
                  <label htmlFor="new-password">New password <span>REQUIRED</span></label>
                  <PasswordInput id="new-password" autoComplete="new-password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} aria-describedby="new-password-help" aria-invalid={tooShort} required />
                  <p id="new-password-help" className={tooShort ? 'field-help field-warning' : 'field-help'}>{MIN_PASSWORD} to 72 characters, different from your current one.</p>
                </div>
                <div className="field">
                  <label htmlFor="confirm-password">Confirm new password <span>REQUIRED</span></label>
                  <PasswordInput id="confirm-password" autoComplete="new-password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} aria-describedby={mismatch ? 'confirm-password-help' : undefined} aria-invalid={mismatch} required />
                  {mismatch && <p id="confirm-password-help" className="field-help field-warning">The new passwords do not match yet.</p>}
                </div>
                <button className="primary-button" type="submit" disabled={pending}>
                  {pending ? <><LoaderCircle size={19} className="spin" /> Updating password...</> : <>Update password <ArrowUpRight size={19} /></>}
                </button>
                <p className="form-footnote">Every other device signed in to this account will be logged out.</p>
              </form>
            </div>
          </div>
        </section>
      </main>
      <footer className="site-footer"><div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8"><span>ATTENDEE / STUDIO</span><p>Meetings, made useful.</p><a href="#top">Back to top <ArrowUpRight size={16} /></a></div></footer>
    </div>
  );
}
