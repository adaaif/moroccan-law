import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useSession } from '@/shared/stores/session';

export function RequireAuth({ children }: { children: ReactNode }) {
  const signedIn = useSession((s) => s.tokens !== null);
  const location = useLocation();
  if (!signedIn) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return children;
}
