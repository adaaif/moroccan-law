import { useState } from 'react';
import type { TFunction } from 'i18next';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Button, Note } from '@/shared/components/ui';
import { longDate } from '@/features/corpus/format';
import { KitPage } from './parts';
import { calendarFile } from './share';
import { ending, type Event } from './dates';
import { HolidayLine } from './HolidayLine';
import { todayIso } from '@/shared/services/today';
import { AnswerCard, Chips, DayChips } from './tool/parts';
import { daysUntil } from './tool/days';
import { useKitT } from './api';

/** «تواريخ يحددها القانون» for any topic (F7 of the family plan, T10 of the work plan): what happened and on which
 *  day, then each limit its texts set as a date with its article, and the lot as a calendar file the phone keeps.
 *  Nothing leaves the phone. The words come from the topic's own namespace, under `dates.`. */
export default function DatesTool({ slug, events, t }: { slug: string; events: Event[]; t: TFunction }) {
  const lang = useTranslation().i18n.language;
  const kit = useKitT().t;
  const [event, setEvent] = useState(events[0].key);
  const [day, setDay] = useState(() => todayIso());
  const chosen = events.find((e) => e.key === event) ?? events[0];
  const rows = chosen.deadlines.map((d) => ({ d, ...ending(day, d) }));
  // The answer on top (G13 of the family-papers review): the nearest limit not yet passed, else the last one.
  const next = [...rows].sort((a, b) => a.date.localeCompare(b.date)).find((r) => daysUntil(r.date) >= 0) ?? rows[rows.length - 1];
  const left = daysUntil(next.date);
  const save = () => calendarFile(rows.map(({ d, date }) => ({
    date, title: t(`dates.deadline.${d.key}`), detail: `${t(`dates.event.${chosen.key}`)} · ${d.label}`,
  })), t('dates.file'));
  const span = (d: Event['deadlines'][number]) =>
    d.hours ? t('topicKit:hours', { count: d.hours })
      : d.months && d.months % 12 === 0 ? t('topicKit:line.years', { count: d.months / 12 })
        : d.months ? t('topicKit:months', { count: d.months }) : t('topicKit:days', { count: d.days ?? 0 });
  return (
    <KitPage slug={slug} title={t('dates.title')} lead={t('dates.lead')}>
      <AnswerCard tone={left < 0 ? 'warn' : 'stamp'} over={kit('dates.next', { name: t(`dates.deadline.${next.d.key}`) })}
                  value={longDate(next.date, lang)}
                  under={<span>{left < 0 ? kit('journey.passed') : left === 0 ? kit('journey.lastDay') : kit('journey.left', { days: kit('days', { count: left }) })} · <Link to={next.d.path} lang="ar" dir="rtl">{next.d.label}</Link></span>} />
      {/* Touched, not typed: the event as chips, the day as the reader says it. */}
      <section className="flex flex-col gap-4 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <Chips label={t('dates.what')} value={event} onChange={setEvent}
               options={events.map((e) => ({ key: e.key, label: t(`dates.event.${e.key}`) }))} />
        <DayChips label={t('dates.when')} value={day} onChange={setDay} ago={[0, 1, 2, 7]} />
      </section>
      <section className="flex flex-col gap-1 rounded-card bg-sheet px-5 py-5 sm:px-7" aria-live="polite">
        <ul className="m-0 flex list-none flex-col p-0">
          {rows.map(({ d, date, moved, on }) => (
            <li key={d.key} className="flex flex-wrap items-baseline gap-x-4 gap-y-1 border-t border-rule py-3 first:border-t-0">
              <span className="min-w-0 flex-1 text-body font-semibold">{t(`dates.deadline.${d.key}`)}</span>
              <time dateTime={date} className="text-lead font-bold text-[var(--t)]">{longDate(date, lang)}</time>
              <span className="basis-full text-meta text-ink-soft">
                {span(d)}{d.extraDays ? ` + ${t('topicKit:days', { count: d.extraDays })}` : ''}
                {d.complete ? ` · ${t('topicKit:complete')}` : ''} · <Link to={d.path} lang="ar" dir="rtl">{d.label}</Link>
              </span>
              {d.note ? <span className="basis-full text-meta text-ink-soft">{t(`dates.words.${d.note}`)}</span> : null}
              <HolidayLine moved={moved} on={on} />
            </li>
          ))}
        </ul>
        {chosen.words?.map((w) => <p key={w} className="m-0 border-t border-rule pt-3 text-meta text-ink-soft">{t(`dates.words.${w}`)}</p>)}
        <Button className="mt-3 self-start" onClick={save}>{t('topicKit:calendar')}</Button>
      </section>
      <Note tone="warn" quiet>
        <p className="m-0 text-meta">{t('dates.rule')}</p>
      </Note>
    </KitPage>
  );
}

