import { useState, type FormEvent } from 'react';
import { ArrowUpRight, CircleAlert, LoaderCircle, LockKeyhole, Mail } from 'lucide-react';
import { Navigate, useLocation } from 'react-router-dom';

import { useAuth } from '@/auth/AuthProvider';
import { PasswordInput } from '@/auth/PasswordInput';
import { StudioHeader } from '@/components/StudioHeader';
import { getApiError } from '@/lib/http';
import './auth.css';

function safeRedirect(value: unknown): string {
  if (typeof value !== 'string' || !value.startsWith('/') || value.startsWith('//') || value.startsWith('/login')) return '/';
  return value;
}

export default function LoginPage() {
  const { user, signIn } = useAuth();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');

  if (user) return <Navigate to={safeRedirect((location.state as { from?: unknown } | null)?.from)} replace />;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!email.trim() || !password) {
      setError('Enter your email and password.');
      return;
    }
    setPending(true);
    setError('');
    try {
      await signIn(email.trim(), password);
    } catch (requestError) {
      setError(getApiError(requestError));
      setPending(false);
    }
  }

  return (
    <div className="site-shell overflow-x-hidden">
      <a className="skip-link" href="#main">Skip to main content</a>
      <StudioHeader />
      <main id="main">
        <section className="hero-section auth-hero">
          <div className="hero-inner max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="hero-copy">
              <div className="section-index"><span className="index-line" /> TEAM ACCESS <span className="index-number">/ 000</span></div>
              <h1>Welcome<br /><em>back.</em></h1>
              <p className="hero-subtitle">Sign in with your TCG Digital account to send the notetaker, follow live transcripts, and read the minutes.</p>
              <div className="hero-art" aria-hidden="true"><div className="orbit orbit-one" /><div className="orbit orbit-two" /><div className="orbit orbit-three" /><div className="art-core"><LockKeyhole size={38} strokeWidth={1.2} /></div><span className="art-label label-one">SECURE</span><span className="art-label label-two">PRIVATE</span><span className="art-label label-three">YOURS</span></div>
            </div>

            <div className="create-panel auth-panel">
              <div className="panel-heading"><div><span className="eyebrow">SIGN IN</span><h2>Log in<span className="blue-period">.</span></h2></div><ArrowUpRight size={24} strokeWidth={1.5} /></div>
              <form onSubmit={handleSubmit} noValidate>
                {error && <div className="auth-alert error" role="alert"><CircleAlert size={18} /><span>{error}</span></div>}
                <div className="field">
                  <label htmlFor="login-email">Work email</label>
                  <div className="input-icon"><Mail size={18} /><input id="login-email" type="email" autoComplete="username" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@tcgdigital.com" autoFocus required /></div>
                </div>
                <div className="field">
                  <label htmlFor="login-password">Password</label>
                  <PasswordInput id="login-password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Your password" required />
                </div>
                <button className="primary-button" type="submit" disabled={pending}>
                  {pending ? <><LoaderCircle size={19} className="spin" /> Signing in...</> : <>Sign in <ArrowUpRight size={19} /></>}
                </button>
                <p className="form-footnote">No account yet? Ask your admin to create one for you.</p>
              </form>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
