import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import type { ArticleItem, TextDetail } from '../corpus.api';
import { articleName, longDate, splitLabel } from '../format';
import { textName } from '../names';
import { STANDING_TONE, articleStanding } from '../article/status';
import { BACK, keptBack, type Kept } from './back';
import { OnBefore } from '../history/Links';
import { api } from '@/shared/services/api';
import '@/shared/locales/pages';

// A search's words lit in the law (H1–H5 of the search's marks), loaded from here when a search led to the law: the law's
// page is at its first-load budget.
const SearchMarks = lazy(() => import('./SearchMarks'));

/** The day a copy assembled from amendments was brought up to: the SGG's, Adala's or the DGI's date, the machine's
 *  last change; none for a text as printed. */
function asOfOf(v: TextDetail['version']): string | null {
  if (!v || v.consolidation === 'as_published' || v.consolidation === 'bill') return null;
  if (v.consolidation === 'sgg' || v.consolidation === 'adala' || v.consolidation === 'dgi') return v.source?.as_of ?? null;
  return v.consolidation === 'machine' ? v.valid_from : null;
}

/** Above an article opened by its own address (N6): which law this is, where the article stands, how current the
 *  text is, and the way to its beginning. A link to art. 65 used to fill the screen without «مدونة الشغل» anywhere.
 *  And the article itself lit (30 Oct 2026: a reader could not tell which article the link named; landing.css): its
 *  sheet, its number filled, its margin's rule drawn down its words; on a wide desk a tab with its number out of the
 *  paper's edge, as on a code's page; opened from a peek, the way back to the page the peek was on (reading/open.ts). */
export function Landing({ a, d }: { a: ArticleItem; d: TextDetail }) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from;
  // A law asked on a day before the oldest version held, said where the article is read (HM26).
  const on = new URLSearchParams(location.search).get('on') ?? '';
  const [, number] = splitLabel(articleName(a.label, t));
  // Its look from here: imported by this module, its name would be listed in the first load (the law's page is at its
  // budget). A peek fetches it with the text (open.ts).
  useEffect(() => { void import('./landing.css'); }, []);
  const standing = articleStanding(a, d);
  const asOf = asOfOf(d.version);
  const latest = d.standing?.coverage?.latest;
  const read = latest ? latest.key.replace('-bis', ` ${t('corpus.suffix.bis')}`) : '';
  // «حتى 29 يوليوز 2021» said with what the site read since (HM26 of the hard-moment review): a reader took the
  // consolidation's day for the day the law stopped being checked.
  const newer = asOf ? d.amended_by.some((x) => (x.effective_on ?? x.published_on ?? '') > asOf) : false;
  const quiet = asOf && read && !newer && !d.standing?.coverage?.missing_count;
  const current = asOf ? `${t('stamp.consolidatedTo', { date: longDate(asOf, i18n.language) })}${quiet ? t('pages:landing.noneSince', { number: read }) : ''}`
    : read ? t('corpus.readToShort', { number: read }) : '';
  const sep = <span aria-hidden="true" className="text-muted">·</span>;
  return (
    <div className="ln" data-noprint>
      {from ? (
        <button type="button" onClick={() => navigate(-1)} className="ln-back">
          <span aria-hidden="true">‹</span><span className="ln-from">{t('pages:landing.back', { title: from })}</span>
        </button>
      ) : null}
      <p className="m-0 flex flex-wrap items-center gap-x-2 gap-y-1 text-meta text-ink-soft">
        <span className="font-semibold text-ink">{textName(d, i18n.language)}</span>
        {standing ? <>{sep}<span className={STANDING_TONE[standing].text}>{t(`article.standing.${standing}`)}</span></> : null}
        {current ? <>{sep}<span>{current}</span></> : null}
        {sep}
        <Link to={d.path} className="ln-start font-medium no-underline">{t('corpus.fromStart')}</Link>
      </p>
      {on ? <div className="mt-2"><OnBefore d={d} on={on} /></div> : null}
      {[...number].length <= 5 ? <span className="ln-tab" aria-hidden="true">{number}</span> : null}
    </div>
  );
}

type Place = { eid: string; label: string; at: number };
const PLACES = 'law.places';
const KEPT = 60;

function places(): Record<string, Place> {
  try {
    return JSON.parse(localStorage.getItem(PLACES) ?? '{}') as Record<string, Place>;
  } catch {
    return {};
  }
}

/** Where the reader stopped in a text (N9): the last article at the top of the screen, kept on this device only
 *  (never sent), for the sixty texts read last. Kept once the reader has scrolled, so opening a text at its top does
 *  not forget the place before it can be offered. A text of one article has no place to keep. And when a search led
 *  here (?hl=), its words are lit in the law. */
