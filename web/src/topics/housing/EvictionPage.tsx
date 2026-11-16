import { useState } from 'react';
import { Note, PageSkeleton } from '@/shared/components/ui';
import { useRateOn } from '../kit/api';
import { KitPage } from '../kit/parts';
import { noticeCheck, type NoticeInput, type Premises, type Reason } from './rules/eviction';
import { Arts, CARD, FIELD } from './parts';
import { useHousingT } from './strings';
import { todayIso } from '@/shared/services/today';

const today = () => todayIso();

/** «بغا يخرجني» (H11 of the housing plan): the notice in hand read against arts 45–49 of 67.12 (49.16 art. 26 for a
 *  shop), the day to leave at the earliest, and what the law sets if a court validates it. Validating the notice and
 *  every sum the law leaves to the court stay the court's. On the phone only. */
export default function EvictionPage({ slug }: { slug: string }) {
  const { t, i18n } = useHousingT();
  const nf = new Intl.NumberFormat(i18n.language === 'fr' ? 'fr-MA' : 'ar-MA', { maximumFractionDigits: 2 });
  const dh = (n: number) => t('dh', { amount: nf.format(n) });
  const date = (d: string) => new Date(`${d}T12:00:00Z`).toLocaleDateString(i18n.language === 'fr' ? 'fr-MA' : 'ar-MA', { dateStyle: 'long' });
  const [f, setF] = useState<NoticeInput>({ premises: 'home', reason: 'live', dated: today(), received: today(), months: 2, days: 0,
    reasonStated: true, wholePremises: true, ownedSince: '', offeredSimilar: false, rent: 2500, tenantSince: '' });
  const set = (p: Partial<NoticeInput>) => setF({ ...f, ...p });
  const home = useRateOn(slug, 'eviction', f.received);
  const shop = useRateOn(slug, 'shop', f.received);
  if (!home || !shop) return <KitPage slug={slug} title={t('eviction.title')} lead={t('eviction.lead')}><PageSkeleton /></KitPage>;
  const r = noticeCheck(f, { home, shop });
  const tick = (key: keyof NoticeInput) => (
    <label className="inline-flex min-h-11 items-center gap-2">
      <input type="checkbox" checked={Boolean(f[key])} onChange={() => set({ [key]: !f[key] } as Partial<NoticeInput>)} className="size-5" />
      {t(`eviction.${key}`)}
    </label>
  );
  const reasons: Reason[] = ['live', 'rebuild', 'arrears', 'other'];
  return (
    <KitPage slug={slug} title={t('eviction.title')} lead={t('eviction.lead')}>
      <section className={`${CARD} sm:grid sm:grid-cols-2 sm:gap-4`}>
        <label className="flex flex-col gap-1.5"><span className="text-body font-semibold">{t('eviction.premises')}</span>
          <select value={f.premises} onChange={(e) => set({ premises: e.target.value as Premises })} className={FIELD}>
            {(['home', 'shop'] as const).map((p) => <option key={p} value={p}>{t(`eviction.premisesOf.${p}`)}</option>)}
          </select></label>
        <label className="flex flex-col gap-1.5"><span className="text-body font-semibold">{t('eviction.reason')}</span>
          <select value={f.reason} onChange={(e) => set({ reason: e.target.value as Reason })} className={FIELD}>
            {reasons.map((x) => <option key={x} value={x}>{t(`eviction.reasons.${f.premises}.${x}`)}</option>)}
          </select></label>
        <label className="flex flex-col gap-1.5"><span className="text-body font-semibold">{t('eviction.received')}</span>
          <input type="date" value={f.received} onChange={(e) => e.target.value && set({ received: e.target.value })} className={FIELD} dir="ltr" /></label>
        <div className="flex gap-3">
          <label className="flex min-w-0 flex-1 flex-col gap-1.5"><span className="text-body font-semibold">{t('eviction.months')}</span>
            <input type="number" min={0} value={f.months} onChange={(e) => set({ months: Number(e.target.value) })} className={FIELD} dir="ltr" /></label>
          <label className="flex min-w-0 flex-1 flex-col gap-1.5"><span className="text-body font-semibold">{t('eviction.days')}</span>
            <input type="number" min={0} value={f.days} onChange={(e) => set({ days: Number(e.target.value) })} className={FIELD} dir="ltr" /></label>
        </div>
        <label className="flex flex-col gap-1.5"><span className="text-body font-semibold">{t('eviction.rent')}</span>
          <input type="number" inputMode="decimal" min={0} value={f.rent || ''} onChange={(e) => set({ rent: Number(e.target.value) })} className={FIELD} dir="ltr" /></label>
        {f.premises === 'home' && f.reason === 'live' ? (
          <>
            <label className="flex flex-col gap-1.5"><span className="text-body font-semibold">{t('eviction.dated')}</span>
              <input type="date" value={f.dated} onChange={(e) => set({ dated: e.target.value })} className={FIELD} dir="ltr" /></label>
            <label className="flex flex-col gap-1.5"><span className="text-body font-semibold">{t('eviction.ownedSince')}</span>
              <input type="date" value={f.ownedSince} onChange={(e) => set({ ownedSince: e.target.value })} className={FIELD} dir="ltr" /></label>
          </>
        ) : null}
        {f.premises === 'shop' ? (
          <label className="flex flex-col gap-1.5"><span className="text-body font-semibold">{t('eviction.tenantSince')}</span>
            <input type="date" value={f.tenantSince} onChange={(e) => set({ tenantSince: e.target.value })} className={FIELD} dir="ltr" /></label>
        ) : null}
        <div className="flex flex-col gap-0.5 sm:col-span-2">
          {tick('reasonStated')}
          {f.premises === 'home' ? tick('wholePremises') : null}
          {f.premises === 'home' && f.reason === 'live' ? tick('offeredSimilar') : null}
        </div>
      </section>

      <section className={CARD} aria-live="polite">
        <h2 className="m-0 text-lead font-semibold">{t('eviction.reading')}</h2>
        <ul className="m-0 flex list-none flex-col p-0">
          {r.checks.map((c) => (
            <li key={c.key} className="flex flex-col gap-1 border-t border-rule py-2.5 first:border-t-0">
              <span className="text-body"><b aria-hidden="true" className={c.met ? 'text-[var(--t)]' : c.met === null ? 'text-ink-soft' : 'text-amended'}>{c.met ? '✓' : c.met === null ? '؟' : '✗'}</b>{' '}
                {t(`eviction.check.${c.key}.${c.met ? 'met' : c.met === null ? 'unknown' : 'missed'}`)}</span>
              <Arts paths={c.cites} />
            </li>
          ))}
        </ul>
        <Note tone={r.valid ? 'law' : 'warn'} quiet>
          <p className="m-0 text-body">{t(r.valid ? 'eviction.seemsValid' : 'eviction.missing')}</p>
        </Note>
        <p className="m-0 text-body font-semibold">{t('eviction.leaveBy', { date: date(r.leaveBy) })}</p>
        {r.lapsesOn ? <p className="m-0 text-meta">{t('eviction.lapses', { date: date(r.lapsesOn) })}</p> : null}
      </section>

      <section className={CARD}>
        <h2 className="m-0 text-lead font-semibold">{t('eviction.ifValidated')}</h2>
        <ul className="m-0 flex list-none flex-col p-0">
          {r.sums.map((s) => (
            <li key={s.key} className="flex flex-col gap-1 border-t border-rule py-2.5 first:border-t-0">
              <div className="flex flex-wrap items-baseline justify-between gap-x-4">
                <span className="text-body font-semibold">{t(`eviction.sum.${s.key}`)}</span>
                {s.amount !== null ? <b className="text-lead tabular-nums text-[var(--t)]">{dh(s.amount)}</b> : null}
              </div>
              <span className="text-meta text-ink-soft">{t(`eviction.sumNote.${s.key}`)}</span>
              {s.court && s.key === 'yearOfRent' ? <span className="text-meta text-amended">{t('eviction.arrearsCourt')}</span> : null}
              <Arts paths={s.cites} />
            </li>
          ))}
        </ul>
        <p className="m-0 text-meta text-ink-soft">{t('eviction.noSelfHelp')}</p>
        <Arts paths={['/ma/loi/67-12/art_44', '/ma/dahir/1-59-413/art_441', '/ma/dahir/1-59-413/art_570']} />
      </section>
    </KitPage>
  );
}
