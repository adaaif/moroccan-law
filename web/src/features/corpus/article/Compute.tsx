import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { todayIso } from '@/shared/services/today';
import { useRateOn } from '@/topics/kit/api';
import { scaleTax, slices } from '@/topics/tax/rules/income';
import { endOfContract, noticeOf, stairs, startFor, HOURS_MONTH, type Category } from '@/topics/work/rules/end';
import type { Citing } from './Cites';
import './compute.css';
import '@/shared/locales/pages';

type Kind = 'severance' | 'notice' | 'scale';
const KIND: Record<string, Kind> = {
  '/ma/loi/65-99/art_53': 'severance',
  '/ma/decret/2-04-469/art_1': 'notice',
  '/ma/code/cgi/art_73': 'scale',
};

/** A line of the article, found in its words as the page drew them: the first element (or the `nth`) whose text
 *  matches, in Arabic and in the official French. Never guessed: a line not found is not lit, and not quoted. */
type Line = { ar: RegExp; fr?: RegExp; nth?: number };
const LINES: Record<Kind, Record<string, Line>> = {
  severance: {
    96: { ar: /(^|\D)96\s*ساعة/, fr: /96 heures/ }, 144: { ar: /(^|\D)144\s*ساعة/, fr: /144 heures/ },
    192: { ar: /(^|\D)192\s*ساعة/, fr: /192 heures/ }, 240: { ar: /(^|\D)240\s*ساعة/, fr: /240 heures/ },
  },
  notice: {
    cadre_under1: { ar: /أقل من سنة/, nth: 0 }, cadre_1to5: { ar: /من سنة إلى/, nth: 0 }, cadre_over5: { ar: /أكثر من/, nth: 0 },
    worker_under1: { ar: /أقل من سنة/, nth: 1 }, worker_1to5: { ar: /من سنة إلى/, nth: 1 }, worker_over5: { ar: /أكثر من/, nth: 1 },
  },
  scale: {},
};
// The scale's lines by their rate («10%»), the exempt one by its word; the first of each, in part I.
const scaleLine = (rate: number): Line => rate
  ? { ar: new RegExp(`(^|[^\\d.,])${rate}\\s*[%٪]`), fr: new RegExp(`(^|[^\\d.,])${rate}\\s*%`) }
  : { ar: /معفا/, fr: /exonér/ };

/** «احسبها بهذه المادة» (HM29 of the hard-moment review): under the few articles that set a figure, the reader's
 *  numbers light the very line of the law that applies, the amount beside it, from the topic's own rules (work's end of
 *  a contract: art. 53's staircase, the notice decree's table; tax's scale slice by slice) and its rates on today's
 *  date. The tool it borrows from says what it says: not reviewed yet, until a person checks it. */
export default function Compute({ path, eid, tool }: { path: string; eid: string; tool: Citing }) {
  const kind = KIND[path];
  const { t, i18n } = useTranslation();
  const [open, setOpen] = useState(true);
  if (!kind) return null;
  return (
    <section className="cp" aria-labelledby={`cp-${eid}`} data-noprint>
      <button type="button" id={`cp-${eid}`} className="cp-head" aria-expanded={open} onClick={() => setOpen(!open)}>
        <CalcIcon />
        <span>{t('pages:articleUse.compute.title')}</span>
        <span className="cp-lead">{t(`pages:articleUse.compute.lead.${kind}`)}</span>
      </button>
      {open ? (
        <>
          {kind === 'severance' ? <Severance eid={eid} /> : kind === 'notice' ? <Notice eid={eid} /> : <Scale eid={eid} />}
          <p className="cp-note">
            {t('pages:articleUse.compute.full')}{' '}
            <Link to={tool.path}>{(i18n.language === 'fr' && tool.title.fr) || tool.title.ar}</Link>
          </p>
        </>
      ) : null}
    </section>
  );
}

