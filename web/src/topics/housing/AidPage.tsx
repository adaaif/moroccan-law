import { useState } from 'react';
import { Button, Note, PageSkeleton } from '@/shared/components/ui';
import { useRateOn } from '../kit/api';
import { KitPage } from '../kit/parts';
import { aid, type AidInput, type Owns } from './rules/aid';
import { Arts, CARD, FIELD } from './parts';
import { useHousingT } from './strings';
import { todayIso } from '@/shared/services/today';

const today = () => todayIso();
const PLATFORM = 'https://www.daamsakane.ma';

/** «دعم السكن» (H13 of the housing plan): each condition of the aid read on its article, the amount by the price, and
 *  the five years after the final deed. The application itself is made on the ministry's platform. On the phone only. */
export default function AidPage({ slug }: { slug: string }) {
  const { t, i18n } = useHousingT();
  const nf = new Intl.NumberFormat(i18n.language === 'fr' ? 'fr-MA' : 'ar-MA', { maximumFractionDigits: 0 });
  const dh = (n: number) => t('dh', { amount: nf.format(n) });
  const date = (d: string) => new Date(`${d}T12:00:00Z`).toLocaleDateString(i18n.language === 'fr' ? 'fr-MA' : 'ar-MA', { dateStyle: 'long' });
  const [f, setF] = useState<AidInput>({ moroccan: true, before: false, owns: 'no', price: 280000, permit: '2024-01-01', rooms: 2,
    firstSale: true, deed: '', on: today() });
  const set = (p: Partial<AidInput>) => setF({ ...f, ...p });
  const rates = useRateOn(slug, 'aid', f.on);
  if (!rates) return <KitPage slug={slug} title={t('aid.title')} lead={t('aid.lead')}><PageSkeleton /></KitPage>;
  const r = aid(f, rates);
  const tick = (key: 'moroccan' | 'before' | 'firstSale') => (
    <label className="inline-flex min-h-11 items-center gap-2">
      <input type="checkbox" checked={f[key]} onChange={() => set({ [key]: !f[key] })} className="size-5" />{t(`aid.${key}`)}
    </label>
  );
  return (
    <KitPage slug={slug} title={t('aid.title')} lead={t('aid.lead')}>
      <section className={`${CARD} sm:grid sm:grid-cols-2 sm:gap-4`}>
        <label className="flex flex-col gap-1.5"><span className="text-body font-semibold">{t('aid.price')}</span>
          <input type="number" inputMode="decimal" min={0} value={f.price || ''} onChange={(e) => set({ price: Number(e.target.value) })} className={FIELD} dir="ltr" />
          <span className="text-meta text-ink-soft">{t('aid.priceHint')}</span></label>
        <label className="flex flex-col gap-1.5"><span className="text-body font-semibold">{t('aid.owns')}</span>
          <select value={f.owns} onChange={(e) => set({ owns: e.target.value as Owns })} className={FIELD}>
            {(['no', 'indivision', 'yes'] as const).map((o) => <option key={o} value={o}>{t(`aid.ownsOf.${o}`)}</option>)}
          </select></label>
        <label className="flex flex-col gap-1.5"><span className="text-body font-semibold">{t('aid.permit')}</span>
          <input type="date" value={f.permit} onChange={(e) => set({ permit: e.target.value })} className={FIELD} dir="ltr" /></label>
        <label className="flex flex-col gap-1.5"><span className="text-body font-semibold">{t('aid.rooms')}</span>
          <input type="number" min={0} value={f.rooms} onChange={(e) => set({ rooms: Number(e.target.value) })} className={FIELD} dir="ltr" /></label>
        <div className="flex flex-col gap-0.5 sm:col-span-2">{tick('moroccan')}{tick('before')}{tick('firstSale')}</div>
      </section>

      <section className={CARD} aria-live="polite">
        <ul className="m-0 flex list-none flex-col p-0">
          {r.conditions.map((c) => (
            <li key={c.key} className="flex flex-col gap-1 border-t border-rule py-2.5 first:border-t-0">
              <span className="text-body"><b aria-hidden="true" className={c.met ? 'text-[var(--t)]' : 'text-amended'}>{c.met ? '✓' : '✗'}</b>{' '}
                {t(`aid.condition.${c.key}`)}</span>
              <Arts paths={c.cites} />
            </li>
          ))}
        </ul>
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 border-t-2 border-rule pt-3">
          <span className="text-body font-bold">{t('aid.amount')}</span>
          <b className="text-h2 tabular-nums text-[var(--t)]">{r.eligible ? dh(r.amount) : '—'}</b>
        </div>
        <Note tone={r.eligible ? 'law' : 'warn'} quiet>
          <p className="m-0 text-body">{r.eligible ? t(`aid.band.${r.band}`) : t('aid.notEligible')}</p>
        </Note>
        <Button href={PLATFORM} target="_blank" rel="noreferrer">{t('aid.platform')}</Button>
      </section>

      <section className={CARD}>
        <h2 className="m-0 text-lead font-semibold">{t('aid.after')}</h2>
        <p className="m-0 text-body">{t('aid.deedDays', { days: r.deedDays })}</p>
        <label className="flex flex-col gap-1.5 sm:max-w-xs"><span className="text-body font-semibold">{t('aid.deed')}</span>
          <input type="date" value={f.deed} onChange={(e) => set({ deed: e.target.value })} className={FIELD} dir="ltr" /></label>
        {r.until ? <p className="m-0 text-body font-semibold">{t('aid.until', { date: date(r.until) })}</p> : null}
        <p className="m-0 text-meta text-ink-soft">{t('aid.afterNote')}</p>
        <Arts paths={['/ma/loi/50-22/art_8', '/ma/loi/55-23/art_10', '/ma/loi/50-25/art_8', '/ma/decret/2-23-350/art_6', '/ma/decret/2-23-350/art_6-bis']} />
      </section>
    </KitPage>
  );
}
