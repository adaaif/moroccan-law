import { PageSkeleton } from '@/shared/components/ui';
import { todayIso } from '@/shared/services/today';
import { useRateOn } from '../kit/api';
import { KitPage } from '../kit/parts';
import { AnswerCard, Chips, SourceFold } from '../kit/tool/parts';
import Stepper from '../kit/tool/Stepper';
import { useToolState } from '../kit/tool/state';
import { Inputs } from './parts';
import { carTax, type Fuel } from './rules/things';
import { articleLabel, useMoney, useTaxT } from './strings';

/** «الفينييت ديالي شحال؟» (T16): horsepower and fuel give the year's tax (262-I-A), electric and hybrid exempt (260-15°),
 *  a private diesel pick-up at the petrol tariff; a car new this year pays a twelfth for each month left (262-II), within
 *  60 days of its grey card's receipt (261). The tariff drawn as its table, the reader's cell lit. */
export default function CarPage({ slug }: { slug: string }) {
  const { t } = useTaxT();
  const { n } = useMoney();
  const [s, set] = useToolState({ cv: '6', f: 'diesel', p: '0', m: '0' });
  const c = useRateOn(slug, 'car', todayIso());
  if (!c) return <KitPage slug={slug} title={t('car.title')} lead={t('car.lead')}><PageSkeleton /></KitPage>;
  const fuel = s.f as Fuel;
  const month = Number(s.m) || 0;
  const r = carTax(Number(s.cv), fuel, s.p === '1', month || null, c);
  const bands = ['lt8', '8_10', '11_14', '15'];
  const heads = ['< 8', '8–10', '11–14', '≥ 15'];
  return (
    <KitPage slug={slug} title={t('car.title')} lead={t('car.lead')}>
      <AnswerCard share over={t('car.title')} tone={fuel === 'electric' ? 'good' : 'stamp'}
                  value={fuel === 'electric' ? t('car.free') : t('dh', { amount: n(r.due) })}
                  under={<p className="m-0">{month ? `${t('car.months', { count: r.months })} · ${t('car.dueNew')}` : t('car.due')}</p>} />
      <Inputs>
        <Stepper label={t('car.cv')} value={Number(s.cv)} min={1} max={40} onChange={(v) => set({ cv: String(v) })} />
        <Chips label={t('car.fuel')} value={s.f} onChange={(f) => set({ f })} options={(['petrol', 'diesel', 'electric'] as const).map((k) => ({ key: k, label: t(`car.fuels.${k}`) }))} />
        {fuel === 'diesel' ? <Chips label={t('car.pickup')} value={s.p} onChange={(p) => set({ p })} options={[{ key: '0', label: t('no') }, { key: '1', label: t('yes') }]} /> : null}
        <Chips label={t('car.new')} value={month ? 'y' : 'n'} onChange={(v) => set({ m: v === 'y' ? String(Number(todayIso().slice(5, 7))) : '0' })} options={[{ key: 'n', label: t('no') }, { key: 'y', label: t('yes') }]} />
        {month ? <Stepper label={t('car.month')} value={month} min={1} max={12} onChange={(v) => set({ m: String(v) })} /> : null}
      </Inputs>
      <section className="flex flex-col gap-3 overflow-x-auto rounded-card bg-sheet px-5 py-5 sm:px-7">
        {/* The tariff as art. 262 prints it, a band a row: the reader's cell lit. */}
        <table className="w-full border-collapse text-body tabular-nums">
          <thead><tr className="border-b-2 border-ink text-meta"><th className="py-2 text-start">{t('car.cv')}</th><th className="text-end">{t('car.fuels.petrol')}</th><th className="text-end">{t('car.fuels.diesel')}</th></tr></thead>
          <tbody>
            {bands.map((b, i) => (
              <tr key={b} className="border-b border-rule">
                <th className="py-2 text-start font-medium"><bdi dir="ltr">{heads[i]}</bdi></th>
                {(['petrol', 'diesel'] as const).map((f) => {
                  const on = fuel !== 'electric' && r.band === b && (f === 'petrol' ? fuel === 'petrol' || s.p === '1' : fuel === 'diesel' && s.p !== '1');
                  return <td key={f} className="py-1 text-end"><span dir="ltr" className={`inline-block rounded-control px-2 py-1 ${on ? 'bg-[var(--t)] font-bold text-on-sign' : ''}`}>{n(c[`${f}_${b}`])}</span></td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
        <p className="m-0 text-meta text-ink-soft">{t('car.late')}</p>
        <SourceFold paths={['/ma/code/cgi/art_259', '/ma/code/cgi/art_260', '/ma/code/cgi/art_261', '/ma/code/cgi/art_262', '/ma/code/cgi/art_208']} label={articleLabel} />
      </section>
    </KitPage>
  );
}
