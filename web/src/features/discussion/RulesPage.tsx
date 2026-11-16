import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Page } from '@/shared/components/ui';
import { api } from '@/shared/services/api';
import { usePageTitle } from '@/shared/services/title';
import { REASONS, RULES, type Rule } from './discussion.api';
import { useHashTarget } from './hash';
import { useT } from './strings';
import './privacy.css';
import './rules.css';

type Month = { month: string; contributions: number; held: number; reports: Record<string, number>;
               acts: Record<string, number>; pauses: number; appeals: number;
               checks: Record<'publish' | 'return' | 'hold' | 'unavailable', number>; overturned: number };

/** What keeps each rule before anyone reads it (holds.py), the model's check (check.py, all seven) and readers'
 *  reports (review.REASON_RULE: none names «honest»). */
type Guard = 'fixed' | 'check' | 'report';
const GUARDS: Record<Rule, Guard[]> = {
  privacy: ['fixed', 'check', 'report'], respect: ['fixed', 'check', 'report'], soliciting: ['fixed', 'check', 'report'],
  lawful: ['check', 'report'], decent: ['check', 'report'], on_topic: ['check', 'report'], honest: ['check'],
};
const FIXED = new Set<Rule>(['privacy', 'respect', 'soliciting']);
/** The sections after the road, each in the margin as on /privacy. */
const PARTS = ['moderators', 'votes', 'edit', 'explain', 'yours'] as const;

/**
 * /rules, «قواعد النقاش» (29 Oct 2026; drawn again on 31 Oct 2026 from an audit of the code, as /privacy
 * was). The seven rules set as the discussion's own law, numbered in the margin in the law's type,
 * each with what guards it: the fixed patterns before any reading, the model's check, readers' reports. Then the road
 * a post travels, drawn as a route: sent, the patterns, the check, and its three ways (published, back to its writer,
 * waiting for a moderator, who publishes, sends back or removes, and an appeal decided by someone else). Then who
 * moderates, «مفيد» and points, editing and deleting, what one's words become, and the month's numbers.
 */
