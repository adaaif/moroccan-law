import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';
import { longDate } from '@/features/corpus/format';
import { useBudget, useBudgetLaws, type BudgetDetail, type Check, type LawSummary, type Ministry } from './budget.api';
import { HundredGrid, type Share } from './HundredGrid';
import { count, money } from './money';
import { usePageTitle } from '@/shared/services/title';
import { Page, PageSkeleton } from '@/shared/components/ui';
import './words';

/** A finance law told in the questions people ask, every figure checked against the law's own totals and
 *  linked to the article and the BO page it comes from. */
export default function BudgetPage() {
  const { year = '' } = useParams();
  const { t } = useTranslation();
  const budget = useBudget(year);
  usePageTitle([budget.data ? t(budget.data.filed ? 'budget.billTitle' : 'budget.title', { year: budget.data.year }) : null]);

  if (budget.isLoading) return <Shell><PageSkeleton /></Shell>;
  if (!budget.data) return <Shell><p className="text-repealed">{t('budget.notFound', { year })}</p></Shell>;
  const d = budget.data;
  const b = d.balance;

  return (
    <Shell>
      <Header d={d} />
      {b ? (
        <>
          <BigPicture d={d} />
          <Revenue d={d} />
          <Spending d={d} />
        </>
      ) : (
        <>
          <Unchecked what={t('budget.balanceTitle')} />
          {d.ministries.length ? (
            <Section id="spending" title={t('budget.q.spending')}>
              <Ministries d={d} />
            </Section>
          ) : null}
        </>
      )}
      {d.posts ? <Posts d={d} /> : null}
      {d.contents.articles.length ? <Contents d={d} /> : null}
      <Decided d={d} />
      <Years current={d.year} />
      <Checks d={d} />
    </Shell>
  );
}

function Header({ d }: { d: BudgetDetail }) {
  const { t, i18n } = useTranslation();
  const questions = [
    ['picture', t('budget.q.picture')],
    ['revenue', t('budget.q.revenue')],
    ['spending', t('budget.q.spending')],
    ['posts', t('budget.q.posts')],
    ['contents', t('budget.q.contents')],
    ['decided', t('budget.q.decided')],
    ['years', t('budget.q.years')],
    ['checks', t('budget.q.checks')],
  ];
  return (
    <header className="flex flex-col gap-6">
      <div className="flex flex-col gap-3">
        <h1 className="m-0 font-law text-h1 font-semibold leading-tight">{t(d.filed ? 'budget.billTitle' : 'budget.title', { year: d.year })}</h1>
        {d.filed ? <p className="m-0 max-w-[68ch] rounded-control px-4 py-3 text-body font-medium" style={DASHED}>{t('budget.billBand')}</p> : null}
        <p className="m-0 max-w-[68ch] text-lead leading-relaxed text-ink-soft">
          {d.filed ? t('budget.billLead', { number: d.number, date: longDate(d.filed.on, i18n.language) }) : t('budget.lead', { number: d.number })}
          {d.issue ? <> {t('budget.publishedIn', { issue: issueLabel(d, t), date: longDate(d.issue.date, i18n.language) })}</> : null}
        </p>
        <div className="flex flex-wrap gap-x-6 gap-y-2 text-body">
          {d.text_id ? <Link to={d.filed ? d.filed.path : `/texts/${d.text_id}`} className="no-underline">{t(d.filed ? 'budget.billText' : 'budget.readText')}</Link> : null}
          {d.filed?.document_id ? (
            <a href={`/api/sources/documents/${d.filed.document_id}/file/`} target="_blank" rel="noreferrer" className="no-underline">
              {t('budget.billPdf')}
            </a>
          ) : null}
          {d.issue ? (
            <a href={`/api/sources/documents/${d.issue.document_id}/file/`} target="_blank" rel="noreferrer" className="no-underline">
              {t('corpus.openPdf')}
            </a>
          ) : null}
        </div>
      </div>
      <nav aria-label={t('budget.questions')} className="flex flex-wrap gap-2">
        {questions.map(([id, label]) => (
          <a key={id} href={`#${id}`}
             className="rounded-full border border-rule bg-sheet px-4 py-2 text-body text-ink no-underline hover:border-stamp hover:text-ink">
            {label}
          </a>
        ))}
      </nav>
    </header>
  );
}

