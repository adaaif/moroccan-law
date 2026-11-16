import { PageSkeleton } from '@/shared/components/ui';
import { todayIso } from '@/shared/services/today';
import { useRateOn } from '../kit/api';
import { KitPage } from '../kit/parts';
import { AnswerCard, Chips, SourceFold } from '../kit/tool/parts';
import { useToolState } from '../kit/tool/state';
import { Inputs, Ledger, MoneyField } from './parts';
import { autoEntrepreneur, type Activity } from './rules/things';
import { articleLabel, useMoney, useTaxT } from './strings';

/** «المقاول الذاتي: شحال نخلص؟» (T17): the year's turnover collected and the activity give the tax (73-III), the
 *  complementary duty by the scale of 73-II-B-6°, the ceiling (42 ter); for services, one client above 80,000 a year
 *  withholds 30% on the excess (42 bis). */
export default function OwnPage({ slug }: { slug: string }) {
  const { t } = useTaxT();
  const { n, c } = useMoney();
  const [s, set] = useToolState({ r: '150000', a: 'service', b: '0' });
  const o = useRateOn(slug, 'own', todayIso());
  if (!o) return <KitPage slug={slug} title={t('own.title')} lead={t('own.lead')}><PageSkeleton /></KitPage>;
  const r = autoEntrepreneur(Math.max(0, Number(s.r) || 0), s.a as Activity, Number(s.b) || 0, o);
  return (
    <KitPage slug={slug} title={t('own.title')} lead={t('own.lead')}>
      <AnswerCard share over={t('own.total')} tone={r.over ? 'warn' : 'stamp'} value={t('dh', { amount: c(r.total) })}
                  under={<p className="m-0">{r.over ? t('own.over', { cap: n(r.cap) }) : t('own.declare')}</p>} />
      <Inputs>
        <Chips label={t('own.activity')} value={s.a} onChange={(a) => set({ a })} options={(['trade', 'service'] as const).map((k) => ({ key: k, label: t(`own.activities.${k}`) }))} />
        <MoneyField label={t('own.turnover')} value={s.r} onChange={(v) => set({ r: v })} />
        {s.a === 'service' ? <MoneyField label={t('own.client')} value={s.b} onChange={(v) => set({ b: v })} /> : null}
      </Inputs>
      <Ledger title={t('perYear')} lines={[
        { key: 'tax', label: t('own.tax', { rate: r.rate }), amount: r.tax, cites: ['/ma/code/cgi/art_73'] },
        { key: 'complementary', label: t('own.complementary'), note: t('own.complementaryNote'), amount: r.complementary, cites: ['/ma/code/cgi/art_73'] },
        { key: 'total', label: t('own.total'), amount: r.total, sum: true },
      ]}>
        {r.excess ? <p className="m-0 pt-3 text-body">{t('own.withheld', { excess: n(r.excess), amount: c(r.withheld) })}</p> : null}
      </Ledger>
      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <p className="m-0 text-meta text-ink-soft">{t('estimate')}</p>
        <SourceFold paths={['/ma/code/cgi/art_42-bis', '/ma/code/cgi/art_42-ter', '/ma/code/cgi/art_73', '/ma/code/cgi/art_82-bis']} label={articleLabel} />
      </section>
    </KitPage>
  );
}
