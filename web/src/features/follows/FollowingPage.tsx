import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { useRegistrationOpen } from '@/features/accounts/registration';
import { Stamp } from '@/features/corpus/article/Stamp';
import { AR, issueNo, longDate } from '@/features/corpus/format';
import { useSession } from '@/shared/stores/session';
import '@/shared/locales/pages';
import { useAccountFollows, useNews, type News, type NewsItem } from './follows.api';
import FollowButton from './FollowButton';
import { follow, markSeen, useFollows, type Followed } from './store';
import { usePageTitle } from '@/shared/services/title';
import { Button, EmptyState, LinesSkeleton, Page } from '@/shared/components/ui';
import { EmptyArt } from '@/shared/components/EmptyArt';
import { todayIso } from '@/shared/services/today';

const SHOWN = 4;

/** /me/following, «ما أتابعه» (R13 of the for-everyone review): each law, article or topic one follows, and what changed
 *  it — the text that changed it and the BO page that printed it — the changes new to the reader first. Looking marks
 *  them seen. With an account, a letter says it too. */
export default function FollowingPage() {
  const { t } = useTranslation();
  usePageTitle([t('pages:follow.title')]);
  const signedIn = useSession((s) => s.tokens !== null);
  const registrationOpen = useRegistrationOpen();
  const follows = useFollows();
  const mine = useAccountFollows(signedIn);
  // What the account follows from another device joins this one, its changes until now seen (a letter told them).
  const merged = useRef(false);
  useEffect(() => {
    if (!mine.data || merged.current) return;
    merged.current = true;
    for (const f of mine.data.following) {
      if (!follows.some((x) => x.path === f.path)) {
        follow({ path: f.path, kind: f.kind, name: f.name, article: f.article, since: f.since, seen: [] });
      }
    }
  }, [mine.data, follows]);
  const news = useNews(follows.map((f) => f.path));
  // What was new when the page opened stays marked while the reader is here; the device counts it seen.
  const [seenBefore] = useState(() => new Map(follows.map((f) => [f.path, new Set(f.seen)])));
  useEffect(() => {
    if (news.data) markSeen(Object.fromEntries(news.data.news.map((n) => [n.path, n.items.map((i) => i.key)])));
  }, [news.data]);

  return (
    <Page width="reading" className="gap-4">
      <Link to="/me" className="px-1 text-body text-ink-soft no-underline hover:text-stamp">{t('pages:follow.back')}</Link>
      <header className="flex flex-col gap-2 px-1">
        <h1 className="m-0 text-h2 font-bold">{t('pages:follow.title')}</h1>
        <p className="m-0 max-w-[60ch] text-body text-ink-soft">{t('pages:follow.lead')}</p>
        {signedIn || registrationOpen ? (
          <p className="m-0 text-meta text-ink-soft">
            {signedIn ? t('pages:follow.letters') : <>{t('pages:follow.noAccount')} <Link to="/register" className="font-medium no-underline">{t('pages:follow.createAccount')}</Link></>}
          </p>
        ) : null}
      </header>
      {follows.length ? (
        <ul className="m-0 flex list-none flex-col gap-3 p-0">
          {follows.map((f) => (
            <Card key={f.path} f={f} n={news.data?.news.find((x) => x.path === f.path)} loading={news.isLoading}
                  seen={seenBefore.get(f.path) ?? new Set(f.seen)} />
          ))}
        </ul>
      ) : (
        <EmptyState art={<EmptyArt kind="follow" />} title={t('pages:follow.none')} lead={t('pages:follow.howTo')}>
          <div className="flex flex-wrap gap-2">
            <Button variant="primary" to="/codes">{t('pages:follow.toCodes')}</Button>
            <Button to="/topics">{t('pages:follow.toTopics')}</Button>
          </div>
        </EmptyState>
      )}
    </Page>
  );
}

