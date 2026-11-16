import { useLocation } from 'react-router-dom';
import { Button, Note, PageSkeleton } from '@/shared/components/ui';
import { KitPage } from '../kit/parts';
import { whatsapp, here } from '../kit/share';
import { AnswerCard, Chips } from '../kit/tool/parts';
import Stepper from '../kit/tool/Stepper';
import { useToolState } from '../kit/tool/state';
import { useProfile } from '../kit/profile';
import { bandOf, endOfContract, HOURS_MONTH, LEAVE_DAYS_MONTH, startFor, stairs, type Category, type Ending } from './rules/end';
import { Arts } from './parts';
import { useRateOn, useRateStart } from './rates';
import { useWorkT } from './strings';
import { todayIso } from '@/shared/services/today';

const SIMULATOR = 'https://miepeec.gov.ma/simulation/?lang=ar';
/** A year begun: the topic's colour hatched. */
const HATCH = 'repeating-linear-gradient(135deg, var(--t) 0 4px, color-mix(in srgb, var(--t) 35%, var(--color-sheet)) 4px 8px)';

/** «شنو كيتسالني؟» (T8 of the work plan; E13 of the work-counted review): at the end of a contract of indefinite duration, the
 *  total the law fixes on top, held in view, then what the reader tells it, touched rather than typed: how it ended,
 *  their category, the years and months served, the wage. Art. 53's staircase under the total draws each year of
 *  service as a step of its band's hours; each sum keeps its article and condition; the damages stay apart as what
 *  art. 41 sets if a court finds the dismissal abusive. The inputs are kept in the address (a link opens the same
 *  answer); a journey hands over its day as the last day worked (`d`). Computed on the phone. */
