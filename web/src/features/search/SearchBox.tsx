import { useEffect, useId, useRef, useState, useTransition } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { primaryButton } from '@/shared/components/buttons';
import { AR, articleName } from '@/features/corpus/format';
import { shortName } from '@/features/corpus/article/message';
import { textName } from '@/features/corpus/names';
import { EXAMPLES, EXAMPLES_FR } from './examples';
import { askEarly, useSettled, useSuggest, type Resolved, type TextBrief } from './search.api';
import { loaders } from './loaders';

type Group = 'citation' | 'topics' | 'texts' | 'words' | 'recent' | 'try' | 'search';
type Option = { key: string; group: Group; path: string | null; query?: string; label: string; detail?: string; lang?: string };

const RECENT_KEY = 'law.searches';
const RECENT_MOST = 4;

/** The searches typed on this device, newest first: never sent anywhere. */
function recentSearches(): string[] {
  try {
    const kept = JSON.parse(localStorage.getItem(RECENT_KEY) ?? '[]');
    return Array.isArray(kept) ? kept.filter((x) => typeof x === 'string').slice(0, RECENT_MOST) : [];
  } catch {
    return [];
  }
}

function keep(q: string | null) {
  try {
    if (q === null) localStorage.removeItem(RECENT_KEY);
    else localStorage.setItem(RECENT_KEY, JSON.stringify([q, ...recentSearches().filter((x) => x !== q)].slice(0, RECENT_MOST)));
  } catch {
    /* a private window keeps nothing */
  }
}

/** The one search box (home, search page, a missing page): as you type, what a citation opens, then the topics and
 *  guides, the laws by everyday name and the word they open, one line each and six at most (P8 of the polish review);
 *  empty, the last searches on this device and two examples. Chosen with the arrows and Enter, or the words searched.
 *  A combobox (WAI-ARIA 1.2). */
