import { lazy, Suspense, useState, type CSSProperties } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Button, Page } from '@/shared/components/ui';
import { refuse, refused, staffDevice } from '@/shared/analytics/device';
import { api } from '@/shared/services/api';
import { usePageTitle } from '@/shared/services/title';
import { useSession } from '@/shared/stores/session';
import { useRegistration } from '@/features/accounts/registration';
import { useHashTarget } from './hash';
import { useT } from './strings';
import './privacy.css';

const Peek = lazy(() => import('@/features/corpus/reading/Peek'));

/**
 * /privacy, «ما نحفظ وإلى متى» (31 Oct 2026, written again to be exact and easier to read). What reaches
 * the site, where it stays, who sees it, until when, and how to take it or erase it (law 09.08, art. 5), written from
 * what the code does (the audit of 31 Oct 2026), not from what was meant. One sentence in the law's type answers first;
 * then the page's own question, «until when», drawn as a ruler: each thing kept a line from the moment it arrives to the
 * day it is erased, on one scale, the site's in the source's violet and the phone's in the green of «the document never
 * leaves your device»; «شنو كتدير؟» leaves lit the lines of what the reader does. Then each act in the margin as the
 * law numbers its articles, what the site counts (the analytics review, 15 Nov 2026: its measures as the server lists
 * them, GET /api/measure/, and «لا تحسبني»), who sees what, the three companies the data passes through, and the
 * rights, each with its article a tap away.
 */
type Act = 'read' | 'search' | 'keep' | 'write';
type At = 'now' | 'day' | 'week' | 'fortnight' | 'month' | 'quarter' | 'half' | 'year' | 'open';
/** Where a thing kept lives: on the site's server, or on the reader's own device, never sent. */
type Where = 'here' | 'phone';
type Kept = { id: string; act: Act; where: Where; at: At; part?: boolean };

/** Each moment as a share of the ruler: a day to a year on a logarithm (a day and two weeks far apart, six months and
 *  a year near), the moment it arrives and «بلا أجل» at its ends. */
const AT: Record<At, number> = { now: 0, day: 9, week: 33, fortnight: 42, month: 51, quarter: 65, half: 73, year: 82, open: 100 };
/** The moments the scale names; the start is each line's own dot. */
const TICKS: At[] = ['day', 'fortnight', 'month', 'quarter', 'half', 'year', 'open'];
/** A phone's ruler names fewer moments; a line with no end says so itself. */
const NARROW = new Set<At>(['day', 'month', 'year']);

/** What is kept, by what the reader does, until when (keep_promises, prune_search_logs, nginx's
 *  logrotate: 7 days since the analytics review, nightly.sh and pull-backup.sh: 14 dumps on the server, 30 on a second
 *  machine; the measures' events ANALYTICS_DAYS, said by GET /api/measure/, and their day counts); `part`: something
 *  stays past the mark (a search's results without its words). */
const KEPT: Kept[] = [
  { id: 'day', act: 'read', where: 'here', at: 'day' },
  { id: 'web', act: 'read', where: 'here', at: 'week' },
  { id: 'measured', act: 'read', where: 'here', at: 'quarter' },
  { id: 'counts', act: 'read', where: 'here', at: 'open' },
  { id: 'lastday', act: 'read', where: 'phone', at: 'open' },
  { id: 'backups', act: 'read', where: 'here', at: 'month' },
  { id: 'report', act: 'read', where: 'here', at: 'open' },
  { id: 'words', act: 'search', where: 'here', at: 'quarter', part: true },
  { id: 'recent', act: 'search', where: 'phone', at: 'open' },
  { id: 'saved', act: 'keep', where: 'phone', at: 'open' },
  { id: 'document', act: 'keep', where: 'phone', at: 'now' },
  { id: 'account', act: 'write', where: 'here', at: 'open' },
  // A request for the data (apps/opendata, forget_typed): its typed answers while the access lives and 12 months after,
  // 6 months after a decline; its kind, dates and decision stay.
  { id: 'access', act: 'write', where: 'here', at: 'open' },
  { id: 'declined', act: 'write', where: 'here', at: 'half', part: true },
  { id: 'deleted', act: 'write', where: 'here', at: 'now' },
  { id: 'edits', act: 'write', where: 'here', at: 'quarter' },
  { id: 'check', act: 'write', where: 'here', at: 'quarter' },
  { id: 'removed', act: 'write', where: 'here', at: 'quarter' },
  { id: 'reports', act: 'write', where: 'here', at: 'quarter' },
  { id: 'notices', act: 'write', where: 'here', at: 'half' },
  { id: 'ledger', act: 'write', where: 'here', at: 'year' },
  { id: 'left', act: 'write', where: 'here', at: 'open' },
];
const ACTS: Act[] = ['read', 'search', 'keep', 'write'];
/** Each act's paragraphs, and the ruler's line each one keeps. */
const ITEMS: Record<Act, { id: string; row?: string }[]> = {
  read: [{ id: 'day', row: 'day' }, { id: 'web', row: 'web' }, { id: 'counted', row: 'measured' }, { id: 'backups', row: 'backups' },
    { id: 'report', row: 'report' }, { id: 'word' }, { id: 'assistants' }],
  search: [{ id: 'words', row: 'words' }, { id: 'violence' }, { id: 'but' }, { id: 'recent', row: 'recent' }, { id: 'people' }],
  keep: [{ id: 'saved', row: 'saved' }, { id: 'tools' }, { id: 'reading' }, { id: 'offline' }, { id: 'document', row: 'document' }],
  write: [{ id: 'account', row: 'account' }, { id: 'written' }, { id: 'signin' }, { id: 'access', row: 'access' }, { id: 'media' },
    { id: 'mail' }, { id: 'check', row: 'check' }],
};