function Card({ f, n, seen, loading }: { f: Followed; n?: News; seen: Set<string>; loading: boolean }) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const items = n ? [...n.items].sort((a, b) => Number(seen.has(a.key)) - Number(seen.has(b.key))) : [];
  const fresh = items.filter((i) => !seen.has(i.key)).length;
  return (
    <li className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-4">
      <div className="flex items-start gap-3">
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className="text-meta font-medium text-ink-soft">
            {t(`pages:follow.kind.${f.kind}`)}{fresh ? <span className="ms-2 rounded-full bg-people-fill px-2 py-0.5 text-meta font-semibold text-on-people">{t('pages:follow.newCount', { count: fresh })}</span> : null}
          </span>
          <Link to={f.path} lang={lang} className="text-lead font-semibold leading-snug text-ink no-underline hover:text-stamp">
            {f.article ? `${f.article} · ` : ''}{f.name[lang]}
          </Link>
        </div>
        <FollowButton path={f.path} quiet />
      </div>
      {loading && !n ? <LinesSkeleton /> : items.length ? (
        <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
          {items.slice(0, SHOWN).map((i) => <Item key={i.key} i={i} f={f} fresh={!seen.has(i.key)} />)}
          {n && n.total > SHOWN ? (
            <li><Link to={f.path} className="text-meta font-medium no-underline">
              {t('pages:follow.more', { count: n.total - SHOWN })}
            </Link></li>
          ) : null}
        </ul>
      ) : n ? (
        <p className="m-0 text-meta text-ink-soft">{t(f.kind === 'topic' ? 'pages:follow.quietTopic' : 'pages:follow.quiet')}</p>
      ) : null}
    </li>
  );
}

function Item({ i, f, fresh }: { i: NewsItem; f: Followed; fresh: boolean }) {
  const { t, i18n } = useTranslation();
  const list = (xs: string[]) => xs.slice(0, 6).join(t('corpus.listSep'));
  const today = todayIso();
  if (i.kind === 'reform') {
    const lang = i18n.language === 'fr' ? 'fr' : 'ar';
    return (
      <li className={`flex flex-col gap-1 rounded-card px-3 py-2.5 ${fresh ? 'bg-people-wash' : 'bg-paper'}`}>
        <span className="text-meta text-ink-soft">{fresh ? <b className="text-people">{t('pages:follow.new')} · </b> : null}{longDate(i.on, i18n.language)}</span>
        <Link to={f.path} lang={lang} className="text-body leading-snug text-ink no-underline hover:text-stamp">{i.text[lang] || i.text.ar}</Link>
        <a href={i.source.url} target="_blank" rel="noreferrer" lang={lang} className="self-start text-meta">{i.source.name[lang] || i.source.name.ar}</a>
      </li>
    );
  }
  if (i.kind === 'new_text') {
    return (
      <li className={`flex flex-col gap-1 rounded-card px-3 py-2.5 ${fresh ? 'bg-people-wash' : 'bg-paper'}`}>
        <span className="text-meta text-ink-soft">{fresh ? <b className="text-people">{t('pages:follow.new')} · </b> : null}{longDate(i.on, i18n.language)}</span>
        <Link {...AR} to={i.text.path} className="text-body leading-snug text-ink no-underline hover:text-stamp">{i.text.title}</Link>
      </li>
    );
  }
  const by = t('pages:follow.by', { type: t(`corpus.types.${i.by.kind}`, { defaultValue: t('corpus.types.other') }), number: i.by.number.replace(/-/g, '.') });
  const where = f.kind === 'article' ? t('pages:follow.thisArticle')
    : i.articles.length > 1 ? t('pages:follow.articles', { list: list(i.articles) })
    : i.articles.length ? t('pages:follow.article', { n: i.articles[0] }) : t('pages:follow.wholeText');
  const verb = t(i.verbs.length === 1 && i.verbs[0] === 'repealed' ? 'pages:follow.repealed' : 'pages:follow.changed');
  return (
    <li className={`flex flex-col gap-1.5 rounded-card px-3 py-2.5 ${fresh ? 'bg-people-wash' : 'bg-paper'}`}>
      <span className="text-meta text-ink-soft">{fresh ? <b className="text-people">{t('pages:follow.new')} · </b> : null}{longDate(i.on, i18n.language)}</span>
      <p className="m-0 text-body leading-snug">
        {i.by.path ? <Link to={i.by.path} className="font-semibold no-underline">{by}</Link> : <b>{by}</b>} {verb} {where}
      </p>
      <span className="flex flex-wrap items-center gap-2">
        <Stamp issue={i.issue.number ? issueNo({ number: i.issue.number, suffix: i.issue.bis ? 'bis' : '' }, t) : null} page={i.issue.page} to={i.issue.path} />
        {!i.settled ? <span className="rounded-full bg-amended-wash px-2.5 py-1 text-meta text-amended">{t('pages:follow.unsettled')}</span> : null}
        {i.effective_on && i.effective_on > today ? <span className="text-meta text-ink-soft">{t('pages:follow.from', { date: longDate(i.effective_on, i18n.language) })}</span> : null}
      </span>
    </li>
  );
}
