import { useState } from 'react';
import { PageSkeleton } from '@/shared/components/ui';
import { KitPage } from '../kit/parts';
import { useProfile } from '../kit/profile';
import { AnswerCard, ArticlePeek, Chips, DayChips } from '../kit/tool/parts';
import Stepper from '../kit/tool/Stepper';
import { useToolState } from '../kit/tool/state';
import { leaveDays, payslip, type OvertimeKind, type Sector } from './rules/pay';
import { Arts } from './parts';
import { useRateOn, useRateStart } from './rates';
import { articleLabel, useWorkT } from './strings';
import { monthTax } from '../tax/rules/income';
import { todayIso } from '@/shared/services/today';

/** «ورقة الأداء» (T9 of the work plan; E14 of the work-counted review): the payslip the law writes for the reader's hours,
 *  years and overtime, drawn as a payslip. Each line its amount and its article, a tap opening the article over the
 *  page; the minimum for the hours ruled under the base; the net before income tax on top, income tax a grey line the
 *  tool says it does not compute. The inputs are touched (sector, hours, years, overtime) but the wage, and kept in
 *  the address. On the phone only. */
export default function PayPage({ slug }: { slug: string }) {
  const { t, i18n } = useWorkT();
  const [mine] = useProfile(slug);
  const nf = new Intl.NumberFormat(i18n.language === 'fr' ? 'fr-MA' : 'ar-MA', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const dh = (n: number) => t('dh', { amount: nf.format(n) });
  const fromProfile: Sector = mine === 'farm' ? 'farm' : mine === 'home' ? 'home' : 'nonfarm';
  const [s, set] = useToolState({ d: todayIso(), s: fromProfile as string, h: '44', w: '3800', y: '6', o: '0', k: 'day', m: '24', u: '0' }, ['s']);
  const [peek, setPeek] = useState<string | null>(null);
  const sector = s.s as Sector;
  // A day before the first minimum wage the site holds is counted on that first row, and said (PX22).
  const start = useRateStart(slug, 'smig');
  const on = start && s.d < start ? start : s.d;
  const smig = useRateOn(slug, 'smig', on);
  const smag = useRateOn(slug, 'smag', on);
  const home = useRateOn(slug, 'home', on);
  const cnss = useRateOn(slug, 'cnss', on);
  // Income tax by the tax topic's rows in force that day (the tax review, T10): the grey line made real.
  const scale = useRateOn('tax', 'scale', on);
  const family = useRateOn('tax', 'family', on);
  const expenses = useRateOn('tax', 'expenses', on);
  if (!smig || !smag || !cnss) return <KitPage slug={slug} title={t('pay.title')} lead={t('pay.lead')}><PageSkeleton /></KitPage>;
  const p = payslip({ sector, hoursWeek: sector === 'nonfarm' ? Number(s.h) : 44, base: Number(s.w) || 0, years: Number(s.y), overtime: Number(s.o), kind: s.k as OvertimeKind },
    { smigHour: smig.hour, smagDay: smag.day, homeShare: home?.share_of_smig ?? 60, cnss });
  const below = p.base > 0 && p.gap > 0;
  const tax = scale && family && expenses ? monthTax(p.gross, 0, { scale, family, expenses, cnss }) : null;
  const net = tax === null ? p.net : Math.round((p.net - tax) * 100) / 100;
  const baseCites = sector === 'home' ? ['/ma/loi/19-12/art_19', '/ma/decret/2-25-983/art_1']
    : sector === 'farm' ? ['/ma/loi/65-99/art_356', '/ma/decret/2-25-983/art_2'] : ['/ma/loi/65-99/art_356', '/ma/decret/2-25-983/art_1'];
  type Row = { key: string; label: string; note?: string; amount: number | null; minus?: boolean; sum?: boolean; cites?: string[] };
  const rows: Row[] = [
    { key: 'base', label: t('pay.slip.base'), note: sector === 'farm' ? t('pay.slip.baseFarm') : sector === 'home' ? t('pay.slip.baseHome') : t('pay.slip.baseHours', { hours: s.h }), amount: p.base, cites: baseCites },
    { key: 'seniority', label: t('pay.slip.seniority', { rate: p.seniorityRate }), note: t(`pay.slip.band.${p.seniorityRate}`), amount: p.seniority, cites: ['/ma/loi/65-99/art_350'] },
    ...(sector === 'home' ? [] : [{ key: 'overtime', label: t('pay.slip.overtime'), note: Number(s.o) ? t('pay.slip.overtimeNote', { hours: s.o, hourly: nf.format(p.hourly), rate: 100 + p.overtimeRate }) : t('pay.slip.none'), amount: p.overtime, cites: ['/ma/loi/65-99/art_201'] }]),
    { key: 'gross', label: t('pay.slip.gross'), amount: p.gross, sum: true },
    { key: 'cnss', label: t('pay.slip.cnss', { rate: nf.format(p.cnssRate) }), note: t('pay.slip.ceiling', { ceiling: nf.format(cnss.ceiling) }), amount: p.cnss, minus: true, cites: ['/ma/decret/2-01-2723/art_2', '/ma/decret/2-01-2723/art_3', '/ma/decret/2-01-2723/art_4'] },
    { key: 'amo', label: t('pay.slip.amo', { rate: nf.format(p.amoRate) }), amount: p.amo, minus: true, cites: ['/ma/decret/2-05-734/art_1'] },
    { key: 'tax', label: t('pay.slip.tax'), note: t('pay.slip.taxNote'), amount: tax, minus: true, cites: ['/ma/code/cgi/art_73', '/ma/code/cgi/art_59'] },
  ];
  const leave = leaveDays(Number(s.m), s.u === '1');
  return (
    <KitPage slug={slug} title={t('pay.title')} lead={t('pay.lead')}>
      <AnswerCard share over={t('pay.slip.net')} value={Math.round(net * 100)} format={(n) => dh(n / 100)} tone={below ? 'warn' : 'stamp'}
                  under={<span>{t('pay.slip.grossLine', { gross: nf.format(p.gross) })}</span>}>
        {p.base > 0 ? <p className={`m-0 text-meta ${below ? 'font-semibold text-amended' : 'text-ink-soft'}`}>{below ? t('pay.below', { gap: nf.format(p.gap) }) : t('pay.slip.above', { minimum: nf.format(p.minimum) })}</p> : null}
      </AnswerCard>

      {/* The payslip: white paper, a torn edge at its top, each line a button to its article. */}
      <section aria-labelledby="slip" style={PAPER} className="flex flex-col rounded-control bg-sheet px-4 pb-4 pt-5 sm:px-6">
        <div className="flex flex-wrap items-baseline justify-between gap-2 border-b-2 border-ink pb-2">
          <h2 id="slip" className="m-0 text-lead font-bold">{t('pay.slip.title')}</h2>
          <span className="text-meta text-ink-soft">{t('pay.slip.example')}</span>
        </div>
        <ul className="m-0 flex list-none flex-col p-0">
          {rows.map((r, i) => {
            const amount = r.amount === null ? '—' : `${r.minus ? '−' : ''}${nf.format(r.amount)}`;
            const inner = (
              <>
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className={`text-body ${r.sum ? 'font-bold' : 'font-medium'} ${r.amount === null ? 'text-muted' : ''}`}>{r.label}</span>
                  {r.note ? <span className={`text-meta ${r.amount === null ? 'text-muted' : 'text-ink-soft'}`}>{r.note}</span> : null}
                  {r.cites ? <span lang="ar" dir="rtl" className="self-start text-meta text-stamp">{articleLabel(r.cites[0])}</span> : null}
                </span>
                <span dir="ltr" className={`shrink-0 text-body tabular-nums ${r.sum ? 'font-bold' : 'font-semibold'} ${r.minus ? 'text-amended' : ''} ${r.amount === null ? 'text-muted' : ''}`}>{amount}</span>
              </>
            );
            const cls = `flex w-full items-start gap-3 py-2.5 text-start ${r.sum ? 'border-t-2 border-ink' : i ? 'border-t border-rule' : ''}`;
            return (
              <li key={r.key}>
                {r.cites ? <button type="button" onClick={() => setPeek(r.cites![0])} className={`${cls} hover:text-stamp`}>{inner}</button> : <div className={cls}>{inner}</div>}
                {r.key === 'base' && p.base > 0 ? <MinimumRule base={p.base} minimum={p.minimum} label={t('pay.slip.minimumRule', { minimum: nf.format(p.minimum) })} /> : null}
              </li>
            );
          })}
        </ul>
        <div className="flex items-baseline justify-between gap-3 border-t-2 border-ink pt-3">
          <span className="text-body font-bold">{t('pay.slip.net')}</span>
          <b dir="ltr" className="text-h3 tabular-nums">{nf.format(net)}</b>
        </div>
        {peek ? <ArticlePeek path={peek} onClose={() => setPeek(null)} /> : null}
      </section>

      <section className="flex flex-col gap-4 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <Chips label={t('pay.sector')} value={s.s} onChange={(v) => set({ s: v })}
               options={(['nonfarm', 'farm', 'home'] as const).map((k) => ({ key: k, label: t(`pay.sectors.${k}`) }))} />
        <label className="flex flex-col gap-1.5">
          <span className="text-body font-semibold">{t('pay.slip.baseAsk')}</span>
          <span className="flex flex-wrap items-center gap-2">
            <input type="number" inputMode="decimal" min={0} value={s.w === '0' ? '' : s.w} onChange={(e) => set({ w: e.target.value || '0' })}
                   className="h-12 w-40 max-w-full rounded-control border border-field bg-sheet px-3 text-body tabular-nums" dir="ltr" />
            <button type="button" onClick={() => set({ w: String(p.minimum) })}
                    className={`min-h-11 rounded-full border px-4 text-body ${Number(s.w) === p.minimum ? 'border-ink bg-ink font-semibold text-sheet' : 'border-field bg-sheet'}`}>
              {t('end.useMinimum', { amount: nf.format(p.minimum) })}
            </button>
          </span>
        </label>
        <div className="flex flex-col">
          {sector === 'nonfarm' ? <Stepper label={t('pay.hours')} value={Number(s.h)} min={1} max={44} onChange={(v) => set({ h: String(v) })} /> : null}
          <Stepper label={t('pay.years')} value={Number(s.y)} max={45} onChange={(v) => set({ y: String(v) })} />
          {sector === 'home' ? null : <Stepper label={t('pay.slip.overtimeAsk')} value={Number(s.o)} max={80} onChange={(v) => set({ o: String(v) })} />}
        </div>
        {sector !== 'home' && Number(s.o) ? (
          <Chips label={t('pay.slip.when')} value={s.k} onChange={(k) => set({ k })}
                 options={(['day', 'night', 'restDay', 'restNight'] as const).map((k) => ({ key: k, label: t(`pay.slip.kind.${k}`) }))} />
        ) : null}
        <DayChips label={t('pay.date')} value={s.d} onChange={(d) => set({ d })} ago={[0]} />
        {on !== s.d ? <p className="m-0 text-meta text-amended">{t('pay.before', { date: new Date(`${on}T12:00:00Z`).toLocaleDateString(i18n.language === 'fr' ? 'fr-MA' : 'ar-MA', { dateStyle: 'long' }) })}</p> : null}
      </section>

      <details className="group rounded-card bg-sheet px-5 py-4 sm:px-7">
        <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3">
          <span className="text-lead font-semibold">{t('pay.leave')}: {t('pay.leaveLine', { days: leave })}</span>
          <span aria-hidden="true" className="transition-transform group-open:rotate-180 motion-reduce:transition-none">⌄</span>
        </summary>
        <div className="flex flex-col gap-3 pt-2">
          <Stepper label={t('pay.months')} value={Number(s.m)} max={480} onChange={(v) => set({ m: String(v) })} />
          <Chips value={s.u} onChange={(u) => set({ u })} options={[{ key: '0', label: t('pay.slip.adult') }, { key: '1', label: t('pay.under18') }]} />
          <Arts paths={['/ma/loi/65-99/art_231', '/ma/loi/65-99/art_232']} />
        </div>
      </details>
    </KitPage>
  );
}

/** A payslip's paper: its torn top edge, the shadow of a sheet on the table. */
const PAPER: React.CSSProperties = {
  backgroundImage: 'radial-gradient(circle at 8px -2px, var(--color-paper) 4px, transparent 4.5px)', backgroundSize: '16px 8px', backgroundRepeat: 'repeat-x',
  boxShadow: '0 1px 0 var(--color-rule), 0 10px 24px -18px var(--color-scrim)',
};

/** The minimum for the hours as a rule across the base: the bar as long as the larger, the rule where the minimum is. */
function MinimumRule({ base, minimum, label }: { base: number; minimum: number; label: string }) {
  const top = Math.max(base, minimum);
  return (
    <div className="flex flex-col gap-1 pb-3">
      <div className="relative h-3 rounded-full bg-rule" aria-hidden="true">
        <div className={`absolute inset-y-0 start-0 rounded-full ${base < minimum ? 'bg-amended' : 'bg-[var(--t)]'}`} style={{ width: `${(base / top) * 100}%` }} />
        <div className="absolute -inset-y-1 w-0.5 bg-ink" style={{ insetInlineStart: `${(minimum / top) * 100}%` }} />
      </div>
      <span className="text-meta text-ink-soft">{label}</span>
    </div>
  );
}
