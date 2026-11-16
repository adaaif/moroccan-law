import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { AR } from '@/features/corpus/format';
import { Stamp } from '@/features/corpus/article/Stamp';
import { usePreview } from '@/features/corpus/corpus.api';
import { textName } from '@/features/corpus/names';
import { openArticle, warmArticle } from '@/features/corpus/reading/open';
import { useVoice, speak } from '@/features/corpus/article/speech';
import { Sheet } from '@/shared/components/Sheet';
import { useKitT } from '../api';
import { useTween } from '../motion';
import { dayWords } from './days';
import { noteUse } from '../use';
import { whatsapp, here } from '../share';
import { daysAgo, todayIso } from '@/shared/services/today';

/** The parts every topic tool is built from (F1–F4, F9 of the road tools review): the answer on top, days as chips,
 *  the article behind a figure one tap away, the answer read aloud. A tool's own page lays them out. */

/** The answer a tool is for, on top of the tool and in view on a phone while the reader changes the inputs below
 *  (F1): a line over the figure, the figure itself counting to its new value, the lines under it. Once its own place
 *  has scrolled away on a phone it folds to one line held at the top (A14 of the road-signposted review: the card kept
 *  150 to 175 px of the screen and covered the dial); a tap brings the whole card back. The figure is ink: the
 *  topic's colour measures, it does not answer (A13). */
export function AnswerCard({ over, value, format, under, children, tone = 'stamp', share = false }: {
  over?: ReactNode;
  /** A number counts to its new value; anything else is shown as it is. */
  value: number | ReactNode;
  format?: (n: number) => string;
  under?: ReactNode;
  children?: ReactNode;
  tone?: 'stamp' | 'warn' | 'good';
  /** «إرسال في واتساب» under the card (HM5 of the hard-moment review): the tool's question, what the card says
   *  as the reader sees it, and the link that keeps their inputs. For the tools without a message of their own. */
  share?: boolean;
}) {
  const { t } = useKitT();
  const card = useRef<HTMLElement>(null);
  const look = tone === 'warn' ? 'bg-amended-wash' : tone === 'good' ? 'bg-[color-mix(in_srgb,var(--color-in-force)_10%,var(--color-sheet))]' : 'bg-wash';
  const after = useRef<HTMLDivElement>(null);
  const [folded, setFolded] = useState(false);
  useEffect(() => {
    const el = after.current;
    if (!el || typeof IntersectionObserver === 'undefined') return;
    const phone = window.matchMedia('(max-width: 639px)');
    const io = new IntersectionObserver(([e]) => setFolded(phone.matches && !e.isIntersecting && e.boundingClientRect.top < 0));
    io.observe(el);
    return () => io.disconnect();
  }, []);
  // The tool's first result for the reader (the analytics review): what the card says changed after they answered.
  // The card is drawn from the opening, with an example or a prompt, so its first words are no result.
  const said = useRef<string | null>(null);
  useEffect(() => {
    const now = card.current?.textContent ?? '';
    if (said.current !== null && now !== said.current) noteUse('result');
    said.current = now;
  });
  const figure = typeof value === 'number' ? <Counted value={value} format={format} /> : value;
  // What a screen reader hears (HM30 of the hard-moment review): the final figure once, from a hidden copy. The
  // card itself was the live region, and one tap on «+» read 46 changes as the figure counted to its new value.
  const final = typeof value === 'number' ? (format ? format(value) : value) : value;
  return (
    <>
      <section ref={card} data-answer
               className={`z-20 -mx-1 flex flex-col gap-1 rounded-card px-5 py-4 sm:static sm:shadow-none lg:sticky lg:top-6 lg:mx-0 ${look} ${folded ? 'static' : 'sticky top-0 shadow-[0_6px_18px_-14px_var(--color-scrim)]'}`}>
        {over ? <p className="m-0 text-body text-ink-soft">{over}</p> : null}
        <p className="m-0 text-h2 font-bold leading-tight text-ink tabular-nums"><span aria-hidden="true">{figure}</span><span className="sr-only" aria-live="polite">{final}</span></p>
        {under ? <div className="text-body">{under}</div> : null}
        {children}
      </section>
      <div ref={after} aria-hidden="true" className="-mt-5 h-0" />
      {share ? (
        <button type="button" className="-mt-2 inline-flex min-h-11 items-center self-start px-1 text-body font-medium text-stamp"
                onClick={() => {
                  // The card as the reader sees it, without the hidden copy of its figure that a screen reader hears.
                  let seen = card.current?.innerText ?? '';
                  for (const x of card.current?.querySelectorAll('.sr-only') ?? []) seen = seen.replace(x.textContent ?? '', '');
                  whatsapp([document.title.split(' — ')[0], ...seen.split('\n').map((l) => l.trim()).filter(Boolean), here()].join('\n'));
                }}>
          {t('share')}
        </button>
      ) : null}
      {folded ? (
        <button type="button" onClick={() => after.current?.previousElementSibling?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
                className={`fixed inset-x-0 top-0 z-30 flex min-h-13 items-center gap-3 px-4 pt-[env(safe-area-inset-top,0px)] text-start shadow-[0_6px_18px_-12px_var(--color-scrim)] motion-safe:animate-[fade-in_150ms_ease-out] sm:hidden ${look}`}>
          <span className="text-lead font-bold text-ink tabular-nums">{figure}</span>
          {over ? <span className="min-w-0 flex-1 truncate text-meta text-ink-soft">{over}</span> : null}
          <span aria-hidden="true" className="text-ink-soft">⌃</span>
        </button>
      ) : null}
    </>
  );
}

function Counted({ value, format }: { value: number; format?: (n: number) => string }) {
  const n = useTween(value);
  return <>{format ? format(n) : n}</>;
}

/** A choice among a few, as large chips (F2, F3): one pressed at a time. */
export function Chips<K extends string | number>({ label, options, value, onChange, className = '' }: {
  label?: string;
  options: { key: K; label: ReactNode; hint?: string }[];
  value: K;
  onChange: (k: K) => void;
  className?: string;
}) {
  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      {label ? <span className="text-body font-semibold">{label}</span> : null}
      <div role="radiogroup" aria-label={label} className="flex flex-wrap gap-2">
        {options.map((o) => (
          <button key={String(o.key)} type="button" role="radio" aria-checked={o.key === value} title={o.hint}
                  onClick={() => { if (o.key !== value) noteUse('answered'); onChange(o.key); }}
                  className={`min-h-11 rounded-full border px-4 text-body transition-[background-color,border-color,transform] duration-150 active:scale-[.97] motion-reduce:transition-none ${
                    o.key === value ? 'border-ink bg-ink font-semibold text-sheet' : 'border-field bg-sheet text-ink'}`}>
            {o.label}
          </button>
        ))}
      </div>
    </div>
  );
}