export default function EndPage({ slug }: { slug: string }) {
  const { t, i18n } = useWorkT();
  const [mine] = useProfile(slug);
  const nf = new Intl.NumberFormat(i18n.language === 'fr' ? 'fr-MA' : 'ar-MA', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const [s, set] = useToolState({ d: todayIso(), e: 'dismissed', c: 'employee', y: '5', m: '0', w: '4000', f: mine === 'farm' ? '1' : '0', n: '0', l: '0', g: '0' }, ['f']);
  // Until the reader gives their years or wage, the answer is the example's and says so (HM15 of
  // the hard-moment review: «14.052,36 درهم · 5 سنوات» stood as if it were theirs).
  const { search } = useLocation();
  const example = !['y', 'm', 'w'].some((k) => new URLSearchParams(search).has(k));
  const end = s.d;
  const service = Number(s.y) * 12 + Number(s.m);
  const farm = s.f === '1';
  const monthly = Number(s.w) || 0;
  // A day before the first rates the site holds is counted on them (PX22): it was a skeleton for good.
  const start = [useRateStart(slug, 'smig'), useRateStart(slug, 'notice')].filter(Boolean).sort().reverse()[0];
  const on = start && end < start ? start : end;
  const smig = useRateOn(slug, 'smig', on);
  const smag = useRateOn(slug, 'smag', on);
  const notice = useRateOn(slug, 'notice', on);
  const dh = (n: number) => t('dh', { amount: nf.format(n) });
  if (!smig || !smag || !notice) return <KitPage slug={slug} title={t('end.title')} lead={t('end.lead')}><PageSkeleton /></KitPage>;
  const lines = monthly > 0 ? endOfContract({
    start: startFor(end, service), end, category: s.c as Category, farm, monthly, noticeGiven: s.n === '1',
    leaveDays: Number(s.l), delegate: s.g === '1', ending: s.e as Ending,
  }, { notice, smigHour: smig.hour, smagDay: smag.day }) : [];
  const owed = lines.filter((l) => l.applies && !l.conditional);
  const total = owed.reduce((sum, l) => sum + l.amount, 0);
  const damages = lines.find((l) => l.key === 'damages');
  const severance = lines.find((l) => l.key === 'severance');
  // The minimum a month on the day the contract ends: the hour × 191, or the farm day × 26.
  const minimum = Math.round((farm ? smag.day * LEAVE_DAYS_MONTH : smig.hour * HOURS_MONTH) * 100) / 100;
  const span = [Number(s.y) ? t('topicKit:line.years', { count: Number(s.y) }) : '', Number(s.m) ? t('topicKit:months', { count: Number(s.m) }) : '']
    .filter(Boolean).join(t('end.and')) || t('end.lessThanMonth');
  const detail = (l: (typeof lines)[number]) => l.key === 'notice'
    ? (l.detail.months ? t('end.detail.noticeMonths', { n: l.detail.months }) : t('end.detail.noticeDays', { n: l.detail.days }))
    : l.key === 'severance' ? t('end.detail.severance', { hours: l.detail.hours, hourly: nf.format(Number(l.detail.hourly)) })
      : l.key === 'leave' ? t('end.detail.leave', { days: l.detail.days })
        : t('end.detail.damages', { years: l.detail.years });
  const share = () => whatsapp([t('end.message'), ...owed.map((l) => `${t(`end.line.${l.key}`)}: ${dh(l.amount)}`),
    `${t('end.total')}: ${dh(total)}`, here()].join('\n'));
  return (
    <KitPage slug={slug} title={t('end.title')} lead={t('end.lead')}>
      <AnswerCard over={example ? t('end.example') : t('end.total')} value={Math.round(total * 100)} format={(n) => dh(n / 100)}
                  under={<span>{t('end.service', { span })}</span>}>
        {damages?.applies ? <p className="m-0 text-meta text-amended">{t('end.ifCourt')}: {dh(damages.amount)}</p> : null}
      </AnswerCard>

      <section className="flex flex-col gap-4 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <Chips label={t('end.ending')} value={s.e} onChange={(e) => set({ e })}
               options={(['dismissed', 'seriousFault', 'resigned', 'retired'] as const).map((k) => ({ key: k, label: t(`end.how.${k}`) }))} />
        <Chips label={t('end.category')} value={s.c} onChange={(c) => set({ c })}
               options={(['worker', 'employee', 'cadre'] as const).map((k) => ({ key: k, label: t(`end.cat.${k}`) }))} />
        <div className="flex flex-col">
          <span className="text-body font-semibold">{t('end.served')}</span>
          <Stepper label={t('end.years')} value={Number(s.y)} max={45} onChange={(v) => set({ y: String(v) })} />
          <Stepper label={t('end.monthsLabel')} value={Number(s.m)} max={11} onChange={(v) => set({ m: String(v) })} />
        </div>
        <label className="flex flex-col gap-1.5">
          <span className="text-body font-semibold">{t('end.monthly')}</span>
          <span className="flex flex-wrap items-center gap-2">
            <input type="number" inputMode="decimal" min={0} value={s.w === '0' ? '' : s.w} onChange={(e) => set({ w: e.target.value || '0' })}
                   className="h-12 w-40 max-w-full rounded-control border border-field bg-sheet px-3 text-body tabular-nums" dir="ltr" />
            <button type="button" onClick={() => set({ w: String(minimum) })}
                    className={`min-h-11 rounded-full border px-4 text-body ${Number(s.w) === minimum ? 'border-ink bg-ink font-semibold text-sheet' : 'border-field bg-sheet'}`}>
              {t('end.useMinimum', { amount: nf.format(minimum) })}
            </button>
          </span>
          <span className="text-meta text-ink-soft">{t('end.monthlyHint')}</span>
        </label>
        <Chips label={t('end.sector')} value={s.f} onChange={(f) => set({ f })}
               options={[{ key: '0', label: t('end.nonfarm') }, { key: '1', label: t('end.farm') }]} />
        {s.e === 'dismissed' ? (
          <Chips label={t('end.noticeGiven')} value={s.n} onChange={(n) => set({ n })}
                 options={[{ key: '0', label: t('end.no') }, { key: '1', label: t('end.yes') }]} />
        ) : null}
        <div className="flex flex-col">
          <Stepper label={t('end.leaveDays')} value={Number(s.l)} max={30} onChange={(v) => set({ l: String(v) })} />
        </div>
        <Chips label={t('end.delegate')} value={s.g} onChange={(g) => set({ g })}
               options={[{ key: '0', label: t('end.no') }, { key: '1', label: t('end.yes') }]} />
      </section>

      {/* Art. 53's staircase: a step a year begun, the next band waiting, the hours times the wage of an hour. */}
      {service > 0 ? (
        <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7" aria-labelledby="stairs">
          <h2 id="stairs" className="m-0 text-lead font-semibold">{t('end.stairs')}</h2>
          <Staircase service={service} />
          {severance?.applies ? <p className="m-0 text-body">{detail(severance)} = <b className="tabular-nums">{dh(severance.amount)}</b></p>
            : <p className="m-0 text-body text-ink-soft">{severance?.why ? t(`end.why.${severance.why}`) : ''}</p>}
          <Arts paths={['/ma/loi/65-99/art_53']} />
        </section>
      ) : null}

      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <ul className="m-0 flex list-none flex-col p-0">
          {lines.filter((l) => !l.conditional).map((l) => (
            <li key={l.key} className="flex flex-col gap-1.5 border-t border-rule py-3 first:border-t-0">
              <div className="flex flex-wrap items-baseline justify-between gap-x-4">
                <span className="text-body font-semibold">{t(`end.line.${l.key}`)}</span>
                {l.applies ? <b className="text-lead tabular-nums">{dh(l.amount)}</b> : <span className="text-meta text-ink-soft">—</span>}
              </div>
              <span className="text-meta text-ink-soft">{l.applies ? detail(l) : t(`end.why.${l.why}`)}</span>
              {l.applies && l.key === 'severance' && l.detail.floored ? <span className="text-meta text-ink-soft">{t('end.detail.floored')}</span> : null}
              {l.applies && l.key === 'severance' && l.detail.delegate ? <span className="text-meta text-ink-soft">{t('end.detail.delegate')}</span> : null}
              <Arts paths={l.cites} />
            </li>
          ))}
        </ul>
        {damages?.applies ? (
          <Note tone="warn">
            <p className="m-0 text-body font-semibold">{t('end.ifCourt')}: {t('end.line.damages')} {dh(damages.amount)}</p>
            <div className="h-2.5 overflow-hidden rounded-full" style={{ background: 'color-mix(in srgb, var(--color-amended) 18%, var(--color-sheet))' }} aria-hidden="true">
              <div className="h-full rounded-full bg-amended" style={{ width: `${Math.min(100, (damages.amount / (36 * monthly)) * 100)}%` }} />
            </div>
            <p className="m-0 text-meta">{detail(damages)}{damages.detail.capped ? ` · ${t('end.detail.capped')}` : ''} · {t('end.ceiling', { amount: nf.format(36 * monthly) })}</p>
            <p className="m-0 text-meta">{t('end.ifCourtNote')}</p>
            <Arts paths={damages.cites} />
          </Note>
        ) : null}
        <div className="flex flex-wrap gap-2">
          <Button onClick={share} disabled={!owed.length}>{t('share')}</Button>
          <Button variant="quiet" href={SIMULATOR} target="_blank" rel="noreferrer" className="h-auto min-h-11 py-2 text-start">{t('end.compare')}</Button>
        </div>
      </section>
      <Note tone="warn" quiet>
        <p className="m-0 text-meta">{t('draftRule')} {t('end.choices')}</p>
      </Note>
    </KitPage>
  );
}

/** Each year of service a step as tall as its band's hours (96, 144, 192, 240), a year begun hatched by its months,
 *  the next year dashed: what one more year would add. Left to right on every page (the chart rule of 1 Nov 2026,
 *  HM34): the first year at the left; the hours over each step. */
function Staircase({ service }: { service: number }) {
  const { t } = useWorkT();
  const steps = stairs(service);
  const shown = steps.slice(-14);
  const next = steps.length ? steps[steps.length - 1] : null;
  const nextYear = next ? next.year + 1 : null;
  const tall = (band: number) => `${(band / 240) * 100}%`;
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex h-32 items-end gap-1" dir="ltr" role="img" aria-label={t('end.stairsLabel', { years: steps.length, hours: Math.round(steps.reduce((a, x) => a + x.hours, 0)) })}>
        {steps.length > shown.length ? <span className="self-center px-1 text-meta text-ink-soft">…</span> : null}
        {shown.map((x) => (
          <div key={x.year} className="flex h-full min-w-0 flex-1 flex-col items-center justify-end gap-1">
            <span className="text-meta tabular-nums text-ink-soft">{x.months === 12 ? x.band : Math.round(x.hours)}</span>
            <span className="w-full rounded-t-control bg-[var(--t)]"
                  style={{ height: tall(x.band), ...(x.months === 12 ? {} : { background: HATCH }) }} />
          </div>
        ))}
        {nextYear ? (
          <div className="flex h-full min-w-0 flex-1 flex-col items-center justify-end gap-1">
            <span className="text-meta tabular-nums text-ink-soft">{bandOf(nextYear)}</span>
            <span className="w-full rounded-t-control border-2 border-b-0 border-dashed border-field" style={{ height: tall(bandOf(nextYear)) }} />
          </div>
        ) : null}
      </div>
      <div className="flex gap-1 border-t-2 border-ink pt-1" dir="ltr">
        {steps.length > shown.length ? <span aria-hidden="true" className="px-1 text-meta opacity-0">…</span> : null}
        {shown.map((x) => <span key={x.year} className="min-w-0 flex-1 text-center text-meta tabular-nums text-ink-soft">{x.year}</span>)}
        {nextYear ? <span className="min-w-0 flex-1 text-center text-meta tabular-nums text-ink-soft">{nextYear}</span> : null}
      </div>
      <p className="m-0 text-meta text-ink-soft">{t('end.stairsNote')}</p>
    </div>
  );
}

