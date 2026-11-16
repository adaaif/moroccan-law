import { Button } from '@/shared/components/ui';
import { todayIso } from '@/shared/services/today';
import { refPath } from '../kit/api';
import { KitPage } from '../kit/parts';
import { calendarFile, whatsapp, here } from '../kit/share';
import { AnswerCard, Chips, DayChips, SourceFold, SourceMark } from '../kit/tool/parts';
import { dayWords, daysUntil } from '../kit/tool/days';
import { useToolState } from '../kit/tool/state';
import { ARTICLES, road } from './rules/info';
import { Sheet, Thread } from './parts';
import { articleLabel, useDigitalT } from './strings';

/** «فوقاش خاص الإدارة تجاوب؟» (the digital review): the day the institution received the request, and whether
 *  it is urgent or the institution said in writing it extends → the correspondence the law sets, as a conversation: the
 *  last day for its answer, then, if each step waits to its end, the complaint to the head and his answer, the commission
 *  and its answer, the administrative court (31.13 arts 16, 17, 19, 20, 21). It waits for a person's check. The inputs
 *  live in the address. */
export default function InfoToolPage({ slug }: { slug: string }) {
  const { t, i18n } = useDigitalT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const [s, set] = useToolState({ d: todayIso(), u: 'no', x: 'no' });
  const urgent = s.u === 'yes';
  const stops = road(s.d, urgent, s.x === 'yes' && !urgent);
  const answer = stops.find((x) => x.key === 'answer')!;
  const left = daysUntil(answer.date);
  const yesNo = [{ key: 'no', label: t('info.no') }, { key: 'yes', label: t('info.yes') }];
  const remind = () => calendarFile(stops.filter((x) => x.date >= todayIso() && x.key !== 'received')
    .map((x) => ({ date: x.date, title: t(`info.stops.${x.key}`, { date: '' }), detail: here() })), 'information');
  return (
    <KitPage slug={slug} title={t('info.title')} lead={t('info.lead')}>
      <AnswerCard over={t('info.over')} tone={left < 0 ? 'warn' : 'stamp'}
                  value={left < 0 ? t('info.passed') : t('info.left', { count: left })}
                  under={<p className="m-0">{t('info.until', { date: dayWords(answer.date, lang) })}</p>} />
      <Sheet>
        <DayChips label={t('info.received')} value={s.d} onChange={(d) => set({ d })} ago={[0, 7, 20]} />
        <Chips label={t('info.urgent')} value={urgent ? 'yes' : 'no'} onChange={(u) => set({ u })} options={yesNo} />
        {!urgent ? <Chips label={t('info.extended')} value={s.x === 'yes' ? 'yes' : 'no'} onChange={(x) => set({ x })} options={yesNo} /> : null}
      </Sheet>
      <Thread label={t('info.threadLabel')}
              messages={stops.map((x) => ({ key: x.key, who: x.who, warn: x.key === 'answer' && left < 0,
                                           body: t(`info.stops.${x.key}`, { date: dayWords(x.date, lang) }),
                                           time: dayWords(x.date, lang, false), chip: <SourceMark path={x.path} label={articleLabel(x.path)} /> }))} />
      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <p className="m-0 text-body text-ink-soft">{t('info.ifWait')}</p>
        <SourceFold paths={[...Object.values(ARTICLES), '/ma/loi/31-13/art_5']} label={articleLabel} />
        <div className="flex flex-wrap gap-2">
          <Button to={refPath(slug, 'journeys/info-request')}>{t('info.toJourney')}</Button>
          <Button variant="quiet" to={refPath(slug, 'checklists/info-request')}>{t('info.toList')}</Button>
          <Button variant="quiet" onClick={remind}>{t('info.remind')}</Button>
          <Button variant="quiet" onClick={() => whatsapp([t('info.message'), ...stops.map((x) => t(`info.stops.${x.key}`, { date: dayWords(x.date, lang) })), here()].join('\n'))}>{t('info.share')}</Button>
        </div>
      </section>
    </KitPage>
  );
}