/** Who sees each thing a writer leaves: everyone, the topic's moderators, the site's team. */
const SEEN: [string, [boolean, boolean, boolean]][] = [
  ['public', [true, true, true]], ['waiting', [false, true, true]], ['reporter', [false, false, true]],
  ['email', [false, false, true]], ['anon', [false, false, true]],
];

const LAW = '/ma/loi/9-08/art_';
const RIGHTS: { id: string; art: number; to?: [string, string][]; href?: string }[] = [
  { id: 'know', art: 5 },
  { id: 'copy', art: 7, to: [['action', '/account/settings#data']] },
  { id: 'fix', art: 8, to: [['settings', '/account/settings#settings'], ['leave', '/account/settings#leave']] },
  { id: 'object', art: 9 },
  { id: 'complain', art: 28, href: 'https://www.cndp.ma' },
];

export default function PrivacyPage() {
  const { t } = useT();
  usePageTitle([t('privacy.title')]);
  const [peek, setPeek] = useState<string | null>(null);
  useHashTarget();
  const art = (n: number) => (
    <button type="button" className="pv-art" onClick={() => setPeek(`${LAW}${n}`)}>{t('privacy.article', { n })}</button>
  );
  return (
    <Page width="wide" className="pv">
      <header className="pv-head">
        <h1>{t('privacy.title')}</h1>
        <p className="lead">{t('privacy.lead')}</p>
        <p className="pv-plaque">{t('privacy.plaque')}</p>
        <p className="pv-draft">{t('privacy.draft')} <span>{t('privacy.changed')}</span></p>
      </header>
      <Ruler />
      <div className="pv-acts">{ACTS.map((a) => <ActPart key={a} act={a} />)}</div>
      <Counted />
      <Firms art={art} />
      <Rights art={art} />
      <Suspense fallback={null}>{peek ? <Peek to={peek} onClose={() => setPeek(null)} /> : null}</Suspense>
    </Page>
  );
}

/** «إلى متى»: every thing kept on one scale of time, a line from its arrival to its erasing; the reader's act leaves
 *  its own lines lit. */
