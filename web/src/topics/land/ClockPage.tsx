import { Button } from '@/shared/components/ui';
import { HolidayLine } from '../kit/HolidayLine';
import { KitPage } from '../kit/parts';
import { calendarFile, whatsapp, here } from '../kit/share';
import { AnswerCard, Chips, DayChips, Listen, SourceFold } from '../kit/tool/parts';
import { dayWords, daysUntil } from '../kit/tool/days';
import { useToolState } from '../kit/tool/state';
import { refPath } from '../kit/api';
import { PAPERS, gone, lastDay, type Paper } from './rules/clock';
import { articleLabel, useLandT } from './strings';
import { todayIso } from '@/shared/services/today';

/** «شحال بقا ليا؟», the land's clock (the land review, M11): the paper received and the day it counts from → its
 *  last day, the days left in large type, the share gone on one bar, the article; after the limit, what the law still
 *  leaves. It waits for a person's check (C3 «wait»). It never says whether to act. The inputs live in the address. */
export default function ClockPage({ slug }: { slug: string }) {
  const { t, i18n } = useLandT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const [s, set] = useToolState({ p: 'oppose', d: todayIso() });
  const paper = (PAPERS.includes(s.p as Paper) ? s.p : 'oppose') as Paper;
  const end = lastDay(paper, s.d);
  const left = daysUntil(end.date);
  const today = todayIso();
  const over = t(`clock.for.${paper}`);
  const value = left < 0 ? t('clock.passed') : t('clock.left', { count: left });
  const under = t('clock.lastDay', { date: dayWords(end.date, lang) });
  const cites = [end.limit.deadline.path, ...(end.limit.after ? [end.limit.after.path] : [])];
  const message = [t('clock.message'), t(`clock.papers.${paper}`), `${t(`clock.day.${paper}`)}: ${dayWords(s.d, lang)}`, under, here()].join('\n');
  const remind = () => calendarFile([{ date: end.date, title: t('clock.remindTitle'), detail: `${t(`clock.papers.${paper}`)}. ${here()}` }], 'land');
  const share = gone(s.d, end.date, today);

  return (
    <KitPage slug={slug} title={t('clock.title')} lead={t('clock.lead')}>
      <AnswerCard over={over} value={value} under={<p className="m-0">{under}</p>} tone={left < 0 ? 'warn' : 'stamp'}>
        <div dir="ltr" className="flex flex-col gap-1 pt-2" aria-hidden="true">
          {/* The limit as one bar, left to right on an Arabic page too (the chart rule of 1 Nov 2026): the days gone in ink, what is left in the topic's colour. */}
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
        <Chips label={t('clock.which')} value={paper} onChange={(p) => set({ p })}
               options={PAPERS.map((p) => ({ key: p, label: t(`clock.papers.${p}`) }))} />
        <DayChips label={t(`clock.day.${paper}`)} value={s.d} onChange={(d) => set({ d })} ago={[0, 7, 30, 60]} />
      </section>

      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <p className="m-0 text-body">{t(`clock.after.${paper}`)}</p>
        {end.moved.length || end.on ? <HolidayLine moved={end.moved} on={end.on} /> : null}
        <p className="m-0 text-meta text-ink-soft">{end.limit.deadline.complete ? t('clock.complete') : t('clock.how')}</p>
        <SourceFold paths={cites} label={articleLabel} />
        <div className="flex flex-wrap gap-2">
          <Button to={refPath(slug, end.limit.journey)}>{t('clock.toJourney')}</Button>
          <Button onClick={() => whatsapp(message)}>{t('share')}</Button>
          {left >= 0 ? <Button onClick={remind}>{t('remind')}</Button> : null}
          <Listen text={[over, value, under].join('. ')} lang={lang} />
        </div>
      </section>
    </KitPage>
  );
}
