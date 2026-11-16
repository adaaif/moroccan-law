import { useCallback, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import type { Mark } from '../corpus.api';
import { Floating } from './Popover';

// The pages' words come with the first meaning opened: this module also sets a line of leaders, which needs none of them.
let loading: Promise<unknown> | null = null;
const pages = () => (loading ??= import('@/shared/locales/pages'));

/** A word that opens the law, dotted in the people's saffron once its meaning was written and checked, and opened in
 *  place like a term the text defines (HM35 of the hard-moment review: a tap used to leave the article for a page
 *  holding a title and a list of other articles). The meaning is people's words, said so, never the law's. Loaded with
 *  the first article that holds such a word, or a line of leaders (`Leaders`, below). */
export default function WordNote({ words, m }: { words: string; m: Extract<Mark, { kind: 'word' }> }) {
  const { t, i18n } = useTranslation();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const [ready, setReady] = useState(false);
  const close = useCallback(() => setAnchor(null), []);
  const register = i18n.language === 'fr' && m.means.fr ? 'fr' : m.means.ar ? 'ar' : (Object.keys(m.means)[0] as keyof typeof m.means);
  return (
    <>
      <button type="button" aria-expanded={Boolean(anchor)} data-hit onClick={(e) => { setAnchor(anchor ? null : e.currentTarget); void pages().then(() => setReady(true)); }}
              className="cursor-pointer underline decoration-dotted decoration-1 underline-offset-[6px] decoration-people-fill text-inherit [font:inherit]">
        {words}
      </button>
      {anchor ? (
        <Floating anchor={anchor} onClose={close} label={t('words.whatIs', { word: words })}>
          <p lang="ar" dir="rtl" className="m-0 font-law text-law font-semibold text-people">{words}</p>
          <p lang={register === 'fr' ? 'fr' : 'ar'} dir="auto" className="m-0 mt-1 max-w-[36ch] text-body leading-relaxed">{m.means[register]}</p>
          {ready ? (
            <>
              <p className="m-0 mt-2 text-meta text-ink-soft">{t('pages:wordNote.told')}</p>
              <Link to={`/words/${m.slug}`} onClick={close} className="mt-2 inline-block text-meta">{t('pages:wordNote.page')}</Link>
            </>
          ) : null}
        </Floating>
      ) : null}
    </>
  );
}

/** A run of the dots a table of the Bulletin leads a label to its value with: «أقل من سنة ....... شهر واحد». */
const RUN = /\.{4,}|…{2,}/g;
/** Where a value ends and the next label begins, when the page set two rows on one line: «شهران؛ أكثر من 5 سنوات». */
const END = /[؛;]|\.(?=\s+\S)/;

/** Some of a line's words and where they start in it. */
type Part = { t: string; at: number };
type Row = { label: Part; dots: string; value: Part };

/** The words between `a` and `b`, without the spaces around them. */
const part = (text: string, a: number, b: number): Part => {
  const s = text.slice(a, b);
  return { t: s.trim(), at: a + s.length - s.trimStart().length };
};

/** A line of «label …… value» rows; null when its parts do not pair (two runs with no «؛» between them: the words are
 *  left as they are, the dots wrapping like any word). */
function rows(text: string): Row[] | null {
  const runs = [...text.matchAll(RUN)];
  const out: Row[] = [];
  let start = 0;
  for (const [i, run] of runs.entries()) {
    const from = run.index + run[0].length;
    let to = text.length;
    let next = to;
    if (i + 1 < runs.length) {
      const between = text.slice(from, runs[i + 1].index);
      const end = END.exec(between);
      if (!end) return null;
      to = next = from + end.index + 1;
    }
    out.push({ label: part(text, start, run.index), dots: run[0], value: part(text, from, to) });
    start = next;
  }
  return out.length ? out : null;
}

/** «label …… value» set as the Bulletin's tables set it, a row a line (HM14 of the hard-moment review): the label at
 *  the start, the value at the end, the printed dots between them as the leader, clipped to the room the line has (a run
 *  of 140 dots laid the 2027 bill's art. 7 out at 506 px on a 390 px phone; the notice decree's «شهران؛ أكثر من 5
 *  سنوات» stood on one line). The words and dots stay as printed. `words` draws a part with its marks (LawBody's
 *  Inline). Loaded with the first such line. */
export function Leaders({ text, at, words }: { text: string; at: number; words: (text: string, at: number) => ReactNode }) {
  const found = rows(text);
  if (!found) return <>{words(text, at)}</>;
  return (
    <>
      {found.map((r, i) => (
        <span key={i} className="flex items-end gap-x-1.5">
          {r.label.t ? <span className="min-w-0">{words(r.label.t, at + r.label.at)}</span> : null}
          <span aria-hidden="true" className="flex-1 overflow-hidden whitespace-nowrap text-ink-soft" style={{ minWidth: '1.5em' }}>{r.dots}</span>
          {r.value.t ? <span style={{ maxWidth: '62%' }}>{words(r.value.t, at + r.value.at)}</span> : null}
        </span>
      ))}
    </>
  );
}
