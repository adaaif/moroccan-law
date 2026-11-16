import { PageSkeleton } from '@/shared/components/ui';
import { todayIso } from '@/shared/services/today';
import { useRateOn } from '../kit/api';
import { KitPage } from '../kit/parts';
import { AnswerCard, Chips, SourceFold } from '../kit/tool/parts';
import { useToolState } from '../kit/tool/state';
import { Inputs, Ledger, MoneyField } from './parts';
import { rentTax } from './rules/income';
import { articleLabel, useMoney, useTaxT } from './strings';

/** «شحال على الكراء ديالي؟» (T12): the month's gross rent; with a private tenant, the scale on 60% of it, declared before 1
 *  March; with a company or an administration, the withholding at 10% or 15% (160 bis), or the 20% final rate on option
 *  (64-IV) side by side. */
export default function RentPage({ slug }: { slug: string }) {
  const { t } = useTaxT();
  const { c } = useMoney();
  const [s, set] = useToolState({ g: '4000', w: 'person' });
  const scale = useRateOn(slug, 'scale', todayIso());
  const rent = useRateOn(slug, 'rent', todayIso());
  if (!scale || !rent) return <KitPage slug={slug} title={t('rent.title')} lead={t('rent.lead')}><PageSkeleton /></KitPage>;
  const r = rentTax(Math.max(0, Number(s.g) || 0) * 12, { scale, rent });
  const company = s.w === 'company';
  return (
    <KitPage slug={slug} title={t('rent.title')} lead={t('rent.lead')}>
      <AnswerCard share over={company ? t('rent.withheld', { rate: r.withheldRate }) : t('rent.scale')}
                  value={t('dh', { amount: c(company ? r.withheld : r.scale) })}
                  under={<p className="m-0">{company ? t('rent.withheldNote') : t('rent.scaleNote', { rate: rent.abatement })}</p>} />
      <Inputs>
        <MoneyField label={t('rent.gross')} value={s.g} onChange={(g) => set({ g })} />
        <Chips label={t('rent.who')} value={s.w} onChange={(w) => set({ w })} options={(['person', 'company'] as const).map((k) => ({ key: k, label: t(`rent.whos.${k}`) }))} />
      </Inputs>
      <Ledger title={t('perYear')} lines={[
        { key: 'gross', label: t('rent.gross'), amount: r.gross, cites: ['/ma/code/cgi/art_64'] },
        { key: 'abatement', label: `40%`, amount: r.abatement, minus: true, cites: ['/ma/code/cgi/art_64'] },
        { key: 'net', label: t('salary.lines.taxable'), amount: r.net, sum: true },
        { key: 'scale', label: t('rent.scale'), amount: r.scale, cites: ['/ma/code/cgi/art_73'] },
        ...(company ? [{ key: 'withheld', label: t('rent.withheld', { rate: r.withheldRate }), note: t('rent.withheldNote'), amount: r.withheld, cites: ['/ma/code/cgi/art_160-bis'] }] : []),
        { key: 'final', label: t('rent.final'), note: company ? t('rent.finalNote') : undefined, amount: company ? r.final : null, cites: ['/ma/code/cgi/art_64'] },
      ]}>
        <p className="m-0 pt-3 text-meta text-ink-soft">{t('rent.declare')}</p>
      </Ledger>
      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <p className="m-0 text-meta text-ink-soft">{t('estimate')}</p>
        <SourceFold paths={['/ma/code/cgi/art_61', '/ma/code/cgi/art_64', '/ma/code/cgi/art_73', '/ma/code/cgi/art_82', '/ma/code/cgi/art_160-bis']} label={articleLabel} />
      </section>
    </KitPage>
  );
}
