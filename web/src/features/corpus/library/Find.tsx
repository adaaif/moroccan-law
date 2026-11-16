import { useQueryClient } from '@tanstack/react-query';
import { useDeferredValue, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '@/shared/services/api';
import { buttonClass } from '@/shared/components/buttons';
import type { IssueDetail } from '../corpus.api';
import { AR, longDate } from '../format';
import { useOpenCard } from './card';
import { findQuery, span, state, useArchive, useFind, useLibrary, useNum, type Book, type Found, type FoundArticle, type FoundBrief, type FoundNote, type FoundText } from './library.api';
import type { Held } from './map';
import { issuesOn, read, type BookRef } from './read';
import '@/shared/locales/pages';

const EXAMPLES = {
  ar: [['ق.م.م'], ['المادة 16 من مدونة الأسرة'], ['ظهير 2 أكتوبر 1984'], ['ref', 'الجريدة الرسمية عدد 5167 بتاريخ 8 دجنبر 2003، ص. 3969'], ['43.20', '', 'wide'], ['قانون المالية 2019', '', 'wide'],
       ['ظهير 9 رمضان 1331', '', 'wide'], ['آخر عدد', '', 'wide']],
  fr: [['CPC'], ['article 16 du code de la famille'], ['dahir du 2 octobre 1984'], ['ref', 'B.O. n° 5167 du 8 décembre 2003'], ['43.20', '', 'wide'], ['loi de finances 2019', '', 'wide'],
       ['moudawana', '', 'wide'], ['le dernier BO', '', 'wide']],
} as const;

/** A line of the box's answer: what «فتح» may open when it is sure, and how it is drawn. */
type Line = { key: string; sure: boolean; to?: string; open?: () => void; node: React.ReactNode };

/** The library's box (LB2 of the every-code review; W1–W6, W9 and W10 of the library-search review). Whatever a reader
 *  knows of a text or an issue is read while they type: issues, days and the 67 books here at once, any other text on
 *  the server once they pause. The answer stands directly under the field, above a phone's keyboard; «فتح» opens a sure
 *  first answer and nothing else. `onBooks` hears the books it names, for the index to light them at leisure. */
export function Find({ id = 'library-find', onBooks, examples = true }: { id?: string; onBooks?: (keys: Set<string> | null) => void; examples?: boolean }) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const navigate = useNavigate();
  const num = useNum();
  const archive = useArchive().data ?? null;
  const library = useLibrary().data;
  const openCard = useOpenCard();
  const form = useRef<HTMLFormElement>(null);
  const [q, setQ] = useState('');
  const [unsure, setUnsure] = useState(false);
  const client = useQueryClient();
  const books = useMemo(() => new Map((library?.branches ?? []).flatMap((b) => b.books).filter((b) => b.path).map((b) => [b.key, b])), [library]);
  const refs = useMemo<BookRef[]>(() => [...books.values()].map((b) => ({ key: b.key, number: b.number, base: b.base, shelf: b.shelf,
                                                                       names: [b.name.ar, b.name.fr, ...b.aliases] })), [books]);
  const local = useMemo(() => read(q, archive, refs), [q, archive, refs]);
  // The server is asked once the reader pauses: one request for a word, not one a letter.
  const [asked, setAsked] = useState('');
  useEffect(() => {
    if (!local.ask) { setAsked(''); return undefined; }
    const timer = window.setTimeout(() => setAsked(local.query), 180);
    return () => window.clearTimeout(timer);
  }, [local.ask, local.query]);
  const found = useFind(asked);
  const server = local.ask && asked === local.query ? found.data : undefined;
  const waiting = local.ask && (asked !== local.query || found.isLoading);

  // An issue named with a page opens on that page: the issue's pages say which of its images bears the printed number.
  const openPage = async (issue: Held, page: number) => {
    try {
      const d = await api<IssueDetail>(`/corpus/issues/${issue.edition}/${issue.key}/`);
      const p = d.pages.find((x) => x.printed_number === page);
      navigate(p ? `/pages/${d.document_id}/${p.index}` : `/bo/${issue.edition}/${issue.key}`);
    } catch {
      navigate(`/bo/${issue.edition}/${issue.key}`);
    }
  };

  const day = (iso: string) => longDate(iso, i18n.language);
  const lines: Line[] = [];
  const und: { text: string; warn?: boolean }[] = [];
  const named = new Set<string>();
  const issueLine = (x: Held, key: string, sure: boolean, extra: React.ReactNode[] = [], go?: string, open?: () => void) =>
    lines.push({ key, sure, to: `/bo/${x.edition}/${x.key}`, open, node: <IssueAnswer x={x} lines={extra} go={go} /> });
  const bookLine = (b: Book, sure: boolean, why = '') => {
    named.add(b.key);
    lines.push({ key: `b:${b.key}`, sure, to: b.path!, node: <BookAnswer book={b} why={why} onCard={openCard ? () => openCard(b) : undefined} /> });
  };
  for (const r of local.readings) {
    if (r.kind === 'issue') {
      const n = r.number + (r.suffix ? ` ${t(`corpus.suffix.${r.suffix}`)}` : '');
      if (!local.readings.some((x) => x.kind === 'year')) und.push({ text: t(r.french ? 'pages:lib4.und.frenchIssue' : 'pages:lib4.und.issue', { n }) });
      if (r.claimed) und.push({ text: day(r.claimed.date) });
      if (r.page !== null) und.push({ text: t('pages:lib4.und.page', { n: r.page }) });
      if (r.french) {
        if (r.issue) issueLine(r.issue, 'fr', true, [<span key="f" className="ft">{t('pages:lib4.issue.frenchEdition')}</span>]);
        else lines.push({ key: 'fr-none', sure: false, node: <p className="lb-a note warn">{t('pages:lib4.issue.frenchMissing', { n })}{r.page !== null ? ` ${t('pages:lib4.issue.frenchPage', { page: r.page })}` : ''}</p> });
        if (r.arabic) issueLine(r.arabic, 'ar-same', false, [<span key="s" className="ft">{t('pages:lib4.issue.sameArabic')}{r.arabic.first && r.arabic.pages ? `${t('corpus.listSep')}${t('pages:lib4.issue.itsPages', { range: span(r.arabic.first, r.arabic.first + r.arabic.pages - 1) })}` : ''}</span>]);
        continue;
      }
      if (!r.issue) {
        lines.push({ key: 'none', sure: false, node: <p className="lb-a note warn">{t(`pages:lib3.issue.${r.nowhere ? 'nowhere' : r.past ? 'past' : 'missing'}`, { n })}</p> });
        continue;
      }
      const x = r.issue, extra: React.ReactNode[] = [];
      if (r.cover) extra.push(<span key="c" className="ft">{t('pages:lib3.issue.cover', { n: r.number, range: span(x.number, x.last) })}</span>);
      if (r.page !== null) {
        extra.push(r.pageOut ? <span key="p" className="warn">{t('pages:lib3.issue.pageOut', { page: r.page, from: x.first, to: x.first + x.pages - 1 })}</span>
          : r.pageAt ? <span key="p" className="ok">{t('pages:lib3.issue.pageAt', { page: r.page, at: r.pageAt, pages: x.pages })}</span>
            : <span key="p" className="ft">{t('pages:lib3.issue.pageFind', { page: r.page })}</span>);
      }
      if (r.claimed) extra.push(r.claimed.date === x.date ? <span key="d" className="ok">{t('pages:lib3.issue.dateOk')}</span>
        : <span key="d" className="warn">{t('pages:lib3.issue.dateOther', { was: day(x.date), said: day(r.claimed.date) })}</span>);
      const onPage = r.page !== null && !r.pageOut;
      issueLine(x, `i:${x.key}`, r.sure, extra, onPage ? t('pages:lib3.issue.openPage', { page: r.page }) : undefined, onPage ? () => void openPage(x, r.page!) : undefined);
    } else if (r.kind === 'newest') {
      und.push({ text: t('pages:lib4.und.newest') });
      r.issues.forEach((x, i) => issueLine(x, `n:${x.key}`, r.sure && i === 0));
    } else if (r.kind === 'day') {
      und.push({ text: day(r.day.date) });
      if (!r.exact.length) lines.push({ key: 'noday', sure: false, node: <p className="lb-a note">{t('pages:lib3.day.none', { day: day(r.day.date) })}</p> });
      r.exact.forEach((x) => issueLine(x, `d:${x.key}`, r.sure, [<span key="o" className="ft">{t('pages:lib4.issue.thatDay')}</span>]));
      r.before.forEach((x) => issueLine(x, `db:${x.key}`, false, [<span key="b" className="ft">{t('pages:lib3.day.before')}</span>]));
      r.after.forEach((x) => issueLine(x, `da:${x.key}`, false, [<span key="a" className="ft">{t('pages:lib3.day.after')}</span>]));
    } else if (r.kind === 'month' || r.kind === 'year') {
      const y = archive?.years.get(r.year);
      const said = r.kind === 'month'
        ? (r.issues.length ? t('pages:lib4.month.said', { issues: t('pages:lib2.issuesN', { count: r.issues.length, n: num(r.issues.length) }), range: span(r.issues[0].number, r.issues[r.issues.length - 1].number) }) : t('pages:lib4.month.none'))
        : y ? `${t('pages:lib2.issuesN', { count: y.ar.length, n: num(y.ar.length) })}${y.ar.length ? `${t('corpus.listSep')}${span(y.min, y.max)}` : ''}` : '';
      const name = r.kind === 'month' ? new Intl.DateTimeFormat(lang === 'fr' ? 'fr-MA' : 'ar-MA', { month: 'long', year: 'numeric', timeZone: 'UTC' }).format(Date.UTC(r.year, r.month - 1, 1)) : String(r.year);
      und.push({ text: r.kind === 'year' && local.readings.length > 1 ? t('pages:lib4.und.yearOrIssue', { n: r.year }) : name });
      lines.push({ key: `y:${r.year}:${r.kind}`, sure: r.sure, to: `/bo?year=${r.year}`, node: (
        <Link to={`/bo?year=${r.year}`} className="lb-a"><span className="k">{t(`pages:lib4.k.${r.kind}`)}</span>
          <span className="m"><b>{name}</b><small>{said}</small></span><span className="go">{t('pages:lib3.year.go')}</span></Link>) });
    } else if (r.kind === 'number') {
      und.push({ text: t(r.textKind === 'law' ? 'pages:lib4.und.law' : 'pages:lib4.und.numbered', { a: r.parts[0].value, year: r.year, kind: t(`pages:lib3.kind.${r.textKind}`) }) });
      r.books.forEach((k) => bookLine(books.get(k)!, r.sure));
    } else if (r.kind === 'books') {
      r.books.slice(0, 4).forEach((k, i) => bookLine(books.get(k)!, r.sure && i === 0));
    }
  }
  if (server) {
    const u = server.understood;
    if (u.read_as) und.push({ text: t('pages:lib4.und.readAs', { q: u.read_as }) });
    if (u.short) und.push({ text: t('pages:lib4.und.short') });
    if (u.finance) und.push({ text: t(u.bill ? 'pages:lib4.und.bill' : 'pages:lib4.und.finance', { year: u.finance }) });
    if (u.article) und.push({ text: t('pages:lib4.und.article', { n: u.article }) });
    if (u.promulgated_by) und.push({ text: t('pages:lib4.und.promulgated', { n: u.promulgated_by }) });
    if (u.day && !local.readings.length) {
      // A Hijri day with no kind beside it («18 جمادى الأولى 1448») is a day like any other: its issue, once the
      // server has said which day it is; the texts signed that day follow.
      const plain = !u.day.kind;
      und.push({ text: plain ? `${day(u.day.date)}${u.day.hijri ? ` · ${u.day.hijri}` : ''}`
        : `${t(`pages:lib3.kind.${u.day.kind === 'order' ? 'order' : u.day.kind}`)} ${t('pages:lib4.und.signed', { day: day(u.day.date) })}${u.day.hijri ? ` · ${u.day.hijri}` : ''}` });
      if (u.day.estimate) und.push({ text: t('pages:lib4.und.estimate'), warn: true });
      if (plain && archive) {
        const on = issuesOn(archive, u.day.date);
        const one = on.exact.length === 1 && !u.day.estimate && !server.answers.some((a) => a.kind !== 'note' && a.sure);
        if (!on.exact.length) lines.push({ key: 'noday', sure: false, node: <p className="lb-a note">{t('pages:lib3.day.none', { day: day(u.day.date) })}</p> });
        on.exact.forEach((x) => issueLine(x, `d:${x.key}`, one, [<span key="o" className="ft">{t('pages:lib4.issue.thatDay')}</span>]));
        on.before.forEach((x) => issueLine(x, `db:${x.key}`, false, [<span key="b" className="ft">{t('pages:lib3.day.before')}</span>]));
        on.after.forEach((x) => issueLine(x, `da:${x.key}`, false, [<span key="a" className="ft">{t('pages:lib3.day.after')}</span>]));
      }
    }
    if (u.year && u.kind) und.push({ text: t('pages:lib4.und.yearOf', { kind: t(`pages:lib3.kind.${u.kind}`), year: u.year }) });
    for (const a of server.answers) {
      if (a.kind === 'note') {
        lines.push({ key: `note:${a.code}`, sure: false, node: <Note a={a} /> });
        // No text read with that signing day (half of the 1910s' dahirs carry none): the issues that followed it,
        // where the Bulletin printed it, are one tap away (W4). Offered, never opened.
        if (a.code === 'no_text_that_day' && a.date && archive) {
          const on = issuesOn(archive, a.date);
          [...on.exact, ...on.after].slice(0, 2).forEach((x) => issueLine(x, `nf:${x.key}`, false, [<span key="f" className="ft">{t('pages:lib4.issue.followed')}</span>]));
        }
      }
      else if (a.kind === 'article') lines.push({ key: `a:${a.path}`, sure: a.sure, to: a.path, node: <ArticleAnswer a={a} books={books} /> });
      else if (a.kind === 'issue') {
        const held = archive?.byNumber.get(`${a.number}:${a.suffix}`);
        if (held) issueLine(held, `si:${held.key}`, a.sure);
      } else if (a.book && books.has(a.book)) {
        if (!named.has(a.book)) bookLine(books.get(a.book)!, a.sure && !lines.some((l) => l.sure), a.why === 'former' ? a.former : a.why);
      } else lines.push({ key: `t:${a.path}`, sure: a.sure && !lines.some((l) => l.sure), to: a.path, node: <TextAnswer a={a} /> });
    }
  }
  // A kind and a year («ظهير 1958 …»): after what was found, the year's own laws and dahirs are one line away (W8).
  const yearOf = server?.understood.year && server.understood.kind ? server.understood.year : 0;
  if (yearOf) lines.push({ key: `yt:${yearOf}`, sure: false, to: `/bo?year=${yearOf}&view=texts`, node: (
    <Link to={`/bo?year=${yearOf}&view=texts`} className="lb-a"><span className="k">{t('pages:lib4.k.year')}</span>
      <span className="m"><b>{yearOf}</b><small>{t('pages:lib4.bo.tabTexts')}</small></span><span className="go">{t('pages:lib3.year.go')}</span></Link>) });
  const shown = q.trim() !== '';
  const first = lines.find((l) => l.to || l.open);
  const offered = lines.filter((l) => l.to || l.open).length;
  const search = `/search?q=${encodeURIComponent(q.trim())}`;

  // The books it names light the index, after the answer is on screen: a letter never re-draws the page (W2).
  const key = [...named].join(',');
  const lit = useDeferredValue(key);
  useEffect(() => { onBooks?.(lit ? new Set(lit.split(',')) : null); }, [lit, onBooks]);

  const go = (line: Line) => { if (line.open) line.open(); else if (line.to) navigate(line.to); };
  const hesitate = () => { setUnsure(true); form.current?.querySelector<HTMLElement>('.lb-read a')?.focus(); };
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!shown) return;
    if (first?.sure) { go(first); return; }
    if (!local.ask) { if (offered) hesitate(); return; }
    // «فتح» pressed before the server answered: its answer is awaited (the same request, not a second one), then judged
    // as the lines would be: a sure first answer opens, a choice is left to the reader, nothing found goes to search.
    try {
      const answer: Found = server ?? await client.fetchQuery<Found>(findQuery(local.query));
      const found = answer.answers.find((a) => a.kind !== 'note');
      if (found?.sure && !offered) navigate(found.path);
      else if (found || offered) hesitate();
      else navigate(search);
    } catch {
      navigate(search);
    }
  };
  const rise = () => {
    // On a phone the field rises to the top of the screen, so its answer stands above the keyboard (W2).
    if (window.matchMedia('(max-width: 767px)').matches) form.current?.scrollIntoView({ block: 'start', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
  };
  return (
    <form ref={form} role="search" onSubmit={(e) => void submit(e)} className={`lb-find${shown ? ' typing' : ''}`} autoComplete="off">
      <label htmlFor={id}>{t('pages:lib4.find.label')}</label>
      <span className="row">
        <input id={id} type="search" value={q} onChange={(e) => { setQ(e.target.value); setUnsure(false); }} onFocus={rise} dir="auto" enterKeyHint="go"
               placeholder={t('pages:lib4.find.hint')} />
        <button type="submit" className={buttonClass('primary', 'px-5')}>{t('pages:lib3.find.open')}</button>
      </span>
      {und.length ? <p className="lb-und" aria-live="polite">{und.map((u, i) => <span key={i} className={u.warn ? 'warn' : undefined} {...(lang === 'ar' ? AR : {})}>{u.text}</span>)}</p> : null}
      <div className="lb-read" aria-live="polite">
        {lines.map((l) => <div key={l.key} className={`lb-line${l.sure && l === first ? ' sure' : ''}`}>{l.node}</div>)}
        {shown && waiting ? <p className="lb-a note">{t('pages:lib4.find.reading')}</p> : null}
        {shown && local.ask && !waiting && !first?.sure ? (
          <div className="lb-line"><Link to={search} className="lb-a"><span className="k">{t('pages:lib4.k.search')}</span>
            <span className="m"><small>{t('pages:lib4.find.search', { q: q.trim() })}</small></span><span className="go">{t('pages:lib3.search.go')}</span></Link></div>
        ) : null}
        {unsure && offered ? <p className="lb-a note" role="status">{t('pages:lib4.find.unsure')}</p> : null}
      </div>
      {examples ? (
        <span className="lb-eg" aria-label={t('pages:lib3.find.examples')}>
          {EXAMPLES[lang].map(([label, value, cls]) => {
            const typed = label === 'ref' ? value! : label;
            return <button key={typed} type="button" className={cls || undefined} onClick={() => { setQ(typed); setUnsure(false); }}><bdi>{label === 'ref' ? t('pages:lib3.find.reference') : label}</bdi></button>;
          })}
        </span>
      ) : null}
    </form>
  );
}

function kindWord(type: string, number: string, t: (k: string) => string): string {
  // A dahir bearing a law is filed as a law: it is called what its number says («ظهير بمثابة قانون»).
  return type === 'law' && /^1\.\d/.test(number) ? t('pages:lib4.k.dahirLaw') : t(`corpus.types.${type}`);
}

function Facts({ a }: { a: FoundBrief }) {
  const { t, i18n } = useTranslation();
  const parts = [a.number ? <bdi key="n" dir="ltr">{a.number}</bdi> : null,
    a.signed_on ? <span key="s">{t('pages:lib4.text.signed', { day: longDate(a.signed_on, i18n.language) })}</span> : null,
    a.status === 'repealed' ? <span key="r" className="gone">{t('pages:lib4.text.repealed')}</span> : a.status === 'partly_repealed' ? <span key="r">{t('pages:lib4.text.partly')}</span> : null,
    a.issue ? <span key="i" className="lb-stp">{t('pages:lib4.text.issue', { n: a.issue.number + (a.issue.suffix ? ` ${t(`corpus.suffix.${a.issue.suffix}`)}` : '') })}</span> : null].filter(Boolean);
  return <small>{parts.map((p, i) => <span key={i}>{i ? ' · ' : null}{p}</span>)}</small>;
}

/** A text outside the 67: what it is about, its number, the day it was signed, its issue. */
function TextAnswer({ a }: { a: FoundText }) {
  const { t, i18n } = useTranslation();
  const french = i18n.language === 'fr' && a.name.fr;
  const why = a.why === 'bill' ? t('pages:lib4.text.bill') : a.why === 'promulgated' ? t('pages:lib4.text.promulgated') : a.why === 'former' && a.former ? t(`pages:lib4.former.${a.former}`)
    : a.why === 'finance' ? '' : a.cited && a.cited >= 20 && a.why === 'day' ? t('pages:lib4.text.cited', { count: a.cited, n: a.cited }) : '';
  return (
    <Link to={a.path} className="lb-a"><span className="k">{kindWord(a.type, a.number, t)}</span>
      <span className="m"><b {...(french ? {} : AR)}>{french || a.subject || a.name.ar}</b><Facts a={a} />{why ? <small className={a.why === 'bill' ? 'warn' : undefined}>{why}</small> : null}</span>
      <span className="go">{t('pages:lib4.go.open')}</span></Link>
  );
}

/** An article of a text: the law opens at it. */
function ArticleAnswer({ a, books }: { a: FoundArticle; books: Map<string, Book> }) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const book = a.text.book ? books.get(a.text.book) : undefined;
  const name = book ? book.name[lang] : (lang === 'fr' && a.text.name.fr) || a.text.name.ar;
  const found = a.state === 'found';
  return (
    <Link to={a.path} className="lb-a"><span className="k">{t('pages:lib4.k.article')}</span>
      <span className="m"><b {...AR}>{found ? `${a.label} · ` : ''}{name}</b>
        <small className={found ? undefined : 'warn'}>{found ? t('pages:lib4.article.at') : t('pages:lib4.article.none', { n: a.asked })}</small></span>
      <span className="go">{t(found ? 'pages:lib4.go.openArticle' : 'pages:lib4.go.open')}</span></Link>
  );
}