function Ruler() {
  const { t } = useT();
  const [act, setAct] = useState<Act | null>(null);
  const { rows, days } = useKept();
  let i = 0;
  return (
    <section className="pv-ruler" aria-labelledby="pv-ruler-h">
      <div className="pv-ruler-head">
        <div>
          <h2 id="pv-ruler-h">{t('privacy.ruler.title')}</h2>
          <p>{t('privacy.ruler.lead')}</p>
        </div>
        <ul className="pv-key">
          <li data-where="here"><i />{t('privacy.ruler.here')}</li>
          <li data-where="phone"><i />{t('privacy.ruler.phone')}</li>
          <li data-where="part"><i />{t('privacy.ruler.part')}</li>
        </ul>
      </div>
      <div className="pv-ask">
        <span id="pv-ask">{t('privacy.ask.label')}</span>
        <div role="group" aria-labelledby="pv-ask" className="pv-chips">
          {([null, ...ACTS] as (Act | null)[]).map((a) => (
            <button key={a ?? 'all'} type="button" aria-pressed={act === a} onClick={() => setAct(a)}>
              {t(`privacy.ask.${a ?? 'all'}`)}
            </button>
          ))}
        </div>
      </div>
      <div className="pv-scale" aria-hidden="true">
        <span />
        <ol>
          {TICKS.map((at) => (
            <li key={at} data-at={at} data-narrow={NARROW.has(at) ? '' : undefined} style={{ '--x': `${AT[at]}%` } as CSSProperties}>
              {t(`privacy.ruler.ticks.${at}`)}
            </li>
          ))}
        </ol>
      </div>
      <ul className="pv-rows">
        {ACTS.map((a) => [
          <li key={a} className="pv-group" data-off={act && act !== a ? '' : undefined}>
            <a href={`#${a}`}>{t(`privacy.acts.${a}.head`)}</a>
            <span>{t(`privacy.acts.${a}.sub`)}</span>
          </li>,
          ...rows.filter((k) => k.act === a).map((k) => {
            const [what, when] = t(`privacy.rows.${k.id}`, { returnObjects: true, days }) as [string, string];
            return (
              <li key={k.id} className="pv-row" data-where={k.where} data-at={k.at} data-part={k.part ? '' : undefined}
                  data-off={act && act !== a ? '' : undefined}>
                <div className="pv-what"><b>{what}</b><span>{when}</span></div>
                <div className="pv-track" aria-hidden="true">
                  {TICKS.slice(0, -1).map((at) => <i key={at} className="pv-tick" style={{ '--x': `${AT[at]}%` } as CSSProperties} />)}
                  {k.part ? <span className="pv-rest" style={{ '--to': `${AT[k.at]}%` } as CSSProperties} /> : null}
                  <span className="pv-bar" style={{ '--to': `${AT[k.at]}%`, '--i': i++ } as CSSProperties} />
                  {/* On a desk the time stands where its line ends: past its ring, or on the line when it has none. */}
                  <span className="pv-end" style={{ '--to': `${AT[k.at]}%` } as CSSProperties}>{when}</span>
                </div>
              </li>
            );
          }),
        ])}
      </ul>
    </section>
  );
}

/** An act in the margin, as the law numbers its articles: the answer in one sentence, then what is kept, each with its
 *  line's time. */
function ActPart({ act }: { act: Act }) {
  const { t } = useT();
  const k = `privacy.acts.${act}`;
  const care = act === 'keep' ? t(`${k}.care`, { returnObjects: true }) as string[] : [];
  // Sign-up as the server has it (REGISTRATION_OPEN): the page never says closed while it is open, nor the reverse.
  const closed = useRegistration().data?.open === false;
  const { rows, days } = useKept();
  return (
    <section id={act} className="pv-act" data-act={act} aria-labelledby={`pv-${act}`}>
      <div className="pv-margin">
        <h2 id={`pv-${act}`}>{t(`${k}.head`)}</h2>
        <span>{t(`${k}.sub`)}</span>
        {act === 'keep' ? <span className="pv-lock"><Lock />{t(`${k}.lock`)}</span> : null}
      </div>
      <div className="pv-body">
        <p className="pv-answer">{t(act === 'write' && closed ? `${k}.answerClosed` : `${k}.answer`)}</p>
        <ul className="pv-items">
          {ITEMS[act].map(({ id, row }) => {
            const kept = row ? rows.find((x) => x.id === row) : undefined;
            return (
              <li key={id} className="pv-item">
                <div>
                  <h3>{t(`${k}.items.${id}.t`)}</h3>
                  <p>{t(`${k}.items.${id}.d`)}</p>
                </div>
                {kept ? <When kept={kept} days={days} /> : null}
              </li>
            );
          })}
        </ul>
        {care.length ? <ul className="pv-care">{care.map((c) => <li key={c}>{c}</li>)}</ul> : null}
        {act === 'read' ? <p className="pv-not">{t(`${k}.not`)}</p> : null}
        {act === 'write' ? <Who /> : null}
      </div>
    </section>
  );
}

