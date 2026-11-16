import { useId, useState, type ReactNode } from 'react';
import { useQuery, useQueryClient, type UseQueryResult } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { count } from '@/features/budget/money';
import { Button, LinesSkeleton, Page, PageSkeleton } from '@/shared/components/ui';
import { ApiError } from '@/shared/services/api';
import { usePageTitle } from '@/shared/services/title';
import { todayIso } from '@/shared/services/today';
import '@/shared/locales/pages';
import {
  BIG_FILES, changeBody, changing, checkChange, DATA_FILES, editionBytes, examples, firstCall, KEYS_MOST, lastDays, mayAsk,
  mayChange, MOST, READS, share, size, SIZES, standing, type AccessBody, type AccessRow, type Change, type Keys,
  type NewKey, type RequestRow, type Standing,
} from './access';
import { accessApi, useAccess, useKeepAccess, useManifest } from './access.api';
import './locales/mine';
import { Alerts, Copy } from './parts';
import { dateOf, useGranted, useRefusals } from './said';
import { Sent } from './Sent';
import '@/features/corpus/library.css';
import './access.css';

const KEYS = ['access', 'keys'];

/** French says a grant inside a sentence («l’API»); at a line's start it takes a capital. */
const capital = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/**
 * «وصولي» (/data/access, behind sign-in; where the letters about a request link). It opens on where the account stands
 * and the one thing to do next: nothing asked, a line and the way to ask; a request waiting, the day it was sent and the
 * day the answer is due; a question from the staff, the question and the box to answer it, first; a live access, what
 * it holds in one line, then its keys (the first one to make, when there is none), today's use and the last 30 days,
 * the edition's two large files, and at the foot a change to ask for, what was sent, the terms and ending it; declined or
 * ended, the reason and when one may ask again. A request to change the access shows its own state beside it. On a desk
 * the API's six reads sit beside the key. Loaded apart from the first load.
 */
export default function AccessPage() {
  const { t } = useTranslation('mine');
  usePageTitle([t('title')]);
  const access = useAccess();
  const b = access.data;
  if (b) return <Mine body={b} />;
  if (!access.isError) return <Page width="wide"><PageSkeleton /></Page>;
  return (
    <Page width="wide" className="lb ax-me">
      <header className="lb-head"><div><h1>{t('title')}</h1></div></header>
      <p className="lb-failed">
        {t('pages:data.failed')} <button type="button" onClick={() => void access.refetch()}>{t('pages:access.retry')}</button>
      </p>
    </Page>
  );
}

function Mine({ body: b }: { body: AccessBody }) {
  const { t } = useTranslation('mine');
  const s = shownStanding(b);
  const live = b.access?.state === 'live' ? b.access : null;
  const keys = useQuery({ queryKey: KEYS, queryFn: accessApi.keys, staleTime: 30_000, enabled: Boolean(live) });
  const asked = s === 'more' ? b.request : null;
  return (
    <Page width="wide" className="lb ax-me">
      <header className="lb-head ax-head">
        <div className="ax-stand">
          <h1>{t('title')}</h1>
          {live ? <Held access={live} /> : <Where body={b} s={s} />}
          {live ? <ChangeLine body={b} /> : null}
        </div>
      </header>
      <div className={live?.api ? 'ax-grid' : 'ax-grid one'}>
        <div className="ax-main">
          {asked ? <Question request={asked} change={Boolean(live)} /> : null}
          {live ? <Holding access={live} keys={keys} /> : null}
          <Foot body={b} live={live} s={s} />
        </div>
        {live?.api ? <ApiSide /> : null}
      </div>
    </Page>
  );
}

/** Where the account stands, as the page says it: a decline of a change request after the access ended reads as the
 *  access's end (the day one may ask again still holds). */
function shownStanding(b: AccessBody): Standing {
  const s = standing(b);
  return (s === 'declined' || s === 'again') && b.request?.change_of != null && b.access?.state === 'ended' ? 'ended' : s;
}

