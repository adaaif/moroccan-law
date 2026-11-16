import { Button } from '@/shared/components/ui';
import { todayIso } from '@/shared/services/today';
import { HolidayLine } from '../kit/HolidayLine';
import { holiday } from '../kit/holidays';
import { refPath } from '../kit/api';
import { KitPage } from '../kit/parts';
import { calendarFile, whatsapp, here } from '../kit/share';
import { AnswerCard, Chips, DayChips, SourceFold } from '../kit/tool/parts';
import { dayWords, daysUntil } from '../kit/tool/days';
import { useToolState } from '../kit/tool/state';
import { COUNTING, RULES, cells, lastDay, rule, startsFrom, type Group, type Kind } from './rules/deadline';
import { MonthGrid, RegistryStamp, Sheet } from './parts';
import { articleLabel, useJusticeT, stampLabel } from './strings';

const GROUPS: Group[] = ['civil', 'criminal', 'complaint'];
const offDay = (d: string) => Boolean(holiday(d)) || [0, 6].includes(new Date(`${d}T12:00:00Z`).getUTCDay());
const JOURNEY: Record<Group, string> = { civil: 'journeys/appeal', criminal: 'journeys/trial', complaint: 'journeys/complaint' };

/** «شحال باقي ليا؟» (the justice review): what was decided (or the facts, for a complaint) and the day it started →
 *  the last day one may still act, drawn as the registry's date stamp, and under it the days as a month grid: the start
 *  and the uncounted last day hatched, the days off the end moved past in grey (58.25 art. 602, 22.01 art. 750). For a
 *  complaint, the years of art. 5 unless interrupted (art. 6). It waits for a person's check. The inputs live in the
 *  address. */
export default function DeadlinePage({ slug }: { slug: string }) {
  const { t, i18n } = useJusticeT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const today = todayIso();
  const [s, set] = useToolState({ k: 'appeal', d: today, p: 'yes' });
  const kind = (RULES.some((r) => r.kind === s.k) ? s.k : 'appeal') as Kind;
  const r = rule(kind);
  const present = s.p !== 'no';
  const from = startsFrom(r, present);
  const last = lastDay(kind, s.d);
  const left = daysUntil(last.date);
  const years = Boolean(r.years);
  const grid = years ? null : cells(s.d, last, offDay);
  const over = t(`deadline.over.${kind}`);
  const under = t('deadline.until', { date: dayWords(last.date, lang) });
  const how = years ? t('deadline.howYears', { count: r.years }) : t('deadline.how', { count: r.days, from: t(`deadline.from.${from}`) });
  const paths = years ? [r.path, '/ma/loi/22-01/art_6'] : [r.path, r.group === 'criminal' ? COUNTING.criminal : COUNTING.civil];
  const message = [t('deadline.message'), t(`deadline.kinds.${kind}`), `${t(`deadline.day.${from}`)}: ${dayWords(s.d, lang)}`, under, here()].join('\n');
  const remind = () => calendarFile([{ date: last.date, title: over, detail: `${t(`deadline.kinds.${kind}`)}. ${here()}` }], 'deadline');

  return (
    <KitPage slug={slug} title={t('deadline.title')} lead={t('deadline.lead')}>
      <AnswerCard over={over} tone={left < 0 ? 'warn' : 'stamp'}
                  value={left < 0 ? t(years ? 'deadline.lapsed' : 'deadline.passed') : t('deadline.left', { count: left })}
                  under={<p className="m-0">{t(`deadline.kinds.${kind}`)}{lang === 'fr' ? ', ' : '، '}{under}</p>} />

      <RegistryStamp day={last.date} lang={lang} caption={t(years ? 'deadline.stampYears' : 'deadline.stamp')} foot={stampLabel(r.path, lang)} />

      <Sheet>
        <Chips label={t('deadline.where')} value={r.group} onChange={(g) => set({ k: RULES.find((x) => x.group === g)!.kind })}
               options={GROUPS.map((g) => ({ key: g, label: t(`deadline.groups.${g}`) }))} />
        <Chips label={t('deadline.what')} value={kind} onChange={(k) => set({ k })}
               options={RULES.filter((x) => x.group === r.group).map((x) => ({ key: x.kind, label: t(`deadline.kinds.${x.kind}`) }))} />
        {r.from === 'pronounced' ? (
          <Chips label={t(`deadline.present.${kind}`)} value={present ? 'yes' : 'no'} onChange={(p) => set({ p })}
                 options={[{ key: 'yes', label: t('deadline.yes') }, { key: 'no', label: t('deadline.no') }]} />
        ) : null}
        <DayChips label={t(`deadline.day.${from}`)} value={s.d} onChange={(d) => set({ d })} ago={years ? [0, 30, 365] : [0, 3, 7, 14]} />
      </Sheet>

      <section className="flex flex-col gap-4 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <h2 className="m-0 text-h3 font-bold">{t('deadline.howTitle')}</h2>
        <p className="m-0 text-body">{how}</p>
        {grid ? (
          <MonthGrid cells={grid} lang={lang} today={today}
                     legend={{ start: t('deadline.legend.start'), counted: t('deadline.legend.counted', { count: r.days }), off: t('deadline.legend.off'), last: t('deadline.legend.last') }} />
        ) : <p className="m-0 text-body text-ink-soft">{t('deadline.interrupted')}</p>}
        {last.moved.length ? <HolidayLine moved={last.moved} on={null} /> : null}
        <SourceFold paths={paths} label={articleLabel} />
        <div className="flex flex-wrap gap-2">
          <Button to={refPath(slug, JOURNEY[r.group])}>{t(`deadline.toJourney.${r.group}`)}</Button>
          <Button variant="quiet" to={refPath(slug, 'pages/deadlines')}>{t('deadline.toPage')}</Button>
          <Button variant="quiet" onClick={remind}>{t('deadline.remind')}</Button>
          <Button variant="quiet" onClick={() => whatsapp(message)}>{t('deadline.share')}</Button>
        </div>
      </section>
    </KitPage>
  );
}
