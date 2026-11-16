import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { AR, articleName, longDate } from '@/features/corpus/format';
import { searchApi, shortTitle, type Resolved } from './search.api';
import { usePageTitle } from '@/shared/services/title';
import { Page } from '@/shared/components/ui';
import { buttonClass } from '@/shared/components/buttons';
import '@/shared/locales/pages';
import './checkWords';
import '@/features/corpus/library.css';

type Found = { start16: number; end16: number; raw: string } & Record<string, unknown>;

/** ma_law in the browser (WASM, loaded with this page only): the pasted document never leaves the device. */
async function readCitations(text: string): Promise<Found[]> {
  const [mod, wasm] = await Promise.all([
    import('@/shared/wasm/ma_law/ma_law.js'),
    import('@/shared/wasm/ma_law/ma_law_bg.wasm?url'),
  ]);
  await mod.default({ module_or_path: wasm.default });
  return JSON.parse(mod.parseCitations(text)) as Found[];
}

/**
 * «تحقق من الإحالات» (drawn again on 30 Oct 2026, as a reviewer marks up a document): paste a contract, a judgment or a
 * memo on a ruled sheet; every reference in it is read on the device, then the sheet shows the document marked up, each
 * reference in the colour of where it stands and numbered, and beside it the notes say what each one is, link it, and
 * what changed it after the document's date. A mark leads to its note and a note to its mark.
 */
