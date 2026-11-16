import { Button } from '@/shared/components/ui';
import { todayIso } from '@/shared/services/today';
import { HolidayLine } from '../kit/HolidayLine';
import { refPath } from '../kit/api';
import { KitPage } from '../kit/parts';
import { calendarFile, whatsapp, here } from '../kit/share';
import { AnswerCard, Chips, DayChips, SourceFold } from '../kit/tool/parts';
import { dayWords, daysUntil } from '../kit/tool/days';
import { useToolState } from '../kit/tool/state';
import { MOMENTS, gone, lastDay, type Moment } from './rules/clock';
import { articleLabel, useHealthT } from './strings';

/** The feuille de soins' clock (S18 of the health review): what happened and the day it happened → the last day
 *  the law leaves, the days left in large type, the share gone on one bar left to right on an Arabic page too (the chart rule of 1 Nov 2026) (gone in ink, left in
 *  the topic's colour), its article. It waits for a person's check (C4 «wait»). The inputs live in the address. */
export default function ClockPage({ slug }: { slug: string }) {
  const { t, i18n } = useHealthT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const [s, set] = useToolState({ m: 'first-act', d: todayIso() });
  const moment = (MOMENTS.includes(s.m as Moment) ? s.m : 'first-act') as Exclude<Moment, 'pregnancy'>;
  const end = lastDay(moment, s.d);
  const left = daysUntil(end.date);
  const share = gone(s.d, end.date, todayIso());
  const under = t('clock.lastDay', { date: dayWords(end.date, lang) });
  const message = [t('clock.message'), t(`clock.moments.${moment}`), `${t(`clock.day.${moment}`)}: ${dayWords(s.d, lang)}`, under, here()].join('\n');
  const remind = () => calendarFile([{ date: end.date, title: t('clock.remindTitle'), detail: `${t(`clock.for.${moment}`)}. ${here()}` }], 'health');
  return (
    <KitPage slug={slug} title={t('clock.title')} lead={t('clock.lead')}>
      <AnswerCard over={t(`clock.for.${moment}`)} value={left < 0 ? t('clock.passed') : t('clock.left', { count: left })}
                  under={<p className="m-0">{under}</p>} tone={left < 0 ? 'warn' : 'stamp'}>
        <div dir="ltr" className="flex flex-col gap-1 pt-2" aria-hidden="true">
          <div className="relative h-3 overflow-hidden rounded-full bg-rule">
            <div className="absolute inset-y-0 start-0 bg-ink transition-[width] duration-500 motion-reduce:transition-none" style={{ width: `${share * 100}%` }} />
            <div className="absolute inset-y-0 end-0 bg-[var(--t)]" style={{ width: `${(1 - share) * 100}%` }} />
          </div>
          <div className="flex justify-between text-meta text-ink-soft">
            <span>{dayWords(s.d, lang, false)}</span>
            <span className="font-semibold text-ink">{dayWords(end.date, lang, false)}</span>
          </div>
        </div>
      </AnswerCard>
      <section className="flex flex-col gap-5 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <Chips label={t('clock.which')} value={moment} onChange={(m) => set({ m })}
               options={MOMENTS.map((m) => ({ key: m, label: t(`clock.moments.${m}`) }))} />
        <DayChips label={t(`clock.day.${moment}`)} value={s.d} onChange={(d) => set({ d })} ago={[0, 7, 30, 60]} />
      </section>
      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <p className="m-0 text-body">{t(`clock.after.${moment}`)}</p>
        {end.moved.length || end.on ? <HolidayLine moved={end.moved} on={end.on} /> : null}
        <SourceFold paths={[end.limit.deadline.path!]} label={articleLabel} />
        <div className="flex flex-wrap gap-2">
          <Button to={refPath(slug, end.limit.journey)}>{t('clock.toJourney')}</Button>
          <Button variant="quiet" onClick={remind}>{t('clock.remind')}</Button>
          <Button variant="quiet" onClick={() => whatsapp(message)}>{t('clock.share')}</Button>
        </div>
      </section>
    </KitPage>
  );
}
