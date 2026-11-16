import { Link } from 'react-router-dom';
import { toolLink } from '../kit/tool/state';
import { offenceIn } from './answer';
import { useFines } from './rules/rates';
import { articleLabel, useRoadT } from './strings';
import { todayIso } from '@/shared/services/today';

/** A road question answered by the fine tool's own rules (X2 of the road tools review): the price today, the points
 *  and the article, worked out in the browser, with «احسبها» into the tool set to it. Nothing when the question names
 *  no offence, or more than one equally. */
export default function SearchAnswer({ q }: { q: string }) {
  const { t, i18n } = useRoadT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const nf = new Intl.NumberFormat(lang === 'fr' ? 'fr-MA' : 'ar-MA');
  const rates = useFines('road', todayIso()).values;
  const o = offenceIn(q, (x) => `${t(`offences.${x.key}`)} ${t(`offenceWords.${x.key}`, { defaultValue: '' })}`);
  if (!o) return null;
  const walk = o.klass === 'walk';
  const k = walk ? 'walk' : `c${o.klass}`;
  const price = walk ? rates.walk_30 : rates[`${k}_day`];
  const art = `/ma/loi/52-05/art_${o.article}`;
  return (
    <section className="flex flex-col gap-2 rounded-card bg-sheet px-5 py-4" style={{ ['--t' as string]: 'var(--color-t-road)' }}>
      <p className="m-0 text-meta text-ink-soft">{t(`offences.${o.key}`)}</p>
      <p className="m-0 text-h3 font-bold text-[color:var(--t)]">{t('dh', { amount: nf.format(price) })}</p>
      <p className="m-0 text-body">
        {walk ? t('answer.walk') : t('answer.when', { full: t('dh', { amount: nf.format(rates[`${k}_30`]) }) })}
        {' · '}{o.points ? t('points_n', { count: o.points }) : t('answer.noPoints')}
        {' · '}<Link to={art} lang="ar">{articleLabel(art)}</Link>
      </p>
      <Link to={toolLink('/topics/road/tools/fine', { o: o.key })} className="inline-flex min-h-11 items-center self-start text-body font-semibold">{t('answer.open')}</Link>
    </section>
  );
}
