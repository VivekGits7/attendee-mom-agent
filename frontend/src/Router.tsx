import { lazy, Suspense } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';

import { AuthProvider } from '@/auth/AuthProvider';
import { RequireAuth } from '@/auth/RequireAuth';

const Home = lazy(() => import('@/App'));
const MeetingsPage = lazy(() => import('@/meeting/MeetingsPage'));
const MeetingDetailPage = lazy(() => import('@/meeting/MeetingDetailPage'));
const CalendarPage = lazy(() => import('@/meeting/CalendarPage'));
const LoginPage = lazy(() => import('@/auth/LoginPage'));
const AccountPage = lazy(() => import('@/auth/AccountPage'));

export default function Router() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Suspense fallback={<div className="route-loading" role="status">Opening the studio...</div>}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route element={<RequireAuth />}>
              <Route path="/" element={<Home />} />
              <Route path="/meetings" element={<MeetingsPage />} />
              <Route path="/calendar" element={<CalendarPage />} />
              <Route path="/meetings/:meetingId" element={<MeetingDetailPage />} />
              <Route path="/account" element={<AccountPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </AuthProvider>
    </BrowserRouter>
  );
}