/** A thing's time beside it, drawn as its line is on the ruler. */
function When({ kept, days }: { kept: Kept; days?: number }) {
  const { t } = useT();
  const [, when] = t(`privacy.rows.${kept.id}`, { returnObjects: true, days }) as [string, string];
  return <span className="pv-when" data-where={kept.where}><i aria-hidden="true" />{when}</span>;
}

/** What the server says of its measures (registry.public): how long an event is kept, and each measure. */
type Measures = { days: number; measures: { name: string; category: string; props: string[] }[] };

function useMeasures() {
  return useQuery({ queryKey: ['measures'], queryFn: () => api<Measures>('/measure/'), staleTime: 3600_000 });
}

/** The ruler's rows, the events' line ending where the server keeps them; until it says, without that line. */
function useKept(): { rows: Kept[]; days?: number } {
  const days = useMeasures().data?.days;
  if (!days) return { rows: KEPT.filter((k) => k.id !== 'measured') };
  const at: At = days <= 1 ? 'day' : days <= 7 ? 'week' : days <= 14 ? 'fortnight' : days <= 31 ? 'month' : days <= 92 ? 'quarter'
    : days <= 183 ? 'half' : days <= 366 ? 'year' : 'open';
  return { rows: KEPT.map((k) => (k.id === 'measured' ? { ...k, at } : k)), days };
}

/** «ما نعدّه»: the promise, every measure the server takes (its sentence from the words, by its name with «_» for
 *  «.»; a measure the words do not know shows its name, and test_privacy_page.py fails), what the phone keeps for it,
 *  the country, and «لا تحسبني». */
function Counted() {
  const { t } = useT();
  const q = useMeasures();
  const days = q.data?.days;
  const list = q.data?.measures ?? [];
  const groups = [...new Set(list.map((m) => m.category))];
  return (
    <section id="counted" className="pv-count" aria-labelledby="pv-count-h">
      <header className="pv-part-head">
        <h2 id="pv-count-h">{t('privacy.counted.title')}</h2>
        <p>{t('privacy.counted.lead')}</p>
      </header>
      <div className="pv-count-sheet">
        <p className="pv-answer">{t('privacy.counted.answer')}</p>
        <ul className="pv-promise">
          {(t('privacy.counted.promise', { returnObjects: true }) as string[]).map((line) => <li key={line}>{line}</li>)}
          {days ? <li>{t('privacy.counted.kept', { days })}</li> : null}
        </ul>
        <h3>{t('privacy.counted.list')}</h3>
        {q.isError ? <p className="pv-small">{t('privacy.counted.noList')}</p> : null}
        {groups.map((c) => (
          <div key={c} className="pv-measures">
            <h4>{t(`privacy.counted.categories.${c}`, { defaultValue: c })}</h4>
            <ul>
              {list.filter((m) => m.category === c).map((m) => (
                <li key={m.name} className="pv-measure">
                  <code dir="ltr">{m.name}</code>
                  <p>{t(`privacy.measures.${m.name.replaceAll('.', '_')}`, { defaultValue: m.name })}</p>
                  {m.props.length ? <p className="pv-props">{t('privacy.counted.carries')} <span dir="ltr">{m.props.join(' · ')}</span></p> : null}
                </li>
              ))}
            </ul>
          </div>
        ))}
        <p className="pv-device"><span className="pv-when" data-where="phone"><i aria-hidden="true" />{t('privacy.ruler.phone')}</span>{t('privacy.counted.phone')}</p>
        <p className="pv-not">{t('privacy.counted.country')}</p>
        <NotMe />
      </div>
    </section>
  );
}

/** «لا تحسبني»: this device sends no measure, and the day kept for them goes (shared/analytics/device.ts). Global
 *  Privacy Control does the same without it. */
function NotMe() {
  const { t } = useT();
  // Read from the device once mounted: the prerender has none.
  const [off, setOff] = useState(() => typeof window !== 'undefined' && refused());
  const gpc = typeof navigator !== 'undefined' && (navigator as Navigator & { globalPrivacyControl?: boolean }).globalPrivacyControl === true;
  const staff = typeof window !== 'undefined' && staffDevice();
  const state = off ? 'off' : gpc ? 'gpcOn' : staff ? 'staff' : 'on';
  return (
    <div className="pv-switch">
      <Button variant={off ? 'primary' : 'secondary'} aria-pressed={off} onClick={() => { refuse(!off); setOff(!off); }}>
        <svg aria-hidden="true" width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="1" y="1" width="16" height="16" rx="4" />{off ? <path d="M5 9.5l3 3 5-6" /> : null}
        </svg>
        {t('privacy.counted.switch')}
      </Button>
      <p aria-live="polite">{t(`privacy.counted.${state}`)}</p>
      <p className="pv-small">{t('privacy.counted.gpc')}</p>
    </div>
  );
}

