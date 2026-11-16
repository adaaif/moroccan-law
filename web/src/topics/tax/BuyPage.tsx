import { PageSkeleton } from '@/shared/components/ui';
import { todayIso } from '@/shared/services/today';
import { pct } from '@/shared/locales/i18n';
import { useRateOn } from '../kit/api';
import { KitPage } from '../kit/parts';
import { AnswerCard, Chips, SourceFold } from '../kit/tool/parts';
import { useToolState } from '../kit/tool/state';
import { Inputs, MoneyField } from './parts';
import { buyDuties, type Kind } from './rules/things';
import { articleLabel, useMoney, useTaxT } from './strings';

/** «شريت عقار: شحال التسجيل؟» (T14): the price in the deed and the kind of property give the registration duties of art.
 *  133 (4% built, 5% bare land, 3% the first sale of social housing, 1.5% a gift in the family), within 30 days (128). */
export default function BuyPage({ slug }: { slug: string }) {
  const { t } = useTaxT();
  const { c } = useMoney();
  const [s, set] = useToolState({ p: '900000', k: 'built' });
  const r = useRateOn(slug, 'registration', todayIso());
  if (!r) return <KitPage slug={slug} title={t('buy.title')} lead={t('buy.lead')}><PageSkeleton /></KitPage>;
  const d = buyDuties(Math.max(0, Number(s.p) || 0), s.k as Kind, r);
  return (
    <KitPage slug={slug} title={t('buy.title')} lead={t('buy.lead')}>
      <AnswerCard share over={pct(`${t('buy.duties')} · ${d.rate}%`)} value={t('dh', { amount: c(d.duties) })}
                  under={<p className="m-0">{t('buy.deadline', { days: d.days })}</p>} />
      <Inputs>
        <MoneyField label={t('buy.price')} value={s.p} onChange={(p) => set({ p })} />
        <Chips label={t('buy.kind')} value={s.k} onChange={(k) => set({ k })} options={(['built', 'land', 'social', 'family_gift'] as const).map((k) => ({ key: k, label: t(`buy.kinds.${k}`) }))} />
      </Inputs>
      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <p className="m-0 text-body">{t('buy.other')}</p>
        <p className="m-0 text-meta text-ink-soft">{t('estimate')}</p>
        <SourceFold paths={['/ma/code/cgi/art_127', '/ma/code/cgi/art_128', '/ma/code/cgi/art_133']} label={articleLabel} />
      </section>
    </KitPage>
  );
}
