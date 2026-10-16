import type { Session } from '@/auth/types';

const STORAGE_KEY = 'meeting-console.session';

type Listener = (session: Session | null) => void;
const listeners = new Set<Listener>();

function readStored(): Session | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const session = JSON.parse(raw) as Session;
    return session.accessToken && session.expiresAt > Date.now() ? session : null;
  } catch {
    return null;
  }
}

function writeStored(session: Session | null) {
  try {
    if (session) window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    else window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Private windows can block storage, the session then lives only in this tab.
  }
}

let current = readStored();

function emit() {
  listeners.forEach((listener) => listener(current));
}

export function getSession(): Session | null {
  if (current && current.expiresAt <= Date.now()) clearSession();
  return current;
}

export function saveSession(session: Session) {
  current = session;
  writeStored(session);
  emit();
}

export function clearSession() {
  const hadSession = current !== null;
  current = null;
  writeStored(null);
  if (hadSession) emit();
}

export function subscribeSession(listener: Listener): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

window.addEventListener('storage', (event) => {
  if (event.key !== STORAGE_KEY) return;
  current = readStored();
  emit();
});
