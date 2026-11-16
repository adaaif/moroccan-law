import { useContext, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArticlePeek } from '../../../kit/tool/parts';
import { article, type Cite } from '../engine';
import { OLD_BOOK, citeLabel, codePath, useT } from '../strings';
import { RulesContext, inBook } from './rules';

const CHIP = 'inline-flex min-h-11 items-center rounded-full bg-wash px-3 text-meta font-semibold text-stamp no-underline hover:bg-stamp hover:text-on-stamp';

/** The articles a line rests on, each a mark that opens the article over the tool: the family is not lost by reading
 *  the law (IR16), and the mark names the paragraph (IR20). One sheet for the lot. A death before 2004 cites the 1958
 *  book (IR27), whose marks open the Bulletin that printed it. `cites` are the engine's, already in the numbers of the
 *  book it counted by; `today` are a screen's own, written in today's numbers and said here in the book's. */
export default function Cites({ cites = [], today = [], className = '' }: { cites?: Cite[]; today?: Cite[]; className?: string }) {
  const { t } = useT();
  const code = useContext(RulesContext);
  const old = code === '1958';
  const [open, setOpen] = useState<number | null>(null);
  const seen = new Set<string>();
  const unique = [...cites, ...inBook(code, today)].filter((c) => { const k = String(c); if (seen.has(k)) return false; seen.add(k); return true; });
  if (!unique.length) return null;
  return (
    <span className={`flex flex-wrap gap-1.5 ${className}`}>
      {unique.map((c) => (old
        ? <Link key={String(c)} to={OLD_BOOK} className={CHIP}>{citeLabel(c, t, true)}</Link>
        : <button key={String(c)} type="button" onClick={() => setOpen(article(c))} className={CHIP}>{citeLabel(c, t)}</button>
      ))}
      {open !== null ? <ArticlePeek path={codePath(open)} onClose={() => setOpen(null)} /> : null}
    </span>
  );
}