/** A state's word in its colour, before the sentence that says it. */
function Mark({ tone, children }: { tone: 'live' | 'wait' | 'ask' | 'no' | 'off'; children: ReactNode }) {
  return <p className="ax-mark" data-tone={tone}><i aria-hidden="true" />{children}</p>;
}

/** Every state but a live access: its word, its sentence, and the one act it allows. */
function Where({ body: b, s }: { body: AccessBody; s: Standing }) {
  const { t, i18n } = useTranslation('mine');
  const lang = i18n.language;
  const r = b.request;
  const closed = b.position === 'closed';
  const ask = mayAsk(s) && !closed && !r?.ask_again_on;
  if (s === 'none') {
    return (
      <>
        <p className="ax-say">{t(closed ? 'say.noneClosed' : 'say.none')}</p>
        <p className="ax-acts">
          {closed ? null : <Button variant="primary" to="/data/request">{t('say.ask')}</Button>}
          <Link to="/data" className="ax-link">{t('say.see')}</Link>
        </p>
      </>
    );
  }
  if (s === 'waiting' && r) {
    return (
      <>
        <Mark tone="wait">{t('mark.waiting')}</Mark>
        <p className="ax-say">
          {r.due_on ? t('say.waiting', { sent: dateOf(r.created_at, lang), due: dateOf(r.due_on, lang) })
            : t('pages:access.states.waiting', { date: dateOf(r.created_at, lang), days: b.answer_days })}
        </p>
      </>
    );
  }
  if (s === 'more') {
    return <><Mark tone="ask">{t('mark.more')}</Mark><p className="ax-say">{t('say.more')}</p></>;
  }
  const ended = s === 'ended';
  const reason = ended
    ? t(`pages:access.ended.${b.access?.ended_reason || 'expired'}`)
    : t(`pages:access.reasons.${r?.reason || 'unclear'}.d`);
  return (
    <>
      <Mark tone={ended ? 'off' : 'no'}>{t(`mark.${ended ? 'ended' : 'declined'}`)}</Mark>
      <p className="ax-say">
        {t('say.reason', { reason })}{' '}
        {r?.ask_again_on ? t('say.againOn', { date: dateOf(r.ask_again_on, lang) }) : ended || closed ? null : t('say.againNow')}
      </p>
      {ask ? <p className="ax-acts"><Button variant="primary" to="/data/request">{t('say.askAgain')}</Button></p> : null}
    </>
  );
}

/** A live access in one line: what it holds, its size by its name, its end. */
function Held({ access: a }: { access: AccessRow }) {
  const { t, i18n } = useTranslation('mine');
  const granted = useGranted();
  return (
    <>
      <Mark tone="live">{t('mark.live')}</Mark>
      <p className="ax-say ax-held">
        {t('say.held', { granted: capital(granted(a)), size: t(`pages:access.how.size.${a.size}.t`), date: dateOf(a.ends_on, i18n.language) })}
      </p>
    </>
  );
}

/** A request to change the live access, beside it: waiting (when it was sent, what it asks, when the answer is due) or
 *  declined (why, and when one may ask again). A question about it is the page's first block instead. */
function ChangeLine({ body }: { body: AccessBody }) {
  const { t, i18n } = useTranslation('mine');
  const lang = i18n.language;
  const granted = useGranted();
  const r = changing(body);
  if (r?.state === 'waiting') {
    const sized = r.wanted_size ? t('change.sizeNew', { size: t(`pages:access.how.size.${r.wanted_size}.t`) }) : t('change.sizeSame');
    return (
      <div className="ax-change-line">
        <Mark tone="wait">{t('change.mark.waiting')}</Mark>
        <p>{t('change.waiting', { sent: dateOf(r.created_at, lang), granted: granted(r), size: sized, due: r.due_on ? dateOf(r.due_on, lang) : '' })}</p>
      </div>
    );
  }
  if (r?.state === 'declined') {
    return (
      <div className="ax-change-line">
        <Mark tone="no">{t('change.mark.declined')}</Mark>
        <p>
          {t('say.reason', { reason: t(`pages:access.reasons.${r.reason || 'unclear'}.d`) })}{' '}
          {r.ask_again_on ? t('change.againOn', { date: dateOf(r.ask_again_on, lang) }) : t('change.againNow')}
        </p>
      </div>
    );
  }
  return null;
}

