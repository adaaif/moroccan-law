import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSession } from '@/shared/stores/session';
import '@/shared/locales/pages';
import { accountFollow, fetchNews } from './follows.api';
import { follow, unfollow, useFollows } from './store';
import { todayIso } from '@/shared/services/today';

/** «تابع» (R13 of the for-everyone review): on a law, an article or a topic. On the device at once, and on the account
 *  too when signed in, for a letter. What changed it until now counts as seen. */
/** `compact`: the bell alone on a phone, its word from a tablet up (a topic's one-line face, A6 of the road-signposted review). */
export default function FollowButton({ path, quiet, compact }: { path: string; quiet?: boolean; compact?: boolean }) {
  const { t } = useTranslation();
  const signedIn = useSession((s) => s.tokens !== null);
  const on = useFollows().some((f) => f.path === path);
  const [busy, setBusy] = useState(false);
  const client = useQueryClient();
  const tell = (on: boolean) => {
    if (signedIn) void accountFollow(path, on).then(() => client.invalidateQueries({ queryKey: ['follows', 'mine'] }), () => undefined);
  };
  const toggle = async () => {
    if (on) {
      unfollow(path);
      tell(false);
      return;
    }
    setBusy(true);
    try {
      const n = (await fetchNews([path])).news[0];
      if (!n) return;
      follow({ path, kind: n.kind, name: n.name, article: n.article, since: todayIso(),
               seen: n.items.map((i) => i.key) });
      tell(true);
    } catch {
      // Offline: nothing is followed, the button says so by staying as it was.
    } finally {
      setBusy(false);
    }
  };
  return (
    <button type="button" onClick={() => void toggle()} aria-pressed={on} disabled={busy} title={t('pages:follow.hint')}
            className={`inline-flex h-11 min-w-11 shrink-0 items-center justify-center gap-2 rounded-full text-body ${compact ? 'px-3 sm:px-4' : 'px-4'} font-medium disabled:opacity-60 ${
              on ? 'bg-people-wash text-people' : quiet ? 'text-ink hover:bg-paper hover:text-stamp' : 'bg-sheet text-ink ring-1 ring-rule hover:ring-stamp-line'}`}>
      <Bell on={on} />
      {/* Its word shown on a phone too (UX13 of the phone-test review): a bell alone read as notifications. */}
      <span aria-live="polite">{on ? t('pages:follow.on') : t('pages:follow.do')}</span>
    </button>
  );
}

const Bell = ({ on }: { on: boolean }) => (
  <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill={on ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="1.8"
       strokeLinecap="round" strokeLinejoin="round">
    <path d="M6 9a6 6 0 1 1 12 0c0 5 2 6.5 2 6.5H4S6 14 6 9Z" /><path d="M10 19a2 2 0 0 0 4 0" />
  </svg>
);