export function SearchBox({ initial = '', big = false, autoFocus = false }: { initial?: string; big?: boolean; autoFocus?: boolean }) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const navigate = useNavigate();
  const client = useQueryClient();
  // The search page comes in a transition (the router's): the box stays, its bar running, until the page can show.
  const [going, start] = useTransition();
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  const [q, setQ] = useState(initial);
  // The search page keeps one box from question to question (PX25): it takes each new question's words.
  useEffect(() => setQ(initial), [initial]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [recent, setRecent] = useState<string[]>([]);
  const settled = useSettled(q.trim());
  const suggest = useSuggest(settled);
  const data = open && settled.length > 1 ? suggest.data : undefined;
  const pick = (both: { ar: string; fr: string }) => (lang === 'fr' && both.fr) || both.ar;

  const options: Option[] = [];
  if (!q.trim()) {
    for (const r of recent) options.push({ key: `r-${r}`, group: 'recent', path: null, query: r, label: r });
    for (const x of (lang === 'fr' ? EXAMPLES_FR : EXAMPLES).filter((e) => !recent.includes(e)).slice(0, 2))
      options.push({ key: `e-${x}`, group: 'try', path: null, query: x, label: x, lang: lang === 'fr' ? 'fr' : 'ar' });
  } else {
    for (const x of data?.finds ?? []) options.push({ key: `f-${x.path}`, group: 'citation', path: x.path, label: (lang === 'fr' && x.name.fr) || x.name.ar, detail: `${t(`corpus.types.${x.type}`)} ${x.number}` });
    for (const c of data?.citations ?? []) options.push(citationOption(c, t, lang));
    for (const x of data?.topics ?? []) options.push({ key: `p-${x.slug}`, group: 'topics', path: x.path, label: pick(x.name), detail: t('search.topic') });
    for (const x of data?.guides ?? []) options.push({ key: `g-${x.slug}`, group: 'topics', path: x.path, label: pick(x.title), detail: t('search.guide') });
    for (const x of data?.texts ?? []) options.push(textOption(x, t, lang));
    for (const x of data?.words ?? []) options.push({ key: `w-${x.slug}`, group: 'words', path: x.path, label: pick(x.term), detail: t('search.word') });
    options.push({ key: 'search', group: 'search', path: null, query: q.trim(), label: q.trim(), detail: t('search.searchAll') });
  }
  const shown = open && (q.trim() ? options.length > 1 : options.length > 0);

  const go = (o: Option | undefined) => {
    setOpen(false);
    const words = o ? o.query : q.trim();
    if (o?.path) navigate(o.path);
    else if (words) {
      keep(words);
      askEarly(client, words, lang);
      start(() => navigate(`/search?q=${encodeURIComponent(words)}`));
    }
  };

  return (
    <form
      role="search"
      aria-busy={going}
      className="relative"
      onSubmit={(e) => {
        e.preventDefault();
        go(active >= 0 ? options[active] : undefined);
      }}
    >
      <div className={`flex items-center gap-1 rounded-control border-2 border-ink bg-sheet p-1.5 ps-4 focus-within:border-stamp ${big ? 'h-16' : 'h-14'}`}>
        <label htmlFor={`${id}-q`} className="sr-only">{t('corpus.searchPlaceholder')}</label>
        <input
          ref={input}
          id={`${id}-q`}
          type="search"
          dir="auto"
          role="combobox"
          aria-expanded={shown}
          aria-controls={`${id}-list`}
          aria-activedescendant={active >= 0 ? `${id}-o${active}` : undefined}
          aria-autocomplete="list"
          autoComplete="off"
          enterKeyHint="search"
          autoFocus={autoFocus}
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setOpen(true);
            setActive(-1);
          }}
          onFocus={() => {
            setRecent(recentSearches());
            setOpen(true);
            void loaders.searchPage?.();
          }}
          onBlur={() => window.setTimeout(() => setOpen(false), 150)}
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown') {
              e.preventDefault();
              setOpen(true);
              setActive((a) => Math.min(a + 1, options.length - 1));
            } else if (e.key === 'ArrowUp') {
              e.preventDefault();
              setActive((a) => Math.max(a - 1, -1));
            } else if (e.key === 'Escape' && open) {
              // The suggestions first; the sheet the box sits in closes on the next Escape, its words kept (PX25).
              e.stopPropagation();
              e.preventDefault(); // a search field clears itself on Escape
              setOpen(false);
              setActive(-1);
            }
          }}
          placeholder={t('corpus.searchPlaceholder')}
          className="h-full min-w-0 flex-1 bg-transparent text-lead text-ink outline-none placeholder:text-ink-soft"
        />
        {q ? (
          <button type="button" aria-label={t('search.clear')} onClick={() => { setQ(''); setActive(-1); input.current?.focus(); }}
                  className="inline-flex size-11 shrink-0 items-center justify-center rounded-full text-ink-soft hover:bg-wash hover:text-ink">
            <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
              <path d="M6 6l12 12M18 6 6 18" />
            </svg>
          </button>
        ) : null}
        <button type="submit" className={`${primaryButton} max-sm:px-4`}>{t('corpus.search')}</button>
      </div>
      {/* From the tap until the search page shows (on 3G its code takes seconds): the box says it heard. */}
      {going ? <span aria-hidden="true" className="absolute inset-x-3 top-full mt-1.5 block h-1 rounded-full bg-stamp motion-safe:animate-pulse" /> : null}
      {shown ? (
        <ul id={`${id}-list`} role="listbox" aria-label={t('search.suggestions')}
            className="absolute inset-x-0 top-full z-30 m-0 mt-2 list-none overflow-hidden rounded-card border border-rule bg-sheet p-1.5 shadow-[0_12px_32px_-12px_rgba(30,27,58,0.35)] motion-safe:animate-[fade-in_120ms_ease-out]">
          {data?.repaired ? (
            <li role="presentation" className="px-3 pb-1 pt-2 text-meta text-ink-soft">
              {t('search.typedLatin')} <bdi {...AR} className="font-medium text-ink">{data.repaired}</bdi>
            </li>
          ) : null}
          {options.map((o, i) => (
            <Row key={o.key} o={o} i={i} id={id} active={i === active} first={i === 0 || options[i - 1].group !== o.group}
                 onChoose={() => go(o)} onHover={() => setActive(i)}
                 onForget={o.group === 'recent' ? () => { keep(null); setRecent([]); } : undefined} />
          ))}
        </ul>
      ) : null}
    </form>
  );
}