function BigPicture({ d }: { d: BudgetDetail }) {
  const { t, i18n } = useTranslation();
  const b = d.balance!;
  const n = (key: string) => Number(b[key]?.amount ?? 0);
  const facts = [
    { label: t('budget.fact.revenue'), value: n('ordinary_revenue'), note: t('budget.fact.revenueNote') },
    { label: t('budget.fact.spending'), value: n('ordinary_spending') + n('investment'), note: t('budget.fact.spendingNote') },
    { label: t('budget.fact.deficit'), value: -n('state_balance'), note: t('budget.fact.deficitNote'), tone: 'text-amended' },
  ];
  return (
    <Section id="picture" title={t('budget.q.picture')} source={<Source d={d} article={d.sources.balance} page={b.ordinary_revenue?.page} />}>
      <dl className="m-0 grid gap-4 sm:grid-cols-3">
        {facts.map((f) => (
          <div key={f.label} className="flex flex-col gap-1 rounded-control border border-rule bg-sheet px-5 py-4">
            <dt className="text-body text-ink-soft">{f.label}</dt>
            <dd className={`m-0 font-law text-h1 font-semibold leading-tight ${f.tone ?? ''}`}>{money(f.value, i18n.language, t)}</dd>
            <dd className="m-0 text-meta text-ink-soft">{f.note}</dd>
          </div>
        ))}
      </dl>
      <p className="m-0 max-w-[70ch] text-lead leading-relaxed">
        {t('budget.borrowing', {
          borrowing: money(n('borrowing'), i18n.language, t),
          internal: money(n('borrowing_internal'), i18n.language, t),
          external: money(n('borrowing_external'), i18n.language, t),
          repaid: money(n('amortisation'), i18n.language, t),
          interest: money(n('interest'), i18n.language, t),
          remaining: money(-n('remaining_needs'), i18n.language, t),
        })}
      </p>
    </Section>
  );
}

function Revenue({ d }: { d: BudgetDetail }) {
  const { t } = useTranslation();
  const b = d.balance!;
  const n = (key: string) => Number(b[key]?.amount ?? 0);
  const shares: Share[] = [
    { label: t('budget.lines.direct_taxes'), value: n('direct_taxes'), color: 'bg-share-1' },
    { label: t('budget.lines.indirect_taxes'), value: n('indirect_taxes'), color: 'bg-share-2' },
    { label: t('budget.lines.customs'), value: n('customs'), color: 'bg-share-3' },
    { label: t('budget.lines.registration'), value: n('registration'), color: 'bg-share-6' },
    { label: t('budget.lines.monopolies'), value: n('monopolies'), color: 'bg-share-4' },
    { label: t('budget.otherRevenue'), value: n('privatisation') + n('domain') + n('other_revenue') + n('gifts'), color: 'bg-share-5' },
  ];
  return (
    <Section id="revenue" title={t('budget.q.revenue')} source={<Source d={d} article={d.sources.balance} page={b.ordinary_revenue?.page} />}>
      <HundredGrid shares={shares} caption={t('budget.revenueCaption')} total={n('ordinary_revenue')} />
    </Section>
  );
}

function Spending({ d }: { d: BudgetDetail }) {
  const { t } = useTranslation();
  const b = d.balance!;
  const n = (key: string) => Number(b[key]?.amount ?? 0);
  const shares: Share[] = [
    { label: t('budget.lines.staff'), value: n('staff'), color: 'bg-share-1' },
    { label: t('budget.lines.materials'), value: n('materials'), color: 'bg-share-2' },
    { label: t('budget.lines.common'), value: n('common'), color: 'bg-share-3' },
    { label: t('budget.lines.investment'), value: n('investment'), color: 'bg-share-4' },
    { label: t('budget.lines.interest'), value: n('interest'), color: 'bg-share-5' },
    { label: t('budget.otherSpending'), value: n('tax_refunds') + n('contingencies'), color: 'bg-share-6' },
  ];
  return (
    <Section id="spending" title={t('budget.q.spending')} source={<Source d={d} article={d.sources.balance} page={b.ordinary_spending?.page} />}>
      <HundredGrid shares={shares} caption={t('budget.spendingCaption')} total={n('ordinary_spending') + n('investment')} />
      {d.ministries.length ? <Ministries d={d} /> : <Unchecked what={t('budget.ministriesTitle')} />}
    </Section>
  );
}