const money = (lang: string) => new Intl.NumberFormat(lang === 'fr' ? 'fr-MA' : 'ar-MA', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const whole = (lang: string) => new Intl.NumberFormat(lang === 'fr' ? 'fr-MA' : 'ar-MA', { maximumFractionDigits: 0 });
/** A number as typed: «4500», «4.500», «4 500,50», «7,5». */
const parse = (s: string) => {
  const v = s.replace(/[\s\u00a0\u202f]/g, '').replace(/[\u0660-\u0669]/g, (d) => String(d.charCodeAt(0) - 0x660));
  const n = Number(/,\d{1,2}$/.test(v) ? v.replace(/\./g, '').replace(',', '.') : /^\d{1,3}(\.\d{3})+$/.test(v) ? v.replace(/\./g, '') : v.replace(',', '.'));
  return Number.isFinite(n) && n > 0 ? n : 0;
};

/** Art. 53: years and a monthly wage; each band's line lit with the years it covers, its hours and dirhams; the
 *  indemnity as the end-of-contract tool counts it (art. 56's hour, 191 hours a month). */
function Severance({ eid }: { eid: string }) {
  const { t, i18n } = useTranslation();
  const [years, setYears] = useState('');
  const [wage, setWage] = useState('');
  const day = todayIso();
  const smig = useRateOn('work', 'smig', day);
  const smag = useRateOn('work', 'smag', day);
  const notice = useRateOn('work', 'notice', day);
  const service = Math.round(parse(years) * 12);
  const monthly = parse(wage);
  const ready = Boolean(smig && smag && notice && service > 0 && monthly > 0);
  const severance = ready && smig && smag && notice ? endOfContract({
    start: startFor(day, service), end: day, category: 'employee', farm: false, monthly, noticeGiven: false, leaveDays: 0,
    delegate: false, ending: 'dismissed',
  }, { notice, smigHour: smig.hour, smagDay: smag.day }).find((l) => l.key === 'severance') : undefined;
  // The staircase by band: the months each line of the article covers and the hours it gives.
  const bands = useMemo(() => {
    const out = new Map<number, { months: number; hours: number }>();
    for (const s of ready ? stairs(service) : []) {
      const b = out.get(s.band) ?? { months: 0, hours: 0 };
      out.set(s.band, { months: b.months + s.months, hours: b.hours + s.hours });
    }
    return out;
  }, [ready, service]);
  const on = severance?.applies ? [...bands.keys()].map(String) : [];
  const quotes = useLines(eid, LINES.severance, on, on.at(-1) ?? null);
  const m = money(i18n.language);
  const hourly = Number(severance?.detail.hourly ?? 0);
  return (
    <>
      <div className="cp-inputs">
        <Field label={t('pages:articleUse.compute.years')} hint={t('pages:articleUse.compute.yearsHint')} value={years} onChange={setYears} />
        <Field label={t('pages:articleUse.compute.wage')} hint={t('pages:articleUse.compute.wageHint')} value={wage} onChange={setWage} />
      </div>
      {severance && !severance.applies ? <p className="cp-why">{t('pages:articleUse.compute.underSix')}</p> : null}
      {severance?.applies ? (
        <>
          <ol className="cp-lines">
            {[96, 144, 192, 240].map((band) => {
              const b = bands.get(band);
              return (
                <li key={band} className={b ? 'is-on' : ''}>
                  <q>{quotes[band] ?? t('pages:articleUse.compute.band', { hours: band })}</q>
                  {b ? (
                    <span className="cp-fig">
                      {t('pages:articleUse.compute.bandFig', { span: span(b.months, t), hours: whole(i18n.language).format(b.hours) })}
                      {/* The rule's amount shared by the band's hours: the lines add up to the total it gives. */}
                      <b>{t('pages:articleUse.compute.dh', { amount: whole(i18n.language).format((severance.amount * b.hours) / Number(severance.detail.hours)) })}</b>
                    </span>
                  ) : <span className="cp-fig cp-not">{t('pages:articleUse.compute.notReached')}</span>}
                </li>
              );
            })}
          </ol>
          <p className="cp-total">
            <span>{t('pages:articleUse.compute.severanceTotal', { hours: whole(i18n.language).format(Number(severance.detail.hours)), hourly: m.format(hourly) })}</span>
            <b>{t('pages:articleUse.compute.dh', { amount: m.format(severance.amount) })}</b>
          </p>
          <p className="cp-how">
            {t('pages:articleUse.compute.hourly', { hours: HOURS_MONTH })}
            {severance.detail.floored ? <> {t('pages:articleUse.compute.floored', { smig: m.format(smig!.hour) })}</> : null}
          </p>
          <p className="cp-how">
            <Link to={`/topics/work/tools/end?y=${Math.floor(service / 12)}&m=${service % 12}&w=${monthly}`}>{t('pages:articleUse.compute.wholeEnd')}</Link>
          </p>
        </>
      ) : null}
    </>
  );
}

/** Decree 2.04.469, art. 1: who you are and your years light the row of the table that applies; the notice, and what
 *  it costs when not given (Labour Code art. 51), as the end-of-contract tool counts it. */
function Notice({ eid }: { eid: string }) {
  const { t, i18n } = useTranslation();
  const [who, setWho] = useState<Category>('employee');
  const [years, setYears] = useState('');
  const [wage, setWage] = useState('');
  const day = todayIso();
  const smig = useRateOn('work', 'smig', day);
  const smag = useRateOn('work', 'smag', day);
  const rates = useRateOn('work', 'notice', day);
  const service = Math.round(parse(years) * 12);
  const monthly = parse(wage);
  const got = rates && service > 0 ? noticeOf(who, service, rates) : null;
  // The decree's row, by the same thresholds noticeOf reads (under a year, one to five, over five): to light it, not to count.
  const row = got ? `${who === 'cadre' ? 'cadre' : 'worker'}_${service < 12 ? 'under1' : service <= 60 ? '1to5' : 'over5'}` : null;
  const quotes = useLines(eid, LINES.notice, row ? [row] : [], row);
  const line = got && rates && smig && smag && monthly > 0 ? endOfContract({
    start: startFor(day, service), end: day, category: who, farm: false, monthly, noticeGiven: false, leaveDays: 0,
    delegate: false, ending: 'dismissed',
  }, { notice: rates, smigHour: smig.hour, smagDay: smag.day }).find((l) => l.key === 'notice') : undefined;
  return (
    <>
      <div className="cp-chips" role="group" aria-label={t('pages:articleUse.compute.who')}>
        {(['cadre', 'employee'] as const).map((k) => (
          <button key={k} type="button" aria-pressed={who === k} onClick={() => setWho(k)}>{t(`pages:articleUse.compute.cat.${k}`)}</button>
        ))}
      </div>
      <div className="cp-inputs">
        <Field label={t('pages:articleUse.compute.years')} hint={t('pages:articleUse.compute.yearsHint')} value={years} onChange={setYears} />
        <Field label={t('pages:articleUse.compute.wage')} hint={t('pages:articleUse.compute.optional')} value={wage} onChange={setWage} />
      </div>
      {got && row ? (
        <>
          <ol className="cp-lines"><li className="is-on">
            {quotes[row] ? <q>{quotes[row]}</q> : null}
            <span className="cp-fig"><b>{got.months ? t('pages:articleUse.compute.months', { count: got.months }) : t('pages:articleUse.compute.days', { count: got.days })}</b></span>
          </li></ol>
          {line ? (
            <p className="cp-total">
              <span>{t('pages:articleUse.compute.noticeTotal')}</span>
              <b>{t('pages:articleUse.compute.dh', { amount: money(i18n.language).format(line.amount) })}</b>
            </p>
          ) : null}
        </>
      ) : null}
    </>
  );
}

/** CGI art. 73-I: an income a year (or a month, times twelve) lights each slice of the scale it reaches, the tax of
 *  each beside its line, the slice it ends in strongest; the tax is the scale's alone, before art. 74's deduction. */
function Scale({ eid }: { eid: string }) {
  const { t, i18n } = useTranslation();
  const [amount, setAmount] = useState('');
  const [per, setPer] = useState<'month' | 'year'>('month');
  const sc = useRateOn('tax', 'scale', todayIso());
  const income = parse(amount) * (per === 'month' ? 12 : 1);
  const r = sc && income > 0 ? scaleTax(income, sc) : null;
  const reached = r ? r.slices.filter((s) => income > s.from) : [];
  const lines = useMemo(() => Object.fromEntries((sc ? slices(sc) : []).map((s) => [String(s.rate), scaleLine(s.rate)])), [sc]);
  const quotes = useLines(eid, lines, reached.map((s) => String(s.rate)), reached.at(-1) ? String(reached.at(-1)!.rate) : null);
  const m = money(i18n.language);
  return (
    <>
      <div className="cp-chips" role="group" aria-label={t('pages:articleUse.compute.per')}>
        {(['month', 'year'] as const).map((k) => (
          <button key={k} type="button" aria-pressed={per === k} onClick={() => setPer(k)}>{t(`pages:articleUse.compute.perOf.${k}`)}</button>
        ))}
      </div>
      <div className="cp-inputs">
        <Field label={t('pages:articleUse.compute.income')} hint={t('pages:articleUse.compute.incomeHint')} value={amount} onChange={setAmount} />
      </div>
      {r ? (
        <>
          <ol className="cp-lines">
            {r.slices.map((s) => (
              <li key={s.from} className={income > s.from ? 'is-on' : ''}>
                {quotes[String(s.rate)] ? <q>{quotes[String(s.rate)]}</q> : null}
                {income > s.from ? (
                  <span className="cp-fig">
                    {s.rate ? t('pages:articleUse.compute.slice', { base: m.format(s.base), rate: s.rate }) : t('pages:articleUse.compute.exempt', { base: m.format(s.base) })}
                    <b>{t('pages:articleUse.compute.dh', { amount: m.format(s.tax) })}</b>
                  </span>
                ) : <span className="cp-fig cp-not">{t('pages:articleUse.compute.notReached')}</span>}
              </li>
            ))}
          </ol>
          <p className="cp-total">
            <span>{t('pages:articleUse.compute.scaleTotal', { month: m.format(r.tax / 12) })}</span>
            <b>{t('pages:articleUse.compute.dhYear', { amount: m.format(r.tax) })}</b>
          </p>
          <p className="cp-how">{t('pages:articleUse.compute.scaleNote')}</p>
        </>
      ) : null}
    </>
  );
}

function Field({ label, hint, value, onChange }: { label: string; hint: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="cp-field">
      <span>{label}</span>
      <input type="text" inputMode="decimal" dir="ltr" autoComplete="off" value={value} onChange={(e) => onChange(e.target.value)} />
      <small>{hint}</small>
    </label>
  );
}

const span = (months: number, t: (k: string, o?: Record<string, unknown>) => string) => {
  const y = Math.floor(months / 12), m = months % 12;
  return [y ? t('pages:articleUse.compute.yearsN', { count: y }) : '', m ? t('pages:articleUse.compute.months', { count: m }) : '']
    .filter(Boolean).join(t('pages:articleUse.compute.and'));
};

const NAME = 'compute-line';
const NOW = 'compute-now';
/** The browser's own highlight over the article's lines (no element added to the law React draws), written once: the
 *  people's wash for the lines that count, their saffron under the one the reader's numbers end on. */
function style() {
  if (document.getElementById(NAME)) return;
  const s = document.createElement('style');
  s.id = NAME;
  s.textContent = `::highlight(${NAME}){background-color:var(--color-people-wash);color:var(--color-ink)}`
    + `::highlight(${NOW}){background-color:var(--color-people-wash);color:var(--color-ink);text-decoration:underline 3px var(--color-people-fill);text-underline-offset:6px}`;
  document.head.appendChild(s);
}

/** The article's lines the keys name, read from its words as drawn (they come late when a row of dots loads its own
 *  setting); the `on` ones lit, `now` the most; their words returned for the answer to quote, in the reader's first
 *  language when the page shows the official French first. */
function useLines(eid: string, lines: Record<string, Line>, on: string[], now: string | null): Record<string, string> {
  const [quotes, setQuotes] = useState<Record<string, string>>({});
  const key = on.join(',');
  useEffect(() => {
    const article = document.getElementById(eid);
    if (!article) return undefined;
    const registry = (CSS as unknown as { highlights?: Map<string, unknown> }).highlights;
    const HighlightCtor = (window as unknown as { Highlight?: new (...r: Range[]) => unknown }).Highlight;
    const read = () => {
      const roots = [...article.querySelectorAll<HTMLElement>('div[lang]')].filter((d) => d.lang === 'ar' || d.lang === 'fr');
      const found: Record<string, HTMLElement[]> = {};
      for (const root of roots) {
        const fr = root.lang === 'fr';
        const blocks = [...root.querySelectorAll<HTMLElement>('p, span.flex')];
        for (const [k, line] of Object.entries(lines)) {
          const re = fr ? line.fr : line.ar;
          if (!re) continue;
          const hits = blocks.filter((b) => re.test(b.textContent ?? ''));
          const inner = hits.filter((b) => !hits.some((o) => o !== b && b.contains(o)));
          const el = inner[line.nth ?? 0];
          if (el && (line.nth === undefined || inner.length > line.nth)) (found[k] ??= []).push(el);
        }
      }
      const said: Record<string, string> = {};
      for (const [k, els] of Object.entries(found)) {
        // The law's no-break spaces stay: «40 000» keeps its groups together in a right-to-left line (HM14).
        said[k] = (els[0].textContent ?? '').replace(/^\s*[-–—٠•]\s*/, '').replace(/[.…]{3,}/g, ' … ').replace(/[ \t\r\n]+/g, ' ').trim();
      }
      setQuotes((q) => (JSON.stringify(q) === JSON.stringify(said) ? q : said));
      if (!registry || !HighlightCtor) return;
      style();
      const range = (el: HTMLElement) => { const r = new Range(); r.selectNodeContents(el); return r; };
      registry.set(NAME, new HighlightCtor(...on.filter((k) => k !== now).flatMap((k) => (found[k] ?? []).map(range))));
      registry.set(NOW, new HighlightCtor(...(now ? found[now] ?? [] : []).map(range)));
    };
    read();
    const watch = new MutationObserver(() => read());
    watch.observe(article, { childList: true, subtree: true });
    return () => {
      watch.disconnect();
      registry?.delete(NAME);
      registry?.delete(NOW);
    };
  }, [eid, lines, key, now]); // eslint-disable-line react-hooks/exhaustive-deps
  return quotes;
}

const CalcIcon = () => (
  <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
    <rect x="5" y="3" width="14" height="18" rx="2" /><path d="M8 7h8M8 12h.01M12 12h.01M16 12h.01M8 16h.01M12 16h.01M16 16h.01" />
  </svg>
);
