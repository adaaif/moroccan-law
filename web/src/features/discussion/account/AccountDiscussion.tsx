import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { ME_KEY, type User } from '@/features/accounts/accounts.service';
import { useFollows } from '@/features/follows/store';
import { Button, LinesSkeleton, ListRow } from '@/shared/components/ui';
import { api } from '@/shared/services/api';
import { useSaved } from '@/shared/services/saved';
import { TopicTag } from '../TalkParts';
import { discussionApi, MINE_KEY, useMine, usePerson, type Appeal, type Label, type Mine } from '../discussion.api';
import { errorText, homeColour, labelName, pageOf, ruleNo, shortDate, useT } from '../strings';
import AccountSettings from './AccountSettings';
import { Face } from './Face';
import { useDeskWaiting } from '@/features/opendata/deskLine';
import { useAccessLine } from './accessLine';
import { Line, Part } from './Part';
import { useScrollToHash } from './scroll';
import '@/shared/locales/pages';

const field = 'h-11 rounded-control border border-field bg-paper px-3 text-body focus:border-stamp focus:bg-sheet focus:outline-none';

/**
 * The account's two pages (16 Nov 2026; drawn as one page of nine cards on 30 Oct 2026): a short head (the name, the
 * username, whether the address is proven, the counts when there are any, the public page) and two tabs that are
 * addresses, «أنا» (/account) and «الإعدادات» (/account/settings). Titles on rules and rows under them; a part with
 * nothing in it is one line; only what needs the person now is set apart.
 */
export default function AccountDiscussion({ user, page }: { user: User; page: 'me' | 'settings' }) {
  const { t } = useT();
  return (
    <div className="ac">
      <Head user={user} />
      <nav className="ac-tabs" aria-label={t('me2.pagesLabel')}>
        <Link to="/account" aria-current={page === 'me' ? 'page' : undefined}>{t('me2.tabMe')}</Link>
        <Link to="/account/settings" aria-current={page === 'settings' ? 'page' : undefined}>{t('me2.settings')}</Link>
      </nav>
      {page === 'me' ? <Me user={user} /> : <AccountSettings user={user} />}
    </div>
  );
}

/** The name and what is said beside it, in as little of the first screen as it takes. */
function Head({ user }: { user: User }) {
  const { t } = useT();
  const p = usePerson(user.username).data?.pages[0]?.person;
  const name = user.display_name || user.username;
  const counts: [string, number][] = p ? [['statPosts', p.posts], ['statAnswers', p.answers], ['statAccepted', p.accepted]] : [];
  const shown = counts.filter(([, n]) => n > 0);
  return (
    <header className="ac-head" style={homeColour(p?.places)}>
      <Face name={name} />
      <div className="ac-head-text">
        <h1><bdi dir="auto">{name}</bdi></h1>
        <p className="ac-head-line">
          <bdi dir="ltr">@{user.username}</bdi>
          {user.email_proven ? <span className="on">✓ {t('me2.emailProven')}</span>
            : <Link to="/account#prove" className="off">{t('me2.proveAlert')}</Link>}
        </p>
        {p?.karma || shown.length ? (
          <p className="ac-head-line">
            {p?.karma ? <span title={t('karma.hint')}>✦ <b>{p.karma}</b> {t('me2.statKarma')}</span> : null}
            {shown.map(([key, n]) => <span key={key}><b>{n}</b> {t(`me2.${key}`)}</span>)}
          </p>
        ) : null}
        <Link to={`/people/${encodeURIComponent(user.username)}`} className="ac-head-link">{t('me2.seeAsOthers')}</Link>
      </div>
    </header>
  );
}

/**
 * «أنا»: what needs the person now (prove the address, a pause, a question about their access), what is new, what they
 * wrote and what came of it; beside it on a desk, what they follow, their reports, «وصولي» once they asked for the
 * data, and a moderator's desk. An account with nothing in it is offered the two things worth doing, once.
 */
