import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import '@/shared/locales/pages';
import { api } from '@/shared/services/api';
import { useDismiss } from '@/shared/components/dismiss';
import { useSettled, type Segment } from '@/features/search/search.api';
import type { OutlineEntry } from '../corpus.api';
import { AR, DIVISION, articleName, splitLabel } from '../format';
import { icon, useGoTo } from './navigation';

/* Finding one's way in a long text (P10–P12 of the polish review): the words searched inside it, its outline with each
   article's first words and its parts folded, and a jump by number. The phone opens them from the reading bar, as
   panels; a desk keeps them in the side column while it reads. */

type Found = { query: string; count: number; together?: number; articles: { eid: string; label: string; path: string; together?: boolean; snippet: Segment[] }[] };

/** «ابحث في هذا النص»: the articles that hold every word, those holding them side by side as typed first, then the
 *  text's order, two lines each; a tap goes there with the words lit and lands on the first (HM33 of
 *  the hard-moment review: «السكن الاجتماعي» opened the tax code's art. 6, which holds neither side by side, at its top). */
export function FindInText({ textPath, initial = '', autoFocus = false, onGo, onQuery }: {
  textPath: string;
  initial?: string;
  autoFocus?: boolean;
  onGo?: () => void;
  /** Told whether words are typed: the desk shows the outline again when they are cleared. */
  onQuery?: (typed: boolean) => void;
}) {
  const { t } = useTranslation();
  const goTo = useGoTo(textPath);
  const [q, setQ] = useState(initial);
  const settled = useSettled(q.trim(), 250);
  const found = useQuery({
    queryKey: ['findIn', textPath, settled],
    queryFn: () => api<Found>(`/search/in/?path=${encodeURIComponent(textPath)}&q=${encodeURIComponent(settled)}`),
    enabled: settled.length > 1,
    staleTime: 300_000,
  });
  useEffect(() => onQuery?.(settled.length > 1), [settled, onQuery]);
  const d = settled.length > 1 ? found.data : undefined;
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2">
      <form role="search" onSubmit={(e) => e.preventDefault()}
            className="flex h-12 items-center gap-2 rounded-control border border-field bg-sheet px-3 focus-within:border-stamp">
        <SearchIcon />
        <label htmlFor={`find-${textPath}`} className="sr-only">{t('reading.find')}</label>
        <input id={`find-${textPath}`} type="search" dir="auto" autoFocus={autoFocus} value={q} enterKeyHint="search"
               placeholder={t('reading.find')} onChange={(e) => setQ(e.target.value)}
               className="h-full min-w-0 flex-1 bg-transparent text-body text-ink outline-none placeholder:text-ink-soft" />
        {q ? (
          <button type="button" aria-label={t('search.clear')} onClick={() => setQ('')}
                  className="grid size-11 shrink-0 place-items-center rounded-full text-ink-soft hover:bg-wash hover:text-ink">
            <svg {...icon} width={16} height={16}><path d="M6 6l12 12M18 6 6 18" /></svg>
          </button>
        ) : null}
      </form>
      {d ? (
        <>
          <p role="status" className="m-0 px-1 text-meta text-ink-soft">
            {t('pages:reading.found', { count: d.count, q: d.query })}
            {d.together && d.together < d.count ? `${t('corpus.listSep')}${t('pages:reading.together', { count: d.together })}` : ''}
          </p>
          <ol className="m-0 min-h-0 flex-1 list-none overflow-y-auto overscroll-contain p-0">
            {d.articles.map((a) => (
              <li key={a.eid}>
                <button type="button" onClick={() => { goTo(a.eid, `?hl=${encodeURIComponent(a.together ? `«${d.query}»` : d.query)}`); onGo?.(); }}
                        className="flex w-full flex-col gap-0.5 rounded-control px-3 py-2.5 text-start hover:bg-paper">
                  <span {...AR} className="text-body font-bold text-stamp">{articleName(a.label, t)}</span>
                  <span {...AR} className="line-clamp-2 font-law text-lead leading-snug text-ink"><Snippet s={a.snippet} /></span>
                </button>
              </li>
            ))}
          </ol>
        </>
      ) : found.isError && settled.length > 1 ? <p role="status" className="m-0 px-1 text-meta text-repealed">{t('pages:reading.findFailed')}</p> : null}
    </div>
  );
}

function Snippet({ s }: { s: Segment[] }) {
  return <>{s.map((x, i) => x.hit ? <mark key={i} className="rounded-sm bg-wash px-0.5 text-ink">{x.t}</mark> : <span key={i}>{x.t}</span>)}</>;
}