function Ministries({ d }: { d: BudgetDetail }) {
  const { t, i18n } = useTranslation();
  const [all, setAll] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const total = (m: Ministry) => Number(m.running) + Number(m.investment);
  const max = Math.max(...d.ministries.map(total));
  const shown = all ? d.ministries : d.ministries.slice(0, 12);
  return (
    <div className="flex flex-col gap-3">
      <h3 className="m-0 text-h3 font-semibold">{t('budget.ministriesTitle')}</h3>
      <p className="m-0 max-w-[70ch] text-body text-ink-soft">{t('budget.ministriesLead')}</p>
      <ol className="m-0 flex list-none flex-col p-0">
        {shown.map((m) => (
          <li key={m.code} className="border-b border-rule-soft py-3 last:border-b-0">
            <button type="button" onClick={() => setOpen(open === m.code ? null : m.code)} aria-expanded={open === m.code}
                    className="flex w-full flex-col gap-1.5 text-start">
              <span className="flex flex-wrap items-baseline justify-between gap-x-4">
                <span className="flex flex-wrap items-baseline gap-x-2">
                  <span lang="ar" dir="rtl" className="text-body font-medium">{m.state ? t(`budget.lines.${m.state}`) : m.name}</span>
                  {m.state ? <span className="rounded-full bg-paper px-1.5 py-0.5 text-meta text-ink-soft">{t('budget.stateWide')}</span> : null}
                </span>
                <span className="font-law text-law font-semibold">{money(total(m), i18n.language, t)}</span>
              </span>
              <span className="flex h-2.5 w-full overflow-hidden rounded-full bg-paper" aria-hidden="true">
                <span className="h-full bg-share-1" style={{ width: `${(Number(m.running) / max) * 100}%` }} />
                <span className="h-full bg-share-4" style={{ width: `${(Number(m.investment) / max) * 100}%` }} />
              </span>
              <span className="flex flex-wrap gap-x-4 text-meta text-ink-soft">
                <span>{t('budget.running')}: {money(m.running, i18n.language, t)}</span>
                {Number(m.investment) > 0 ? <span>{t('budget.investment')}: {money(m.investment, i18n.language, t)}</span> : null}
                {m.posts ? <span>{t('budget.postsCount', { count: m.posts, n: count(m.posts, i18n.language) })}</span> : null}
              </span>
            </button>
            {open === m.code ? <MinistryDetail d={d} m={m} /> : null}
          </li>
        ))}
      </ol>
      {d.ministries.length > 12 ? (
        <button type="button" onClick={() => setAll((a) => !a)} className="self-start text-body text-stamp">
          {all ? t('budget.fewerMinistries') : t('budget.allMinistries', { count: d.ministries.length })}
        </button>
      ) : null}
    </div>
  );
}

function MinistryDetail({ d, m }: { d: BudgetDetail; m: Ministry }) {
  const { t, i18n } = useTranslation();
  return (
    <div className="mt-3 flex flex-col gap-2 rounded-control bg-paper px-4 py-3 text-meta">
      <ul className="m-0 flex list-none flex-col gap-1.5 p-0">
        {m.chapters.map((c) => (
          <li key={c.code} className="flex flex-wrap items-baseline justify-between gap-x-3">
            <span><bdi lang="ar" dir="rtl">{c.label}</bdi> <span className="text-ink-soft" dir="ltr">{c.code}</span></span>
            <span>{money(c.amount, i18n.language, t)}{c.page ? <> <PageLink d={d} page={c.page} /></> : null}</span>
          </li>
        ))}
        <li className="flex flex-wrap items-baseline justify-between gap-x-3">
          <span>{t('budget.investmentPaid')}</span>
          <span>{money(m.investment, i18n.language, t)}</span>
        </li>
        {Number(m.commitment) > 0 ? (
          <li className="flex flex-wrap items-baseline justify-between gap-x-3 text-ink-soft">
            <span>{t('budget.commitment')}</span>
            <span>{money(m.commitment, i18n.language, t)}</span>
          </li>
        ) : null}
      </ul>
    </div>
  );
}

