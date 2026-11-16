import { lazy, useState, type CSSProperties } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Link, Route, Routes } from 'react-router-dom';
import { RequireAuth } from '@/features/accounts/RequireAuth';
import { count } from '@/features/budget/money';
import { api, ApiError } from '@/shared/services/api';
import { daysAgo } from '@/shared/services/today';
import '@/shared/locales/pages';
import { usePageTitle } from '@/shared/services/title';
import { Button, LinesSkeleton, Page } from '@/shared/components/ui';
import { buttonClass } from '@/shared/components/buttons';
import { DATA_FILES, DESCRIBE_FILES, examples, fileKey, mayAsk, READS, size, standing, type AccessBody } from './access';
import { useAccess, useManifest } from './access.api';
import { Copy, StandingLine } from './parts';
import { dateOf } from './said';
import '@/features/corpus/library.css';
import './data.css';
import './access.css';

// The request's form and the terms load when they are opened: none of it with the programme's page.
const RequestPage = lazy(() => import('./RequestPage'));
const TermsPage = lazy(() => import('./TermsPage'));
const AccessPage = lazy(() => import('./AccessPage'));
const DeskPage = lazy(() => import('./DeskPage'));
const NotFound = lazy(() => import('@/features/corpus/NotFound'));

/** Three addresses to take apart: a code's article, a law's, the Constitution's. */
const ADDRESSES = ['/ma/loi/65-99/art_53', '/ma/loi/31-13/art_1', '/ma/dahir/1-11-91/art_27'];
/** The kinds an address may name, as the corpus holds them (31 Oct 2026). */
const KINDS = ['loi', 'decret', 'dahir', 'arrete', 'decision', 'loi-organique', 'decret-loi', 'code', 'convention', 'texte'];
const EMBED_EXAMPLE = '/ma/loi/65-99/art_53';
/** The licence of what the site builds (ODbL 1.0, chosen on 2 Nov 2026). */
const ODBL = 'https://opendatacommons.org/licenses/odbl/1-0/';
/** A file's format, said by its name. */
const format = (name: string) => (name.endsWith('.jsonl.gz') ? 'JSON Lines' : name === 'akn.zip' ? 'Akoma Ntoso' : name.split('.').pop()?.toUpperCase() ?? '');

/** /data and the two pages under it: the programme's page, the request's form (behind sign-in, as /account is) and
 *  the terms. One route of the app, so the first load names one page's code, not three. */