export function KeepPlace({ path, articles, returning, known, reach, onBack }: {
  path: string; articles: ArticleItem[]; returning: boolean; known: boolean; reach: (eid: string) => Promise<void>;
  onBack: () => void;
}) {
  const { pathname, search, key } = useLocation();
  const hl = new URLSearchParams(search).get('hl')?.trim() ?? '';
  // A law page restores its place itself, so the browser does not (its scroll, put back before the window was drawn,
  // landed past the window's end).
  useEffect(() => {
    history.scrollRestoration = 'manual';
    return () => { history.scrollRestoration = 'auto'; };
  }, []);
  const focus = pathname.startsWith(`${path}/`) ? pathname.slice(path.length + 1) : null;
  return (
    <>
      {/* One per history entry (RD21 of the readers review, 9 Nov 2026): an article the law names opens on this same
          page, and back from it found the place of the first entry only, read when the page was mounted. */}
      <Entry key={key} at={key} address={pathname} path={path} articles={articles} returning={returning} known={known} reach={reach} onBack={onBack} />
      {hl ? <Suspense fallback={null}><SearchMarks textPath={path} hl={hl} focus={focus} /></Suspense> : null}
    </>
  );
}

/** The article put where it stood on the screen, and held there while the page settles under it: the articles above
 *  are drawn only as they near the screen (content-visibility) and take their real height then, and on a page loaded
 *  anew (a reload, a phone that had dropped the tab) the text's head and the lines under the articles arrive after the
 *  law's words (858 px too low on a phone's reload). The page is moved by this alone meanwhile: the browser's own
 *  anchoring is set aside, so that one change is not answered twice. For three seconds at most, never once the reader
 *  touches the page, and not past this history entry (the returned function ends it). */
function hold({ eid, dy }: Kept): () => void {
  const root = document.documentElement;
  const put = () => {
    const el = document.getElementById(eid);
    if (!el) return;
    // Drawn whole, whatever the browser draws ahead of the screen: skipped above it, it would keep a guessed height,
    // and the articles after it would stand that much off.
    el.style.contentVisibility = 'visible';
    const off = Math.round(el.getBoundingClientRect().top - dy);
    if (off) window.scrollBy(0, off);
  };
  root.style.overflowAnchor = 'none';
  put();
  const watch = new ResizeObserver(put);
  watch.observe(document.body);
  const acts = ['wheel', 'touchstart', 'pointerdown', 'keydown'];
  let on = true;
  const stop = () => {
    if (!on) return;
    on = false;
    watch.disconnect();
    root.style.overflowAnchor = '';
    for (const a of acts) window.removeEventListener(a, stop, true);
  };
  for (const a of acts) window.addEventListener(a, stop, { capture: true, passive: true });
  window.setTimeout(stop, 3000);
  return stop;
}

