import { useState } from 'react';
import { Note, PageSkeleton } from '@/shared/components/ui';
import { useRateOn } from '../kit/api';
import { KitPage } from '../kit/parts';
import { capAt, offplan, STAGES, type OffplanInput, type Stage } from './rules/offplan';
import { Arts, CARD, FIELD } from './parts';
import { useHousingT } from './strings';
import { todayIso } from '@/shared/services/today';

const today = () => todayIso();

/** «شريت على التصميم» (H12 of the housing plan): what may have been paid at each stage (DOC 618-6), and, once the
 *  delivery date has passed, the delay's indemnity (618-12) and what rescission gives (618-14). On the phone only. */
export default function OffplanPage({ slug }: { slug: string }) {
  const { t, i18n } = useHousingT();
  const nf = new Intl.NumberFormat(i18n.language === 'fr' ? 'fr-MA' : 'ar-MA', { maximumFractionDigits: 2 });
  const dh = (n: number) => t('dh', { amount: nf.format(n) });
  const date = (d: string) => new Date(`${d}T12:00:00Z`).toLocaleDateString(i18n.language === 'fr' ? 'fr-MA' : 'ar-MA', { dateStyle: 'long' });
  const [f, setF] = useState<OffplanInput>({ price: 600000, reserved: true, stage: 'start', paid: 120000, delivery: '', extended: false,
    notice: '', on: today() });
  const set = (p: Partial<OffplanInput>) => setF({ ...f, ...p });
  const r0 = useRateOn(slug, 'offplan', f.on);
  if (!r0) return <KitPage slug={slug} title={t('offplan.title')} lead={t('offplan.lead')}><PageSkeleton /></KitPage>;
  const r = offplan(f, r0);
  const num = (v: number, key: 'price' | 'paid') => (
    <input type="number" inputMode="decimal" min={0} value={v || ''} onChange={(e) => set({ [key]: Number(e.target.value) })} className={FIELD} dir="ltr" />
  );
  return (
    <KitPage slug={slug} title={t('offplan.title')} lead={t('offplan.lead')}>
      <section className={`${CARD} sm:grid sm:grid-cols-2 sm:gap-4`}>
        <label className="flex flex-col gap-1.5"><span className="text-body font-semibold">{t('offplan.price')}</span>{num(f.price, 'price')}</label>
        <label className="flex flex-col gap-1.5"><span className="text-body font-semibold">{t('offplan.paid')}</span>{num(f.paid, 'paid')}</label>
        <label className="flex flex-col gap-1.5"><span className="text-body font-semibold">{t('offplan.stage')}</span>
          <select value={f.stage} onChange={(e) => set({ stage: e.target.value as Stage })} className={FIELD}>
            {STAGES.filter((s) => f.reserved || s !== 'reservation').map((s) => <option key={s} value={s}>{t(`offplan.stages.${s}`)}</option>)}
          </select></label>
        <label className="inline-flex min-h-11 items-center gap-2 self-end">
          <input type="checkbox" checked={f.reserved} onChange={() => set({ reserved: !f.reserved, stage: f.stage === 'reservation' ? 'preliminary' : f.stage })} className="size-5" />
          {t('offplan.reserved')}
        </label>
        <label className="flex flex-col gap-1.5"><span className="text-body font-semibold">{t('offplan.delivery')}</span>
          <input type="date" value={f.delivery} onChange={(e) => set({ delivery: e.target.value })} className={FIELD} dir="ltr" /></label>
        <label className="flex flex-col gap-1.5"><span className="text-body font-semibold">{t('offplan.notice')}</span>
          <input type="date" value={f.notice} onChange={(e) => set({ notice: e.target.value })} className={FIELD} dir="ltr" />
          <span className="text-meta text-ink-soft">{t('offplan.noticeHint')}</span></label>
        <label className="inline-flex min-h-11 items-center gap-2 sm:col-span-2">
          <input type="checkbox" checked={f.extended} onChange={() => set({ extended: !f.extended })} className="size-5" />
          {t('offplan.extended')}
        </label>
      </section>

      <section className={CARD} aria-live="polite">
        <h2 className="m-0 text-lead font-semibold">{t('offplan.schedule')}</h2>
        <ol className="m-0 flex list-none flex-col p-0">
          {STAGES.filter((s) => f.reserved || s !== 'reservation').map((s) => (
            <li key={s} className={`flex flex-wrap items-baseline justify-between gap-x-4 border-t border-rule py-2 first:border-t-0 ${s === f.stage ? 'font-semibold' : ''}`}>
              <span className="text-body">{t(`offplan.stages.${s}`)}</span>
              <span className="tabular-nums">{t('offplan.upTo', { pct: capAt(s, f.reserved, r0), amount: dh((f.price * capAt(s, f.reserved, r0)) / 100) })}</span>
            </li>
          ))}
        </ol>
        <p className="m-0 text-meta text-ink-soft">{t('offplan.works')}</p>
        {f.paid ? <Note tone={r.over ? 'warn' : 'law'} quiet><p className="m-0 text-body">{t(r.over ? 'offplan.over' : 'offplan.within', { amount: dh(r.capAmount) })}</p></Note> : null}
        {r.register ? <p className="m-0 text-body">{t('offplan.register')}</p> : null}
        <Arts paths={[...r.cites.cap, ...(r.register ? r.cites.register : [])]} />
      </section>

      {f.delivery ? (
        <section className={CARD} aria-live="polite">
          <h2 className="m-0 text-lead font-semibold">{t('offplan.delay')}</h2>
          <p className="m-0 text-body">{t(r.late ? 'offplan.late' : 'offplan.notLate', { date: date(r.due) })}</p>
          {r.late ? (
            <>
              {f.notice ? (
                <div className="flex flex-wrap items-baseline justify-between gap-x-4 border-t border-rule pt-3">
                  <span className="text-body font-semibold">{t('offplan.penalty', { months: r.penalty.months })}</span>
                  <b className="text-lead tabular-nums text-[var(--t)]">{dh(r.penalty.amount)}</b>
                </div>
              ) : <p className="m-0 text-meta text-amended">{t('offplan.needNotice')}</p>}
              <Arts paths={r.cites.delay} />
              <div className="flex flex-wrap items-baseline justify-between gap-x-4 border-t border-rule pt-3">
                <span className="text-body font-semibold">{t('offplan.rescind')}</span>
                <b className="text-lead tabular-nums text-[var(--t)]">{dh(r.rescission)}</b>
              </div>
              <p className="m-0 text-meta text-ink-soft">{t('offplan.rescindNote')}</p>
              <Arts paths={r.cites.rescission} />
            </>
          ) : null}
        </section>
      ) : null}
      <Note tone="law" quiet><p className="m-0 text-meta">{t('offplan.reservation')}</p><Arts paths={r.cites.reservation} /></Note>
    </KitPage>
  );
}