function Me({ user }: { user: User }) {
  const { t } = useT();
  const mine = useMine(user.email_proven);
  const m = mine.data;
  const access = useAccessLine();
  const saved = useSaved().length;
  const follows = useFollows().length;
  useScrollToHash(Boolean(m) || !user.email_proven || mine.isError);
  const loading = user.email_proven && mine.isPending;
  const wrote = Boolean(m?.contributions.length);
  const followsAny = follows > 0 || Boolean(m?.following.length);
  // Nothing written and nothing new: the steps say where to start, and no empty part says it again.
  const fresh = !wrote && !m?.notices.length;
  const steps = loading ? [] : [!wrote && 'ask', !followsAny && 'follow'].filter((s): s is string => Boolean(s));
  const asked = access?.standing === 'more';
  // For a superuser, the requests that wait for an answer on the access desk.
  const desk = useDeskWaiting(user.desk);
  const now = !user.email_proven || Boolean(m?.pause) || asked || desk > 0;
  const side = saved || followsAny || m?.reports.length || (access && !asked) || m?.standing.reviewer;
  return (
    <div className="ac-body">
      <div className="ac-me-main">
        {now ? (
          <div className="ac-now">
            {!user.email_proven ? <Prove user={user} /> : null}
            {m?.pause ? <Pause m={m} /> : null}
            {asked ? <ListRow to="/data/access" title={<b>{t('me2.access')}</b>} lead={access.line} /> : null}
            {desk ? <ListRow to="/data/desk" title={<b>{t('me2.deskWaiting', { count: desk })}</b>} lead={t('me2.desk')} /> : null}
          </div>
        ) : null}
        {loading ? <LinesSkeleton lines={4} /> : null}
        {mine.isError ? <p role="alert" className="m-0 text-meta text-repealed">{errorText(t, mine.error)}</p> : null}
        {m?.notices.length ? <Notices m={m} /> : m && !fresh ? <Line id="notices" title={t('account.noticesTitle')}>{t('account.noNotices')}</Line> : null}
        {m && wrote ? <Contributions m={m} /> : null}
        {steps.length ? (
          <Part id={wrote ? undefined : 'mine'} title={t('me2.stepsTitle')}>
            <ul className="ac-list">
              {steps.includes('ask') ? <li><ListRow to="/talk" title={t('me2.stepAsk')} lead={t('me2.stepAskLead')} /></li> : null}
              {steps.includes('follow') ? <li><ListRow to="/codes" title={t('me2.stepFollow')} lead={t('me2.stepFollowLead')} /></li> : null}
            </ul>
          </Part>
        ) : null}
      </div>
      {side ? (
        <div className="ac-me-side">
          {saved || followsAny ? <Following m={m} saved={saved} follows={follows} /> : null}
          {m?.reports.length ? <Reports m={m} /> : null}
          {(access && !asked) || m?.standing.reviewer ? (
            <ul className="ac-list ac-ruled">
              {access && !asked ? <li><ListRow to="/data/access" title={t('me2.access')} lead={access.line} /></li> : null}
              {m?.standing.reviewer ? <li><ListRow to="/review" title={t('me2.review')} lead={t('me2.reviewLead')} /></li> : null}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

/** The code went at sign-up (and goes again on a new address): its box is open at once, a new code a tap away, and a
 *  wrong address a link to where it is changed (3 Nov 2026). */
function Prove({ user }: { user: User }) {
  const { t } = useT();
  const client = useQueryClient();
  const [sent, setSent] = useState(false);
  const [code, setCode] = useState('');
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  return (
    <section id="prove" className="ac-part">
      <h2>{t('account.proveTitle')}</h2>
      <p className="m-0 text-body text-ink-soft">{t('account.proveLede', { email: `\u2068${user.email}\u2069` })}</p>
      <form className="flex flex-wrap items-end gap-3" onSubmit={async (e) => {
        e.preventDefault(); setBusy(true); setError(null);
        try {
          const saved = await api<User>('/auth/email/prove/', { method: 'POST', json: { code } });
          client.setQueryData(ME_KEY, saved);
          void client.invalidateQueries({ queryKey: ['discussion'] });
        } catch (err) { setError(err); } finally { setBusy(false); }
      }}>
        <label className="flex flex-col gap-1 text-meta">
          {t('account.code')}
          <input value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))} inputMode="numeric"
                 autoComplete="one-time-code" dir="ltr" placeholder="••••••"
                 className={`${field} w-36 text-center text-lead tracking-[0.3em]`} />
        </label>
        <Button variant="primary" type="submit" disabled={busy || code.length !== 6}>{t('account.prove')}</Button>
        <Button disabled={busy} onClick={async () => {
          setBusy(true); setError(null);
          try { await api('/auth/email/code/', { method: 'POST' }); setSent(true); setCode(''); } catch (e) { setError(e); } finally { setBusy(false); }
        }}>{t('account.send')}</Button>
      </form>
      {sent ? <p role="status" className="m-0 text-meta text-in-force">{t('account.sent')}</p> : null}
      {error ? <p role="alert" className="m-0 text-meta text-repealed">{errorText(t, error)}</p> : null}
      <p className="m-0 text-meta"><Link to="/account/settings#signin" className="ac-inline">{t('account.wrongAddress')}</Link></p>
    </section>
  );
}

function Pause({ m }: { m: Mine }) {
  const { t, i18n } = useT();
  const p = m.pause!;
  return (
    <section id="pause" className="ac-part stop">
      <h2>{t('account.pauseTitle')}</h2>
      <p className="m-0 text-body">
        {p.until ? t('account.pauseUntil', { date: shortDate(p.until, i18n.language), n: ruleNo(p.rule) })
          : t('account.pauseForGood', { n: ruleNo(p.rule) })} <Link to={`/rules#rule-${ruleNo(p.rule)}`}>{t(`rules.${p.rule}`)}</Link>
      </p>
      <AppealBox appeal={p.appeal} target={{ pause: p.id }} />
    </section>
  );
}

function Notices({ m }: { m: Mine }) {
  const { t, i18n } = useT();
  const client = useQueryClient();
  /** One line per discussion for what is new where one follows; who answered, when they wrote with a name (R2). */
  const noticeText = (n: Mine['notices'][number]) =>
    n.kind === 'new' ? t('account.notices.newGroup', { count: n.count })
      : n.kind === 'answer' && n.who ? t('account.notices.answerWho', { who: n.who })
        : t(`account.notices.${n.kind}`, { n: ruleNo(n.detail) });
  const seen = m.unseen ? (
    <button type="button" className="ac-more"
            onClick={async () => { await discussionApi.seen(); void client.invalidateQueries({ queryKey: MINE_KEY }); void client.invalidateQueries({ queryKey: ['discussion', 'unseen'] }); }}>
      {t('account.markSeen')}
    </button>
  ) : null;
  return (
    <Part id="notices" title={t('account.noticesTitle')} more={seen}>
      <ul className="ac-rows">
        {m.notices.map((n) => (
          <li key={n.id} className={`ac-notice ${n.seen ? 'seen' : 'new'}`}>
            {n.path ? <Link to={`${pageOf(n.path)}${n.contribution ? `#c${n.contribution}` : ''}`}>{noticeText(n)}</Link>
              : <span>{noticeText(n)}</span>}
            <time dateTime={n.created_at}>{shortDate(n.created_at, i18n.language)}</time>
          </li>
        ))}
      </ul>
    </Part>
  );
}

function Contributions({ m }: { m: Mine }) {
  const { t, i18n } = useT();
  return (
    <Part id="mine" title={t('account.mineTitle')}>
      <ul className="ac-rows">
        {m.contributions.map((c) => (
          <li key={c.id}>
            <div className="ac-row-head">
              {c.label.place ? <TopicTag place={c.label.place} name={c.label.name} /> : null}
              <span className={`ac-state ${c.removed ? 'gone' : c.held ? 'wait' : 'ok'}`}>
                {c.removed ? t('account.states.removed', { n: ruleNo(c.rule) }) : c.held ? t('account.states.held') : `✓ ${t('account.states.published')}`}
              </span>
              <time dateTime={c.created_at}>{shortDate(c.created_at, i18n.language)}</time>
            </div>
            <div className="ac-row-head">
              <Link to={`${pageOf(c.path)}#c${c.id}`} dir="auto"><Where label={c.label} title={c.title || c.post_title} comment={c.kind === 'comment'} /></Link>
            </div>
            {c.body ? <p className="ac-row-body" dir="auto">{c.body}</p> : null}
            {c.removed ? <AppealBox appeal={c.appeal} target={{ contribution: c.id }} /> : null}
          </li>
        ))}
      </ul>
    </Part>
  );
}

function AppealBox({ appeal, target }: { appeal: Appeal | null; target: { contribution?: number; pause?: number } }) {
  const { t } = useT();
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState('');
  const [error, setError] = useState<unknown>(null);
  if (appeal) {
    const state = !appeal.decided ? 'waiting' : appeal.outcome === 'lifted' ? 'lifted' : 'kept';
    return <p className="m-0 text-meta text-ink-soft">{t(`account.appealStates.${state}`)}</p>;
  }
  if (!open) return <button type="button" onClick={() => setOpen(true)} className="ac-more self-start">{t('account.appeal')}</button>;
  return (
    <form className="flex flex-col gap-2" onSubmit={async (e) => {
      e.preventDefault(); setError(null);
      try { await discussionApi.appeal({ ...target, text }); void client.invalidateQueries({ queryKey: MINE_KEY }); } catch (err) { setError(err); }
    }}>
      <p className="m-0 text-meta text-ink-soft">{t('account.appealHint')}</p>
      <textarea dir="auto" value={text} onChange={(e) => setText(e.target.value)} rows={3} maxLength={1000} aria-label={t('account.appealTitle')}
                className="rounded-control border border-field bg-sheet px-3 py-2 text-body focus:border-stamp focus:outline-none" />
      <Button variant="primary" type="submit" disabled={!text.trim()} className="self-start">{t('account.appealSend')}</Button>
      {error ? <p role="alert" className="m-0 text-meta text-repealed">{errorText(t, error)}</p> : null}
    </form>
  );
}

/** What one follows: on this device the articles kept and the laws and topics whose news come weekly; here, the
 *  discussions whose new answers are told. */
function Following({ m, saved, follows }: { m?: Mine; saved: number; follows: number }) {
  const { t } = useT();
  const app = useTranslation().t;
  const client = useQueryClient();
  return (
    <Part id="following" title={t('me2.followingTitle')}>
      <ul className="ac-list">
        <li><ListRow to="/saved" title={app('nav.saved')} lead={t('me2.savedTile', { count: saved })} /></li>
        <li><ListRow to="/me/following" title={t('me2.lawsTile')} lead={t('me2.lawsTileLead', { count: follows })} /></li>
        {m?.following.map((f) => (
          <li key={f.path} className="ac-pair">
            <Link to={pageOf(f.path)} dir="auto"><Where label={f.label} title={f.label.title} /></Link>
            <button type="button" className="ac-more quiet"
                    onClick={async () => { await discussionApi.follow(f.path, false); void client.invalidateQueries({ queryKey: MINE_KEY }); }}>
              {t('account.unfollow')}
            </button>
          </li>
        ))}
      </ul>
    </Part>
  );
}

function Reports({ m }: { m: Mine }) {
  const { t, i18n } = useT();
  return (
    <Part id="reports" title={t('account.reportsTitle')}>
      <ul className="ac-rows">
        {m.reports.map((r, i) => (
          <li key={i} className="ac-pair">
            <span>{t(`reasons.${r.reason}`)} <span className="text-ink-soft">· {t(`account.reportStates.${r.status}`)}</span></span>
            <time dateTime={r.created_at}>{shortDate(r.created_at, i18n.language)}</time>
          </li>
        ))}
      </ul>
    </Part>
  );
}

/** A topic and a post's title (for a comment, the post it answers); or, for an article thread of before, the article
 *  and its text as the law prints them. */
function Where({ label, title, comment = false }: { label: Label; title?: string; comment?: boolean }) {
  const { t, i18n } = useT();
  // A comment's post readers can no longer read comes without its title: «a post» stands for it.
  if (label.place) return <>{comment ? `${t('me2.answerTo')} ${title ? `«${title}»` : t('review.post')}` : title || labelName(label, i18n.language)}</>;
  return (
    <span lang="ar" dir="rtl" className="inline-flex min-w-0 max-w-full items-baseline gap-2">
      <span className="shrink-0 font-semibold">{label.article}</span>
      <span dir="auto" className="text-body text-ink-soft">{label.text}</span>
    </span>
  );
}
