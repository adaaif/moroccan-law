import { memo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Sheet } from '@/shared/components/Sheet';
import { Stamp } from '../article/Stamp';
import { AR, longDate } from '../format';
import { CardContext, useOpenCard } from './card';
import { state, useBookCard, useNum, type Book, type Branch } from './library.api';
import '@/shared/locales/pages';

/** Holds the card's sheet for the index and the box (LB6). */
export function CardHost({ children }: { children: React.ReactNode }) {
  const [book, setBook] = useState<Book | null>(null);
  return (
    <CardContext.Provider value={setBook}>
      {children}
      {book ? <CardSheet book={book} onClose={() => setBook(null)} /> : null}
    </CardContext.Provider>
  );
}

/** How thick a bound code stands on its shelf, from its articles: three thicknesses, as on a real shelf. */
const thick = (articles: number) => (articles > 600 ? 3 : articles > 250 ? 2 : 1);

/** A branch's general code, bound: its name on the cloth of its branch, its number at the foot, the spine on the side a
 *  book of that language is bound on. It opens the code. */
function Cover({ book, lang, hit }: { book: Book; lang: 'ar' | 'fr'; hit: boolean }) {
  const foot = book.number || book.version?.from.slice(0, 4) || '';
  const inside = <><span className="t">{book.name[lang]}</span>{foot ? <span className="n"><bdi dir="ltr">{foot}</bdi></span> : null}</>;
  const props = { className: `lb-cover${hit ? ' hit' : ''}`, lang, 'data-thick': thick(book.articles) };
  return book.path ? <Link to={book.path} {...props}>{inside}</Link> : <span {...props}>{inside}</span>;
}

/** The codes and core laws as nine shelves (15 Nov 2026, drawn again: the index of 10 Nov was a wall of
 *  small lines): each branch is led by its general code as a bound book in the branch's cloth, the branch's other
 *  laws beside it as names alone, every one in view on a phone as on a desk. The people's dozen stand first on their
 *  shelves. A text's number, its size and what a reader will read («محيَّن إلى 2026», «كما نُشر سنة 2018») are kept off
 *  the lines until `detail` is on; then each line's facts open its card. */
export const Shelves = memo(function Shelves({ branches, most = [], hits, detail = false }: {
  branches: Branch[]; most?: string[]; hits?: Set<string> | null; detail?: boolean;
}) {
  const { t, i18n } = useTranslation();
  const num = useNum();
  const open = useOpenCard();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const stale = branches.some((b) => b.books.some((x) => x.stale));
  const rank = (x: Book) => { const i = most.indexOf(x.key); return i < 0 ? most.length : i; };
  const line = (x: Book) => {
    const name = x.name[lang];
    const mark = x.stale ? <i aria-label={t('pages:lib4.index.stale')}>●</i> : null;
    // Its number and what a reader will read; a text with no number says its size instead. The card has the rest.
    const facts = <>{x.number ? <bdi dir="ltr">{x.number}</bdi> : t('pages:lib2.articlesN', { count: x.articles, n: num(x.articles) })}
      {state(x, t) ? <>{t('corpus.listSep')}{state(x, t)}</> : null}{x.stale ? <>{t('corpus.listSep')}<i>{t('pages:lib4.index.stale')}</i></> : null}</>;
    return (
      <li key={x.key} className={hits?.has(x.key) ? 'hit' : undefined}>
        {x.path ? <Link to={x.path} lang={lang}>{name}{mark}</Link> : <span lang={lang}>{name}{mark}</span>}
        {detail ? (open ? <button type="button" onClick={() => open(x)} aria-label={t('pages:lib3.card.of', { name })}>{facts}</button> : <small>{facts}</small>) : null}
      </li>
    );
  };
  return (
    <>
      <div className="lb-shelves">
        {branches.map((b) => {
          // The book that leads the shelf: the branch's general code, or the one people ask for most where it has none.
          const sorted = [...b.books].sort((x, y) => Number(y.base) - Number(x.base) || rank(x) - rank(y));
          const [head, ...rest] = sorted;
          return (
            <section key={b.key} id={`branch-${b.key}`} className="lb-shelf" data-branch={b.key} aria-labelledby={`branch-${b.key}-h`}>
              <h3 id={`branch-${b.key}-h`}><span>{b.name[lang]}</span><small>{t('pages:lib2.textsN', { count: b.books.length, n: num(b.books.length) })}</small></h3>
              <div>
                {head ? <Cover book={head} lang={lang} hit={!!hits?.has(head.key)} /> : null}
                <ul>
                  {detail && head ? line(head) : null}
                  {rest.map(line)}
                  {b.replaced.map((g) => (
                    <li key={g.path} className="old"><Link to={g.path} lang={lang}>{t('pages:lib5.before', { name: g.name[lang], years: g.years })}</Link></li>
                  ))}
                </ul>
              </div>
            </section>
          );
        })}
      </div>
      {stale ? <p className="lb-stalenote"><i>●</i> {t('pages:lib4.index.staleNote')}</p> : null}
    </>
  );
});

const COMPILER = ['adala', 'sgg', 'dgi', 'machine'];

