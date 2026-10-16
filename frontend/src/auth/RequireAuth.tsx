import { Navigate, Outlet, useLocation } from 'react-router-dom';

import { useAuth } from '@/auth/AuthProvider';

export function RequireAuth() {
  const { user } = useAuth();
  const location = useLocation();

  if (!user) {
    return <Navigate to="/login" replace state={{ from: `${location.pathname}${location.search}${location.hash}` }} />;
  }
  return <Outlet />;
}
