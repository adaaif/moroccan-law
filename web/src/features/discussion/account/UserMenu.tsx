import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';
import { accountsApi, useMe } from '@/features/accounts/accounts.service';
import { useFollows } from '@/features/follows/store';
import { Sheet } from '@/shared/components/Sheet';
import { useDismiss } from '@/shared/components/dismiss';
import { useSaved } from '@/shared/services/saved';
import { useSession } from '@/shared/stores/session';
import { discussionApi } from '../discussion.api';
import { useT } from '../strings';
import { useDeskWaiting } from '@/features/opendata/deskLine';
import { useAccessLine } from './accessLine';
import { Face, Icon } from './Face';
import '@/shared/locales/pages';

/**
 * The reader's menu in the header (30 Oct 2026: the entries a reader needs, in one place). One button for a signed-in reader, where «أنا» and «حسابي» were two: their face, a dot when something is new,
 * a moderator's count of what waits. It opens on who they are and their public page, then what is theirs (what is new,
 * their posts, what they saved, what they follow, and «وصولي» once they asked for the data), a moderator's desk, their
 * settings and reading, and leaving. A panel under the button on a desk, the app's sheet on a phone. Loaded after the
 * page, for a signed-in reader only.
 */
export default function UserMenu() {
  const { t } = useT();
  const me = useMe();
  // The same question the dot asked before, every two minutes and on coming back to the tab.
  const poll = useQuery({ queryKey: ['discussion', 'unseen'], queryFn: discussionApi.unseen, refetchInterval: 120_000,
                          refetchOnWindowFocus: true, retry: false });
  const [open, setOpen] = useState<'' | 'pop' | 'sheet'>('');
  const name = me.data?.display_name || me.data?.username || '';
  const d = poll.data;
  const label = [t('me2.menuLabel', { name }), d?.unseen ? t('dot.label') : '', d?.review ? t('dot.review', { count: d.review }) : '']
    .filter(Boolean).join('، ');
  const close = () => setOpen('');
  const menu = me.data ? (
    <Menu name={name} username={me.data.username} proven={me.data.email_proven} karma={d?.karma ?? 0} unseen={d?.unseen ?? 0}
          review={d?.review ?? 0} reviewer={Boolean(d?.reviewer)} desk={Boolean(me.data.desk)} onGo={close} />
  ) : null;
  return (
    <span className="relative">
      <button type="button" className="ac-trigger" aria-expanded={Boolean(open)} aria-haspopup="dialog" aria-label={label}
              onClick={() => setOpen((o) => (o ? '' : window.matchMedia('(min-width: 640px)').matches ? 'pop' : 'sheet'))}>
        <span className="ac-trigger-name" dir="auto">{name}</span>
        {d?.review ? <span className="ac-review" aria-hidden="true">{d.review}</span> : null}
        <Face name={name} size={34} />
        {d?.unseen ? <span className="ac-dot" aria-hidden="true" /> : null}
      </button>
      {open === 'pop' ? <Pop onClose={close}>{menu}</Pop> : null}
      {open === 'sheet' ? <Sheet label={t('me2.menuTitle')} onClose={close}>{menu}</Sheet> : null}
    </span>
  );
}

