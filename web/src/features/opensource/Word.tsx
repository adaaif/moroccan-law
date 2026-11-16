import { useCallback, useEffect, useLayoutEffect, useReducer, useRef, useState, type RefObject } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Stamp } from '@/features/corpus/article/Stamp';
import { issueNo, longDate } from '@/features/corpus/format';
import { count } from '@/features/budget/money';
import { Skeleton } from '@/shared/components/ui';
import { tick } from '@/shared/services/motion';
import { answer, nextWord, notList, readKept, remember, sideOf, slots, START, step, wantsWord, type Kept, type Pending,
  type Says, type Word as Asked } from './words';
import './locales/open';

/** The device's count of answers and the ids it has seen (`localStorage`, in try/catch: the page works without it). */
const KEPT = 'law.open.words';
const readStore = (): Kept => {
  try { return readKept(localStorage.getItem(KEPT)); } catch { return readKept(null); }
};
const writeStore = (k: Kept) => {
  try { localStorage.setItem(KEPT, JSON.stringify(k)); } catch { /* a private window: this visit only */ }
};

/**
 * The one thing on /open-source that works: a doubtful word as the printed line it stands on, its two readings, and a
 * press for the one the page prints. A press sends the answer and shows the next word at once (it was asked for while
 * this one was read); the answer counts on this device once the server has it. The sheet keeps its height from word to
 * word, and holds it for the lines that say there is none, a pause, or no connection (a press on those tries again).
 * Nothing is read from the device while the server draws the page.
 */
export default function Word() {
  const { t, i18n } = useTranslation('open');
  const lang = i18n.language;
  const [s, dispatch] = useReducer(step, START);
  const [kept] = useState<Kept | null>(() => (typeof window === 'undefined' ? null : readStore()));
  const seen = useRef<number[]>(kept?.seen ?? []);
  const mine = useRef(kept?.mine ?? 0);
  const [shownMine, setShownMine] = useState(mine.current);
  const [thanks, setThanks] = useState(false);
  const thanksTimer = useRef<number | undefined>(undefined);
  const [hold, setHold] = useState(0);
  const [loaded, setLoaded] = useState<number | null>(null);
  const sheet = useRef<HTMLElement>(null);
  const body = useRef<HTMLDivElement>(null);
  const keys = useRef<HTMLDivElement>(null);
  const inView = useRef(false);

  // Ask for a word when one is wanted: the one for the sheet, or the one after it. Not on the server (`kept` is null
  // there): a word asked while drawing would be the same for everyone.
  useEffect(() => {
    if (!kept || !wantsWord(s)) return;
    dispatch({ type: 'asked' });
    void nextWord(notList(seen.current, [s.word?.id, s.next?.id])).then((asked) => dispatch({ type: 'got', asked }));
  }, [kept, s]);

  // The next word's strip comes while this one is read: the press then shows it whole.
  useEffect(() => {
    if (s.next) new Image().src = s.next.strip.url;
  }, [s.next]);

  // The sheet never shrinks between words: it keeps the tallest height a word gave it.
  useLayoutEffect(() => {
    if (s.phase === 'word' && body.current) setHold((h) => Math.max(h, body.current?.offsetHeight ?? 0));
  }, [s.phase, s.word?.id]);

  useEffect(() => () => window.clearTimeout(thanksTimer.current), []);

  const send = useCallback(async (p: Pending) => {
    const sent = await answer(p.id, p.says);
    if (sent === 'ok') {
      mine.current += 1;
      writeStore({ mine: mine.current, seen: seen.current });
      setShownMine(mine.current);
      setThanks(true);
      window.clearTimeout(thanksTimer.current);
      thanksTimer.current = window.setTimeout(() => setThanks(false), 1400);
    } else if (sent !== 'gone') {
      dispatch({ type: 'unsent', answer: p, why: sent });
    }
  }, []);

  const press = useCallback((says: Says) => {
    const w = s.word;
    if (!w || s.phase !== 'word') return;
    seen.current = remember(seen.current, w.id);
    writeStore({ mine: mine.current, seen: seen.current });
    tick();
    dispatch({ type: 'pressed' });
    void send({ id: w.id, says });
  }, [s.word, s.phase, send]);

  const again = () => {
    const pending = s.retry;
    dispatch({ type: 'again' });
    for (const p of pending) void send(p);
  };

  // A desk's arrows choose the key on their side, while the sheet is in view and no field has focus.
  useEffect(() => {
    const el = sheet.current;
    if (!el || typeof IntersectionObserver === 'undefined') return;
    const seenBy = new IntersectionObserver(([e]) => { inView.current = e.isIntersecting; }, { threshold: 0.4 });
    seenBy.observe(el);
    return () => seenBy.disconnect();
  }, []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // A key held down answers once, not a word at each repeat; Alt with an arrow is the browser's back.
      if (e.repeat || e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey || e.shiftKey || !inView.current || !keys.current) return;
      const focus = document.activeElement as HTMLElement | null;
      if (focus && (/^(INPUT|TEXTAREA|SELECT)$/.test(focus.tagName) || focus.isContentEditable)) return;
      const side = sideOf(e.key, getComputedStyle(keys.current).direction === 'rtl' ? 'rtl' : 'ltr');
      const reading = side === null ? undefined : s.word?.readings[side];
      if (!reading) return;
      e.preventDefault();
      press(reading.key);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [press, s.word]);

  const w = s.phase === 'word' ? s.word : null;
  return (
    <section id="word" ref={sheet} className="os-word" aria-labelledby="os-word-title">
      <div className="os-word-head">
        <h2 id="os-word-title">{t('word.title')}</h2>
        <span className="os-mine" data-thanks={thanks ? '' : undefined} aria-live="polite">
          {thanks ? t('word.thanks') : shownMine ? <Filled text={t('word.mine', { skipInterpolation: true })} values={{ count: count(shownMine, lang) }} /> : null}
        </span>
      </div>
      {t('word.arabic') ? <p className="os-note">{t('word.arabic')}</p> : null}
      <div ref={body} className="os-body" style={hold ? { minHeight: hold } : undefined} aria-busy={s.phase === 'loading'}>
        {w ? <Shown w={w} loaded={loaded === w.id} onLoaded={() => setLoaded(w.id)} press={press} keys={keys} />
          : s.phase === 'loading' ? <Waiting />
          : s.phase === 'none' ? <p className="os-state">{t('word.none')}</p>
          : <button type="button" className="os-state os-again" onClick={again}>{t(`word.${s.phase}`)}</button>}
      </div>
    </section>
  );
}