const back = daysAgo;

/** A day as the reader says it (F3): today, yesterday, two days ago, or another day on the phone's own picker; the
 *  day chosen in words under it. */
export function DayChips({ label, value, onChange, ago = [0, 1, 2] }: {
  label: string;
  value: string;
  onChange: (day: string) => void;
  ago?: number[];
}) {
  const { t, i18n } = useKitT();
  const quick = ago.map((n) => ({ key: back(n), n }));
  const other = !quick.some((q) => q.key === value);
  const [picking, setPicking] = useState(false);
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-body font-semibold">{label}</span>
      <div className="flex flex-wrap gap-2">
        {quick.map((q) => (
          <button key={q.key} type="button" aria-pressed={q.key === value} onClick={() => { setPicking(false); if (q.key !== value) noteUse('answered'); onChange(q.key); }}
                  className={`min-h-11 rounded-full border px-4 text-body ${q.key === value ? 'border-ink bg-ink font-semibold text-sheet' : 'border-field bg-sheet'}`}>
            {/* Not by plural alone: French counts 0 as «one», and today read «Hier». */}
            {q.n === 0 ? t('tool.today') : q.n === 1 ? t('tool.yesterday') : t('tool.daysAgo', { count: q.n })}
          </button>
        ))}
        <button type="button" aria-pressed={other} onClick={() => setPicking(true)}
                className={`min-h-11 rounded-full border px-4 text-body ${other ? 'border-ink bg-ink font-semibold text-sheet' : 'border-field bg-sheet'}`}>
          {t('tool.otherDay')}
        </button>
      </div>
      {picking || other ? (
        <input type="date" value={value} max={todayIso()} aria-label={label} dir="ltr"
               onChange={(e) => { if (e.target.value) { noteUse('answered'); onChange(e.target.value); } }}
               className="h-12 w-full max-w-64 rounded-control border border-field bg-sheet px-3 text-body" />
      ) : null}
      <span className="text-meta text-ink-soft">{dayWords(value, i18n.language)}</span>
    </div>
  );
}

