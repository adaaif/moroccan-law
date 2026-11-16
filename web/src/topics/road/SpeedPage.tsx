import { Button, Note } from '@/shared/components/ui';
import { KitPage } from '../kit/parts';
import { whatsapp, here } from '../kit/share';
import { AnswerCard, Chips, Listen, SourceFold } from '../kit/tool/parts';
import { toolLink, useToolState } from '../kit/tool/state';
import { classify, LIMITS } from './rules/speed';
import { useFines } from './rules/rates';
import { SCENE_COLOURS, speedSign } from './scenes/signs';
import { SpeedDial } from './SpeedDial';
import { articleLabel, useRoadT } from './strings';
import { todayIso } from '@/shared/services/today';

const today = () => todayIso();

/** «شحال كنتي كتسوق؟» (A2 of the road tools review): the sign, the needle, and what the code says of the difference.
 *  The radar's margin is art. 195 as this tool reads it (call K1, said on the page); under +20 the articles name no
 *  class (call K4, said too). The price by the day it is paid is the fine tool's, one tap away with the band set. */
export default function SpeedPage({ slug }: { slug: string }) {
  const { t, i18n } = useRoadT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const nf = new Intl.NumberFormat(lang === 'fr' ? 'fr-MA' : 'ar-MA');
  const dh = (n: number) => t('dh', { amount: nf.format(n) });
  const [s, set] = useToolState({ l: '60', v: '84', by: 'radar' });
  const limit = LIMITS.includes(Number(s.l) as (typeof LIMITS)[number]) ? Number(s.l) : 60;
  const measured = Math.max(0, Math.min(limit + 80, Number(s.v) || limit));
  const radar = s.by !== 'officer';
  const r = classify(limit, measured, radar);
  const fines = useFines(slug, today()).values;
  const k = r.band === 'c1' ? 'c1' : 'c2';
  const priced = r.band === 'c1' || r.band === 'c2';
  const value = priced ? fines[`${k}_day`] : r.band === 'delit' ? t('speed.delit') : r.band === 'under20' ? <bdi dir="ltr">{t('speed.plus', { over: r.over })}</bdi> : t('speed.none');
  const over = radar ? t('speed.over', { measured, margin: r.margin, kept: r.kept }) : t('speed.overOfficer', { measured });
  const under = t(`speed.band.${r.band}`, { over: r.over, points: t('points_n', { count: r.points }), last: dh(fines[`${k}_30`]) });
  return (
    <KitPage slug={slug} title={t('speed.title')} lead={t('speed.lead')}>
      <AnswerCard over={over} value={value} format={dh} under={<p className="m-0">{under}</p>}
                  tone={r.band === 'within' || r.band === 'margin' ? 'good' : r.band === 'delit' ? 'warn' : 'stamp'} />
      <section className="flex flex-col gap-5 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <div className="flex flex-col gap-1.5" style={SCENE_COLOURS}>
          <span className="text-body font-semibold">{t('speed.limit')}</span>
          <div role="radiogroup" aria-label={t('speed.limit')} className="grid grid-cols-6 gap-1.5 sm:flex sm:flex-wrap sm:gap-2">
            {LIMITS.map((l) => (
              <button key={l} type="button" role="radio" aria-checked={l === limit} aria-label={t('speed.kmh', { n: l })}
                      onClick={() => set({ l: String(l), v: String(Math.min(measured, l + 80)) })}
                      className={`grid aspect-square min-h-11 w-full place-items-center rounded-full transition-transform duration-150 active:scale-95 motion-reduce:transition-none sm:size-14 ${l === limit ? 'ring-4 ring-ink' : ''}`}>
                <svg viewBox="0 0 100 100" aria-hidden="true" className="size-[85%] max-h-12 max-w-12" dangerouslySetInnerHTML={{ __html: speedSign(l) }} />
              </button>
            ))}
          </div>
          <p className="m-0 text-meta text-ink-soft">{t('speed.limitsHint')}</p>
        </div>
        <SpeedDial limit={limit} speed={measured} radar={radar} onChange={(v) => set({ v: String(v) })} label={t('speed.measured')} unit={t('speed.unit')} />
        <Chips label={t('speed.by')} value={radar ? 'radar' : 'officer'} onChange={(by) => set({ by })}
               options={[{ key: 'radar', label: t('fine.starts.radar') }, { key: 'officer', label: t('speed.officer') }]} />
      </section>
      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        {radar ? <Note tone="warn" quiet><p className="m-0 text-meta">{t('speed.reading')}</p></Note> : null}
        {r.band === 'under20' ? <p className="m-0 text-meta text-ink-soft">{t('speed.under20Note')}</p> : null}
        <SourceFold paths={r.cites.concat(radar ? ['/ma/loi/52-05/art_195'] : [])} label={articleLabel} />
        <div className="flex flex-wrap gap-2">
          {r.offence ? <Button variant="primary" to={toolLink(`/topics/${slug}/tools/fine`, { o: r.offence, s: radar ? 'radar' : 'officer' })}>{t('speed.toFine')}</Button> : null}
          <Button onClick={() => whatsapp([t('speed.title'), over, typeof value === 'number' ? dh(value) : r.band === 'under20' ? t('speed.plus', { over: r.over }) : String(value), under, here()].join('\n'))}>{t('share')}</Button>
          <Listen text={[over, typeof value === 'number' ? dh(value) : r.band === 'under20' ? t('speed.plus', { over: r.over }) : String(value), under].join('. ')} lang={lang} />
        </div>
      </section>
    </KitPage>
  );
}
