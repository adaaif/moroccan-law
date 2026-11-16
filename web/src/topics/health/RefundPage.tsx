import { Button, PageSkeleton } from '@/shared/components/ui';
import { todayIso } from '@/shared/services/today';
import { refPath, useRateOn } from '../kit/api';
import { KitPage } from '../kit/parts';
import { useProfile } from '../kit/profile';
import { AnswerCard, Chips, SourceFold } from '../kit/tool/parts';
import { useToolState } from '../kit/tool/state';
import { MoneyField, SplitBar } from './parts';
import { fundOf, refund, type Fund, type Kind, type Long, type Place, type Rates } from './rules/refund';
import { articleLabel, useHealthT, useMoney } from './strings';

/** «شحال غادي يرجع ليك؟» (S17 of the health review): a care's price, the reader's fund (from their answer to the
 *  topic's question), what was paid for, where, and whether it is a long illness → what comes back and what stays, as one
 *  bar, each line with its article. It waits for a person's check (C4 «wait»). The inputs live in the address. */
export default function RefundPage({ slug }: { slug: string }) {
  const { t } = useHealthT();
  const money = useMoney();
  const [answer] = useProfile(slug);
  const [s, set] = useToolState({ f: fundOf(answer), k: 'medicine', p: 'private', l: 'no', a: '300' });
  const today = todayIso();
  const fund = (s.f === 'cnops' ? 'cnops' : 'cnss') as Fund;
  const rates = useRateOn(slug, fund === 'cnops' ? 'refund-cnops' : 'refund-cnss', today) as Rates | undefined;
  if (!rates) return <KitPage slug={slug} title={t('refund.title')} lead={t('refund.lead')}><PageSkeleton /></KitPage>;
  const kind = s.k as Kind, place = s.p as Place, long = s.l as Long;
  const price = Math.max(0, Number(s.a) || 0);
  const r = refund(price, fund, kind, place, long, rates);
  const dh = (x: number) => t('dh', { amount: money(x) });
  const decree = fund === 'cnops' ? '/ma/decret/2-05-736/art_1' : '/ma/decret/2-05-737/art_2';
  const cites = [decree, ...(kind === 'medicine' ? ['/ma/loi/65-00/art_12'] : []), ...(fund === 'cnops' && long !== 'no' ? ['/ma/decret/2-05-736/art_2'] : []), ...(long !== 'no' ? ['/ma/loi/65-00/art_9'] : [])];
  return (
    <KitPage slug={slug} title={t('refund.title')} lead={t('refund.lead')}>
      <AnswerCard share over={t('refund.over')} value={dh(r.back)} tone="good"
                  under={<p className="m-0">{t('refund.under', { left: dh(r.left), rate: r.rate })}</p>} />
      <SplitBar price={price} back={r.back} left={r.left} rate={r.rate} money={money} source={articleLabel(decree)} />
      <section className="flex flex-col gap-5 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <Chips label={t('refund.fund')} value={fund} onChange={(f) => set({ f })}
               options={(['cnss', 'cnops'] as const).map((k) => ({ key: k, label: t(`refund.funds.${k}`) }))} />
        <p className="m-0 text-meta text-ink-soft" style={{ marginTop: -12 }}>{fund === 'cnops' ? t('refund.cnops2027') : t('refund.fundNote')}</p>
        <Chips label={t('refund.kind')} value={kind} onChange={(k) => set({ k })}
               options={(['medicine', 'care', 'hospital'] as const).map((k) => ({ key: k, label: t(`refund.kinds.${k}`) }))} />
        {kind !== 'medicine' ? (
          <Chips label={t('refund.place')} value={place} onChange={(p) => set({ p })}
                 options={(['public', 'private'] as const).map((k) => ({ key: k, label: t(`refund.places.${k}`) }))} />
        ) : null}
        <Chips label={t('refund.long')} value={long} onChange={(l) => set({ l })}
               options={(['no', 'long', 'costly'] as const).map((k) => ({ key: k, label: t(`refund.longs.${k}`) }))} />
        <MoneyField label={t('refund.price')} value={s.a} onChange={(a) => set({ a })}
                    note={kind === 'medicine' ? t('refund.priceMedicine') : t('refund.priceCare')} />
      </section>
      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <p className="m-0 text-body">{t(`refund.why.${r.why}`)}</p>
        <p className="m-0 text-meta text-ink-soft">{t('refund.estimate')}</p>
        <SourceFold paths={cites} label={articleLabel} />
        <div className="flex flex-wrap gap-2"><Button to={refPath(slug, 'journeys/refund')}>{t('refund.toJourney')}</Button></div>
      </section>
    </KitPage>
  );
}