/** A word on the sheet: the printed line, the line as read with a blank for the word, the two readings, the two other
 *  answers, and its source. */
function Shown({ w, loaded, onLoaded, press, keys }: {
  w: Asked;
  loaded: boolean;
  onLoaded: () => void;
  press: (says: Says) => void;
  keys: RefObject<HTMLDivElement | null>;
}) {
  const { t, i18n } = useTranslation('open');
  const { strip, source } = w;
  const lang = source.language === 'fr' ? 'fr' : 'ar';
  const dir = lang === 'ar' ? 'rtl' : 'ltr';
  return (
    <>
      <div className="os-strip" style={{ aspectRatio: `${strip.width} / ${strip.height}` }}>
        <img key={w.id} src={strip.url} width={strip.width} height={strip.height} alt={t('word.alt')} decoding="async"
             data-in={loaded ? '' : undefined} onLoad={onLoaded} onError={onLoaded} />
        {/* The strip holds three printed lines: the word's own is named by a bar at each edge, and the word by a rule
            under it. Nothing covers a letter. */}
        {strip.line ? (
          <span className="os-here" aria-hidden="true" style={{ top: `${strip.line.y * 100}%`, height: `${strip.line.h * 100}%` }}>
            {strip.mark ? <i style={{ left: `${strip.mark.x * 100}%`, width: `${strip.mark.w * 100}%` }} /> : null}
          </span>
        ) : null}
      </div>
      {/* A word placed before its line was kept: its place across the strip, under it. */}
      <div className="os-mark" aria-hidden="true">
        {strip.mark && !strip.line ? <i style={{ left: `${strip.mark.x * 100}%`, width: `${strip.mark.w * 100}%` }} /> : null}
      </div>
      <p className="os-line" lang={lang} dir={dir}>
        {w.before}{w.before ? ' ' : null}<span className="os-blank"><span className="sr-only">…</span></span>{w.after ? ' ' : null}{w.after}
      </p>
      <div ref={keys} className="os-keys">
        {w.readings.map((r) => (
          <button key={r.key} type="button" lang={lang} dir={dir} className="os-key" onClick={() => press(r.key)}>{r.text}</button>
        ))}
      </div>
      <p className="os-hint">{t('word.keys')}</p>
      <div className="os-also">
        <button type="button" onClick={() => press('neither')}>{t('word.neither')}</button>
        <button type="button" onClick={() => press('unclear')}>{t('word.unclear')}</button>
      </div>
      <div className="os-source">
        <Stamp issue={source.issue ? issueNo(source.issue, (k) => i18n.t(k)) : null} page={source.page} />
        {source.issue ? <span className="os-date">{longDate(source.issue.date, i18n.language)}</span> : null}
        <Link to={`/pages/${source.document_id}/${source.page_index}`} className="os-page">{t('word.page')}</Link>
      </div>
    </>
  );
}

/** The sheet while its first word comes: quiet, in the shapes it will hold (their sizes in opensource.css: a class
 *  of the shared stylesheet used here alone would weigh on every first visit). */
function Waiting() {
  const { t } = useTranslation('open');
  return (
    <>
      <div className="os-strip" style={{ aspectRatio: '640 / 150' }} />
      <div className="os-mark" />
      <div className="os-line"><Skeleton className="os-sk-line" /></div>
      <div className="os-keys"><Skeleton className="os-sk-key" /><Skeleton className="os-sk-key" /></div>
      <p className="os-hint">{t('word.keys')}</p>
      <div className="os-also"><Skeleton className="os-sk-also" /><Skeleton className="os-sk-also" /></div>
      <div className="os-source"><Skeleton className="os-sk-source" /></div>
    </>
  );
}

/** A sentence with its {{names}} filled, each value set as the page sets a figure; «…» until it has come, so the
 *  sentence never jumps. */
export function Filled({ text, values }: { text: string; values: Record<string, string | undefined> }) {
  return <>{slots(text).map((p, i) => (typeof p === 'string' ? p : <b key={i} className="os-n">{values[p.name] ?? '…'}</b>))}</>;
}