function Posts({ d }: { d: BudgetDetail }) {
  const { t, i18n } = useTranslation();
  const listed = d.posts!.filter((p) => !p.total);
  const [created, byMinistry, distributed] = (d.stated.posts ?? []).map(Number);
  const max = Math.max(...listed.map((p) => p.count));
  return (
    <Section id="posts" title={t('budget.q.posts')} source={<Source d={d} article={d.sources.posts} />}>
      <p className="m-0 flex flex-wrap items-baseline gap-x-3">
        <span className="font-law text-h1 font-semibold leading-none">{count(created || listed.reduce((a, p) => a + p.count, 0), i18n.language)}</span>
        <span className="text-lead">{t('budget.postsCreated')}</span>
      </p>
      {byMinistry && distributed ? (
        <p className="m-0 max-w-[70ch] text-lead leading-relaxed">
          {t('budget.postsSplit', { listed: count(byMinistry, i18n.language), distributed: count(distributed, i18n.language) })}
        </p>
      ) : null}
      <ol className="m-0 grid list-none gap-x-8 gap-y-2 p-0 sm:grid-cols-2">
        {listed.map((p) => (
          <li key={p.label} className="flex flex-col gap-1">
            <span className="flex items-baseline justify-between gap-3 text-body">
              <span lang="ar" dir="rtl">{p.label}</span>
              <span className="font-medium">{count(p.count, i18n.language)}</span>
            </span>
            <span className="h-1.5 rounded-full bg-paper" aria-hidden="true">
              <span className="block h-full rounded-full bg-share-1" style={{ width: `${Math.max(1, (p.count / max) * 100)}%` }} />
            </span>
          </li>
        ))}
      </ol>
    </Section>
  );
}