/** The panel on a desk: Escape or a tap outside closes it, and focus goes back to the button. */
function Pop({ onClose, children }: { onClose: () => void; children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  useDismiss(onClose, false);
  useEffect(() => {
    ref.current?.querySelector<HTMLElement>('a, button')?.focus({ preventScroll: true });
    const away = (e: PointerEvent) => {
      const target = e.target as Node;
      if (!ref.current?.contains(target) && !ref.current?.parentElement?.querySelector('.ac-trigger')?.contains(target)) onClose();
    };
    document.addEventListener('pointerdown', away);
    return () => document.removeEventListener('pointerdown', away);
  }, [onClose]);
  return <div ref={ref} className="ac-pop">{children}</div>;
}

function Menu({ name, username, proven, karma, unseen, review, reviewer, desk, onGo }: {
  name: string; username: string; proven: boolean; karma: number; unseen: number; review: number; reviewer: boolean;
  desk: boolean; onGo: () => void;
}) {
  const { t } = useT();
  const app = useTranslation().t;
  const saved = useSaved().length;
  const follows = useFollows().length;
  // Asked only while the menu is open: the menu is drawn only then.
  const access = useAccessLine();
  // A superuser's access desk, with the requests waiting for an answer: read from the same answer as «وصولي».
  const waiting = useDeskWaiting(desk);
  const navigate = useNavigate();
  const client = useQueryClient();
  const { tokens, clear } = useSession();
  const signOut = async () => {
    onGo();
    // The server forgets this device's refresh token; whatever it answers, this device signs out.
    if (tokens) await accountsApi.signOut(tokens.refresh).catch(() => undefined);
    clear();
    client.clear();
    navigate('/', { replace: true });
  };
  return (
    <nav className="ac-menu" aria-label={t('me2.menuTitle')}>
      <Link to={`/people/${encodeURIComponent(username)}`} className="ac-menu-who" onClick={onGo}>
        <Face name={name} size={48} />
        <b dir="auto">{name}</b>
        <small><span dir="ltr">@{username}</span><span>✦ {t('karma.count', { count: karma })}</span></small>
        <em>{t('me2.publicPage')}</em>
      </Link>
      {!proven ? (
        <Link to="/account#prove" className="ac-menu-alert" onClick={onGo}>
          <span><b>{t('me2.proveAlert')}</b> {t('me2.proveAlertLead')}</span>
        </Link>
      ) : null}
      <hr />
      <Item to="/account#notices" icon="notices" label={t('me2.notices')} n={unseen} fresh onGo={onGo} />
      <Item to="/account#mine" icon="mine" label={t('me2.mine')} onGo={onGo} />
      <Item to="/saved" icon="saved" label={app('nav.saved')} n={saved} onGo={onGo} />
      <Item to="/me/following" icon="following" label={t('me2.following')} sub={t('me2.followingLead')} n={follows} onGo={onGo} />
      {access ? <Item to="/data/access" icon="key" label={t('me2.access')} sub={access.line} onGo={onGo} /> : null}
      {reviewer || desk ? <hr /> : null}
      {reviewer ? <Item to="/review" icon="review" label={t('me2.review')} sub={t('me2.reviewLead')} n={review} mod onGo={onGo} /> : null}
      {desk ? <Item to="/data/desk" icon="lock" label={t('me2.desk')} sub={waiting ? t('me2.deskWaiting', { count: waiting }) : t('me2.deskLead')} n={waiting} mod onGo={onGo} /> : null}
      <hr />
      <Item to="/account/settings" icon="settings" label={t('me2.settings')} sub={t('me2.settingsLead')} onGo={onGo} />
      <Item to="/me" icon="reading" label={t('me2.reading')} sub={t('me2.readingLead')} onGo={onGo} />
      <hr />
      <button type="button" className="ac-item out" onClick={() => void signOut()}>
        <Icon name="out" /><span>{app('pages:account.signOut')}</span>
      </button>
    </nav>
  );
}

function Item({ to, icon, label, sub, n = 0, fresh = false, mod = false, onGo }: {
  to: string; icon: Parameters<typeof Icon>[0]['name']; label: string; sub?: string; n?: number; fresh?: boolean; mod?: boolean;
  onGo: () => void;
}) {
  return (
    <Link to={to} className={`ac-item ${mod ? 'mod' : ''}`} onClick={onGo}>
      <Icon name={icon} />
      <span>{label}{sub ? <small>{sub}</small> : null}</span>
      {n ? <span className={`ac-n ${fresh || mod ? 'new' : ''}`}>{n}</span> : null}
    </Link>
  );
}