export default function RulesPage() {
  const { t, i18n } = useT();
  usePageTitle([t('rulesPage.title')]);
  useHashTarget();
  const numbers = useQuery({ queryKey: ['discussion', 'numbers'], queryFn: () => api<{ months: Month[] }>('/discussion/numbers/') });
  return (
    <Page width="wide" className="pv">
      <header className="pv-head">
        <h1>{t('rulesPage.title')}</h1>
        <p className="lead">{t('rulesPage.lede')}</p>
        <p className="pv-draft">{t('rulesPage.draft')}</p>
      </header>

      <section className="ru-charter" aria-labelledby="ru-rules">
        <div className="pv-part-head">
          <h2 id="ru-rules">{t('rulesPage.rulesTitle')}</h2>
          <p>{t('rulesPage.rulesLead')}</p>
        </div>
        <ol>
          {RULES.map((r, i) => (
            <li key={r} id={`rule-${i + 1}`}>
              <span className="n" aria-hidden="true">{i + 1}</span>
              <div>
                <h3>{t(`rules.${r}`)}</h3>
                <p>{t(`rulesLong.${r}`)}</p>
                {FIXED.has(r) ? <p className="held">{t(`rulesPage.fixed.${r}`)}</p> : null}
              </div>
              <ul className="ru-guards" aria-label={t('rulesPage.guardsLabel')}>
                {(['fixed', 'check', 'report'] as const).map((g) => (
                  <li key={g} data-on={GUARDS[r].includes(g) ? '' : undefined}>
                    <i aria-hidden="true" />{t(`rulesPage.guards.${g}`)}
                    {GUARDS[r].includes(g) ? null : <span className="pv-sr"> {t('rulesPage.guards.none')}</span>}
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ol>
      </section>

      <Road />

      <div className="pv-acts">
        {PARTS.map((p) => {
          const items = t(`rulesPage.parts.${p}.items`, { returnObjects: true }) as { t: string; d: string }[];
          return (
            <section key={p} id={p} className="pv-act" aria-labelledby={`ru-${p}`}>
              <div className="pv-margin">
                <h2 id={`ru-${p}`}>{t(`rulesPage.parts.${p}.head`)}</h2>
                <span>{t(`rulesPage.parts.${p}.sub`)}</span>
              </div>
              <div className="pv-body">
                <p className="pv-answer">{t(`rulesPage.parts.${p}.answer`)}</p>
                <ul className="pv-items ru-items">
                  {items.map((it) => <li key={it.t} className="pv-item"><div><h3>{it.t}</h3><p>{it.d}</p></div></li>)}
                </ul>
                {p === 'yours' ? <Link to="/privacy" className="ru-more">{t('rulesPage.privacyLink')}</Link> : null}
              </div>
            </section>
          );
        })}
      </div>

      <section id="numbers" className="ru-numbers" aria-labelledby="ru-numbers">
        <div className="pv-part-head">
          <h2 id="ru-numbers">{t('rulesPage.numbersTitle')}</h2>
          <p>{t('rulesPage.numbersLede')}</p>
        </div>
        {/* The table is wider than a 360 px phone: reachable by keyboard too (the accessibility checker, RD23). */}
        {numbers.data ? (
          <div className="ru-table" tabIndex={0} role="region" aria-labelledby="ru-numbers">
            <table>
              <thead>
                <tr>
                  <td />
                  {numbers.data.months.map((m) => <th key={m.month} scope="col">{monthName(m.month, i18n.language)}</th>)}
                </tr>
              </thead>
              <tbody>
                <Row label={t('rulesPage.contributions')} values={numbers.data.months.map((m) => m.contributions)} strong />
                <Row label={t('rulesPage.held')} values={numbers.data.months.map((m) => m.held)} />
                <Group label={t('rulesPage.checks')} span={numbers.data.months.length + 1} />
                {(['publish', 'return', 'hold', 'unavailable'] as const).map((o) => (
                  <Row key={o} label={t(`rulesPage.checkOutcomes.${o}`)} values={numbers.data!.months.map((m) => m.checks?.[o] ?? 0)} />
                ))}
                <Row label={t('rulesPage.overturned')} values={numbers.data.months.map((m) => m.overturned ?? 0)} />
                <Group label={t('rulesPage.reportsBy')} span={numbers.data.months.length + 1} />
                {REASONS.map((r) => <Row key={r} label={t(`reasons.${r}`)} values={numbers.data!.months.map((m) => m.reports[r] ?? 0)} />)}
                <Group label={t('rulesPage.acts')} span={numbers.data.months.length + 1} />
                {Object.keys(numbers.data.months[0]?.acts ?? {}).map((v) => (
                  <Row key={v} label={t(`rulesPage.verbs.${v}`)} values={numbers.data!.months.map((m) => m.acts[v] ?? 0)} />
                ))}
                <Row label={t('rulesPage.pauses')} values={numbers.data.months.map((m) => m.pauses)} />
                <Row label={t('rulesPage.appeals')} values={numbers.data.months.map((m) => m.appeals)} />
              </tbody>
            </table>
          </div>
        ) : null}
        <p className="pv-small">{t('rulesPage.numbersLoad')}</p>
      </section>
    </Page>
  );
}

/** The road a post travels (compose.py, holds.py, check.py, review.py): three stations, then three ways. A sequence,
 *  so its stations are numbered. */
function Road() {
  const { t } = useT();
  const r = (k: string) => t(`rulesPage.road.${k}`);
  return (
    <section className="ru-road" aria-labelledby="ru-road">
      <div className="pv-part-head">
        <h2 id="ru-road">{t('rulesPage.roadTitle')}</h2>
        <p>{t('rulesPage.roadLead')}</p>
      </div>
      <ol className="ru-trunk">
        {(['send', 'fixed', 'check'] as const).map((k, i) => (
          <li key={k}>
            <span className="dot" aria-hidden="true">{i + 1}</span>
            <b>{r(`${k}.t`)}</b>
            <p>{r(`${k}.d`)}</p>
          </li>
        ))}
      </ol>
      <p className="ru-fork">{r('ways')}</p>
      <ul className="ru-ways">
        <li data-way="published">
          <span className="dot" aria-hidden="true" />
          <b>{r('published.t')}</b>
          <p>{r('published.d')}</p>
        </li>
        <li data-way="returned">
          <span className="dot" aria-hidden="true" />
          <b>{r('returned.t')}</b>
          <p>{r('returned.d')}</p>
        </li>
        <li data-way="waits">
          <span className="dot" aria-hidden="true" />
          <b>{r('waits.t')}</b>
          <p>{r('waits.d')}</p>
          <ul className="ru-decide">
            <li data-way="published">{r('decide.publish')}</li>
            <li data-way="returned">{r('decide.back')}</li>
            <li data-way="removed">{r('decide.remove')}</li>
          </ul>
          <p className="ru-appeal">{r('appeal')}</p>
        </li>
      </ul>
      <p className="ru-edits">{r('takedown')}</p>
    </section>
  );
}

/** «2026-10» as people say it: «أكتوبر 2026». */
const monthName = (month: string, lang: string) =>
  new Intl.DateTimeFormat(lang === 'fr' ? 'fr-MA' : 'ar-MA', { month: 'long', year: 'numeric', timeZone: 'UTC' })
    .format(new Date(`${month}-01T00:00:00Z`));

function Group({ label, span }: { label: string; span: number }) {
  return <tr className="g"><th scope="rowgroup" colSpan={span}>{label}</th></tr>;
}

function Row({ label, values, strong }: { label: string; values: number[]; strong?: boolean }) {
  const { i18n } = useT();
  const nf = new Intl.NumberFormat(i18n.language === 'fr' ? 'fr-MA' : 'ar-MA');
  return (
    <tr data-strong={strong ? '' : undefined}>
      <th scope="row">{label}</th>
      {values.map((v, i) => <td key={i} data-zero={v === 0 ? '' : undefined}>{nf.format(v)}</td>)}
    </tr>
  );
}
