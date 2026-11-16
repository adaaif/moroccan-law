import { PageSkeleton } from '@/shared/components/ui';
import { todayIso } from '@/shared/services/today';
import { useRateOn } from '../kit/api';
import { KitPage } from '../kit/parts';
import { AnswerCard, Chips, SourceFold } from '../kit/tool/parts';
import Stepper from '../kit/tool/Stepper';
import { useToolState } from '../kit/tool/state';
import { Inputs, Ledger, MoneyField } from './parts';
import { sellTax } from './rules/things';
import { articleLabel, useMoney, useTaxT } from './strings';

/** «بعت عقار: شحال الضريبة؟» (T13): the price, the purchase price and its costs (15% unless more is given), the works,
 *  the years lived in it: the profit before the administration's coefficient (so the highest it can be), 20% of it and the
 *  3% minimum side by side, the exemptions (main home after five years, a year's sales up to 140,000). */
export default function SellPage({ slug }: { slug: string }) {
  const { t } = useTaxT();
  const { c } = useMoney();
  const [s, set] = useToolState({ p: '1200000', b: '700000', k: '', w: '0', y: '3', m: '0' });
  const p = useRateOn(slug, 'property', todayIso());
  if (!p) return <KitPage slug={slug} title={t('sell.title')} lead={t('sell.lead')}><PageSkeleton /></KitPage>;
  const price = Math.max(0, Number(s.p) || 0);
  const r = sellTax({ price, bought: Number(s.b) || 0, costs: s.k ? Number(s.k) : null, works: Number(s.w) || 0, sellCosts: 0, years: Number(s.y), main: s.m === '1', yearSales: 0 }, p);
  return (
    <KitPage slug={slug} title={t('sell.title')} lead={t('sell.lead')}>
      <AnswerCard share over={t(`sell.cases.${r.case}`)} tone={r.tax ? 'stamp' : 'good'} value={t('dh', { amount: c(r.tax) })}
                  under={<p className="m-0">{t('sell.deadline')}</p>} />
      <Inputs>
        <MoneyField label={t('sell.price')} value={s.p} onChange={(v) => set({ p: v })} />
        <MoneyField label={t('sell.bought')} value={s.b} onChange={(v) => set({ b: v })} />
        <MoneyField label={t('sell.costs')} value={s.k || '0'} onChange={(v) => set({ k: v === '0' ? '' : v })} note={t('sell.costsAuto', { amount: c(((Number(s.b) || 0) * p.costs) / 100) })} />
        <MoneyField label={t('sell.works')} value={s.w} onChange={(v) => set({ w: v })} />
        <Chips label={t('sell.main')} value={s.m} onChange={(m) => set({ m })} options={[{ key: '1', label: t('yes') }, { key: '0', label: t('no') }]} />
        {s.m === '1' ? <Stepper label={t('sell.years')} value={Number(s.y)} max={60} onChange={(v) => set({ y: String(v) })} /> : null}
      </Inputs>
      <Ledger title={t('sell.profit')} lines={[
        { key: 'price', label: t('sell.price'), amount: price },
        { key: 'bought', label: t('sell.bought'), amount: Number(s.b) || 0, minus: true, cites: ['/ma/code/cgi/art_65'] },
        { key: 'costs', label: t('sell.costs'), amount: r.costs, minus: true, cites: ['/ma/code/cgi/art_65'] },
        { key: 'works', label: t('sell.works'), amount: Number(s.w) || 0, minus: true, cites: ['/ma/code/cgi/art_65'] },
        { key: 'profit', label: t('sell.profit'), amount: r.profit, sum: true },
        { key: 'onProfit', label: t('sell.onProfit'), amount: r.onProfit, cites: ['/ma/code/cgi/art_73'] },
        { key: 'minimum', label: t('sell.minimum'), amount: r.minimum, cites: ['/ma/code/cgi/art_144'] },
      ]}>
        <p className="m-0 pt-3 text-meta text-ink-soft">{t('sell.coefficient')}</p>
      </Ledger>
      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <p className="m-0 text-meta text-ink-soft">{t('estimate')}</p>
        <SourceFold paths={['/ma/code/cgi/art_63', '/ma/code/cgi/art_65', '/ma/code/cgi/art_73', '/ma/code/cgi/art_83', '/ma/code/cgi/art_144', '/ma/code/cgi/art_173']} label={articleLabel} />
      </section>
    </KitPage>
  );
}