function Contents({ d }: { d: BudgetDetail }) {
  const { t } = useTranslation();
  const parts: [string, BudgetDetail['contents']['articles']][] = [];
  for (const a of d.contents.articles) {
    const last = parts.at(-1);
    if (last && last[0] === a.part) last[1].push(a);
    else parts.push([a.part, [a]]);
  }
  return (
    <Section id="contents" title={t('budget.q.contents')}>
      <p className="m-0 max-w-[70ch] text-body leading-relaxed text-ink-soft">{t('budget.contentsLead')}</p>
      <div className="grid gap-8 md:grid-cols-[minmax(0,1fr)_minmax(0,320px)]">
        <div className="flex flex-col gap-6">
          {parts.map(([part, articles]) => (
            <div key={part} className="flex flex-col gap-2">
              {part ? <h3 lang="ar" dir="rtl" className="m-0 text-body font-semibold text-ink-soft">{part}</h3> : null}
              <ul className="m-0 flex list-none flex-col p-0">
                {articles.map((a) => (
                  <li key={a.eid} className="border-b border-rule-soft last:border-b-0">
                    <Link to={`/texts/${d.text_id}#${a.eid}`}
                          className="flex items-baseline gap-4 py-2.5 text-ink no-underline hover:text-stamp">
                      <span className="w-24 flex-none text-meta text-ink-soft">{t('budget.article', { n: a.number.replace('-bis', ' ' + t('budget.bis')) })}</span>
                      <span lang="ar" dir="rtl" className="font-law text-law leading-snug">{a.subject}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        {d.contents.changes.length ? (
          <aside className="flex flex-col gap-3">
            <h3 className="m-0 text-body font-semibold">{t('budget.changes')}</h3>
            <ul className="m-0 flex list-none flex-col gap-2 p-0">
              {d.contents.changes.map((c) => (
                <li key={c.id}>
                  <Link to={`/texts/${c.id}`} lang="ar" dir="rtl"
                        className="block rounded-control border border-rule bg-sheet px-4 py-3 font-law text-law leading-snug no-underline hover:border-stamp">
                    {c.title || `${t(`corpus.types.${c.type}`)} ${c.number ?? ''}`}
                  </Link>
                </li>
              ))}
            </ul>
          </aside>
        ) : null}
      </div>
    </Section>
  );
}

/** The years side by side: each law's key figures, only from balances that passed their checks. */
function Years({ current }: { current: number }) {
  const { t, i18n } = useTranslation();
  const laws = useBudgetLaws();
  // A year's bill stands in while its law is not published, said as a bill.
  const all = laws.data ?? [];
  const rows = all.filter((l): l is LawSummary & { headline: NonNullable<LawSummary['headline']> } =>
    l.headline !== null && (l.kind === 'law' || (l.kind === 'bill' && !all.some((o) => o.kind === 'law' && o.year === l.year))))
    .sort((a, b) => b.year - a.year);
  if (rows.length < 2) return null;
  const max = Math.max(...rows.map((r) => Number(r.headline.spending)));
  return (
    <Section id="years" title={t('budget.q.years')}>
      <p className="m-0 max-w-[70ch] text-body leading-relaxed text-ink-soft">{t('budget.yearsLead')}</p>
      <ol className="m-0 flex list-none flex-col gap-4 p-0">
        {rows.map((r) => (
          <li key={r.year}>
            <Link to={`/budget/${r.year}`}
                  className={`flex flex-col gap-1.5 rounded-control px-3 py-2 text-ink no-underline hover:bg-sheet ${r.year === current ? 'bg-sheet ring-1 ring-stamp' : ''}`}>
              <span className="flex flex-wrap items-baseline justify-between gap-x-4">
                <span className="font-law text-h2 font-semibold">{r.kind === 'bill' ? t('budget.billYear', { year: r.year }) : r.year}</span>
                <span className="text-meta text-ink-soft">
                  {t('budget.fact.revenue')}: {money(r.headline.revenue, i18n.language, t)}{t('corpus.listSep')}
                  {t('budget.fact.spending')}: {money(r.headline.spending, i18n.language, t)}{t('corpus.listSep')}
                  <span className="text-amended">{t('budget.fact.deficit')}: {money(r.headline.deficit, i18n.language, t)}</span>
                  {r.headline.posts ? <>{t('corpus.listSep')}{t('budget.postsCount', { count: r.headline.posts, n: count(r.headline.posts, i18n.language) })}</> : null}
                </span>
              </span>
              <span className="flex flex-col gap-1" aria-hidden="true">
                <span className="h-2 rounded-full bg-share-1" style={{ width: `${(Number(r.headline.revenue) / max) * 100}%` }} />
                <span className="h-2 rounded-full bg-share-2" style={{ width: `${(Number(r.headline.spending) / max) * 100}%` }} />
              </span>
            </Link>
          </li>
        ))}
      </ol>
    </Section>
  );
}

function Decided({ d }: { d: BudgetDetail }) {
  const { t, i18n } = useTranslation();
  return (
    <Section id="decided" title={t('budget.q.decided')}>
      <ol className="m-0 flex list-none flex-col gap-3 p-0 text-lead">
        {d.filed ? (
          <>
            <li>{t('budget.billFiled', { date: longDate(d.filed.on, i18n.language) })}</li>
            <li>{t('budget.billNext')} <Link to="/topics/tax/reform/lf-2027" className="underline">{t('budget.billPath')}</Link></li>
          </>
        ) : null}
        {d.dahir ? (
          <li>{t('budget.step.promulgated', { dahir: d.dahir, date: longDate(d.signed_on, i18n.language) })}</li>
        ) : null}
        {d.issue ? (
          <li>{t('budget.step.published', { issue: issueLabel(d, t), date: longDate(d.issue.date, i18n.language) })}</li>
        ) : null}
      </ol>
    </Section>
  );
}

function Checks({ d }: { d: BudgetDetail }) {
  const { t } = useTranslation();
  const all = d.checks.passed === d.checks.count;
  return (
    <Section id="checks" title={t('budget.q.checks')}>
      <p className={`m-0 flex items-center gap-2 text-lead ${all ? 'text-in-force' : 'text-amended'}`}>
        <span aria-hidden="true" className={`size-2 rounded-full ${all ? 'bg-in-force' : 'bg-amended'}`} />
        {t('budget.checksLine', { passed: d.checks.passed, count: d.checks.count })}
      </p>
      <p className="m-0 max-w-[70ch] text-body leading-relaxed text-ink-soft">{t('budget.checksLead')}</p>
      <details className="rounded-control border border-rule bg-sheet px-5 py-3">
        <summary className="cursor-pointer text-body font-medium">{t('budget.checksList')}</summary>
        <ul className="m-0 mt-3 flex list-none flex-col gap-1.5 p-0 text-meta">
          {d.checks.items.map((c, i) => (
            <li key={i} className={`flex gap-2 ${c.ok ? '' : 'text-amended'}`}>
              <span aria-hidden="true">{c.ok ? '✓' : '✗'}</span>
              <span>{checkText(c, t)}</span>
            </li>
          ))}
        </ul>
      </details>
    </Section>
  );
}

function checkText(c: Check, t: (key: string, o?: Record<string, unknown>) => string): string {
  const table = (x: unknown) => t(`budget.tables.${String(x)}`);
  const line = (x: unknown) => t(`budget.lines.${String(x)}`);
  switch (c.id) {
    case 'sum': return t('budget.check.sum', { line: line(c.args.line) });
    case 'table_article': return t('budget.check.tableArticle', { table: table(c.args.table) });
    case 'table_balance': return t('budget.check.tableBalance', { table: table(c.args.table), line: line(c.args.line) });
    case 'table_two_credits': return t('budget.check.twoCredits', { table: table(c.args.table) });
    case 'debt': return t('budget.check.debt');
    case 'posts_list': return t('budget.check.postsList');
    case 'posts_parts': return t('budget.check.postsParts');
    default: return c.name;
  }
}

function Section({ id, title, source, children }: { id: string; title: string; source?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section id={id} className="flex scroll-mt-6 flex-col gap-5 border-t border-rule pt-10">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
        <h2 className="m-0 font-law text-h1 font-semibold leading-tight">{title}</h2>
        {source}
      </div>
      {children}
    </section>
  );
}

/** Where a figure comes from: its article in the law and its printed page. */
function Source({ d, article, page }: { d: BudgetDetail; article?: string; page?: number | null }) {
  const { t } = useTranslation();
  if (!article) return null;
  const a = d.articles[article];
  const at = page ?? a?.page;
  return (
    <span className="text-meta text-ink-soft">
      {t('budget.source')}{' '}
      {d.text_id && a ? <Link to={`/texts/${d.text_id}#${a.eid}`} className="no-underline">{t('budget.article', { n: article })}</Link>
        : t('budget.article', { n: article })}
      {at ? <>{t('corpus.listSep')}<PageLink d={d} page={at} /></> : null}
    </span>
  );
}

function PageLink({ d, page }: { d: BudgetDetail; page: number }) {
  const { t } = useTranslation();
  const index = d.page_index[String(page)];
  // A bill's pages are its own file's, in order.
  if (d.filed?.document_id) return <Link to={`/pages/${d.filed.document_id}/${page - 1}`} className="no-underline">{t('corpus.pageLong', { page })}</Link>;
  return d.issue && index !== undefined
    ? <Link to={`/pages/${d.issue.document_id}/${index}`} className="no-underline">{t('corpus.pageLong', { page })}</Link>
    : <span>{t('corpus.pageLong', { page })}</span>;
}

function Unchecked({ what }: { what: string }) {
  const { t } = useTranslation();
  return <p className="m-0 rounded-control bg-wash px-5 py-4 text-body">{t('budget.unchecked', { what })}</p>;
}

function issueLabel(d: BudgetDetail, t: (key: string, o?: Record<string, unknown>) => string): string {
  const issue = d.issue!;
  return t('corpus.issueTitle', { number: issue.suffix ? `${issue.number} ${t(`corpus.suffix.${issue.suffix}`)}` : issue.number });
}

/** A bill's marks are drawn in dashes: a draft. */
const DASHED = { border: '1px dashed var(--color-ink-soft)' };

function Shell({ children }: { children: React.ReactNode }) {
  return <Page width="wide" className="gap-10">{children}</Page>;
}
