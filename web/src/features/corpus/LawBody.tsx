import { lazy, Suspense, useCallback, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { usePreview, type Definition, type Mark } from './corpus.api';
import { AR, blocks, tableNumber, totalCheck, type Block, type Row } from './format';
import { Floating } from './reading/Popover';
import { textName } from './names';

// An article the law names, as a peek on a phone (U6): its code when first tapped.
const Peek = lazy(() => import('./reading/Peek'));
const WordNote = lazy(() => import('./reading/WordNote'));
// «label …… value» set as rows (HM14), with the first line that holds a run of dots.
const Leaders = lazy(() => import('./reading/WordNote').then((m) => ({ default: m.Leaders })));

type Props = {
  text: string;
  lang?: string;
  className?: string;
  /** Where the body's words link or carry a defined term (body offsets). */
  marks?: Mark[];
  definitions?: Definition[];
  /** The text's address, for a defined term's «where it is defined». */
  textPath?: string;
};

/** The law's own words (the review of 18 Oct 2026): paragraphs, and lists set as lists — each mark («1 -», «أ -»,
 *  «-») hung in its own column, the text beside it, points under the item that opened them — its citations
 *  linked, its defined terms explained on tap, bold kept, and tables where the page printed one. Set in the text's
 *  language and direction, never the interface's. Every word stays as printed; only the setting changes. */
export function LawBody({ text, lang = 'ar', className = '', marks = [], definitions = [], textPath = '' }: Props) {
  const all = blocks(text);
  return (
    <div lang={lang} dir={lang === 'ar' ? 'rtl' : 'ltr'} className={`${STEPS} ${className}`}>
      {all.map((b, i) => {
        const space = i === 0 ? '' : spacing(b, all[i - 1]);
        if (b.kind === 'table') return <div key={i} className={space}><LawTable rows={b.rows} /></div>;
        const inline = (text: string, at: number) => <Inline text={text} at={at} marks={marks} definitions={definitions} textPath={textPath} />;
        const words = /\.{4}|…{2}/.test(b.text)
          ? <Suspense fallback={inline(b.text, b.at)}><Leaders text={b.text} at={b.at} words={inline} /></Suspense> : inline(b.text, b.at);
        if (b.mark === 'ordinal') {
          return <p key={i} className={`${P} ${space}`}><strong className="font-semibold">{b.marker}</strong> {words}</p>;
        }
        if (b.marker) {
          return (
            <div key={i} className={`flex ${space}`} style={{ paddingInlineStart: `calc(${b.depth - 1} * var(--indent))` }}>
              <span className={`shrink-0 pe-[0.4em] tabular-nums ${b.depth === 1 && b.mark !== 'dash' ? 'font-semibold text-stamp' : 'text-ink-soft'}`}
                    style={{ minWidth: b.mark === 'dash' ? 'var(--dash)' : 'var(--marker)' }}>
                {b.marker}
              </span>
              <p className={`${P} min-w-0 flex-1`}>{words}</p>
            </div>
          );
        }
        return (
          <p key={i} className={`${P} ${space}`}
             style={b.depth ? { paddingInlineStart: `calc(${b.depth - 1} * var(--indent) + var(--marker))` } : undefined}>
            {words}
          </p>
        );
      })}
    </div>
  );
}

// A paragraph of the law: a run of dots or a long number wraps rather than widen the page past a phone's (HM14).
const P = 'm-0 [text-wrap:pretty] [overflow-wrap:anywhere]';

/** «40 000» in a right-to-left line shows «000 40»: its groups joined by a no-break space, a number's own separator, it
 *  reads as printed (HM14 of the hard-moment review). Drawn so, never stored so; a search's marks match it. */
const held = (s: string) => s.replace(/(?<![\d.,])\d{1,3}(?: \d{3})+(?!\d)/g, (n) => n.replace(/ /g, '\u00a0'));

// A list's step in, the column its numbers hang in, and a dash's: in the text's own size, so they follow it, and
// narrower on a phone, where a line holds few words.
const STEPS = '[--indent:1.1em] [--marker:1.8em] [--dash:1.1em] sm:[--indent:1.6em] sm:[--marker:2.2em] sm:[--dash:1.3em]';

/** The space above a block: a paragraph stands apart from the next one, a list's items and their lines less so,
 *  an «أولا:» part most. */
function spacing(b: Block, before: Block): string {
  if (b.kind === 'table' || before.kind === 'table') return 'mt-[0.9em]';
  if (b.mark === 'ordinal') return 'mt-[1.1em]';
  if (b.depth === 0) return 'mt-[0.85em]';
  return 'mt-[0.4em]';
}

function Inline({ text, at, marks, definitions, textPath }: { text: string; at: number } & Required<Pick<Props, 'marks' | 'definitions' | 'textPath'>>) {
  const end = at + text.length;
  const out: React.ReactNode[] = [];
  let pos = 0;
  for (const m of marks) {
    if (m.start < at || m.end > end) continue;
    const s = m.start - at;
    const e = m.end - at;
    if (s < pos) continue;
    if (s > pos) out.push(<Bold key={`t${pos}`} text={text.slice(pos, s)} />);
    out.push(<MarkView key={`m${s}`} m={m} words={text.slice(s, e).replace(/\*\*/g, '')} definitions={definitions} textPath={textPath} />);
    pos = e;
  }
  if (pos < text.length) out.push(<Bold key={`t${pos}`} text={text.slice(pos)} />);
  return <>{out}</>;
}

/** The OCR keeps the page's bold as Markdown («**الناشر**»). */
function Bold({ text }: { text: string }) {
  const parts = held(text).split(/\*\*(.+?)\*\*/g);
  return <>{parts.map((p, i) => (i % 2 ? <strong key={i} className="font-semibold">{p}</strong> : p))}</>;
}

function MarkView({ m, words, definitions, textPath }: { m: Mark; words: string; definitions: Definition[]; textPath: string }) {
  if (m.kind === 'term') {
    const d = definitions[m.term];
    return d ? <Term words={words} d={d} textPath={textPath} /> : <>{words}</>;
  }
  // A word that opens the law (R9 of the for-everyone review): its checked meaning in place, the people's dotted line (HM35).
  if (m.kind === 'word') return <Suspense fallback={words}><WordNote words={words} m={m} /></Suspense>;
  if (m.href) return <PreviewLink to={m.href} words={words} />;
  return <Unloaded words={words} title={m.title} />;
}

const tapped = 'cursor-pointer underline decoration-dotted decoration-1 underline-offset-[6px]';

function Term({ words, d, textPath }: { words: string; d: Definition; textPath: string }) {
  const { t } = useTranslation();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const close = useCallback(() => setAnchor(null), []);
  return (
    <>
      <button type="button" aria-expanded={Boolean(anchor)} onClick={(e) => setAnchor(anchor ? null : e.currentTarget)}
              className={`${tapped} decoration-stamp text-inherit [font:inherit]`}>
        {words}
      </button>
      {anchor ? (
        <Floating anchor={anchor} onClose={close} label={t('reading.definitionOf', { term: d.term })}>
          <p className="m-0 text-meta text-ink-soft">{t('reading.definedHere')}</p>
          <p {...AR} className="m-0 mt-1 font-law text-law leading-relaxed">
            <strong className="font-semibold">{d.term}</strong>: {d.definition}
          </p>
          <Link to={`${textPath}/${d.eid}`} onClick={close} className="mt-2 inline-block text-meta">{t('reading.seeDefinition')}</Link>
        </Floating>
      ) : null}
    </>
  );
}

/** A citation the corpus holds: a link, and on a desk a preview of what it opens when the pointer rests; on a phone a tap
 *  opens it as a peek, the reader staying where they were (U6 of the Moroccan-design review). */
function PreviewLink({ to, words }: { to: string; words: string }) {
  const { t, i18n } = useTranslation();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const [peek, setPeek] = useState(false);
  const closePeek = useCallback(() => setPeek(false), []);
  const timer = useRef<number>(0);
  const close = useCallback(() => setAnchor(null), []);
  const fine = typeof window !== 'undefined' && window.matchMedia?.('(hover: hover)').matches;
  const preview = usePreview(anchor ? to : null);
  return (
    <>
      <Link
        to={to}
        className="decoration-1 underline-offset-[6px]"
        onClick={(e) => {
          if (fine || e.metaKey || e.ctrlKey) return;
          e.preventDefault();
          setPeek(true);
        }}
        onMouseEnter={(e) => {
          if (!fine) return;
          const el = e.currentTarget;
          timer.current = window.setTimeout(() => setAnchor(el), 350);
        }}
        onMouseLeave={() => {
          window.clearTimeout(timer.current);
          setAnchor(null);
        }}
      >
        {words}
      </Link>
      {anchor ? (
        <Floating anchor={anchor} onClose={close} label={t('reading.preview')} hover>
          {preview.data ? (
            <>
              <p dir="auto" className="m-0 text-meta text-ink-soft">{textName(preview.data.text, i18n.language)}</p>
              {preview.data.label ? <p {...AR} className="m-0 mt-1 font-law text-law font-semibold">{preview.data.label}</p> : null}
              {preview.data.excerpt ? <p {...AR} className="m-0 mt-1 font-law text-law leading-relaxed">{preview.data.excerpt}</p> : null}
            </>
          ) : (
            <p className="m-0 text-ink-soft">{t('corpus.loading')}</p>
          )}
        </Floating>
      ) : null}
      {peek ? <Suspense fallback={null}><Peek to={to} onClose={closePeek} /></Suspense> : null}
    </>
  );
}

/** A citation to a text the corpus does not hold yet: said, not linked. */
function Unloaded({ words, title }: { words: string; title: string }) {
  const { t } = useTranslation();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const close = useCallback(() => setAnchor(null), []);
  return (
    <>
      <button type="button" aria-expanded={Boolean(anchor)} onClick={(e) => setAnchor(anchor ? null : e.currentTarget)}
              className={`${tapped} decoration-ink-soft text-inherit [font:inherit]`}>
        {words}
      </button>
      {anchor ? (
        <Floating anchor={anchor} onClose={close} label={t('search.notInCorpus')}>
          {title ? <p {...AR} className="m-0 font-law text-law leading-snug">{title}</p> : null}
          <p className="m-0 mt-1 text-meta text-ink-soft">{t('reading.unloaded')}</p>
        </Floating>
      ) : null}
    </>
  );
}

/** A printed table: the first column held while the rest scrolls, its total checked when it has one, and a
 *  copy that pastes into a spreadsheet. */
function LawTable({ rows }: { rows: Row[] }) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
  const check = totalCheck(rows);
  const copy = () => {
    void navigator.clipboard?.writeText(rows.map((r) => r.cells.join('\t')).join('\n'));
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  };
  return (
    <figure className="m-0 flex flex-col gap-1.5 py-1">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 font-ui text-meta">
        <button type="button" onClick={copy} className="min-h-11 text-stamp hover:text-stamp-deep">
          {copied ? t('reading.tableCopied') : t('reading.copyTable')}
        </button>
        {check === true ? <span className="text-in-force">{t('reading.totalOk')}</span> : null}
        {check === false ? <span className="text-amended">{t('reading.totalOff')}</span> : null}
      </div>
      <div className="-mx-1 overflow-x-auto">
        <table className="w-full border-collapse font-ui text-meta leading-snug">
          <tbody>
            {rows.map((row, r) => (
              <tr key={r} className={`${r === 0 ? 'bg-paper font-medium' : 'border-t border-rule-soft'} ${row.strong ? 'font-semibold' : ''}`}>
                {row.cells.map((cell, c) => {
                  const number = tableNumber(cell) !== null;
                  return (
                    <td key={c}
                        className={`px-2 py-1.5 align-top ${c === 0 ? `sticky start-0 ${r === 0 ? 'bg-paper' : 'bg-sheet'}` : ''} ${number ? 'whitespace-nowrap tabular-nums' : ''}`}>
                      {/* «13 000» in a right-to-left cell would show «000 13»: a number reads left to right. */}
                      {number ? <bdi dir="ltr">{cell}</bdi> : held(cell)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </figure>
  );
}
