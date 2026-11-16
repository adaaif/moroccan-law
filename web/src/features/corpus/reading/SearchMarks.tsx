import { useQuery } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { api } from '@/shared/services/api';
import '@/shared/locales/pages';

type Found = { count: number; words: string[]; articles: { eid: string; label: string; path: string }[] };

const NAME = 'search-marks';
const NONE: string[] = [];

/** The search's mark, in the browser's own highlight (no element added to the law React draws): the snippets' mark, a
 *  shade deeper, the law's lines being wide apart. Written once, here: the stylesheet has no room (H2). */
function style() {
  if (document.getElementById(NAME)) return;
  const s = document.createElement('style');
  s.id = NAME;
  s.textContent = `::highlight(${NAME}){background-color:var(--color-stamp-line);color:var(--color-ink);text-decoration:underline 2px var(--color-stamp);text-underline-offset:4px}`;
  document.head.appendChild(s);
}

const escape = (w: string) => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/** The forms the text writes the words in, lit wherever the law shows them: a word whole, never inside another; words
 *  that were between quotes come as one form, lit whole, a line's end between them as good as a space. An article's
 *  words are its one `div` with a language (LawBody's, Arabic or French), never its label or its buttons. */
function paint(words: string[]): Range[] {
  const ranges: Range[] = [];
  if (!words.length) return ranges;
  const pattern = new RegExp(`(?<![\\p{L}\\p{M}])(?:${[...words].sort((a, b) => b.length - a.length).map((w) => escape(w).replace(/ /g, '\\s+')).join('|')})(?![\\p{L}\\p{M}])`, 'giu');
  for (const root of document.querySelectorAll('main article div[lang]')) {
    const walk = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    for (let node = walk.nextNode(); node; node = walk.nextNode()) {
      const text = node.nodeValue ?? '';
      for (const m of text.matchAll(pattern)) {
        const r = new Range();
        r.setStart(node, m.index);
        r.setEnd(node, m.index + m[0].length);
        ranges.push(r);
      }
    }
  }
  return ranges;
}

/** Where a search led (H1–H5 of the search's marks, 29 Oct 2026): the words searched (`hl`, after the question's own
 *  words were set aside and Darija spelled as the law spells it) lit in the law as the search matched them («كراء» lights
 *  «الكراء», «للكراء»), the reader landing on the first one, and a line to go from one article holding them to the next,
 *  or to put the marks away. An article found by meaning alone says so. Loaded only when a search led here. */
