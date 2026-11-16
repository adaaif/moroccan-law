import { Fragment, useEffect, useRef, useSyncExternalStore, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Link, useLocation } from 'react-router-dom';
import { count } from '@/features/budget/money';
import { Page } from '@/shared/components/ui';
import { api } from '@/shared/services/api';
import { usePageTitle } from '@/shared/services/title';
import Word, { Filled } from './Word';
import { bare, percent, readCounts, slots } from './words';
import '@/shared/locales/pages';
import '@/shared/design/french.css';
import './locales/open';
import './opensource.css';

/** The corpus's figures (GET /api/open/about/): `source` is the public repository's address, empty until the code is
 *  published; `contact` the address to write to, empty when none is set. */
type About = { texts: number; articles: number; issues: number; pages: number; corrections: number; contact: string; source?: string };

/** The example the essay gives: a real correction, the Labour Code's article 563, where «ثلاثة» had been read «ثالثة». */
const EXAMPLE = '/ma/loi/65-99/art_563';

/**
 * /open-source, «قانون المغرب، كلمة كلمة». The argument on the reading side, its evidence beside it: the title and the
 * first three sentences beside a doubtful word to settle, live, as its printed line; «the machine errs» beside one
 * real correction, marked as a proofreader marks a proof; «three thousand people» beside how far everyone is. On a
 * phone each claim is followed by its evidence. Then what helping gives everyone, the three rules of a correction,
 * what each length of time can do, and the project by its addresses (the repository's, once `source` is set). The
 * figures are the site's own (GET /api/open/about/ and /api/quality/words/), «…» until they come. Its words, styles
 * and code load with it, never with the first load.
 */
export default function OpenSourcePage() {
  const { t, i18n } = useTranslation('open');
  const lang = i18n.language;
  usePageTitle([t('title')]);
  useHashTarget();
  const about = useQuery({ queryKey: ['about'], queryFn: () => api<About>('/open/about/'), staleTime: 3600_000 }).data;
  // A minute old at most, as the server keeps it; the tab asks again while it is open.
  const words = useQuery({ queryKey: ['quality', 'words'], queryFn: readCounts, staleTime: 60_000, refetchInterval: 60_000 }).data;
  const n = (v: number | undefined) => (v === undefined ? undefined : count(v, lang));
  const figures = {
    issues: n(about?.issues), pages: n(about?.pages), texts: n(about?.texts), articles: n(about?.articles),
    words: n(words?.words),
  };
  // A sentence of the essay, its figures set in place.
  const say = (key: string) => <Filled text={t(key, { skipInterpolation: true })} values={figures} />;
  return (
    <Page width="wide" className="os">
      <article className="os-top">
        <header className="os-head">
          <h1 className="os-title">{t('title')}</h1>
          <p className="os-lead">{t('description')}</p>
        </header>
        <div className="os-first">
          <Word />
          <p className="os-private">{t('word.private')}</p>
        </div>
        <div className="os-essay os-a">
          <p>{say('intro.public')}</p>
          <p>{say('intro.printed')}</p>
          <p>{say('intro.read')}</p>
        </div>
        <p className="os-essay os-b1">{say('intro.wrong')}</p>
        <Erratum />
        <p className="os-essay os-b2">{say('intro.swap')}</p>
        <div className="os-essay os-c">
          <p>{say('intro.doubt')}</p>
          <p>{say('intro.many')}</p>
        </div>
        <Progress words={words?.words} settled={words?.settled} today={words?.today} corrections={about?.corrections} />
      </article>

      <div className="os-below">
        <section className="os-part os-gains" aria-labelledby="os-gains">
          <h2 id="os-gains">{t('gains.title')}</h2>
          <p className="os-essay">{t('gains.all')}</p>
          <dl className="os-defs">
            <div><dt>{t('gains.lawTerm')}</dt><dd>{t('gains.law')}</dd></div>
            <div><dt>{t('gains.dataTerm')}</dt><dd>{t('gains.data')} <Link to="/data" data-hit>{t('gains.dataLink')}</Link></dd></div>
            <div><dt>{t('gains.codeTerm')}</dt><dd>{t(about?.source ? 'gains.code' : 'gains.codeSoon')}</dd></div>
          </dl>
          <p className="os-essay">{t('gains.people')}</p>
        </section>

        <section className="os-part os-rules" aria-labelledby="os-rules">
          <h2 id="os-rules">{t('rules.title')}</h2>
          <ul className="os-rows os-essay">
            <li>{t('rules.printed')}</li>
            <li>{t('rules.person')}</li>
            <li>{t('rules.public')} <Link to="/corrections" data-hit>{t('rules.publicLink')}</Link></li>
          </ul>
        </section>

        <section className="os-part os-time" aria-labelledby="os-time">
          <h2 id="os-time">{t('time.title')}</h2>
          <ul className="os-rows os-ways">
            <Row id="word" go={<a href="#word" className="os-go">{t('time.word.go')}</a>} />
            <Row id="reading" values={{ report: t('pages:quality.reportRow') }} />
            <Row id="send" go={<button type="button" className="os-go" onClick={() => sendPage(t('title'), t('description'))}>{t('time.send.go')}</button>} />
            <Row id="code" go={about?.source
              ? <a href={about.source} className="os-go" target="_blank" rel="noopener noreferrer">{t('time.code.go')}</a>
              : <span className="os-soon">{t('time.code.soon')}</span>} />
            <Row id="law" go={about?.contact ? <a href={`mailto:${about.contact}`} className="os-go" dir="ltr">{about.contact}</a> : null} />
          </ul>
        </section>

        <Addresses source={about?.source} contact={about?.contact} />
      </div>

      <p className="os-last">{t('last')}</p>
    </Page>
  );
}

