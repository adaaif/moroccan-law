import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { api } from '@/shared/services/api';
import { LinesSkeleton, Page } from '@/shared/components/ui';
import { usePageTitle } from '@/shared/services/title';
import '@/shared/locales/pages';
import { longDate } from './format';
import HomeWeek from './HomeWeek';
import { CardHost, Shelves } from './library/Books';
import { Find } from './library/Find';
import { useArchive, useDetail, useLibrary, useNum, type Library, type Newest } from './library/library.api';
import { Strata } from './library/Strata';
import './library.css';

type Room = 'codes' | 'bo';

/** «المكتبة»: one box, then two rooms a reader walks between (15 Nov 2026: tabs between the codes and the
 *  Bulletin; the every-code review had named the two rooms). The box reads whatever a reader knows of a text or
 *  an issue and answers for both rooms. «المدونات والقوانين»: nine shelves, each led by its general code as a bound
 *  book. «الجريدة الرسمية»: the week, the two newest issues as they are with the day the SGG was last asked, then every
 *  issue held since No. 1 as strata. The room is in the address (`#bo`), so a link opens either; the Bulletin's tab
 *  names its newest issue, so the room a reader is not in still says what is new. The tools in four lines under both. */
export default function LibraryPage() {
  const { t, i18n } = useTranslation();
  const num = useNum();
  usePageTitle([t('pages:library.title')]);
  const library = useLibrary();
  const archive = useArchive();
  const data = useQuery({ queryKey: ['openManifest'], queryFn: () => api<{ date: string }>('/open/'), staleTime: 3_600_000 }).data;
  const [hits, setHits] = useState<Set<string> | null>(null);
  const [detail, toggleDetail] = useDetail();
  const { hash } = useLocation();
  const navigate = useNavigate();
  const room: Room = hash === '#bo' ? 'bo' : 'codes';
  // The Bulletin's strata are thousands of marks: drawn the first time its room is entered, kept after.
  const [entered, setEntered] = useState(room === 'bo');
  useEffect(() => { if (room === 'bo') setEntered(true); }, [room]);
  const enter = (to: Room) => navigate({ hash: to === 'bo' ? '#bo' : '' }, { replace: true });
  const a = archive.data;
  const all = library.data?.branches.flatMap((b) => b.books) ?? [];
  const last = library.data?.newest[0];
  const failed = (retry: () => void) => (
    <p className="lb-failed">{t('pages:landing.failed')} <button type="button" onClick={retry}>{t('pages:landing.retry')}</button></p>
  );
  const tab = (key: Room, label: string, sub: string) => (
    <button type="button" role="tab" id={`lb-tab-${key}`} aria-selected={room === key} aria-controls={`lb-room-${key}`} tabIndex={room === key ? 0 : -1}
            className="lb-door" onClick={() => enter(key)}
            onKeyDown={(e) => {
              if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return;
              e.preventDefault();
              const to: Room = e.key === 'Home' ? 'codes' : e.key === 'End' ? 'bo' : key === 'codes' ? 'bo' : 'codes';
              enter(to);
              document.getElementById(`lb-tab-${to}`)?.focus();
            }}>
      <b>{label}</b><small>{sub}</small>
    </button>
  );
  return (
    <Page width="wide" className="lb">
      <CardHost>
        <header className="lb-head plain">
          <h1>{t('pages:library.title')}</h1>
          <p className="lead">{t('pages:lib5.lead')}</p>
        </header>

        <Find onBooks={setHits} />

        <div className="lb-rooms">
          <div className="lb-doors" role="tablist" aria-label={t('pages:lib5.tabs.label')}>
            {tab('codes', t('pages:lib5.tabs.codes'),
              all.length ? t('pages:lib5.tabs.codesSub', { texts: t('pages:lib2.textsN', { count: all.length, n: num(all.length) }), n: library.data!.branches.length }) : '\u00a0')}
            {tab('bo', t('pages:lib3.issue.bulletin'),
              last ? t('pages:lib5.tabs.boSub', { n: last.number + (last.suffix ? ` ${t(`corpus.suffix.${last.suffix}`)}` : ''), date: longDate(last.date, i18n.language) }) : '\u00a0')}
          </div>

          <section role="tabpanel" id="lb-room-codes" aria-labelledby="lb-tab-codes" hidden={room !== 'codes'} className="lb-room">
            <p className="lb-roomtop">
              <span>{t('pages:lib5.codesLead')}</span>
              <button type="button" className="lb-switch" aria-pressed={detail} onClick={toggleDetail}>{t('pages:lib5.detail')}</button>
            </p>
            {library.data ? <Shelves branches={library.data.branches} most={library.data.most} hits={hits} detail={detail} />
              : library.isError ? failed(() => void library.refetch()) : <div className="min-h-svh"><LinesSkeleton /></div>}
          </section>

          <section role="tabpanel" id="lb-room-bo" aria-labelledby="lb-tab-bo" hidden={room !== 'bo'} className="lb-room">
            {entered || room === 'bo' ? (
              <>
                <p className="lb-roomtop"><span>{t('pages:lib3.bulletin.lead', { count: a?.fr.length ?? 0, n: num(a?.fr.length ?? 0) })}</span></p>
                <div className="lb-bonow">
                  <HomeWeek />
                  {library.data ? <NewestIssues library={library.data} /> : <LinesSkeleton lines={3} />}
                </div>
                {a ? <Strata archive={a} /> : archive.isError ? failed(() => void archive.refetch()) : <LinesSkeleton lines={6} />}
                <p className="lb-more">
                  <Link to="/bo">{t('pages:lib3.bulletin.all')}</Link>
                  <Link to="/blog">{t('pages:lib3.bulletin.blog')}</Link>
                </p>
              </>
            ) : null}
          </section>
        </div>

        <section className="lb-room" aria-labelledby="lb-tools">
          <h2 id="lb-tools" className="lb-toolshead">{t('pages:lib2.tools')}</h2>
          <ul className="lb-toolrows">
            <li><Link to="/words"><b>{t('nav.words')}</b><span>{t('pages:library.wordsLead2')}</span></Link></li>
            <li><Link to="/places"><b>{t('pages:places.title')}</b><span>{t('pages:lib3.tools.places')}</span><small dir="ltr">1913–2026</small></Link></li>
            <li><Link to="/check"><b>{t('nav.check')}</b><span>{t('pages:library.checkLead2')}</span><small>{t('pages:lib2.onDevice')}</small></Link></li>
            <li><Link to="/data"><b>{t('data.title')}</b><span>{t(data ? 'pages:library.dataLead2' : 'pages:library.dataSoon')}</span>
              <small>{data ? longDate(data.date, i18n.language) : t('pages:data.soon.tag')}</small></Link></li>
          </ul>
        </section>
      </CardHost>
    </Page>
  );
}