/** «اذهب إلى المادة»: an article by its number, «5» for «المادة 5» (and «5 مكرر» after it). */
export function JumpField({ articles, textPath, onGo }: { articles: OutlineEntry[]; textPath: string; onGo?: () => void }) {
  const { t } = useTranslation();
  const goTo = useGoTo(textPath);
  const [value, setValue] = useState('');
  const [missing, setMissing] = useState(false);
  const go = () => {
    const n = value.trim().replace(/[٠-٩]/g, (d) => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d)));
    const a = articles.find((x) => x.number === n) ?? articles.find((x) => x.number.startsWith(`${n}-`));
    setMissing(!a);
    if (a) {
      goTo(a.eid);
      setValue('');
      onGo?.();
    }
  };
  const id = `jump-${textPath}`;
  return (
    <form className="flex flex-col gap-1" onSubmit={(e) => { e.preventDefault(); go(); }}>
      <div className="flex items-center gap-2">
        {/* The code's own word (HM31 of the hard-moment review): «الفصل» in the DOC or the penal code. */}
        <label htmlFor={id} className="shrink-0 text-meta text-ink-soft">
          {t('reading.jumpTo', { word: /^الفصل/.test(articles[0]?.label ?? '') ? 'الفصل' : 'المادة' })}
        </label>
        <input id={id} inputMode="numeric" value={value} placeholder={t('reading.jumpPlaceholder')}
               onChange={(e) => { setValue(e.target.value); setMissing(false); }}
               aria-invalid={missing} aria-describedby={missing ? `${id}-missing` : undefined}
               className={`h-11 w-20 min-w-0 flex-1 rounded-control border bg-sheet px-3 text-ink ${missing ? 'border-repealed' : 'border-field'}`} />
        <button type="submit" className="h-11 shrink-0 rounded-control bg-stamp px-4 font-medium text-on-stamp hover:bg-stamp-deep">
          {t('reading.go')}
        </button>
      </div>
      {missing ? <p id={`${id}-missing`} role="status" className="m-0 text-meta text-repealed">{t('reading.jumpNotFound')}</p> : null}
    </form>
  );
}

type Part = { key: string; title: string | null; first: string; last: string; rows: { a: OutlineEntry; sub: string | null }[] };

// How deep a division sits, from its first word: a «فرع» under a «باب», a «Section» under a «Chapitre».
const DEPTH: Record<string, number> = { الكتاب: 0, Livre: 0, Partie: 0, القسم: 1, Titre: 1, الجزء: 2, الباب: 3, Chapitre: 3,
                                        الفصل: 4, الفرع: 5, Section: 5, المبحث: 6, الشطر: 6 };
const depth = (h: string) => DEPTH[h.trim().split(/\s/)[0]] ?? 9;

/** The text's parts in order: each top division with its articles and the division nearest each one. A heading
 *  that is no division (the end of a title, a line of an article cut off by a reading) makes no part; a path a
 *  reading left short (none, or only a «فرع») continues the part before it. */
function partsOf(articles: OutlineEntry[]): Part[] {
  const parts: Part[] = [];
  let lastSub: string | null = null;
  for (const a of articles) {
    const divisions = a.heading_path.filter((h) => DIVISION.test(h.trim()));
    const open = parts[parts.length - 1]?.title ?? null;
    const under = open !== null && (!divisions.length || depth(divisions[0]) > depth(open));
    const top = under ? open : divisions[0] ?? null;
    const lower = under ? divisions : divisions.slice(1);
    const near: string | null = lower.length ? lower[lower.length - 1] : under ? lastSub : null;
    let part = parts[parts.length - 1];
    if (!part || part.title !== top) {
      part = { key: `${parts.length}-${a.eid}`, title: top, first: a.label, last: a.label, rows: [] };
      parts.push(part);
      lastSub = null;
    }
    part.last = a.label;
    part.rows.push({ a, sub: near !== lastSub ? near : null });
    lastSub = near;
  }
  return parts;
}

/** The outline (P12): each article with its first words, the parts folded but the current one, each with the range
 *  of its articles («المواد 5-11», a hyphen-minus so that right to left it still reads 5 to 11). */
