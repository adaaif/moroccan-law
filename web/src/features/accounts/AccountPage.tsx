import { lazy, Suspense } from 'react';
import { useTranslation } from 'react-i18next';
import { Navigate, useLocation } from 'react-router-dom';
import { useMe } from './accounts.service';
import { formError } from './errorText';
import { movedTo, tabOf } from './moved';
import { RequireAuth } from './RequireAuth';
import { usePageTitle } from '@/shared/services/title';
import { Page, PageSkeleton } from '@/shared/components/ui';
import '@/shared/locales/pages';

// The two pages come with the discussion's words (the person's part is about the discussion).
const AccountDiscussion = lazy(() => import('@/features/discussion/account/AccountDiscussion'));

/**
 * The account (16 Nov 2026): /account («أنا»: the person, what needs them, what is new, what they wrote and follow) and
 * /account/settings («الإعدادات»: how they are named, addressed, written to and sign in; their personal data; leaving).
 * An old address (/account#apps, /account#access from a letter) leads first to where its section is now, so a visitor
 * who is not signed in is brought back there after signing in.
 */
export default function AccountPage() {
  const { t } = useTranslation();
  const { pathname, hash } = useLocation();
  const page = tabOf(pathname);
  usePageTitle([t(page === 'settings' ? 'pages:account.settings' : 'pages:account.me')]);
  const me = useMe();
  const moved = movedTo(pathname, hash);
  if (moved) return <Navigate to={moved} replace />;

  return (
    <RequireAuth>
      <Page width="wide">
        {me.data ? (
          <Suspense fallback={<PageSkeleton />}><AccountDiscussion key={me.data.id} user={me.data} page={page} /></Suspense>
        ) : me.error ? (
          <p role="alert" className="text-repealed">{formError(t, me.error, [])}</p>
        ) : (
          <PageSkeleton />
        )}
      </Page>
    </RequireAuth>
  );
}