export default function SearchMarks({ textPath, hl, focus }: { textPath: string; hl: string; focus: string | null }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const found = useQuery({
    queryKey: ['marks', textPath, hl],
    queryFn: () => api<Found>(`/search/in/?path=${encodeURIComponent(textPath)}&q=${encodeURIComponent(hl)}&any=1`),
    staleTime: 10 * 60_000,
  });
  const words = found.data?.words ?? NONE;
  const landed = useRef(false);
  const [here, setHere] = useState<string | null>(focus);
  // ‹ › led to another article: land on its first mark, count from it.
  useEffect(() => { landed.current = false; setHere(focus); }, [focus]);

  // Painted now and again as the law's window grows; put away when the reader leaves or hides them.
  useEffect(() => {
    if (!words.length || typeof CSS === 'undefined' || !('highlights' in CSS)) return;
    style();
    let frame = 0;
    const again = () => {
      frame = 0;
      const ranges = paint(words);
      CSS.highlights.set(NAME, new Highlight(...ranges));
      // H4: on a long article, the first lit word rather than its top (once the article is on the page).
      const article = focus ? document.getElementById(focus) : null;
      if (!landed.current && ranges.length && (!focus || article)) {
        landed.current = true;
        const first = ranges.find((r) => !article || article.contains(r.startContainer));
        const box = first?.getBoundingClientRect();
        if (box && (box.top > window.innerHeight * 0.8 || box.top < 0)) {
          window.scrollBy({ top: box.top - window.innerHeight * 0.3, behavior: 'instant' as ScrollBehavior });
        }
      }
    };
    const soon = () => { if (!frame) frame = requestAnimationFrame(again); };
    soon();
    const watch = new MutationObserver(soon);
    const main = document.querySelector('main');
    if (main) watch.observe(main, { childList: true, subtree: true });
    return () => {
      watch.disconnect();
      if (frame) cancelAnimationFrame(frame);
      CSS.highlights.delete(NAME);
    };
  }, [words, focus]);

  // The article at the top of the screen, for ‹ ›.
  useEffect(() => {
    let frame = 0;
    const look = () => {
      frame = 0;
      const top = [...document.querySelectorAll<HTMLElement>('main article[id]')].find((el) => el.getBoundingClientRect().bottom > 120);
      if (top) setHere(top.id);
    };
    const soon = () => { if (!frame) frame = requestAnimationFrame(look); };
    window.addEventListener('scroll', soon, { passive: true });
    return () => { window.removeEventListener('scroll', soon); if (frame) cancelAnimationFrame(frame); };
  }, []);

  if (!found.data) return null;
  const list = found.data.articles;
  // ‹ › from the article at the top of the screen; from one that holds none of the words, the first that does.
  const at = list.findIndex((a) => a.eid === here);
  const after = at >= 0 ? list[at + 1] : list[0];
  const before = at > 0 ? list[at - 1] : undefined;
  const go = (to?: { eid: string }) => to && navigate(`${textPath}/${to.eid}?hl=${encodeURIComponent(hl)}`);
  const hide = () => navigate(focus ? `${textPath}/${focus}` : textPath, { replace: true });
  // H5: the article the search opened holds none of the words: it was found by its meaning.
  const byMeaning = Boolean(focus) && !list.some((a) => a.eid === focus);
  const button = 'grid size-11 shrink-0 place-items-center rounded-full text-ink hover:bg-paper disabled:opacity-40';
  return (
    // Above the phone's bottom bar, like a browser's find bar; its sizes as a style (no room in the stylesheet).
    <div role="region" aria-label={t('pages:marks.label')} data-noprint
         className="fixed mx-auto flex items-center gap-1 rounded-full border border-rule bg-sheet text-meta"
         style={{ bottom: 'calc(env(safe-area-inset-bottom, 0px) + 72px)', insetInline: 12, maxWidth: 576, zIndex: 40,
                  padding: '4px 4px 4px 0', paddingInlineStart: 16, boxShadow: '0 6px 24px rgb(0 0 0 / 0.14)' }}>
      {/* The words on one line, what this article holds of them on the next: neither cut off on a phone. */}
      <p className="m-0 flex min-w-0 flex-1 flex-col leading-snug">
        {byMeaning && !words.length ? t('pages:marks.meaning') : (
          <>
            <span className="truncate"><span className="text-ink-soft">{t('pages:marks.words')} </span><bdi dir="auto" className="font-semibold">{hl}</bdi></span>
            <span className="truncate text-ink-soft">{byMeaning ? t('pages:marks.notHere') : t('pages:marks.count', { count: found.data.count })}</span>
          </>
        )}
      </p>
      {list.length ? (
        <>
          <button type="button" onClick={() => go(before)} disabled={!before} aria-label={t('pages:marks.previous')} title={t('pages:marks.previous')} className={button}>
            <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className="ltr:rotate-180"><path d="m9 6 6 6-6 6" /></svg>
          </button>
          <button type="button" onClick={() => go(after)} disabled={!after} aria-label={t('pages:marks.next')} title={t('pages:marks.next')} className={button}>
            <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className="ltr:rotate-180"><path d="m15 6-6 6 6 6" /></svg>
          </button>
        </>
      ) : null}
      <button type="button" onClick={hide} className="h-11 shrink-0 rounded-full px-3 font-medium text-stamp hover:bg-paper">{t('pages:marks.hide')}</button>
    </div>
  );
}