/** The line the staff asked, and the box to answer it: the request waits for the staff again. */
function Question({ request: r, change }: { request: RequestRow; change: boolean }) {
  const { t } = useTranslation('mine');
  const keep = useKeepAccess();
  const said = useRefusals();
  const id = useId();
  const [text, setText] = useState('');
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  return (
    <section className="ax-now" aria-labelledby={`${id}-h`}>
      <h2 id={`${id}-h`}>{t(change ? 'question.titleChange' : 'question.title')}</h2>
      {r.asked ? <q dir="auto">{r.asked}</q> : null}
      <form className="ax-answer" onSubmit={async (e) => {
        e.preventDefault(); setBusy(true); setError(null);
        try { keep(await accessApi.answer(text)); } catch (err) { setError(err); } finally { setBusy(false); }
      }}>
        <label htmlFor={id} className="ax-label">{t('question.label')}</label>
        <textarea id={id} dir="auto" rows={4} maxLength={MOST.answer} value={text} className="ax-textarea"
                  onChange={(e) => { setText(e.target.value); setError(null); }} />
        {said.field(error, 'answer') ? <p className="ax-error">{said.field(error, 'answer')}</p> : null}
        <Button variant="primary" type="submit" disabled={busy || !text.trim()} className="self-start">{t('question.send')}</Button>
        <Alerts lines={said.form(error, ['answer'])} />
      </form>
    </section>
  );
}

/** What a live access holds, in the order its holder uses it: for the API, the key first, then the use, then the
 *  database; for the database alone, its files first. */
function Holding({ access: a, keys }: { access: AccessRow; keys: UseQueryResult<Keys> }) {
  const said = useRefusals();
  const k = keys.data;
  if (!k) return keys.isError ? <Alerts lines={said.form(keys.error)} /> : <LinesSkeleton lines={4} />;
  const used = k.days.some((d) => d.calls > 0);
  const use = k.keys.length || used ? <Use keys={k} /> : null;
  const edition = a.data ? <Edition /> : null;
  const keyPart = <KeysPart access={a} keys={k} />;
  return a.api ? <>{keyPart}{use}{edition}</> : <>{edition}{keyPart}{use}</>;
}

/** A part of the page: its title on a rule, what it holds under it. */
function Part({ title, aside, children }: { title: string; aside?: ReactNode; children: ReactNode }) {
  const id = useId();
  return (
    <section className="ax-part" aria-labelledby={id}>
      <header><h2 id={id}>{title}</h2>{aside}</header>
      {children}
    </section>
  );
}

/** The keys: each live one as a row (its name, first characters, last day of use, ending it); a new one shown once, with
 *  a first call that already holds it; «مفتاح ثان», a quiet button that opens the small form. With no key yet, an API
 *  holder sees the form first, open. */