/** An article as a small mark beside the figure it gives (F4): a tap opens the article over the tool. */
export function SourceMark({ path, label }: { path: string; label: string }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setOpen(true)} lang="ar" dir="rtl"
              className="inline-flex min-h-11 items-center rounded-full bg-wash px-2.5 text-meta text-stamp hover:bg-stamp hover:text-on-stamp">
        {label}
      </button>
      {open ? <ArticlePeek path={path} onClose={() => setOpen(false)} /> : null}
    </>
  );
}

/** Every article a result rests on, folded behind one line (F4): «على أي مواد؟ · 6». */
export function SourceFold({ paths, label }: { paths: string[]; label: (path: string) => string }) {
  const { t } = useKitT();
  const [open, setOpen] = useState(false);
  const unique = [...new Set(paths)];
  return (
    <div className="flex flex-col gap-2">
      <button type="button" aria-expanded={open} onClick={() => setOpen(!open)}
              className="inline-flex min-h-11 items-center gap-1.5 self-start text-body font-medium text-stamp">
        {t('tool.sources', { count: unique.length })}
        <span aria-hidden="true" className={`transition-transform motion-reduce:transition-none ${open ? 'rotate-180' : ''}`}>⌄</span>
      </button>
      {open ? (
        <span className="flex flex-wrap gap-1.5">
          {unique.map((p) => <SourceMark key={p} path={p} label={label(p)} />)}
        </span>
      ) : null}
    </div>
  );
}

/** The article itself, over the tool, so the reader keeps the place: its words, its printed page, a way to it. */
export function ArticlePeek({ path, onClose }: { path: string; onClose: () => void }) {
  const { t, i18n } = useKitT();
  const q = usePreview(path);
  const p = q.data;
  const navigate = useNavigate();
  const qc = useQueryClient();
  const label = useRef<HTMLSpanElement>(null);
  const warm = () => warmArticle(qc, path);
  return (
    <Sheet centered label={p?.label ?? t('tool.article')} onClose={onClose}>
      <div className="flex flex-col gap-3">
        <div className="flex items-start justify-between gap-3">
          <h2 {...AR} className="m-0 text-lead font-bold">{p ? <><span ref={label}>{p.label ?? ''}</span> · {textName(p.text, i18n.language, 80)}</> : '…'}</h2>
          <button type="button" onClick={onClose} className="min-h-11 shrink-0 px-2 text-body text-ink-soft">{t('tool.close')}</button>
        </div>
        {q.isLoading ? <p className="m-0 text-body text-ink-soft">…</p> : null}
        {p ? (
          <>
            <p {...AR} className="m-0 whitespace-pre-line border-s-[3px] border-stamp-line ps-4 font-law text-law">{p.excerpt}</p>
            <Stamp issue={p.issue} page={p.page} consolidated={Boolean(p.consolidation)} />
            {/* Its label flies to the article's number, where the article lands lit (reading/open.ts). */}
            <Link to={path} onPointerEnter={warm} onPointerDown={warm} onFocus={warm}
                  onClick={(e) => { if (e.metaKey || e.ctrlKey || e.shiftKey) return; e.preventDefault(); openArticle(navigate, path, label.current, onClose); }}
                  className="inline-flex min-h-11 items-center self-start text-body font-medium">{t('tool.openArticle')}</Link>
          </>
        ) : null}
        {q.isError ? <p className="m-0 text-body text-ink-soft">{t('tool.offlineArticle')}</p> : null}
      </div>
    </Sheet>
  );
}

/** «سمع»: the answer in the phone's own voice (F9; nothing is sent). Hidden on a phone that has no voice. */
export function Listen({ text, lang }: { text: string; lang: 'ar' | 'fr' }) {
  const { t } = useKitT();
  const voice = useVoice(lang);
  const [stop, setStop] = useState<(() => void) | null>(null);
  if (!voice) return null;
  return (
    <button type="button" aria-pressed={Boolean(stop)}
            onClick={() => { if (stop) stop(); else { noteUse('listen'); setStop(() => speak(text, voice, () => setStop(null))); } }}
            className="inline-flex min-h-11 items-center gap-1.5 rounded-full border border-field bg-sheet px-4 text-body">
      <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <path d="M4 10v4h4l5 4V6L8 10z" /><path d={stop ? 'M17 9v6M20 9v6' : 'M16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12'} />
      </svg>
      {t(stop ? 'tool.stop' : 'tool.listen')}
    </button>
  );
}