/** A hand's stroke of the pen across or under a word: drawn once, when its figure comes into view. */
const Pen = ({ d }: { d: string }) => (
  <svg className="os-pen" viewBox="0 0 100 10" preserveAspectRatio="none" aria-hidden="true"><path d={d} /></svg>
);

/** The example, marked as a proofreader marks a proof: what the reading had, the misread word struck by hand; what the
 *  page prints, the right word underlined in the site's ink; on a French page each line of law followed by its gloss.
 *  The two strokes are drawn when the figure is first seen (never for a reader who asked for less motion, and
 *  without scripts they are simply there). */
function Erratum() {
  const { t } = useTranslation('open');
  const figure = useRef<HTMLElement>(null);
  useEffect(() => {
    const el = figure.current;
    if (!el || typeof IntersectionObserver === 'undefined' || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    el.dataset.pen = 'held';
    const seen = new IntersectionObserver(([e]) => {
      if (!e.isIntersecting) return;
      el.dataset.pen = 'drawn';
      seen.disconnect();
    }, { threshold: 0.75 });
    seen.observe(el);
    return () => seen.disconnect();
  }, []);
  const law = (word: ReactNode) => slots(t('example.law', { skipInterpolation: true }))
    .map((p, i) => (typeof p === 'string' ? p : <Fragment key={i}>{word}</Fragment>));
  const gloss = (key: string) => (t(key) ? <p className="os-gloss">{t(key)}</p> : null);
  return (
    <figure ref={figure} className="os-erratum">
      <p className="os-said">{t('example.was')}</p>
      <p className="os-law" lang="ar" dir="rtl">{law(<del>{t('example.wrong')}<Pen d="M1 6.5 C 22 2.5, 44 8.5, 99 3.5" /></del>)}</p>
      {gloss('example.wrongGloss')}
      <p className="os-said">{t('example.printed')}</p>
      <p className="os-law" lang="ar" dir="rtl">{law(<ins>{t('example.right')}<Pen d="M1 4 C 30 8, 62 1.5, 99 5.5" /></ins>)}</p>
      {gloss('example.rightGloss')}
      <figcaption><Link to={EXAMPLE} className="os-go">{t('example.link')}</Link></figcaption>
    </figure>
  );
}

/** How many words one square of the field stands for. */
const CELL = 100;

/** How far everyone is: the count settled, then the whole task as a field of squares, one for every hundred words,
 *  filled from the left as words are settled (drawn left to right on every page, the share at its right end); today's
 *  answers and the corrections applied under it. Before the count comes the field holds its place. */
function Progress({ words, settled, today, corrections }: { words?: number; settled?: number; today?: number; corrections?: number }) {
  const { t, i18n } = useTranslation('open');
  const lang = i18n.language;
  const n = (v: number | undefined) => (v === undefined ? undefined : count(v, lang));
  const pct = words !== undefined && settled !== undefined ? percent(settled, words, lang) : undefined;
  const cells = words === undefined ? 300 : Math.ceil(words / CELL);
  const on = Math.floor((settled ?? 0) / CELL);
  return (
    <div className="os-progress">
      <p className="os-tally">
        <span>{t('word.settledLabel')}</span>
        <b className="os-n">{n(settled) ?? '…'}</b>{' '}
        <Filled text={t('word.of', { skipInterpolation: true })} values={{ words: n(words) }} />
      </p>
      <div className="os-field" dir="ltr" role="meter" aria-valuemin={0} aria-valuemax={words ?? 0} aria-valuenow={settled ?? 0}
           aria-valuetext={pct} aria-label={t('word.settled', { settled: n(settled) ?? '…', words: n(words) ?? '…' })}>
        {Array.from({ length: cells }, (_, i) => <i key={i} data-on={i < on ? '' : undefined} />)}
      </div>
      <p className="os-legend" dir="ltr">
        <span dir={i18n.dir(lang)}>{t('word.cell', { n: count(CELL, lang) })}</span>
        <span className="os-pct">{pct ?? '…'}</span>
      </p>
      <p className="os-counts">
        <span><Filled text={t('word.today', { skipInterpolation: true })} values={{ today: n(today) }} /></span>
        <span><Filled text={t('word.applied', { skipInterpolation: true })} values={{ corrections: n(corrections) }} /></span>
      </p>
    </div>
  );
}

/** A row of «على قدر الوقت»: how long, in violet, then what, then where it leads when it leads somewhere. */
function Row({ id, values, go }: { id: string; values?: Record<string, string>; go?: ReactNode }) {
  const { t } = useTranslation('open');
  return (
    <li>
      <span className="os-when">{t(`time.${id}.when`)}</span>
      <p>{t(`time.${id}.what`, values)}</p>
      {go ? <span className="os-to">{go}</span> : null}
    </li>
  );
}

const noHost = () => () => undefined;

/** An address written out, left to right; a long one breaks after a slash, never inside a name. */
const Url = ({ text }: { text: string }) => (
  <span className="os-url" dir="ltr">
    {text.split('/').map((part, i) => <Fragment key={i}>{i ? <>/<wbr /></> : null}{part}</Fragment>)}
  </span>
);

/** The project by its addresses, each written out: the repository's (the code, how to contribute, where to report,
 *  the licences, a security flaw) once the code is published, then the site's own doors and the address to write to.
 *  The site's host is the one the page is read at, known only in the browser. */
function Addresses({ source, contact }: { source?: string; contact?: string }) {
  const { t } = useTranslation('open');
  const host = useSyncExternalStore(noHost, () => window.location.host, () => '');
  const repo: [string, string][] = source ? [
    ['source', source],
    ['contributing', `${source}/blob/main/CONTRIBUTING.md`],
    ['issues', `${source}/issues/new/choose`],
    ['licences', `${source}/blob/main/README.md#licences`],
    ['security', `${source}/blob/main/SECURITY.md`],
  ] : [];
  const site: [string, string][] = [['data', '/data'], ['corrections', '/corrections'], ['assistants', '/ai']];
  return (
    <section className="os-part os-links" aria-labelledby="os-links">
      <h2 id="os-links">{t('links.title')}</h2>
      <ul className="os-rows os-addrs">
        {repo.map(([k, url]) => (
          <li key={k}>
            <a href={url} target="_blank" rel="noopener noreferrer">
              <span>{t(`links.${k}`)}</span><Url text={bare(url)} />
            </a>
          </li>
        ))}
        {source ? null : <li className="os-unpublished">{t('links.soon')}</li>}
        {site.map(([k, to]) => (
          <li key={k}>
            <Link to={to} data-hit><span>{t(`links.${k}`)}</span><Url text={`${host}${to}`} /></Link>
          </li>
        ))}
        {contact ? (
          <li><a href={`mailto:${contact}`}><span>{t('links.mail')}</span><Url text={contact} /></a></li>
        ) : null}
      </ul>
      {source ? <p className="os-fine">{t('links.draft')}</p> : null}
    </section>
  );
}

/** «إرسال»: the device's own share sheet where it has one, else the message to WhatsApp, as the site shares. */
function sendPage(title: string, text: string) {
  const url = `${window.location.origin}/open-source`;
  if (navigator.share) {
    void navigator.share({ title, text, url }).catch(() => undefined);
    return;
  }
  window.open(`https://wa.me/?text=${encodeURIComponent(`${title}\n${text}\n${url}`)}`, '_blank', 'noopener');
}

/** A link to #word from another page lands on the sheet: the page loads after its link, so the place is found once it
 *  stands. */
function useHashTarget() {
  const { hash } = useLocation();
  useEffect(() => {
    if (hash) document.getElementById(decodeURIComponent(hash.slice(1)))?.scrollIntoView();
  }, [hash]);
}