function Row({ o, i, id, active, first, onChoose, onHover, onForget }: {
  o: Option; i: number; id: string; active: boolean; first: boolean; onChoose: () => void; onHover: () => void; onForget?: () => void;
}) {
  const { t } = useTranslation();
  const headed = first && o.group !== 'citation' && o.group !== 'search';
  return (
    <>
      {headed ? (
        <li role="presentation" className="flex items-center gap-2 px-3 pb-0.5 pt-2.5 text-meta font-semibold text-ink-soft">
          {t(`search.groups.${o.group}`)}
          {onForget ? (
            <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={onForget}
                    className="ms-auto inline-flex min-h-11 items-center px-1 font-normal text-ink-soft underline-offset-4 hover:underline">
              {t('search.forget')}
            </button>
          ) : null}
        </li>
      ) : null}
      <li
        id={`${id}-o${i}`}
        role="option"
        aria-selected={active}
        onMouseDown={(e) => e.preventDefault()}
        onClick={onChoose}
        onMouseEnter={onHover}
        className={`flex min-h-11 cursor-pointer items-center gap-3 rounded-control px-3 py-2 ${active ? 'bg-wash' : ''} ${o.group === 'search' ? 'mt-1 border-t border-rule-soft' : ''}`}
      >
        <Glyph group={o.group} />
        {/* The row keeps the page's side, by its icon; the words inside keep their own direction. */}
        <span className={`min-w-0 flex-1 text-body leading-snug text-ink ${o.group === 'search' ? 'font-medium' : ''}`}>
          <bdi lang={o.lang}>{o.label}</bdi>
        </span>
        {o.detail ? <span className="shrink-0 text-meta text-ink-soft">{o.detail}</span> : null}
      </li>
    </>
  );
}

/** A small mark of what a row opens: a page for a law, a compass for a topic or guide, a clock for a past search. */
function Glyph({ group }: { group: Group }) {
  const d = {
    citation: 'M7 3h7l4 4v14H7zM14 3v4h4',
    texts: 'M7 3h7l4 4v14H7zM14 3v4h4',
    topics: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zm3.5 5.5-2 5-5 2 2-5z',
    words: 'M5 19 10 5h1l5 14M7 14h7',
    recent: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 7v5l3 2',
    try: 'm10.5 17.5a7 7 0 1 1 0-14 7 7 0 0 1 0 14zM15.5 15.5 20 20',
    search: 'm10.5 17.5a7 7 0 1 1 0-14 7 7 0 0 1 0 14zM15.5 15.5 20 20',
  }[group];
  return (
    <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
         strokeLinecap="round" strokeLinejoin="round" className="shrink-0 text-ink-soft">
      <path d={d} />
    </svg>
  );
}

function citationOption(c: Resolved, t: (k: string, o?: Record<string, unknown>) => string, lang: string): Option {
  const key = `c-${c.article?.path ?? c.citation.raw}`;      // a citation's completions share its words (B17)
  if (c.state === 'issue' && c.issue)
    return { key, group: 'citation', path: c.issue.path, label: t('search.issue', { key: c.issue.key }), detail: t('search.openIssue') };
  if (c.article && c.text)
    return { key, group: 'citation', path: c.article.path, label: `${articleName(c.article.label, t)} · ${textName(c.text, lang, 40)}`,
             // A famous article says the public's name for it (F7 of the famous-articles review): «490» → «العلاقات الرضائية».
             detail: (lang === 'fr' && c.known_as?.fr[0]) || c.known_as?.ar[0] || t('search.openArticle') };
  if (c.text)
    return { key, group: 'citation', path: c.text.path, label: textName(c.text, lang, 48),
             detail: c.state === 'text_only' ? t('search.articleMissing', { article: c.citation.article }) : t('search.openText') };
  return { key, group: 'citation', path: null, query: c.citation.raw, label: c.name?.ar ?? c.citation.raw, detail: t('search.notInCorpus') };
}

function textOption(x: TextBrief, t: (k: string) => string, lang: string): Option {
  const label = shortName(textName(x, lang, 34), 34);
  // «قانون الكراء» says «قانون 67.12» beside it; a title that holds its number says nothing more.
  const kind = x.number_as_printed && !label.includes(x.number_as_printed) ? `${t(`corpus.types.${x.type}`)} ${x.number_as_printed}` : undefined;
  return { key: `t-${x.path}`, group: 'texts', path: x.path, label, detail: x.in_corpus ? kind : t('search.notLoaded'),
           lang: lang === 'fr' && !x.name?.fr ? 'ar' : undefined };
}
