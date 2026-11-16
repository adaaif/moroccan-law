import { PageSkeleton } from '@/shared/components/ui';
import { todayIso } from '@/shared/services/today';
import { useRateOn } from '../kit/api';
import { KitPage } from '../kit/parts';
import { AnswerCard, Chips, SourceFold } from '../kit/tool/parts';
import { useToolState } from '../kit/tool/state';
import { Inputs, Ledger, MoneyField } from './parts';
import { housingTax, landTax, type Zone } from './rules/things';
import { articleLabel, useMoney, useTaxT } from './strings';

/** «رسوم الدار والأرض» (T15): law 47.06 for a home (the housing tax after 75% off a main residence, slice by slice; the
 *  services tax on the rental value) or an urban plot (its area by the zone's bounds, the floor of 200 dirhams). */
export default function LocalPage({ slug }: { slug: string }) {
  const { t } = useTaxT();
  const { n, c } = useMoney();
  const [s, set] = useToolState({ w: 'home', v: '24000', m: '1', u: 'urban', a: '300', z: 'full' });
  const l = useRateOn(slug, 'local', todayIso());
  if (!l) return <KitPage slug={slug} title={t('local.title')} lead={t('local.lead')}><PageSkeleton /></KitPage>;
  const home = s.w === 'home';
  const h = housingTax(Math.max(0, Number(s.v) || 0), s.m === '1', s.u === 'urban', l);
  const land = landTax(Number(s.a) || 0, s.z as Zone, l);
  return (
    <KitPage slug={slug} title={t('local.title')} lead={t('local.lead')}>
      {home ? (
        <AnswerCard share over={`${t('local.housing')} + ${t('local.services')}`} value={t('dh', { amount: c(h.housing + h.services) })}
                    under={<p className="m-0">{t('local.housing')}: {c(h.housing)} · {t('local.services')}: {c(h.services)}</p>}>
          <p className="m-0 text-meta text-ink-soft">{t('local.owner')}</p>
        </AnswerCard>
      ) : (
        <AnswerCard over={t('local.whats.land')} value={land.none ? t('local.none') : t('local.landLine', { min: n(land.min), max: n(land.max) })}
                    under={<p className="m-0">{t('local.landNote', { a: land.rateMin, b: land.rateMax })}</p>} />
      )}
      <Inputs>
        <Chips label={t('local.what')} value={s.w} onChange={(w) => set({ w })} options={(['home', 'land'] as const).map((k) => ({ key: k, label: t(`local.whats.${k}`) }))} />
        {home ? (
          <>
            <MoneyField label={t('local.value')} value={s.v} onChange={(v) => set({ v })} note={t('local.valueNote')} />
            <Chips label={t('local.main')} value={s.m} onChange={(m) => set({ m })} options={[{ key: '1', label: t('yes') }, { key: '0', label: t('no') }]} />
            <Chips label={t('local.urban')} value={s.u} onChange={(u) => set({ u })} options={(['urban', 'other'] as const).map((k) => ({ key: k, label: t(`local.urbans.${k}`) }))} />
          </>
        ) : (
          <>
            <MoneyField label={t('local.area')} value={s.a} onChange={(a) => set({ a })} />
            <Chips label={t('local.zone')} value={s.z} onChange={(z) => set({ z })} options={(['full', 'mid', 'low'] as const).map((k) => ({ key: k, label: t(`local.zones.${k}`) }))} />
          </>
        )}
      </Inputs>
      {home ? (
        <Ledger title={t('perYear')} lines={[
          { key: 'value', label: t('local.value'), amount: Number(s.v) || 0, cites: ['/ma/loi/47-06/art_23'] },
          ...(s.m === '1' ? [{ key: 'abatement', label: `${l.abatement}%`, amount: (Number(s.v) || 0) - h.base, minus: true, cites: ['/ma/loi/47-06/art_24'] }] : []),
          { key: 'base', label: t('local.base', { base: n(h.base) }), amount: h.base, sum: true },
          ...h.parts.filter((p) => p.base > 0).map((p, i) => ({ key: `p${i}`, label: `${p.rate}% · ${n(p.from)}–${p.to === null ? '…' : n(p.to)}`, amount: p.tax, cites: ['/ma/loi/47-06/art_27'] })),
          { key: 'housing', label: t('local.housing'), amount: h.housing, sum: true },
          { key: 'services', label: t('local.services'), note: t('local.servicesNote', { rate: h.servicesRate }), amount: h.services, cites: ['/ma/loi/47-06/art_36'] },
        ]}>
          <p className="m-0 pt-3 text-meta text-ink-soft">{t('local.slicesNote')}</p>
        </Ledger>
      ) : null}
      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <p className="m-0 text-meta text-ink-soft">{t('estimate')}</p>
        <SourceFold paths={home ? ['/ma/loi/47-06/art_20', '/ma/loi/47-06/art_23', '/ma/loi/47-06/art_24', '/ma/loi/47-06/art_27', '/ma/loi/47-06/art_36', '/ma/loi/47-06/art_147']
          : ['/ma/loi/47-06/art_39', '/ma/loi/47-06/art_43', '/ma/loi/47-06/art_45', '/ma/loi/47-06/art_46', '/ma/loi/47-06/art_47']} label={articleLabel} />
      </section>
    </KitPage>
  );
}
