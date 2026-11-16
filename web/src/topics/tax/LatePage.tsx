import { PageSkeleton } from '@/shared/components/ui';
import { todayIso } from '@/shared/services/today';
import { useRateOn } from '../kit/api';
import { KitPage } from '../kit/parts';
import { AnswerCard, Chips, DayChips, SourceFold } from '../kit/tool/parts';
import { useToolState } from '../kit/tool/state';
import { Inputs, Ledger, MoneyField } from './parts';
import { lateCost, type LateKind } from './rules/things';
import { articleLabel, useMoney, useTaxT } from './strings';

/** «تأخرت: شحال الزيادة؟» (T18): the amount, the day it was due and the day it is paid give the penalty (10%, 5% within 30
 *  days) and the increase month by month (5%, then 0.5% for each month begun) of CGI 208 and 47.06 art. 147; a commune's
 *  housing or services tax of 1,000 dirhams or less bears none; registration and the vignette at least 100. */
export default function LatePage({ slug }: { slug: string }) {
  const { t } = useTaxT();
  const { c } = useMoney();
  const today = todayIso();
  const [s, set] = useToolState({ a: '5000', k: 'state', d: `${today.slice(0, 4)}-03-01` <= today ? `${today.slice(0, 4)}-03-01` : today, p: today });
  const l = useRateOn(slug, 'late', today);
  if (!l) return <KitPage slug={slug} title={t('late.title')} lead={t('late.lead')}><PageSkeleton /></KitPage>;
  const r = lateCost(Math.max(0, Number(s.a) || 0), s.d, s.p, s.k as LateKind, l);
  const local = s.k === 'local';
  return (
    <KitPage slug={slug} title={t('late.title')} lead={t('late.lead')}>
      <AnswerCard share over={t('late.total')} tone={r.total ? 'warn' : 'good'} value={t('dh', { amount: c(r.total) })}
                  under={<p className="m-0">{r.free ? t('late.free') : r.days ? t('late.months', { count: r.months }) : t('late.none')}</p>} />
      <Inputs>
        <MoneyField label={t('late.amount')} value={s.a} onChange={(a) => set({ a })} />
        <Chips label={t('late.kind')} value={s.k} onChange={(k) => set({ k })} options={(['state', 'local', 'registration'] as const).map((k) => ({ key: k, label: t(`late.kinds.${k}`) }))} />
        <DayChips label={t('late.due')} value={s.d} onChange={(d) => set({ d })} ago={[30, 90, 365]} />
        <DayChips label={t('late.paid')} value={s.p} onChange={(p) => set({ p })} ago={[0]} />
      </Inputs>
      {r.total ? (
        <Ledger title={t('late.total')} lines={[
          { key: 'penalty', label: t('late.penalty', { rate: r.penaltyRate }), amount: r.penalty, cites: [local ? '/ma/loi/47-06/art_147' : '/ma/code/cgi/art_208'] },
          { key: 'increase', label: t('late.increase', { count: Math.max(0, r.months - 1) }), amount: r.increase, cites: [local ? '/ma/loi/47-06/art_147' : '/ma/code/cgi/art_208'] },
          { key: 'total', label: t('late.total'), amount: r.total, sum: true },
        ]} />
      ) : null}
      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <p className="m-0 text-meta text-ink-soft">{t('estimate')}</p>
        <SourceFold paths={['/ma/code/cgi/art_184', '/ma/code/cgi/art_208', '/ma/loi/47-06/art_147']} label={articleLabel} />
      </section>
    </KitPage>
  );
}