/** One of the 67: its name, what a reader will read, and its card one tap away. */
function BookAnswer({ book, why, onCard }: { book: Book; why?: string; onCard?: () => void }) {
  const { t, i18n } = useTranslation();
  const num = useNum();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const said = why === 'short' ? '' : why === 'maybe' ? t('pages:lib4.text.maybe') : why && ['replaced', 'elsewhere', 'freedoms', 'courts'].includes(why) ? t(`pages:lib4.former.${why}`) : '';
  return (
    <div className="lb-bk">
      {/* The kind beside the name, unless the name begins with it («قانون المسطرة الجنائية» is not «قانون قانون …»). */}
      <Link to={book.path!} className="lb-a"><span className="k">{why === 'maybe' ? t('pages:lib4.k.maybe') : book.type && !book.name[lang].startsWith(t(`corpus.types.${book.type}`)) ? t(`corpus.types.${book.type}`) : ''}</span>
        <span className="m"><b lang={lang}>{book.name[lang]}</b>
          <small>{book.number ? <><bdi dir="ltr">{book.number}</bdi> · </> : null}{t('pages:lib2.articlesN', { count: book.articles, n: num(book.articles) })} · {state(book, t)}
            {book.stale ? <> · <span className="stale">{t('pages:lib4.index.stale')}</span></> : null}</small>
          {said ? <small>{said}</small> : null}</span>
        <span className="go">{t('pages:lib4.go.read')}</span></Link>
      {onCard ? <button type="button" className="card" onClick={onCard}>{t('pages:lib4.text.card')}</button> : null}
    </div>
  );
}

