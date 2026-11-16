import { PageSkeleton } from '@/shared/components/ui';
import { todayIso } from '@/shared/services/today';
import { useRateOn } from '../kit/api';
import { KitPage } from '../kit/parts';
import { AnswerCard, Chips, SourceFold } from '../kit/tool/parts';
import Stepper from '../kit/tool/Stepper';
import { useToolState } from '../kit/tool/state';
import { Inputs, Ledger, MoneyField, Staircase, YearChips } from './parts';
import { pensionTax, type Scheme } from './rules/income';
import { articleLabel, useMoney, useTaxT, yearDay } from './strings';

/** «واش المعاش ديالي فيه الضريبة؟» (T11): which scheme pays, the month's gross pension, the dependents: exempt for a basic
 *  scheme from 2026 (57-27°, half the tax off in 2025), a CIMR group contract on 28-III's conditions; any other abated
 *  70% then 40% (60-I) and taxed on the scale; a foreign pension's tax 80% off (76). */
export default function PensionPage({ slug }: { slug: string }) {
  const { t } = useTaxT();
  const { c } = useMoney();
  const [s, set] = useToolState({ y: todayIso().slice(0, 4) >= '2026' ? '2026' : '2025', g: '8000', p: 'basic', k: '0' });
  const day = yearDay(s.y, todayIso());
  const scale = useRateOn(slug, 'scale', day);
  const family = useRateOn(slug, 'family', day);
  const pension = useRateOn(slug, 'pension', day);
  if (!scale || !family || !pension) return <KitPage slug={slug} title={t('pension.title')} lead={t('pension.lead')}><PageSkeleton /></KitPage>;
  const scheme = s.p as Scheme;
  const gross = Math.max(0, Number(s.g) || 0) * 12;
  const r = pensionTax(gross, scheme, Number(s.k), { scale, family, pension });
  const share = scheme === 'basic' ? pension.basic_reduction : scheme === 'foreign' ? pension.foreign_reduction : 0;
  return (
    <KitPage slug={slug} title={t('pension.title')} lead={t('pension.lead')}>
      <AnswerCard share over={t('pension.tax')} tone={r.exempt || !r.tax ? 'good' : 'stamp'}
                  value={r.exempt ? t('pension.exempt') : t('dh', { amount: c(r.tax) })}
                  under={<p className="m-0">{r.exempt ? t('pension.exemptLine') : t('pension.monthly', { tax: c(r.tax / 12) })}</p>}>
        {scheme === 'basic' && share ? <p className="m-0 text-meta text-ink-soft">{t('pension.half')}</p> : null}
      </AnswerCard>
      <Inputs>
        <Chips label={t('pension.scheme')} value={s.p} onChange={(p) => set({ p })}
               options={(['basic', 'cimr', 'other', 'foreign'] as const).map((k) => ({ key: k, label: t(`pension.schemes.${k}`) }))} />
        <MoneyField label={t('pension.gross')} value={s.g} onChange={(g) => set({ g })} />
        <Stepper label={t('salary.dependents')} value={Number(s.k)} max={10} onChange={(v) => set({ k: String(v) })} />
        <YearChips value={s.y} onChange={(y) => set({ y })} />
        {scheme === 'cimr' ? <p className="m-0 text-meta text-ink-soft">{t('pension.cimrNote')}</p> : null}
      </Inputs>
      {r.exempt ? null : (
        <>
          <section className="rounded-card bg-sheet px-5 py-5 sm:px-7"><Staircase slices={r.slices} income={r.taxable} /></section>
          <Ledger title={t('perYear')} lines={[
            { key: 'gross', label: t('pension.gross'), amount: gross },
            { key: 'abatement', label: t('pension.abatement'), amount: r.abatement, minus: true, cites: ['/ma/code/cgi/art_60'] },
            { key: 'taxable', label: t('pension.taxable'), amount: r.taxable, sum: true },
            { key: 'scale', label: t('salary.lines.scale'), amount: r.scale, cites: ['/ma/code/cgi/art_73'] },
            { key: 'family', label: t('salary.lines.family', { count: Number(s.k), per: family.per }), amount: r.family, minus: true, cites: ['/ma/code/cgi/art_74'] },
            ...(r.reduction ? [{ key: 'reduction', label: t('pension.reduction', { rate: share }), amount: r.reduction, minus: true, cites: [scheme === 'foreign' ? '/ma/code/cgi/art_76' : '/ma/loi/60-24/art_8'] }] : []),
            { key: 'tax', label: t('pension.tax'), amount: r.tax, sum: true },
          ]} />
        </>
      )}
      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <p className="m-0 text-meta text-ink-soft">{t('estimate')}</p>
        <SourceFold paths={['/ma/code/cgi/art_57', '/ma/code/cgi/art_60', '/ma/code/cgi/art_76', '/ma/code/cgi/art_86']} label={articleLabel} />
      </section>
    </KitPage>
  );
}
