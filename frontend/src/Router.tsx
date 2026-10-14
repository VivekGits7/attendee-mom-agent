import { lazy, Suspense } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';

const Home = lazy(() => import('@/App'));
const MeetingsPage = lazy(() => import('@/meeting/MeetingsPage'));
const MeetingDetailPage = lazy(() => import('@/meeting/MeetingDetailPage'));

export default function Router() {
  return (
    <BrowserRouter>
      <Suspense fallback={<div className="route-loading" role="status">Opening the studio...</div>}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/meetings" element={<MeetingsPage />} />
          <Route path="/meetings/:meetingId" element={<MeetingDetailPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