/** Who sees what a writer leaves. */
function Who() {
  const { t } = useT();
  const cols = ['all', 'mods', 'team'] as const;
  return (
    <div className="pv-who">
      <h3>{t('privacy.who.title')}</h3>
      <table>
        <thead>
          <tr><td />{cols.map((c) => <th key={c} scope="col">{t(`privacy.who.cols.${c}`)}</th>)}</tr>
        </thead>
        <tbody>
          {SEEN.map(([row, sees]) => (
            <tr key={row}>
              <th scope="row">{t(`privacy.who.rows.${row}`)}</th>
              {sees.map((yes, i) => (
                <td key={cols[i]}><i className={yes ? 'yes' : 'no'} aria-hidden="true" /><span className="pv-sr">{t(yes ? 'privacy.who.yes' : 'privacy.who.no')}</span></td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <p>{t('privacy.who.note')}</p>
    </div>
  );
}

/** The three companies the data passes through, as the thirds of one sheet (Resend since 3 Nov 2026, the letters); the
 *  check's third keeps the form's «/privacy#check». */
function Firms({ art }: { art: (n: number) => React.ReactNode }) {
  const { t } = useT();
  return (
    <section id="out" className="pv-out" aria-labelledby="pv-out-h">
      <header className="pv-part-head">
        <h2 id="pv-out-h">{t('privacy.out.title')}</h2>
        <p>{t('privacy.out.lead')}</p>
      </header>
      <div className="pv-firms">
        {(['cloudflare', 'anthropic', 'resend'] as const).map((f) => (
          <article key={f} id={f === 'anthropic' ? 'check' : undefined} className="pv-firm">
            <h3><span dir="ltr">{t(`privacy.out.${f}.name`)}</span>{f === 'anthropic' ? art(44) : null}</h3>
            <dl>
              {(['when', 'what', 'why'] as const).map((x) => (
                <div key={x}><dt>{t(`privacy.out.labels.${x}`)}</dt><dd>{t(`privacy.out.${f}.${x}`)}</dd></div>
              ))}
            </dl>
          </article>
        ))}
      </div>
      <p className="pv-nobody">{t('privacy.out.nobody')}</p>
    </section>
  );
}

/** The rights law 09.08 gives, each with its article and what one does to use it. */
function Rights({ art }: { art: (n: number) => React.ReactNode }) {
  const { t } = useT();
  const signedIn = useSession((s) => s.tokens !== null);
  const contact = useQuery({ queryKey: ['about'], queryFn: () => api<{ contact: string }>('/open/about/'), staleTime: 3600_000 }).data?.contact;
  return (
    <section id="rights" className="pv-rights" aria-labelledby="pv-rights-h">
      <header className="pv-part-head">
        <h2 id="pv-rights-h">{t('privacy.rights.title')}</h2>
        <p>{t('privacy.rights.lead')}</p>
      </header>
      <ul>
        {RIGHTS.map((r) => (
          <li key={r.id} className="pv-right">
            <h3>{t(`privacy.rights.${r.id}.name`)}{art(r.art)}</h3>
            <p>{t(`privacy.rights.${r.id}.text`)}</p>
            {(signedIn && r.to) || r.href ? (
              <span className="pv-do">
                {signedIn ? r.to?.map(([label, to]) => <Link key={label} to={to}>{t(`privacy.rights.${r.id}.${label}`)}</Link>) : null}
                {r.href ? <a href={r.href} target="_blank" rel="noopener noreferrer">{t(`privacy.rights.${r.id}.action`)}</a> : null}
              </span>
            ) : null}
          </li>
        ))}
      </ul>
      <p className="pv-reader">{t('privacy.rights.reader')}</p>
      {!signedIn ? <p className="pv-small">{t('privacy.rights.signedOut')}</p> : null}
      {contact ? <p className="pv-small">{t('privacy.rights.contact')} <a href={`mailto:${contact}`} dir="ltr">{contact}</a></p> : null}
    </section>
  );
}

const Lock = () => (
  <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="5" y="11" width="14" height="10" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3" />
  </svg>
);