export default function DataPage() {
  return (
    <Routes>
      <Route index element={<Programme />} />
      <Route path="request" element={<RequireAuth><RequestPage /></RequireAuth>} />
      <Route path="terms" element={<TermsPage />} />
      <Route path="access" element={<RequireAuth><AccessPage /></RequireAuth>} />
      <Route path="desk" element={<RequireAuth><DeskPage /></RequireAuth>} />
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}

/**
 * «البيانات والواجهة البرمجية» (16 Nov 2026: access on request). The database and an API for programs are given to a
 * person who asked from their account and was accepted; the page says what can be asked for, how a request is decided,
 * the three sizes, the door (or where one's own request stands), the API's six reads, the newest edition with its hash,
 * and the licence. It keeps its opening piece, an article's address taken apart, and the embed. While the server's
 * OPEN_DATA is `closed` it says what is coming, and nothing else.
 */
function Programme() {
  const { t } = useTranslation();
  usePageTitle([t('data.title')]);
  const access = useAccess();
  const b = access.data;
  const closed = b?.position === 'closed';
  const origin = typeof window === 'undefined' ? '' : window.location.origin;
  const embed = `<iframe src="${origin}/embed${EMBED_EXAMPLE}" title="${t('pages:data.embedTitle')}" width="100%" height="420" style="border:0" loading="lazy"></iframe>`;
  const [preview, setPreview] = useState(false);
  // Its title alone until the server says where access stands: never the programme, then «soon».
  if (access.isPending || closed) return <Soon pending={access.isPending} />;
  if (!b) {
    return (
      <Page width="wide" className="lb dt">
        <header className="lb-head"><div><h1>{t('data.title')}</h1></div></header>
        <p className="lb-failed">{t('pages:data.failed')} <button type="button" onClick={() => void access.refetch()}>{t('pages:access.retry')}</button></p>
      </Page>
    );
  }
  return (
    <Page width="wide" className="lb dt">
      <header className="lb-head side">
        <div>
          <h1>{t('data.title')}</h1>
          <p className="ax-line">{t('pages:access.line')}</p>
          <p className="lead">{t('pages:access.lead', { days: b.answer_days })}</p>
        </div>
        <Door body={b} />
      </header>

      <Address />

      <section aria-labelledby="ask" className="lb-sec">
        <h2 id="ask">{t('pages:access.ask.title')}</h2>
        <ul className="lb-rows">
          {(['api', 'data'] as const).map((k) => (
            <li key={k}>
              <span className="what">
                <b className="ax-rowhead">{t(`pages:access.ask.${k}.t`)}</b>
                <span className="sub">{t(`pages:access.ask.${k}.d`)}</span>
              </span>
              <a href={k === 'api' ? '#api' : '#download'} className={buttonClass('quiet')}>{t(`pages:access.ask.${k}.more`)}</a>
            </li>
          ))}
        </ul>
      </section>

      <How body={b} />
      <Api />
      <Edition body={b} />

      <section aria-labelledby="licence" className="lb-sec">
        <h2 id="licence">{t('pages:data.licenceTitle')}</h2>
        <div className="lb-halves">
          <div>
            <h3>{t('pages:data.officialTexts')}<span className="badge free">{t('pages:data.free')}</span></h3>
            <p>{t('pages:data.licenceTexts')}</p>
          </div>
          <div>
            <h3>{t('pages:data.ourWork')}<span className="badge cc" dir="ltr">ODbL 1.0</span></h3>
            <p>{t('pages:data.licenceOurs')}</p>
          </div>
        </div>
        <p className="dt-small">{t('pages:data.licenceNot')} <Link to="/data/terms">{t('pages:access.terms.title')}</Link></p>
      </section>

      <section aria-labelledby="embed" className="lb-sec">
        <h2 id="embed">{t('pages:data.embedTitle')}</h2>
        <p>{t('pages:data.embedLead')}</p>
        <div className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-4">
          <code dir="ltr" className="lb-code">{embed}</code>
          <span className="flex flex-wrap justify-end gap-2">
            <button type="button" onClick={() => setPreview((p) => !p)} aria-expanded={preview} className={buttonClass('quiet')}>
              {preview ? t('pages:data.hide') : t('pages:data.preview')}
            </button>
            <Copy text={embed} label={t('data.copyCode')} />
          </span>
          {preview ? <iframe title={t('pages:data.embedTitle')} src={`/embed${EMBED_EXAMPLE}`} className="lb-embed" loading="lazy" /> : null}
        </div>
        <p className="dt-small">{t('pages:data.embedNote')} <Link to="/privacy">{t('pages:data.privacyLink')}</Link></p>
      </section>
    </Page>
  );
}

/** The way in: what one asks for, when the answer comes, that it is free, and the button; for an account that asked,
 *  where its request stands, with the way to its account page. */
function Door({ body }: { body: AccessBody }) {
  const { t } = useTranslation();
  const s = standing(body);
  return (
    <section className="lb-record ax-door" aria-labelledby="door">
      <span className="h"><b id="door">{t('pages:access.door.title')}</b><span>{t('pages:access.door.free')}</span></span>
      {s === 'none' ? (
        <dl>
          <dt>{t('pages:access.door.what')}</dt><dd>{t('pages:access.door.whatD')}</dd>
          <dt>{t('pages:access.door.when')}</dt><dd>{t('pages:access.door.whenD', { days: body.answer_days })}</dd>
          <dt>{t('pages:access.door.how')}</dt><dd>{t('pages:access.door.howD')}</dd>
        </dl>
      ) : <StandingLine body={body} />}
      <DoorButton body={body} />
    </section>
  );
}

/** The button to the form while the account may ask; while the files are open to anyone, one line that says so too
 *  (a key for the API is still asked for). */
function DoorButton({ body }: { body: AccessBody }) {
  const { t } = useTranslation();
  const s = standing(body);
  const ask = mayAsk(s)
    ? <Button variant="primary" to="/data/request" className="self-start">{t(s === 'none' ? 'pages:access.door.ask' : 'pages:access.door.askAgain')}</Button>
    : null;
  if (body.position !== 'open') return ask;
  return <>{ask}<p className="ax-small">{t('pages:access.door.open')}</p></>;
}

/** How to ask and how a request is decided: the steps, what is accepted and the five reasons it may not be, the three
 *  sizes with their numbers, and that it is free. */
function How({ body }: { body: AccessBody }) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const sizes = [['try', body.sizes.try], ['app', body.sizes.app], ['partner', null]] as const;
  return (
    <section aria-labelledby="how" className="lb-sec">
      <h2 id="how">{t('pages:access.how.title')}</h2>
      <ol className="ax-steps">
        {(t('pages:access.how.steps', { returnObjects: true, days: body.answer_days }) as string[]).map((s) => <li key={s}>{s}</li>)}
      </ol>
      <div className="lb-halves">
        <div>
          <h3>{t('pages:access.how.yes')}</h3>
          <ul className="ax-list">
            {(t('pages:access.how.yesList', { returnObjects: true }) as string[]).map((s) => <li key={s}>{s}</li>)}
          </ul>
        </div>
        <div>
          <h3>{t('pages:access.how.no')}</h3>
          <dl className="ax-reasons">
            {(['unclear', 'identity', 'scope', 'terms', 'later'] as const).map((r) => (
              <div key={r}><dt>{t(`pages:access.reasons.${r}.t`)}</dt><dd>{t(`pages:access.reasons.${r}.d`)}</dd></div>
            ))}
          </dl>
          <p className="ax-small">{t('pages:access.how.again')}</p>
        </div>
      </div>
      <div className="ax-table">
        <table>
          <caption>{t('pages:access.how.sizes')}</caption>
          <thead>
            <tr>
              <th scope="col">{t('pages:access.how.cols.size')}</th>
              <th scope="col">{t('pages:access.how.cols.minute')}</th>
              <th scope="col">{t('pages:access.how.cols.calls')}</th>
              <th scope="col">{t('pages:access.how.cols.articles')}</th>
            </tr>
          </thead>
          <tbody>
            {sizes.map(([k, n]) => (
              <tr key={k}>
                <th scope="row"><b>{t(`pages:access.how.size.${k}.t`)}</b><span>{t(`pages:access.how.size.${k}.d`)}</span></th>
                {n ? (['minute', 'calls', 'articles'] as const).map((c) => <td key={c} data-label={t(`pages:access.how.cols.${c}`)}>{count(n[c], lang)}</td>)
                  : <td colSpan={3} className="agreed">{t('pages:access.how.agreed')}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="ax-small">{t('pages:access.how.sizesNote')}</p>
      <p className="ax-free">{t('pages:access.how.free')}</p>
      <DoorButton body={body} />
    </section>
  );
}

/** The API for programs: its six reads, each with its address, what it gives and one example to copy; its full
 *  description; and the four things a program meets (the key on a server, the errors, the limits, the source). */
function Api() {
  const { t, i18n } = useTranslation();
  const origin = typeof window === 'undefined' ? '' : window.location.origin;
  const ex = examples(origin, daysAgo(30), i18n.language);
  return (
    <section aria-labelledby="api" className="lb-sec">
      <h2 id="api">{t('pages:access.api.title')}</h2>
      <p>{t('pages:access.api.lead')}</p>
      <ul className="lb-rows">
        {READS.map(([k, method, address]) => (
          <li key={k}>
            <span className="what">
              <span dir="ltr" className="flex min-w-0 max-w-full items-baseline gap-2 self-start text-start"><span className="lb-get">{method}</span><code>{address}</code></span>
              <span className="sub">{t(`pages:access.api.reads.${k}`)}</span>
            </span>
            <span className="ax-example">
              <code dir="ltr" className="lb-code">{ex[k]}</code>
              <Copy text={ex[k]} />
            </span>
          </li>
        ))}
      </ul>
      <p className="ax-small">
        {t('pages:access.api.openapi')} <a href="/api/v1/openapi.yaml" dir="ltr" className="ax-mono">/api/v1/openapi.yaml</a>
      </p>
      <dl className="dt-notes">
        {(['key', 'errors', 'limits', 'cite'] as const).map((k) => (
          <div key={k}><dt>{t(`pages:access.api.notes.${k}.t`)}</dt><dd>{t(`pages:access.api.notes.${k}.d`)}</dd></div>
        ))}
      </dl>
    </section>
  );
}

/** The newest edition: its date and counts, each file with its size and what it holds, the manifest's hash to check a
 *  copy against, the earlier editions' hashes, and how a holder takes the files. */
function Edition({ body }: { body: AccessBody }) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const manifest = useManifest();
  const m = manifest.data;
  const today = useQuery({ queryKey: ['about'], queryFn: () => api<{ texts: number }>('/open/about/'), staleTime: 3600_000, enabled: Boolean(m) }).data;
  const none = manifest.error instanceof ApiError && manifest.error.status === 404;
  const open = body.position === 'open';
  const origin = typeof window === 'undefined' ? '' : window.location.origin;
  return (
    <section aria-labelledby="download" className="lb-sec">
      <h2 id="download">{t('pages:access.edition.title')}</h2>
      {manifest.isPending ? <LinesSkeleton /> : !m ? (
        <p>{none ? t('pages:access.edition.none') : t('pages:data.failed')}</p>
      ) : (
        <>
          <p>{t('pages:access.edition.lead', { date: dateOf(m.date, lang) })}</p>
          <div className="lb-record ax-edition">
            <span className="h"><b>{t('pages:access.edition.date')}</b><span>{dateOf(m.date, lang)}</span></span>
            <dl>
              <dt>{t('pages:access.edition.texts')}</dt><dd>{count(m.texts, lang)}</dd>
              <dt>{t('pages:access.edition.articles')}</dt><dd>{count(m.articles, lang)}</dd>
              <dt>{t('pages:access.edition.versions')}</dt><dd>{count(m.versions, lang)}</dd>
            </dl>
            {today?.texts ? (
              <p className="dt-share">
                <span className="bar" style={{ '--of': `${Math.min(100, (m.texts / today.texts) * 100)}%` } as CSSProperties} aria-hidden="true" />
                {t('pages:access.edition.share', { n: count(m.texts, lang), of: count(today.texts, lang) })}
              </p>
            ) : null}
          </div>
          <ul className="lb-rows">
            {[...DATA_FILES, ...DESCRIBE_FILES].filter((name) => name === 'manifest.json' || m.files[name]).map((name) => {
              const data = DATA_FILES.includes(name);
              const f = m.files[name];
              return (
                <li key={name}>
                  <span className="what">
                    <span dir="ltr" className="max-w-full self-start text-start"><code>{name}</code><span className="fmt">{format(name)}</span></span>
                    <span className="sub">{t(`pages:access.edition.files.${fileKey(name)}`)}</span>
                  </span>
                  {f ? <span dir="ltr" className="size">{size(f.bytes)}</span> : null}
                  {data && !open ? <span className="ax-tag">{t('pages:access.edition.toHolders')}</span> : (
                    <a href={`/api/open/latest/${name}`} className={buttonClass('secondary')}>{t(data ? 'pages:access.edition.get' : 'pages:access.edition.open')}</a>
                  )}
                </li>
              );
            })}
          </ul>
          <div className="ax-hash">
            <span className="what">
              <b>{t('pages:access.edition.hash')}</b>
              <span className="sub">{t('pages:access.edition.hashD')}</span>
            </span>
            <code dir="ltr">{m.sha256}</code>
            <Copy text={m.sha256} />
          </div>
          <p className="ax-small">{t('pages:access.edition.check')}</p>
          {m.editions.filter((e) => e.sha256 !== m.sha256).length ? (
            <div className="ax-earlier">
              <h3>{t('pages:access.edition.earlier')}</h3>
              <ul>
                {m.editions.filter((e) => e.sha256 !== m.sha256).map((e) => (
                  <li key={`${e.date}-${e.sha256}`}><span>{dateOf(e.date, lang)}</span><code dir="ltr">{e.sha256}</code></li>
                ))}
              </ul>
            </div>
          ) : null}
          {open ? null : (
            <div className="ax-holders">
              <p className="ax-small">{t('pages:access.edition.holders')} <Link to="/data/access">{t('pages:access.edition.account')}</Link></p>
              <span className="ax-example">
                <code dir="ltr" className="lb-code">{examples(origin, '').edition}</code>
                <Copy text={examples(origin, '').edition} />
              </span>
            </div>
          )}
        </>
      )}
    </section>
  );
}

/** While the downloads are closed (since 2 Nov 2026): the data the team curates is coming, and what it will hold. */
function Soon({ pending }: { pending: boolean }) {
  const { t } = useTranslation();
  return (
    <Page width="wide" className="lb dt">
      <header className="lb-head">
        <div>
          <h1>{t('data.title')}</h1>
          {pending ? null : <p className="lead">{t('pages:data.soon.lead')}</p>}
        </div>
      </header>
      {pending ? null : (
        <section aria-labelledby="soon" className="lb-sec">
          <h2 id="soon">{t('pages:data.soon.title')}</h2>
          <ul className="dt-holds">
            {(t('pages:data.soon.holds', { returnObjects: true }) as string[]).map((h) => <li key={h}>{h}</li>)}
          </ul>
          <p className="dt-small">
            {t('pages:data.soon.licence')}{' '}
            <a href={ODBL} target="_blank" rel="noreferrer">{t('pages:data.soon.licenceLink')}</a>
          </p>
        </section>
      )}
    </Page>
  );
}

/** An article's address taken apart, and the same address on the site, in the API, in an embed and on a date. */
function Address() {
  const { t, i18n } = useTranslation();
  const [path, setPath] = useState(ADDRESSES[0]);
  const [, country, kind, number, article] = path.split('/');
  const origin = typeof window === 'undefined' ? '' : window.location.origin;
  const parts: [string, string, string][] = [
    [country, 'country', t('pages:data.parts.country.d')],
    [kind, 'kind', KINDS.includes(kind) ? t(`pages:data.kinds.${kind}`) : ''],
    [number, 'number', t('pages:data.parts.number.d', { printed: number.replace('-', '.') })],
    [article, 'article', t('pages:data.parts.article.d')],
  ];
  return (
    <section className="dt-address" aria-labelledby="address">
      <div className="dt-address-head">
        <div>
          <h2 id="address">{t('pages:data.addressTitle')}</h2>
          <p>{t('pages:data.addressLead')}</p>
        </div>
        <div role="group" aria-label={t('pages:data.examples')} className="dt-examples">
          {ADDRESSES.map((a) => (
            <button key={a} type="button" aria-pressed={a === path} onClick={() => setPath(a)}>{t(`pages:data.ex.${a.split('/')[3].replace(/\W/g, '_')}`)}</button>
          ))}
        </div>
      </div>
      {/* The address as one reads it, left to right, each part over what it means. */}
      <ol className="dt-parts" dir="ltr">
        {parts.map(([part, k, what]) => (
          <li key={k} data-part={k}>
            <code><span className="slash">/</span>{part}</code>
            <span dir={i18n.language === 'fr' ? 'ltr' : 'rtl'} className="label"><b>{t(`pages:data.parts.${k}.t`)}</b>{what ? <span>{what}</span> : null}</span>
          </li>
        ))}
      </ol>
      <ul className="dt-uses">
        <li>
          <span className="use">{t('pages:data.uses.site')}</span>
          <a href={path} dir="ltr"><span className="o">{origin}</span>{path}</a>
        </li>
        <li>
          <span className="use">{t('pages:data.uses.date')}</span>
          <a href={`${path}?on=2015-01-01`} dir="ltr">{path}<b>?on=2015-01-01</b></a>
        </li>
        <li>
          <span className="use">{t('pages:data.uses.embed')}</span>
          <code dir="ltr"><b>/embed</b>{path}</code>
        </li>
      </ul>
      <ul className="lb-rows">
        <Endpoint key={path} url={`/api/corpus/preview/?path=${path}`} what={t('pages:data.uses.api')} tryable />
      </ul>
    </section>
  );
}

type Answer = { status: number; ms: number; bytes: number; body: string } | { failed: true };

/** An endpoint: its method and address, what it gives, to copy or to try; tried, its answer shows under it. */
function Endpoint({ url, what, tryable = true }: { url: string; what: string; tryable?: boolean }) {
  const { t } = useTranslation();
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [busy, setBusy] = useState(false);
  const run = async () => {
    if (answer) { setAnswer(null); return; }
    setBusy(true);
    const t0 = performance.now();
    try {
      const r = await fetch(url, { headers: { Accept: 'application/json' } });
      const raw = await r.text();
      let body = raw;
      try { body = JSON.stringify(JSON.parse(raw), null, 2); } catch { /* not JSON: shown as it came */ }
      setAnswer({ status: r.status, ms: Math.round(performance.now() - t0), bytes: new Blob([raw]).size, body });
    } catch {
      setAnswer({ failed: true });
    } finally {
      setBusy(false);
    }
  };
  return (
    <li>
      <span className="what">
        <span dir="ltr" className="flex min-w-0 items-baseline gap-2 text-start"><span className="lb-get">GET</span><code>{url}</code></span>
        <span className="sub">{what}</span>
      </span>
      <span className="acts">
        <Copy text={url} />
        {tryable ? (
          <button type="button" onClick={() => void run()} disabled={busy} aria-expanded={Boolean(answer)} className={buttonClass('quiet')}>
            {busy ? t('corpus.loading') : answer ? t('pages:data.hide') : t('pages:data.try')}
          </button>
        ) : null}
      </span>
      {answer ? (
        <div className="lb-answer">
          {'failed' in answer ? <span className="meta"><span className="bad">{t('pages:data.failed')}</span></span> : (
            <>
              <span className="meta" dir="ltr">
                <span className={answer.status < 400 ? 'ok' : 'bad'}>{answer.status}</span>
                <span>{answer.ms} ms</span><span>{size(answer.bytes)}</span>
                <a href={url} target="_blank" rel="noreferrer">{t('pages:data.whole')}</a>
              </span>
              <pre dir="ltr" className="lb-json">{paint(clip(answer.body))}</pre>
            </>
          )}
        </div>
      ) : null}
    </li>
  );
}

/** The answer's first 80 lines: enough to read its shape. */
const clip = (s: string) => {
  const lines = s.split('\n');
  return lines.length > 80 ? `${lines.slice(0, 80).join('\n')}\n…` : s;
};

/** JSON in colour: keys in the source's violet, strings green, numbers amber, true/false/null red. */
function paint(s: string): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  const re = /("(?:\\.|[^"\\])*")(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/g;
  let at = 0;
  let k = 0;
  for (let m = re.exec(s); m; m = re.exec(s)) {
    if (m.index > at) out.push(s.slice(at, m.index));
    const cls = m[1] ? (m[2] ? 'k' : 's') : m[3] ? 'b' : 'n';
    out.push(<span key={k++} className={cls}>{m[1] ?? m[0]}</span>);
    if (m[2]) out.push(m[2]);
    at = m.index + m[0].length;
  }
  out.push(s.slice(at));
  return out;
}