/** What the server found nothing for, or more than it shows: said, never guessed. */
function Note({ a }: { a: FoundNote }) {
  const { t, i18n } = useTranslation();
  const num = useNum();
  const day = a.date ? longDate(a.date, i18n.language) : '';
  const said = a.code === 'not_held' ? t(a.type ? 'pages:lib4.note.notHeldKind' : 'pages:lib4.note.notHeld', { n: a.number, kind: a.type ? t(`corpus.types.${a.type}`) : '' })
    : a.code === 'more_that_day' ? t('pages:lib4.note.moreThatDay', { count: a.n ?? 0, n: num(a.n ?? 0) })
      : t(`pages:lib4.note.${a.code}`, { day, year: a.year });
  return <p className={`lb-a note${a.code === 'not_held' ? ' warn' : ''}`}>{said}</p>;
}

/** An issue as an answer: its number, its day, what it holds. */
function IssueAnswer({ x, lines, go }: { x: Held; lines?: React.ReactNode[]; go?: string }) {
  const { t, i18n } = useTranslation();
  const num = useNum();
  const weekday = new Intl.DateTimeFormat(i18n.language === 'fr' ? 'fr-MA' : 'ar-MA', { weekday: 'long', timeZone: 'UTC' }).format(Date.parse(`${x.date}T00:00:00Z`));
  return (
    <Link to={`/bo/${x.edition}/${x.key}`} className="lb-a lb-issue"><span className="k">{t(x.edition === 'translation_fr' ? 'pages:lib4.k.issueFr' : 'pages:lib4.k.issue')}</span>
      <span className="m"><b><bdi dir="ltr">{x.number}</bdi>{x.suffix ? ` ${t(`corpus.suffix.${x.suffix}`)}` : ''}{x.last ? <> – <bdi dir="ltr">{x.last}</bdi></> : null} · {weekday} {longDate(x.date, i18n.language)}</b>
        <small>{x.pagesOnly ? t('pages:lib3.issue.pagesOnly', { pages: t('pages:lib3.pagesN', { count: x.pages, n: num(x.pages) }) })
          : `${t('pages:lib2.textsN', { count: x.texts, n: num(x.texts) })} · ${t('pages:lib3.pagesN', { count: x.pages, n: num(x.pages) })}`}</small>
        {lines}</span>
      <span className="go">{go ?? t('pages:lib4.go.open')}</span></Link>
  );
}

