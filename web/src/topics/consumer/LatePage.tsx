import { Button, Note } from '@/shared/components/ui';
import { KitPage } from '../kit/parts';
import { calendarFile, whatsapp, here } from '../kit/share';
import { AnswerCard, Chips, Listen, SourceFold } from '../kit/tool/parts';
import { dayWords, daysUntil } from '../kit/tool/days';
import { toolLink, useToolState } from '../kit/tool/state';
import { Periods } from './parts';
import { dateRequired, lateDated, lateDistance } from './rules/delivery';
import { articleLabel, useConsumerT } from './strings';
import { daysAgo, todayIso } from '@/shared/services/today';

const today = todayIso;
const ago = daysAgo;
const FIELD = 'h-12 w-full max-w-64 rounded-control border border-field bg-sheet px-3 text-body';

/** «الطلبية تعطلات» (T3 of the consumer plan): the date written on the paper → the five days in which the contract
 *  may be ended without a court, then the refund's last day and the day interest starts once the supplier has the
 *  notice; at a distance, the order's thirty days. It never says whether to end the contract. */
export default function LatePage({ slug }: { slug: string }) {
  const { t, i18n } = useConsumerT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const [s, set] = useToolState({ m: 'date', p: ago(10), n: '', price: '' });
  const now = today();
  const distance = s.m === 'distance';
  const l = lateDated(s.p, s.n || undefined);
  const d = lateDistance(s.p);
  const price = Number(s.price) || 0;

  let over: string, value: string, under: string, tone: 'stamp' | 'warn' | 'good' = 'stamp';
  if (distance) {
    const left = daysUntil(d.executeBy);
    over = t('late.distanceOver'); value = dayWords(d.executeBy, lang);
    under = left < 0 ? t('late.distancePassed') : t('late.left', { count: left });
  } else if (now < l.from) {
    over = t('late.fromOver'); value = dayWords(l.from, lang); under = t('late.until', { date: dayWords(l.until, lang) });
  } else if (now <= l.until) {
    over = t('late.nowOver'); value = dayWords(l.until, lang); under = t('late.nowLine', { count: daysUntil(l.until) }); tone = 'good';
  } else {
    over = t('late.passedOver'); value = dayWords(l.until, lang); under = t('late.passedLine'); tone = 'warn';
  }
  const refund = distance ? t('late.distanceRefund') : t('late.refund', { notice: dayWords(s.n || l.from, lang), by: dayWords(l.refundBy, lang), from: dayWords(l.interestFrom, lang) });
  const cites = distance ? d.cites : l.cites;
  const message = [t('late.message'), `${over}: ${value}`, under, refund, here()].join('\n');
  const remind = () => calendarFile(distance ? [{ date: d.executeBy, title: t('late.remindDistance'), detail: here() }]
    : [{ date: l.from, title: t('late.remindFrom'), detail: here() }, { date: l.until, title: t('late.remindUntil'), detail: here() }], 'late');

  return (
    <KitPage slug={slug} title={t('late.title')} lead={t('late.lead')}>
      <AnswerCard over={over} value={value} under={<p className="m-0">{under}</p>} tone={tone} />

      <section className="flex flex-col gap-5 rounded-card bg-sheet px-5 py-5 sm:px-7">
        {distance ? (
          <Periods today={now} spans={[{ from: s.p, to: d.executeBy, label: t('late.thirty'), tone: 'main' }]} />
        ) : (
          <Periods today={now} caption={t('late.caption')} spans={[
            { from: s.p, to: l.from, label: t('late.seven'), tone: 'soft' },
            { from: l.from, to: l.until, label: t('late.five'), tone: 'main' },
            { from: s.n || l.from, to: l.refundBy, label: t('late.seven2'), tone: 'extra' },
          ]} />
        )}
        <Chips label={t('late.mode')} value={distance ? 'distance' : 'date'} onChange={(m) => set({ m })}
               options={[{ key: 'date', label: t('late.modes.date') }, { key: 'distance', label: t('late.modes.distance') }]} />
        <label className="flex flex-col gap-1.5 text-body font-semibold">{t(distance ? 'late.confirmedAsk' : 'late.promisedAsk')}
          <input type="date" dir="ltr" value={s.p} onChange={(e) => e.target.value && set({ p: e.target.value })} className={FIELD} />
          <span className="text-meta font-normal text-ink-soft">{dayWords(s.p, lang)}</span>
        </label>
        {distance ? null : (
          <>
            <label className="flex flex-col gap-1.5 text-body font-semibold">{t('late.noticeAsk')}
              <input type="date" dir="ltr" value={s.n} min={l.from} onChange={(e) => set({ n: e.target.value })} className={FIELD} />
              <span className="text-meta font-normal text-ink-soft">{t('late.noticeHint')}</span>
            </label>
            <label className="flex flex-col gap-1.5 text-body font-semibold">{t('late.priceAsk')}
              <input type="number" inputMode="numeric" min={0} value={s.price} placeholder="0" onChange={(e) => set({ price: e.target.value })} className={FIELD} />
              {price ? <span className="text-meta font-normal text-ink-soft">{t(dateRequired(price) ? 'late.required' : 'late.notRequired')}</span> : null}
            </label>
          </>
        )}
      </section>

      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <p className="m-0 text-body">{refund}</p>
        <Note tone="law" quiet><p className="m-0 text-meta">{t(distance ? 'late.distanceNote' : 'late.forceNote')}</p></Note>
        <SourceFold paths={cites} label={articleLabel} />
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => whatsapp(message)}>{t('share')}</Button>
          <Button onClick={remind}>{t('remind')}</Button>
          {distance ? null : <Button to={toolLink(`/topics/${slug}/tools/letters`, { l: 'late' })}>{t('late.toLetter')}</Button>}
          <Listen text={[over, value, under, refund].join('. ')} lang={lang} />
        </div>
      </section>
    </KitPage>
  );
}