export default function CheckPage() {
  const { t } = useTranslation();
  usePageTitle([t('check.title')]);
  const [text, setText] = useState('');
  const [since, setSince] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const [result, setResult] = useState<{ text: string; found: Found[]; resolved: Resolved[] } | null>(null);

  const check = async () => {
    setBusy(true);
    setError(false);
    try {
      const found = await readCitations(text);
      const resolved = found.length ? (await searchApi.resolve(found, since || null)).results : [];
      setResult({ text, found, resolved });
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  };

  const counts = { found: 0, changed: 0, missing: 0 };
  for (const r of result?.resolved ?? []) {
    if (r.state === 'found' || r.state === 'issue') counts.found++;
    else counts.missing++;
    if (r.changes.length) counts.changed++;
  }
  const marked = result && result.found.length;

  return (
    <Page width="wide" className="lb">
      <header className="lb-head">
        <div>
          <h1>{t('check.title')}</h1>
          <p className="lead">{t('check.lead')}</p>
          <p className="lb-private"><Lock />{t('pages:check2.private')}</p>
        </div>
      </header>

      <div className="lb-check">
        <form className="lb-paper" onSubmit={(e) => { e.preventDefault(); void check(); }}>
          <div className="top">
            {marked ? <b>{t('pages:check2.marked')}</b> : <label htmlFor="check-text">{t('check.paste')}</label>}
            {marked ? (
              <button type="button" onClick={() => setResult(null)}>{t('pages:check2.edit')}</button>
            ) : (
              <button type="button" onClick={() => { setText(t('check.example')); setResult(null); }}>{t('check.tryExample')}</button>
            )}
          </div>
          {marked ? (
            <Document text={result.text} found={result.found} resolved={result.resolved} />
          ) : (
            <textarea id="check-text" dir="auto" rows={10} value={text} onChange={(e) => setText(e.target.value)}
                      placeholder={t('check.placeholder')} className="lb-ruled" />
          )}
          <div className="foot">
            <label>
              <span>{t('check.since')}</span>
              <input type="date" value={since} onChange={(e) => setSince(e.target.value)} dir="ltr" />
            </label>
            <span className="go">
              <button type="submit" disabled={!text.trim() || busy} className={buttonClass('primary')}>
                {busy ? t('corpus.loading') : marked ? t('pages:check2.again') : t('check.run')}
              </button>
            </span>
          </div>
          <p className="m-0 text-meta text-ink-soft">{t('check.privacy')}</p>
        </form>

        <section className="lb-notes" aria-live="polite" aria-labelledby="check-results">
          <h2 id="check-results" className="lb-sr">{t('check.results')}</h2>
          {error ? <p role="alert" className="lb-sum" style={{ color: 'var(--color-repealed)' }}>{t('check.failed')}</p> : null}
          {result ? (
            result.found.length ? (
              <>
                <p className="lb-sum">
                  {t('pages:check2.sum', { found: t('check.found', { count: result.found.length }) })}{' '}
                  <b className="ok">{t('check.inCorpus', { count: counts.found })}</b>
                  {counts.missing ? <>{t('corpus.listSep')}<b className="soft">{t('check.notIn', { count: counts.missing })}</b></> : null}.
                  {since && counts.changed ? <span className="chg">{t('check.changed', { count: counts.changed })}</span> : null}
                </p>
                <ol className="lb-noteslist">
                  {result.resolved.map((r, i) => <Note key={i} n={i + 1} r={r} since={since} />)}
                </ol>
              </>
            ) : <p className="lb-sum">{t('check.none')}</p>
          ) : <Sample />}
        </section>
      </div>
    </Page>
  );
}

/** The document as pasted, on its ruled sheet, each reference marked in the colour of where it stands and numbered; a
 *  mark leads to its note. */
function Document({ text, found, resolved }: { text: string; found: Found[]; resolved: Resolved[] }) {
  const out: React.ReactNode[] = [];
  let pos = 0;
  found.forEach((f, i) => {
    if (f.start16 < pos) return;
    out.push(text.slice(pos, f.start16));
    out.push(
      <a key={i} id={`m${i + 1}`} href={`#n${i + 1}`} className={`lb-ref ${resolved[i]?.state ?? 'unknown'}`}>
        {text.slice(f.start16, f.end16)}<sup>{i + 1}</sup>
      </a>,
    );
    pos = f.end16;
  });
  out.push(text.slice(pos));
  return <div dir="auto" className="lb-ruled">{out}</div>;
}

/** A reference's note: its number in the colour of where it stands, the words as written, what they point to (linked
 *  when «قانون» holds it), where it stands, and what changed it. */
function Note({ n, r, since }: { n: number; r: Resolved; since: string }) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const path = r.article?.path ?? r.text?.path ?? r.issue?.path ?? null;
  const title = r.state === 'issue' && r.issue ? t('search.issue', { key: r.issue.key })
    : r.text ? `${r.article ? `${articleName(r.article.label, t)} — ` : ''}${shortTitle(r.text.title, 150)}`
    : r.name?.[lang === 'fr' ? 'fr' : 'ar'] ?? r.citation.raw;
  return (
    <li id={`n${n}`} className={r.state}>
      <a href={`#m${n}`} className="num" aria-label={t('pages:check2.toMark', { n })}>{n}</a>
      <span {...AR} className="raw">«{r.citation.raw}»</span>
      {path ? <Link {...AR} to={path} className="to">{title}</Link> : <span {...AR} className="to">{title}</span>}
      <span className="st">
        {r.state === 'text_only' ? t('search.articleMissing', { article: r.citation.article }) : t(`check.state.${r.state}`)}
      </span>
      {r.changes.length ? (
        <ul className="chg">
          {r.changes.map((c, i) => (
            <li key={i}>
              {since ? t('check.changedBy') : t('check.amendedBy')}{' '}
              <Link {...AR} to={c.by.path}>{shortTitle(c.by.title, 90)}</Link>
              {c.published ? <span className="text-ink-soft">{t('corpus.listSep')}{longDate(c.published, lang)}</span> : null}
            </li>
          ))}
        </ul>
      ) : null}
    </li>
  );
}

/** Before a check: a sentence marked up as a result will be, and what each colour says. */
function Sample() {
  const { t } = useTranslation();
  const states = ['found', 'text_only', 'repealed', 'not_in_corpus'] as const;
  return (
    <div className="lb-sample">
      <p className="font-semibold">{t('check.before')}</p>
      <p {...AR} className="doc">
        {t('pages:check2.sampleStart')}{' '}
        {states.map((k, i) => (
          <span key={k}><span className={`lb-ref ${k}`}>{t(`check.sample.${k}`)}<sup>{i + 1}</sup></span>{i < states.length - 1 ? t('corpus.listSep') : '…'}</span>
        ))}
      </p>
      <ol>
        {states.map((k, i) => (
          <li key={k}><span className={`lb-ref ${k}`}><sup>{i + 1}</sup></span><span>{t(`check.state.${k}`)}</span></li>
        ))}
      </ol>
    </div>
  );
}

const Lock = () => (
  <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="5" y="11" width="14" height="10" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3" />
  </svg>
);
