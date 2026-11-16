import { useQuery } from '@tanstack/react-query';
import { lazy, Suspense } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { api } from '@/shared/services/api';
import { PageSkeleton } from '@/shared/components/ui';

const NotFound = lazy(() => import('../NotFound'));
const History = lazy(() => import('./HistoryPage'));

/** /constitution, /constitution/19, /constitution/1996, /constitution/1996/19 (C1 of the constitution review): the
 *  constitution in force that year, or today's, and its article, at the address the server gives; /constitution/history
 *  is their short history. A year is never an article number (the constitutions have 180 at most). */
export default function ConstitutionRoute() {
  const parts = useLocation().pathname.split('/').filter(Boolean).slice(1);
  const history = parts[0] === 'history';
  const year = parts.find((p) => /^\d{4}$/.test(p) && Number(p) >= 1900) ?? '';
  const article = parts.find((p) => /^\d{1,3}$/.test(p)) ?? '';
  const qs = new URLSearchParams({ ...(year ? { year } : {}), ...(article ? { article } : {}) });
  const found = useQuery({ queryKey: ['constitution', year, article], queryFn: () => api<{ path: string }>(`/corpus/constitution/?${qs}`),
                           enabled: !history });
  if (history) return <Suspense fallback={<PageSkeleton />}><History /></Suspense>;
  if (found.data) return <Navigate to={found.data.path} replace />;
  if (found.isError) return <Suspense fallback={null}><NotFound /></Suspense>;
  return <div className="mx-auto w-full max-w-6xl px-4 pb-14 pt-6 sm:px-6 sm:pt-10"><PageSkeleton kind="text" /></div>;
}
