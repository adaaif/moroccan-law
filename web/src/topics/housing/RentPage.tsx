import { Button, Note, PageSkeleton } from '@/shared/components/ui';
import { useRateOn } from '../kit/api';
import { KitPage } from '../kit/parts';
import { whatsapp, here } from '../kit/share';
import { depositCheck, rentCheck, type Kind } from './rules/rent';
import { Arts, CARD, FIELD } from './parts';
import { useHousingT } from './strings';
import { todayIso } from '@/shared/services/today';
import { useToolState } from '../kit/tool/state';

const today = () => todayIso();

/** «واش الزيادة قانونية؟» (H10 of the housing plan, shown before a professional's review by an editorial call): the day
 *  a rent may rise and the most it may rise, then the deposit's cap and the day it is due back. On the phone only. */
export default function RentPage({ slug }: { slug: string }) {
  const { t, i18n } = useHousingT();
  const nf = new Intl.NumberFormat(i18n.language === 'fr' ? 'fr-MA' : 'ar-MA', { maximumFractionDigits: 2 });
  const dh = (n: number) => t('dh', { amount: nf.format(n) });
  const date = (d: string) => new Date(`${d}T12:00:00Z`).toLocaleDateString(i18n.language === 'fr' ? 'fr-MA' : 'ar-MA', { dateStyle: 'long' });
  // In the address like every tool's (PX12): its link shared opened 2,500 DH and 1 Sep 2023 whatever was typed.
  const [q, set] = useToolState({ k: 'home', r: '2500', p: '', s: '2023-09-01', dp: '', rt: '' });
  const kind = (['home', 'professional', 'commercial'].includes(q.k) ? q.k : 'home') as Kind;
  const rent = Number(q.r) || 0, proposed = Number(q.p) || 0, deposit = Number(q.dp) || 0;
  const since = q.s, returned = q.rt;
  const setKind = (k: Kind) => set({ k });
  const setRent = (n: number) => set({ r: n ? String(n) : '' });
  const setProposed = (n: number) => set({ p: n ? String(n) : '' });
  const setSince = (d: string) => set({ s: d });
  const setDeposit = (n: number) => set({ dp: n ? String(n) : '' });
  const setReturned = (d: string) => set({ rt: d });
  const on = today();
  const revision = useRateOn(slug, 'revision', on);
  const caps = useRateOn(slug, 'deposit', on);
  if (!revision || !caps) return <KitPage slug={slug} title={t('rent.title')} lead={t('rent.lead')}><PageSkeleton /></KitPage>;
  const r = rentCheck({ kind, rent, proposed, since, on }, revision);
  const d = depositCheck(rent, deposit, returned, caps);
  const num = (v: number, set: (n: number) => void) => (
    <input type="number" inputMode="decimal" min={0} value={v || ''} onChange={(e) => set(Number(e.target.value))} className={FIELD} dir="ltr" />
  );
  const share = () => whatsapp([t('rent.message'), t('rent.earliest', { date: date(r.earliest) }), `${t('rent.max')}: ${dh(r.max)}`,
    here()].join('\n'));
  return (
    <KitPage slug={slug} title={t('rent.title')} lead={t('rent.lead')}>
      <section className={CARD} aria-live="polite">
        <h2 className="m-0 text-lead font-semibold">{t('rent.increase')}</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="flex flex-col gap-1.5"><span className="text-body font-semibold">{t('rent.kind')}</span>
            <select value={kind} onChange={(e) => setKind(e.target.value as Kind)} className={FIELD}>
              {(['home', 'professional', 'commercial'] as const).map((k) => <option key={k} value={k}>{t(`rent.kinds.${k}`)}</option>)}
            </select></label>
          <label className="flex flex-col gap-1.5"><span className="text-body font-semibold">{t('rent.since')}</span>
            <input type="date" value={since} onChange={(e) => e.target.value && setSince(e.target.value)} className={FIELD} dir="ltr" />
            <span className="text-meta text-ink-soft">{t('rent.sinceHint')}</span></label>
          <label className="flex flex-col gap-1.5"><span className="text-body font-semibold">{t('rent.rent')}</span>{num(rent, setRent)}</label>
          <label className="flex flex-col gap-1.5"><span className="text-body font-semibold">{t('rent.proposed')}</span>{num(proposed, setProposed)}
            <span className="text-meta text-ink-soft">{t('rent.proposedHint')}</span></label>
        </div>
        <dl className="m-0 grid gap-x-6 gap-y-2 border-t border-rule pt-3 sm:grid-cols-2">
          <div className="flex flex-col"><dt className="text-meta text-ink-soft">{t('rent.earliestLabel')}</dt>
            <dd className="m-0 text-lead font-semibold tabular-nums text-[var(--t)]">{date(r.earliest)}</dd></div>
          <div className="flex flex-col"><dt className="text-meta text-ink-soft">{t('rent.max')} ({t('rent.rate', { rate: r.rate })})</dt>
            <dd className="m-0 text-lead font-semibold tabular-nums text-[var(--t)]">{dh(r.max)}</dd></div>
        </dl>
        {!rent && proposed ? <p className="m-0 text-body font-medium text-[var(--t)]">{t('rent.needRent')}</p> : null}
        {r.verdict !== 'none' ? (
          <Note tone={r.verdict === 'within' ? 'law' : 'warn'} quiet>
            <p className="m-0 text-body">{t(`rent.verdict.${r.verdict}`, { increase: nf.format(r.increase), rate: r.rate, date: date(r.earliest) })}</p>
          </Note>
        ) : null}
        {r.small ? <p className="m-0 text-meta">{t('rent.small', { amount: dh(r.courtMax) })}</p> : null}
        <p className="m-0 text-meta text-ink-soft">{t(kind === 'commercial' ? 'rent.howShop' : 'rent.how')}</p>
        <Arts paths={[...r.cites, ...(kind === 'commercial' ? ['/ma/loi/7-03/art_7'] : ['/ma/loi/67-12/art_37'])]} />
        <div className="flex flex-wrap gap-2"><Button onClick={share}>{t('share')}</Button></div>
      </section>

      {kind !== 'commercial' ? (
        <section className={CARD} aria-live="polite">
          <h2 className="m-0 text-lead font-semibold">{t('rent.deposit')}</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="flex flex-col gap-1.5"><span className="text-body font-semibold">{t('rent.depositPaid')}</span>{num(deposit, setDeposit)}</label>
            <label className="flex flex-col gap-1.5"><span className="text-body font-semibold">{t('rent.returned')}</span>
              <input type="date" value={returned} onChange={(e) => setReturned(e.target.value)} className={FIELD} dir="ltr" /></label>
          </div>
          <p className="m-0 text-body">{t('rent.depositMax', { amount: dh(d.max) })}</p>
          {deposit ? <Note tone={d.over ? 'warn' : 'law'} quiet><p className="m-0 text-body">{t(d.over ? 'rent.depositOver' : 'rent.depositOk')}</p></Note> : null}
          {d.returnBy ? <p className="m-0 text-body font-semibold">{t('rent.returnBy', { date: date(d.returnBy) })}</p> : null}
          <p className="m-0 text-meta text-ink-soft">{t('rent.depositNote')}</p>
          <Arts paths={d.cites} />
        </section>
      ) : null}
    </KitPage>
  );
}