/** The two newest issues as they are (W9): number, weekday and day, what each holds; an issue kept by its pages alone
 *  says what its own contents table prints. Then the day the SGG was last asked and what its list ended on, so a reader
 *  can tell a late site from a quiet Bulletin. */
function NewestIssues({ library }: { library: Library }) {
  const { t, i18n } = useTranslation();
  const num = useNum();
  const locale = i18n.language === 'fr' ? 'fr-MA' : 'ar-MA';
  const weekday = (iso: string) => new Intl.DateTimeFormat(locale, { weekday: 'long', timeZone: 'UTC' }).format(Date.parse(`${iso}T00:00:00Z`));
  const name = (x: { number: number; suffix: string }) => x.number + (x.suffix ? ` ${t(`corpus.suffix.${x.suffix}`)}` : '');
  const line = (x: Newest) => (
    <Link key={x.key} to={`/bo/general_ar/${x.key}`}>
      <b><bdi dir="ltr">{x.number}</bdi>{x.suffix ? <em>{t(`corpus.suffix.${x.suffix}`)}</em> : null}</b>
      <span><strong>{weekday(x.date)} {longDate(x.date, i18n.language)}</strong> · {x.texts
        ? t('pages:lib4.newest.holds', { texts: t('pages:lib2.textsN', { count: x.texts, n: num(x.texts) }), pages: t('pages:lib3.pagesN', { count: x.pages, n: num(x.pages) }) })
        : <>{x.about ? <span lang="ar" dir="rtl">{x.about} </span> : null}{t('pages:lib4.newest.bare', { pages: t('pages:lib3.pagesN', { count: x.pages, n: num(x.pages) }) })}</>}</span>
    </Link>
  );
  const asked = library.asked;
  const newest = library.newest[0];
  // The SGG's list named an issue the site does not hold yet: it is read the night after.
  const ahead = asked && newest && asked.newest && asked.newest !== newest.key && asked.newest_date > newest.date;
  return (
    <section className="lb-new" aria-labelledby="lb-new">
      <h2 id="lb-new">{t('pages:lib4.newest.title')}</h2>
      {library.newest.map(line)}
      <p>{asked && newest ? t(ahead ? 'pages:lib4.newest.askedAhead' : 'pages:lib4.newest.asked', { day: longDate(asked.at.slice(0, 10), i18n.language), n: ahead ? asked.newest.replace('-bis', ` ${t('corpus.suffix.bis')}`) : name(newest) }) : null}
        {' '}<Link to="/new">{t('pages:lib4.newest.all')}</Link></p>
    </section>
  );
}