/** A book's card (LB6): how courts cite it, where it was first printed, what a reader will read and up to when, its
 *  newest change with its issue, its French, its parts each opening the code there. */
function CardSheet({ book, onClose }: { book: Book; onClose: () => void }) {
  const { t, i18n } = useTranslation();
  const num = useNum();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const q = useBookCard(book.path);
  const d = q.data;
  const [copied, setCopied] = useState(false);
  const name = book.name[lang];
  const day = (iso: string | null | undefined) => longDate(iso, i18n.language);
  const v = d?.version ?? (book.version ? { ...book.version, as_of: null } : null);
  const copy = (text: string, el: HTMLElement | null) => {
    const done = () => { setCopied(true); window.setTimeout(() => setCopied(false), 1600); };
    const pick = () => { if (!el) return; const r = document.createRange(); r.selectNodeContents(el); const s = getSelection(); s?.removeAllRanges(); s?.addRange(r); };
    if (navigator.clipboard?.writeText) navigator.clipboard.writeText(text).then(done, pick); else pick();
  };
  return (
    <Sheet label={t('pages:lib3.card.of', { name })} onClose={onClose} centered closeButton half>
      <div className="lb-card">
        <h2 lang={lang}>{name}</h2>
        <p className="formal">
          {book.type ? `${t(`corpus.types.${book.type}`)} ${book.number}${t('corpus.listSep')}` : ''}
          {t('pages:lib2.articlesN', { count: book.articles, n: num(book.articles) })}
          {d?.parts.length ? ` ${t('pages:lib3.card.inParts', { count: d.parts.length, n: num(d.parts.length) })}` : ''}
        </p>
        {d?.issue ? <Stamp issue={`${d.issue.number}${d.issue.suffix ? ` ${t(`corpus.suffix.${d.issue.suffix}`)}` : ''}`} page={d.page}
                           to={`/bo/general_ar/${d.issue.key}`} /> : null}
        <dl className="facts">
          {v ? (
            <div><dt>{t('pages:lib3.card.reads')}</dt>
              <dd>{v.kind === 'as_published' ? t('pages:lib3.cur.printed', { year: v.from.slice(0, 4) })
                : t('pages:lib3.card.consolidated', { who: t(`pages:lib3.compiler.${COMPILER.includes(v.kind) ? v.kind : 'machine'}`), date: day(v.as_of ?? v.from) })}</dd></div>
          ) : null}
          <div><dt>{t('pages:lib3.card.last')}</dt>
            <dd>{d?.last ? (
              <>{d.last.path ? <Link to={d.last.path}>{d.last.type ? t(`corpus.types.${d.last.type}`) : ''} {d.last.number}</Link>
                : `${d.last.type ? t(`corpus.types.${d.last.type}`) : ''} ${d.last.number}`}
                {d.last.issue ? `${t('corpus.listSep')}${t('pages:lib3.card.issue', { n: d.last.issue.number + (d.last.issue.bis ? ` ${t('corpus.suffix.bis')}` : '') })}` : ''}
                {`${t('corpus.listSep')}${day(d.last.on)}`}
                {d.changes > 1 ? <span className="more">{t('pages:lib3.card.changes', { count: d.changes, n: num(d.changes) })}</span> : null}</>
            ) : q.isLoading ? '…' : t('pages:lib3.card.none')}</dd></div>
          {book.stale && book.last_change ? <div className="warn"><dt>{t('pages:lib3.card.mind')}</dt><dd>{t('pages:lib3.card.stale', { date: day(book.last_change) })}</dd></div> : null}
          {d?.french ? <div><dt>{t('pages:lib3.card.french')}</dt>
            <dd>{t(d.french.to ? 'pages:lib3.card.frenchTo' : 'pages:lib3.card.frenchAs', { n: d.french.issue, date: day(d.french.to ?? d.french.date) })}</dd></div> : null}
        </dl>
        {d?.parts.length ? (
          <>
            <h3>{t('pages:lib3.card.parts')}</h3>
            <ol className="parts">
              {d.parts.map((p) => (
                <li key={p.eid}><Link to={`${book.path}/${p.eid}`}><span {...AR}>{p.heading}</span>
                  <small>{t('pages:lib2.articlesN', { count: p.articles, n: num(p.articles) })}</small></Link></li>
              ))}
            </ol>
          </>
        ) : null}
        {d?.citation ? (
          <>
            <h3>{t('pages:lib3.card.cite')}</h3>
            <blockquote {...AR} id="lb-cite">{d.citation}</blockquote>
          </>
        ) : null}
        <p className="acts">
          {book.path ? <Link to={book.path} className="lb-btn">{t('pages:lib3.card.read', { name })}</Link> : null}
          {d?.citation ? <button type="button" className="lb-btn q" onClick={() => copy(d.citation, document.getElementById('lb-cite'))}>
            {copied ? t('pages:lib3.card.copied') : t('pages:lib3.card.copy')}</button> : null}
          {book.extra ? <Link to={book.extra} className="lb-btn q">{t('pages:lib3.card.figures')}</Link> : null}
        </p>
      </div>
    </Sheet>
  );
}
