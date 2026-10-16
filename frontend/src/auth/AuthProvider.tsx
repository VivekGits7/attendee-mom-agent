import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

import { changePassword, login, logout } from '@/auth/Authapi';
import { clearSession, getSession, saveSession, subscribeSession } from '@/auth/session';
import type { AuthUser, ChangePasswordInput } from '@/auth/types';

const MAX_TIMER_MS = 2 ** 31 - 1;

interface AuthContextValue {
  user: AuthUser | null;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  updatePassword: (input: ChangePasswordInput) => Promise<string>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function expiryFrom(expiresIn: number) {
  return Date.now() + expiresIn * 1000;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState(getSession);

  useEffect(() => subscribeSession(setSession), []);

  useEffect(() => {
    if (!session) return;
    const timer = window.setTimeout(() => void getSession(), Math.min(MAX_TIMER_MS, Math.max(0, session.expiresAt - Date.now())));
    return () => window.clearTimeout(timer);
  }, [session]);

  const signIn = useCallback(async (email: string, password: string) => {
    const response = await login(email, password);
    saveSession({ accessToken: response.access_token, expiresAt: expiryFrom(response.expires_in), user: response.data });
  }, []);

  const signOut = useCallback(async () => {
    await logout().catch(() => undefined);
    clearSession();
  }, []);

  const updatePassword = useCallback(async (input: ChangePasswordInput) => {
    // A poll can hit the old token and clear the session before this call returns, so keep the user from before.
    const before = getSession();
    const response = await changePassword(input);
    if (before) saveSession({ ...before, accessToken: response.access_token, expiresAt: expiryFrom(response.expires_in) });
    return response.message;
  }, []);

  const value = useMemo(
    () => ({ user: session?.user ?? null, signIn, signOut, updatePassword }),
    [session, signIn, signOut, updatePassword],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside AuthProvider');
  return context;
}