function KeysPart({ access: a, keys: k }: { access: AccessRow; keys: Keys }) {
  const { t, i18n } = useTranslation('mine');
  const lang = i18n.language;
  const client = useQueryClient();
  const said = useRefusals();
  // The new key lives here only, in this part's state: never in the query cache, gone with «حفظته» or the page.
  const [fresh, setFresh] = useState<NewKey | null>(null);
  const [making, setMaking] = useState(false);
  const [ending, setEnding] = useState<number | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const today = todayIso();
  const make = async (name: string) => {
    setBusy(true); setError(null);
    try {
      setFresh(await accessApi.makeKey(name.trim()));
      setMaking(false);
      void client.invalidateQueries({ queryKey: KEYS });
    } catch (e) { setError(e); } finally { setBusy(false); }
  };
  const drop = async (id: number) => {
    setBusy(true); setError(null);
    try {
      await accessApi.dropKey(id);
      setEnding(null);
      if (fresh?.id === id) setFresh(null);
      client.setQueryData<Keys>(KEYS, (x) => (x ? { ...x, keys: x.keys.filter((y) => y.id !== id) } : x));
      void client.invalidateQueries({ queryKey: KEYS });
    } catch (e) { setError(e); } finally { setBusy(false); }
  };
  const first = !k.keys.length && !fresh && a.api;
  const more = k.keys.length > 0 && k.keys.length < KEYS_MOST && !fresh;
  return (
    <Part title={t('keys.title')}>
      {fresh ? <Fresh fresh={fresh} access={a} onDone={() => setFresh(null)} /> : null}
      {first ? (
        <div className="ax-now">
          <h3>{t('keys.first')}</h3>
          <p className="ax-small">{t('keys.firstLead')}</p>
          <MakeKey busy={busy} label={t('keys.first')} onMake={make} />
        </div>
      ) : null}
      {k.keys.length ? (
        <ul className="ax-rows">
          {k.keys.map((key) => {
            const name = key.name || t('keys.default');
            return (
              <li key={key.id} className="ax-key">
                <span className="what">
                  <span className="ax-key-name"><b dir="auto">{name}</b><code dir="ltr">{key.prefix}…</code></span>
                  <small>
                    {!key.last_used_on ? t('keys.unused') : key.last_used_on === today ? t('keys.usedToday')
                      : t('keys.used', { date: dateOf(key.last_used_on, lang) })}
                  </small>
                </span>
                {ending === key.id ? null : (
                  <Button variant="quiet" onClick={() => setEnding(key.id)} aria-label={t('keys.endLabel', { name })}>{t('keys.end')}</Button>
                )}
                {ending === key.id ? (
                  <Confirm text={t('keys.endSure')} yes={t('keys.endYes')} no={t('keys.cancel')} busy={busy}
                           onYes={() => void drop(key.id)} onNo={() => setEnding(null)} />
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : !fresh && !first ? <p className="ax-small">{t('keys.none')}</p> : null}
      {(more || (!k.keys.length && !fresh && !a.api)) && making ? (
        <div className="ax-second">
          {more ? <p className="ax-small">{t('keys.secondLead')}</p> : null}
          <MakeKey busy={busy} label={t('keys.make')} onMake={make} onCancel={() => setMaking(false)} />
        </div>
      ) : null}
      <Alerts lines={said.form(error)} />
      {/* One row: the quiet way to a second key, and on a phone the way to the API's reads (a desk has them beside). */}
      <p className="ax-acts ax-keys-acts">
        {(more || (!k.keys.length && !fresh && !a.api)) && !making ? (
          <button type="button" className="ax-link" onClick={() => setMaking(true)}>{t(more ? 'keys.second' : 'keys.make')}</button>
        ) : null}
        {a.api ? <Link to="/data#api" className="ax-link ax-phone">{t('keys.reads')}</Link> : null}
      </p>
    </Part>
  );
}

/** The small form that makes a key: a name, optional. */
function MakeKey({ busy, label, onMake, onCancel }: { busy: boolean; label: string; onMake: (name: string) => void; onCancel?: () => void }) {
  const { t } = useTranslation('mine');
  const id = useId();
  const [name, setName] = useState('');
  return (
    <form className="ax-make" onSubmit={(e) => { e.preventDefault(); onMake(name); }}>
      <label htmlFor={id} className="ax-label">{t('keys.name')} <span>{t('keys.optional')}</span></label>
      <span className="row">
        <input id={id} value={name} onChange={(e) => setName(e.target.value)} maxLength={MOST.key} dir="auto"
               placeholder={t('keys.nameHint')} className="ax-input" autoFocus={Boolean(onCancel)} />
        <Button variant="primary" type="submit" disabled={busy}>{label}</Button>
      </span>
      {onCancel ? <Button variant="quiet" onClick={onCancel} className="self-start">{t('keys.cancel')}</Button> : null}
    </form>
  );
}

/** A new key, shown this once, with its copy button and a first call that already holds it; both go together. */
function Fresh({ fresh, access: a, onDone }: { fresh: NewKey; access: AccessRow; onDone: () => void }) {
  const { t, i18n } = useTranslation('mine');
  const origin = typeof window === 'undefined' ? '' : window.location.origin;
  const call = firstCall(origin, fresh.key, a, i18n.language);
  return (
    <div className="ax-fresh" role="status">
      <b>{t('keys.fresh')}</b>
      <code dir="ltr" className="key">{fresh.key}</code>
      <p>{t('keys.once')}</p>
      <span className="flex flex-wrap gap-2"><Copy text={fresh.key} label={t('keys.copy')} variant="secondary" /></span>
      <p className="ax-small">{t('keys.call')}</p>
      <span className="ax-example">
        <code dir="ltr" className="lb-code">{call}</code>
        <Copy text={call} label={t('keys.copyCall')} />
      </span>
      <Button onClick={onDone} className="self-start">{t('keys.done')}</Button>
    </div>
  );
}

/** A question asked inside the page, never in a browser's dialog. */
function Confirm({ text, yes, no, busy, onYes, onNo }: {
  text: string; yes: string; no: string; busy: boolean; onYes: () => void; onNo: () => void;
}) {
  return (
    <div className="ax-confirm" role="group" aria-label={yes}>
      <p>{text}</p>
      <span className="flex flex-wrap gap-2">
        <button type="button" disabled={busy} onClick={onYes} className="ax-danger">{yes}</button>
        <Button onClick={onNo}>{no}</Button>
      </span>
    </div>
  );
}

/** Today's calls and articles against their limits, the requests a minute beside them; the last 30 days as bars drawn
 *  left to right in both languages (hidden when nothing was used), their numbers one tap away. */
function Use({ keys: k }: { keys: Keys }) {
  const { t, i18n } = useTranslation('mine');
  const lang = i18n.language;
  const days = lastDays(k.days, todayIso());
  const most = Math.max(1, ...days.map((d) => d.calls));
  const total = days.reduce((n, d) => ({ calls: n.calls + d.calls, articles: n.articles + d.articles }), { calls: 0, articles: 0 });
  const used = k.days.filter((d) => d.calls || d.articles).slice().reverse();
  return (
    <Part title={t('use.title')}>
      <div className="ax-meters">
        {(['calls', 'articles'] as const).map((c) => (
          <div key={c} className="ax-meter">
            <span className="what">{t(`use.${c}`)}</span>
            <span className="n"><b>{count(k.today[c], lang)}</b> {t('use.of', { of: count(k.limits[c], lang) })}</span>
            <span className="bar" aria-hidden="true"><i style={{ width: `${share(k.today[c], k.limits[c])}%` }} /></span>
          </div>
        ))}
        <p className="ax-minute">{t('use.minute', { n: count(k.limits.minute, lang) })}</p>
      </div>
      {total.calls ? (
        <figure className="ax-chart">
          <figcaption>{t('use.days')}<span>{t('use.sum', { calls: count(total.calls, lang), articles: count(total.articles, lang) })}</span></figcaption>
          {/* Days run left to right on the Arabic page too, as every chart of the site does. */}
          <div dir="ltr" className="ax-bars">
            <span className="top" dir="auto">{count(most, lang)}</span>
            <svg viewBox="0 0 300 64" preserveAspectRatio="none" aria-hidden="true">
              {days.map((d, i) => {
                const h = d.calls ? Math.max(2, (d.calls / most) * 60) : 1;
                return <rect key={d.day} x={i * 10 + 1} y={64 - h} width={8} height={h} className={d.calls ? 'on' : 'off'} />;
              })}
            </svg>
            <span className="ends"><span dir="auto">{dateOf(days[0].day, lang)}</span><span dir="auto">{dateOf(days[days.length - 1].day, lang)}</span></span>
          </div>
          <details className="ax-numbers">
            <summary>{t('use.numbers')}</summary>
            <table>
              <thead><tr><th scope="col">{t('use.day')}</th><th scope="col">{t('use.calls')}</th><th scope="col">{t('use.articles')}</th></tr></thead>
              <tbody>
                {used.map((d) => <tr key={d.day}><th scope="row">{dateOf(d.day, lang)}</th><td>{count(d.calls, lang)}</td><td>{count(d.articles, lang)}</td></tr>)}
              </tbody>
            </table>
          </details>
        </figure>
      ) : null}
    </Part>
  );
}

/** The newest edition as two rows, its two large files, each taken through a ticket the browser then follows; the rest
 *  on demand, what each holds on /data, the receipt, and the line to take a file with the key from a program. */
function Edition() {
  const { t, i18n } = useTranslation('mine');
  const lang = i18n.language;
  const said = useRefusals();
  const manifest = useManifest();
  const m = manifest.data;
  const [error, setError] = useState<{ file: string; error: unknown } | null>(null);
  const [busy, setBusy] = useState('');
  const [receipt, setReceipt] = useState<string | null>(null);
  const origin = typeof window === 'undefined' ? '' : window.location.origin;
  const take = async (file: string) => {
    setBusy(file); setError(null);
    try {
      const { url } = await accessApi.ticket(file);
      if (file === 'RECEIPT.txt') {
        const r = await fetch(url);
        if (!r.ok) throw new ApiError(r.status, ((await r.json().catch(() => ({}))) as { errors?: [] }).errors ?? []);
        setReceipt(await r.text());
      } else {
        window.location.assign(url);
      }
    } catch (e) { setError({ file, error: e }); } finally { setBusy(''); }
  };
  const none = manifest.error instanceof ApiError && manifest.error.status === 404;
  const title = t('pages:access.edition.title');
  if (!m) {
    return (
      <Part title={title}>
        {manifest.isPending ? <LinesSkeleton lines={2} /> : <p className="ax-small">{none ? t('pages:access.edition.none') : t('pages:data.failed')}</p>}
      </Part>
    );
  }
  const files = DATA_FILES.filter((name) => m.files[name]);
  const row = (name: string) => (
    <li key={name} className="ax-file">
      <code dir="ltr">{name}</code>
      <span dir="ltr" className="size">{size(m.files[name].bytes)}</span>
      <Button onClick={() => void take(name)} disabled={busy === name} aria-label={t('edition.getLabel', { file: name })}>{t('edition.get')}</Button>
      {error?.file === name ? <Alerts lines={said.form(error.error)} /> : null}
    </li>
  );
  const script = examples(origin, '').edition;
  return (
    <Part title={title} aside={<span className="ax-part-aside">{t('edition.line', { date: dateOf(m.date, lang), size: size(editionBytes(m)) })}</span>}>
      <ul className="ax-rows">{files.filter((n) => BIG_FILES.includes(n)).map(row)}</ul>
      <details className="ax-fold">
        <summary>{t('edition.all', { n: files.length })}</summary>
        <ul className="ax-rows">{files.filter((n) => !BIG_FILES.includes(n)).map(row)}</ul>
      </details>
      <p className="ax-acts">
        <Link to="/data#download" className="ax-link">{t('edition.what')}</Link>
        <button type="button" className="ax-link" disabled={busy === 'RECEIPT.txt'} aria-expanded={receipt !== null}
                onClick={() => (receipt === null ? void take('RECEIPT.txt') : setReceipt(null))}>
          {t(receipt === null ? 'edition.receipt' : 'edition.receiptHide')}
        </button>
      </p>
      {error?.file === 'RECEIPT.txt' ? <Alerts lines={said.form(error.error)} /> : null}
      {receipt !== null ? <pre dir="auto" className="ax-pre">{receipt}</pre> : null}
      <p className="ax-small">{t('edition.script')}</p>
      <span className="ax-example"><code dir="ltr" className="lb-code">{script}</code><Copy text={script} /></span>
    </Part>
  );
}

/** At the foot, quietly: asking for a change (a live access with no request open), what was sent (not once the access
 *  ended), the terms accepted (with a live access or a request open), and ending the access. */
function Foot({ body: b, live, s }: { body: AccessBody; live: AccessRow | null; s: Standing }) {
  const { t, i18n } = useTranslation('mine');
  const r = b.request;
  const terms = live || s === 'waiting' || s === 'more' ? r?.terms : '';
  const rows = [
    live && mayChange(b) ? <ChangeAsk key="change" access={live} /> : null,
    r && s !== 'ended' ? <Sent key="sent" request={r} open={false} /> : null,
    terms ? (
      <p key="terms" className="ax-terms-line">
        {t('foot.terms', { date: dateOf(terms, i18n.language) })} <Link to="/data/terms">{t('foot.termsLink')}</Link>
      </p>
    ) : null,
    live ? <EndAccess key="end" /> : null,
  ].filter(Boolean);
  if (!rows.length) return null;
  return <div className="ax-foot">{rows}</div>;
}

/** «طلب تعديل»: what the access is to hold afterwards (the API, the database), a size, and why; sent, it waits for the
 *  staff like any request, and the access and its keys stay as they are until then. */
function ChangeAsk({ access: a }: { access: AccessRow }) {
  const { t } = useTranslation('mine');
  const keep = useKeepAccess();
  const said = useRefusals();
  const id = useId();
  const [open, setOpen] = useState(false);
  const empty: Change = { api: a.api, data: a.data, size: '', why: '' };
  const [f, setF] = useState<Change>(empty);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const set = <K extends keyof Change>(k: K, v: Change[K]) => { setF((x) => ({ ...x, [k]: v })); setError(null); };
  const send = async () => {
    // What the server would refuse is said before asking it; it checks again and has the last word.
    const local = checkChange(a, f);
    if (local.length) { setError(new ApiError(400, local.map(([field, code]) => ({ field, code })))); return; }
    setBusy(true); setError(null);
    try {
      keep(await accessApi.change(changeBody(f)));
      setOpen(false); setF(empty);
      window.scrollTo(0, 0);
    } catch (e) { setError(e); } finally { setBusy(false); }
  };
  if (!open) {
    return <button type="button" className="ax-foot-row" onClick={() => setOpen(true)}>{t('change.open')}</button>;
  }
  const err = (name: string) => said.field(error, name);
  const sizes = SIZES.filter((k) => k !== a.size || k === 'partner');
  const left = MOST.why - f.why.length;
  return (
    <form noValidate className="ax-change" aria-labelledby={`${id}-h`} onSubmit={(e) => { e.preventDefault(); void send(); }}>
      <h2 id={`${id}-h`}>{t('change.open')}</h2>
      <p className="ax-small">{t('change.lead')}</p>
      <fieldset className="ax-fieldset">
        <legend className="ax-legend">{t('change.holds')}</legend>
        <label className="ax-tick">
          <input type="checkbox" checked={f.api} onChange={(e) => set('api', e.target.checked)} />
          <span><b>{t('pages:access.form.wantsApi')}</b></span>
        </label>
        <label className="ax-tick">
          <input type="checkbox" checked={f.data} onChange={(e) => set('data', e.target.checked)} />
          <span><b>{t('pages:access.form.wantsData')}</b></span>
        </label>
        {err('wants') ? <p className="ax-error">{err('wants')}</p> : null}
      </fieldset>
      <fieldset className="ax-fieldset">
        <legend className="ax-legend">{t('change.size')}</legend>
        <div className="ax-choices stacked">
          <label>
            <input type="radio" name={`${id}-size`} checked={f.size === ''} onChange={() => set('size', '')} />
            <span>{t('change.keep', { size: t(`pages:access.how.size.${a.size}.t`) })}</span>
          </label>
          {sizes.map((k) => (
            <label key={k}>
              <input type="radio" name={`${id}-size`} checked={f.size === k} onChange={() => set('size', k)} />
              <span className="ax-size"><b>{t(`pages:access.how.size.${k}.t`)}</b><small>{t(`pages:access.how.size.${k}.d`)}</small></span>
            </label>
          ))}
        </div>
        {err('size') ? <p className="ax-error">{err('size')}</p> : null}
      </fieldset>
      <div className="flex flex-col gap-1.5">
        <label htmlFor={`${id}-why`} className="ax-label">{t('change.why')}</label>
        <textarea id={`${id}-why`} dir="auto" rows={4} maxLength={MOST.why} value={f.why} onChange={(e) => set('why', e.target.value)}
                  aria-invalid={err('why') ? true : undefined} aria-describedby={`${id}-hint ${id}-left`}
                  className={`ax-textarea ${err('why') ? 'bad' : ''}`} />
        <div className="ax-under">
          <p id={`${id}-hint`} className="ax-small">{t('change.whyHint')}</p>
          <p id={`${id}-left`} className={`ax-count ${left < 60 ? 'low' : ''}`} aria-live="polite">{t('change.left', { n: left })}</p>
        </div>
        {err('why') ? <p className="ax-error">{err('why')}</p> : null}
      </div>
      <Alerts lines={said.form(error, ['wants', 'wants_api', 'wants_data', 'size', 'why'])} />
      <span className="flex flex-wrap gap-2">
        <Button variant="primary" type="submit" disabled={busy}>{busy ? t('change.sending') : t('change.send')}</Button>
        <Button variant="quiet" onClick={() => { setOpen(false); setF(empty); setError(null); }}>{t('change.cancel')}</Button>
      </span>
    </form>
  );
}

/** Ending one's own access, asked inside the page: its keys end with it. */
function EndAccess() {
  const { t } = useTranslation('mine');
  const keep = useKeepAccess();
  const client = useQueryClient();
  const said = useRefusals();
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const end = async () => {
    setBusy(true); setError(null);
    try {
      keep(await accessApi.end());
      client.removeQueries({ queryKey: KEYS });
      window.scrollTo(0, 0);
    } catch (e) { setError(e); } finally { setBusy(false); setAsking(false); }
  };
  return (
    <div className="ax-end">
      {asking ? (
        <Confirm text={t('foot.endSure')} yes={t('foot.endYes')} no={t('foot.cancel')} busy={busy}
                 onYes={() => void end()} onNo={() => setAsking(false)} />
      ) : <button type="button" className="ax-foot-row danger" onClick={() => setAsking(true)}>{t('foot.end')}</button>}
      <Alerts lines={said.form(error)} />
    </div>
  );
}

/** On a desk, beside the key: the API's six reads with their addresses, its full description, and the shape of a
 *  refusal. A phone has one link to /data instead (in the keys' part). */
function ApiSide() {
  const { t } = useTranslation('mine');
  const id = useId();
  return (
    <aside className="ax-side" aria-labelledby={id}>
      <h2 id={id}>{t('api.title')}</h2>
      <p className="ax-small">{t('api.lead')}</p>
      <ul className="ax-reads">
        {READS.map(([k, method, address]) => (
          <li key={k}>
            <span>{t(`api.reads.${k}`)}</span>
            <span dir="ltr" className="addr"><b className="lb-get">{method}</b><code>{address}</code></span>
          </li>
        ))}
      </ul>
      <p className="ax-small">
        {t('api.openapi')}: <a href="/api/v1/openapi.yaml" dir="ltr" className="ax-mono">/api/v1/openapi.yaml</a>
      </p>
      <p className="ax-small">{t('api.errors')}</p>
      <pre dir="ltr" className="ax-shape">{'{"errors": [\n  {"field": "key",\n   "code": "ended"}\n]}'}</pre>
      <p className="ax-small">{t('api.limits')}</p>
      <Link to="/data#api" className="ax-link">{t('api.more')}</Link>
    </aside>
  );
}