export function OutlineTree({ articles, textPath, current, onGo }: {
  articles: OutlineEntry[];
  textPath: string;
  current: string;
  onGo?: () => void;
}) {
  const { t } = useTranslation();
  const goTo = useGoTo(textPath);
  const parts = partsOf(articles);
  const here = parts.find((p) => p.rows.some((r) => r.a.eid === current))?.key ?? parts[0]?.key;
  const [open, setOpen] = useState<Set<string>>(() => new Set(here ? [here] : []));
  useEffect(() => {
    if (here) setOpen((o) => (o.has(here) ? o : new Set(o).add(here)));
  }, [here]);
  // The current article a third of the way down the outline's own scroll, the page left where it is; again once its
  // part has opened (a law opened on its art. 570 had its part still folded when it first looked, and stayed at art. 1).
  const shown = here !== undefined && open.has(here);
  useEffect(() => {
    const el = document.getElementById(`outline-${current}`);
    const box = el?.closest<HTMLElement>('[data-scroll]');
    if (el && box) box.scrollTo({ top: el.getBoundingClientRect().top - box.getBoundingClientRect().top + box.scrollTop - box.clientHeight / 3 });
  }, [current, shown]);
  const toggle = (key: string) => setOpen((o) => {
    const next = new Set(o);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    return next;
  });
  const range = (p: Part) => {
    const [from, to] = [splitLabel(p.first)[1], splitLabel(p.last)[1]];
    return from === to ? t('pages:reading.rangeOne', { from }) : t('pages:reading.range', { from, to });
  };
  const rows = (p: Part) => p.rows.map(({ a, sub }) => (
    <li key={a.eid} id={`outline-${a.eid}`}>
      {sub ? <p {...AR} className="m-0 px-3 pb-1 pt-3 text-meta font-medium text-ink-soft">{sub}</p> : null}
      <button type="button" onClick={() => { goTo(a.eid); onGo?.(); }} aria-current={a.eid === current ? 'location' : undefined}
              className={`flex w-full flex-col rounded-control px-3 py-2 text-start ${a.eid === current ? 'bg-wash' : 'hover:bg-paper'}`}>
        <span {...AR} className={`text-body font-semibold ${a.eid === current ? 'text-stamp' : 'text-ink'}`}>{articleName(a.label, t)}</span>
        {a.w ? <span {...AR} className="line-clamp-2 text-meta text-ink-soft">{a.w}</span> : null}
      </button>
    </li>
  ));
  return (
    <ol {...AR} className="m-0 list-none p-0">
      {parts.map((p) => p.title === null ? rows(p) : (
        <li key={p.key} className="border-b border-rule-soft last:border-b-0">
          <button type="button" onClick={() => toggle(p.key)} aria-expanded={open.has(p.key)}
                  className="flex min-h-12 w-full items-center gap-2 px-3 py-2 text-start hover:bg-paper">
            <Fold open={open.has(p.key)} />
            <span className="min-w-0 flex-1 text-body font-semibold leading-snug">{p.title}</span>
            <span className="shrink-0 text-meta text-ink-soft">{range(p)}</span>
          </button>
          {open.has(p.key) ? <ol className="m-0 list-none p-0 pb-2 ps-4 motion-safe:animate-[fade-in_160ms_ease-out]">{rows(p)}</ol> : null}
        </li>
      ))}
    </ol>
  );
}

/** A panel over the page, from its side (the outline, the search in the text): Escape or the scrim closes it. */
export function Drawer({ label, onClose, children }: { label: string; onClose: () => void; children: React.ReactNode }) {
  const { t } = useTranslation();
  useDismiss(onClose);
  // At the end of the page: the bar's backdrop blur would otherwise hold a fixed panel inside the bar.
  return createPortal(
    <div className="fixed inset-0 z-50 flex justify-end bg-scrim/40 motion-safe:animate-[fade-in_160ms_ease-out]" onClick={onClose}>
      <section role="dialog" aria-modal="true" aria-label={label} onClick={(e) => e.stopPropagation()}
               className="flex h-full w-full max-w-sm flex-col bg-sheet shadow-xl [--panel-from:24px] motion-safe:animate-[panel-in-start_200ms_ease-out] rtl:[--panel-from:-24px]">
        <div className="flex items-center justify-between border-b border-rule px-5 py-3">
          <h2 className="m-0 text-body font-semibold">{label}</h2>
          <button type="button" onClick={onClose} className="min-h-11 rounded-control px-3 text-meta hover:bg-paper">{t('reading.close')}</button>
        </div>
        {children}
      </section>
    </div>,
    document.body,
  );
}

export const SearchIcon = () => <svg {...icon} className="shrink-0 text-ink-soft"><path d="m10.5 17.5a7 7 0 1 1 0-14 7 7 0 0 1 0 14zM15.5 15.5 20 20" /></svg>;
const Fold = ({ open }: { open: boolean }) => (
  <svg {...icon} width={16} height={16} className={`shrink-0 text-ink-soft transition-transform motion-reduce:transition-none ${open ? '' : 'ltr:-rotate-90 rtl:rotate-90'}`}>
    <path d="m6 9 6 6 6-6" />
  </svg>
);