/** One history entry's stay in a law: its place written as the reader scrolls, and put back when they come back. */
function Entry({ at, address, path, articles, returning, known, reach, onBack }: {
  /** The history entry's key and its address. */
  at: string; address: string;
  path: string; articles: ArticleItem[]; returning: boolean; known: boolean; reach: (eid: string) => Promise<void>;
  onBack: () => void;
}) {
  const { t } = useTranslation();
  const eids = useMemo(() => articles.map((a) => a.eid), [articles]);
  const [current, setCurrent] = useState('');
  const moved = useRef(false);
  // The article at the top of the screen, as the reading bar finds it (its own observer: this module loads apart).
  useEffect(() => {
    const seen = new Map<string, boolean>();
    const io = new IntersectionObserver((entries) => {
      for (const e of entries) seen.set(e.target.id, e.isIntersecting);
      const first = eids.find((id) => seen.get(id));
      if (first) setCurrent(first);
    }, { rootMargin: '-120px 0px -60% 0px' });
    for (const id of eids) { const el = document.getElementById(id); if (el) io.observe(el); }
    return () => io.disconnect();
  }, [eids]);
  // Back here: the article loaded around if it is not on the page, then the screen where it was.
  const [back, setBack] = useState(() => (returning ? keptBack(at) : null));
  const [asked, setAsked] = useState(false);
  const trying = useRef(false);
  const held = useRef<() => void>(undefined);
  useEffect(() => () => held.current?.(), []);
  useEffect(() => {
    if (!back || !known) return; // a long text's outline first: it says where the article is
    const el = document.getElementById(back.eid);
    if (el || asked) {
      if (el) held.current = hold(back);
      setBack(null);
      onBack();
    } else if (!trying.current) {
      trying.current = true;
      void reach(back.eid).finally(() => setAsked(true));
    }
  }, [back, known, asked, eids, reach, onBack]);
  // This history entry's place (PX1 of the where-it-trips review): the article under the reading bar and how far down
  // the screen it stood, written when the entry opens (one never scrolled has its place too), as the reader scrolls,
  // and at a tap, which may be the link that leaves. Not before the place is put back.
  useEffect(() => {
    if (back) return;
    let timer = 0;
    const write = () => {
      window.clearTimeout(timer);
      timer = 0;
      const top = eids.map((id) => document.getElementById(id)).find((el) => el && el.getBoundingClientRect().bottom > 120);
      if (!top) return;
      try {
        sessionStorage.setItem(BACK + at, JSON.stringify({ path: address, eid: top.id, dy: Math.round(top.getBoundingClientRect().top) }));
      } catch { /* refused storage: back opens at the address's article, as before */ }
    };
    const on = () => { if (!timer) timer = window.setTimeout(write, 250); };
    write();
    window.addEventListener('scroll', on, { passive: true });
    window.addEventListener('click', write, true);
    return () => { window.removeEventListener('scroll', on); window.removeEventListener('click', write, true); window.clearTimeout(timer); };
  }, [eids, at, address, back]);
  useEffect(() => {
    const on = () => { moved.current = true; };
    window.addEventListener('scroll', on, { passive: true, once: true });
    return () => window.removeEventListener('scroll', on);
  }, []);
  useEffect(() => {
    const a = articles.find((x) => x.eid === current);
    if (!moved.current || !a || articles.length < 2) return;
    const all = places();
    all[path] = { eid: a.eid, label: articleName(a.label, t), at: Date.now() };
    const keep = Object.entries(all).sort((x, y) => y[1].at - x[1].at).slice(0, KEPT);
    try {
      localStorage.setItem(PLACES, JSON.stringify(Object.fromEntries(keep)));
    } catch { /* a full or refused storage: the place is simply not kept */ }
  }, [current, articles, path, t]);
  return null;
}

/** «كمل من المادة 84», under the title of a text reopened without an article in its address (N9). */
export function GoOn({ d, first }: { d: TextDetail; first: string }) {
  const { t } = useTranslation();
  // Read once, before this visit's scrolling writes the new place.
  const place = useMemo(() => places()[d.path] ?? null, [d.path]);
  if (!place || place.eid === first) return null;
  return (
    <Link to={`${d.path}/${place.eid}`} className="inline-flex min-h-11 items-center gap-2 self-start rounded-full bg-wash px-4 text-body font-medium text-stamp no-underline hover:bg-paper" data-noprint>
      <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
           strokeLinecap="round" strokeLinejoin="round"><path d="M6 4h12v16l-6-4-6 4V4Z" /></svg>
      {t('reading.goOn', { label: place.label })}
    </Link>
  );
}

/** An address names an article this text does not hold (PX20): an old link, a text cut again. Said above its first
 *  articles instead of opening at the top in silence. */
export function Missing({ eid }: { eid: string }) {
  const { t } = useTranslation();
  return (
    <p role="status" className="m-0 mt-4 rounded-control bg-wash px-4 py-3 text-body text-ink">
      {t('pages:landing.missing', { number: eid.replace(/^art_/, '').replace(/_/g, '-') })}
    </p>
  );
}

const ReadingLimit = lazy(() => import('../ReadingLimit'));


/** Articles that could not load (PX23): offline or an error, said where they would be, with a way to try again; the
 *  day's reading reached, said as such (4 Nov 2026). */
export function Failed({ retry }: { retry: () => void }) {
  const { t } = useTranslation();
  // Was it the day's reading? The server says (the failed load's error stays in the window's hook, at first load).
  const [code, setCode] = useState<'check' | 'limit' | null>(null);
  useEffect(() => {
    api<{ check: string; reached: boolean }>('/corpus/reading/')
      .then((r) => { if (r.reached) setCode(r.check ? 'check' : 'limit'); }).catch(() => {});
  }, []);
  if (code) return <Suspense fallback={null}><ReadingLimit code={code} retry={retry} /></Suspense>;
  return (
    <p role="alert" className="m-0 flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-rule-soft py-5 text-ink-soft">
      {t('pages:landing.failed')}
      <button type="button" onClick={retry} className="min-h-11 font-medium text-stamp underline underline-offset-4">{t('pages:landing.retry')}</button>
    </p>
  );
}
