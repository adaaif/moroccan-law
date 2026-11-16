import { Button } from '@/shared/components/ui';
import { todayIso } from '@/shared/services/today';
import { refPath } from '../kit/api';
import { KitPage } from '../kit/parts';
import { calendarFile, whatsapp, here } from '../kit/share';
import Stepper from '../kit/tool/Stepper';
import { AnswerCard, Chips, DayChips, SourceFold, SourceMark } from '../kit/tool/parts';
import { dayWords, daysUntil } from '../kit/tool/days';
import { useToolState } from '../kit/tool/state';
import { ARTICLES, phase, stops, type Kind } from './rules/counter';
import { Road } from './parts';
import { articleLabel, usePapersT } from './strings';

/** «الإدارة ما جاوباتش» (the papers review): the day the file was complete (or the refusal came) → the day the
 *  administration must answer, the last day to appeal, the day the appeal must be answered, on one dashed road; the
 *  reader's place on it said on top (law 55.19 arts 10, 16, 21, 31). It waits for a person's check. The inputs live in
 *  the address. */
export default function CounterPage({ slug }: { slug: string }) {
  const { t, i18n } = usePapersT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const today = todayIso();
  const [s, set] = useToolState({ d: today, k: 'general', n: '30', r: '' });
  const kind = (['general', 'investment', 'own'].includes(s.k) ? s.k : 'general') as Kind;
  const road = stops(s.d, kind, Number(s.n) || 30, s.r || null);
  const where = phase(road, today);
  const answer = road.find((x) => x.key === 'answer')!;
  const appeal = road.find((x) => x.key === 'appeal')!;
  const value = where === 'waiting' ? t('counter.waiting', { count: daysUntil(answer.date) })
    : where === 'appeal' ? t('counter.appeal', { count: daysUntil(appeal.date) }) : t('counter.late');
  const over = where === 'waiting' ? t('counter.waitingOver', { date: dayWords(answer.date, lang) })
    : where === 'appeal' ? t('counter.appealOver', { date: dayWords(appeal.date, lang) }) : t('counter.lateOver');
  const title = (k: string) => t(`counter.stops.${k}.title`);
  const message = [t('counter.message'), ...road.map((x) => `${dayWords(x.date, lang)}: ${title(x.key)}`), here()].join('\n');
  const remind = () => calendarFile(road.filter((x) => x.date >= today && x.key !== 'deposit')
    .map((x) => ({ date: x.date, title: title(x.key), detail: here() })), 'administration');
  return (
    <KitPage slug={slug} title={t('counter.title')} lead={t('counter.lead')}>
      <AnswerCard over={over} value={value} tone={where === 'late' ? 'warn' : 'stamp'}
                  under={<p className="m-0">{t(`counter.under.${where}`)}</p>} />

      <section className="flex flex-col gap-5 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <DayChips label={t('counter.deposit')} value={s.d} onChange={(d) => set({ d })} ago={[0, 30, 60]} />
        <p className="m-0 text-meta text-ink-soft">{t('counter.depositNote')}</p>
        <Chips label={t('counter.kind')} value={kind} onChange={(k) => set({ k })}
               options={(['general', 'investment', 'own'] as Kind[]).map((k) => ({ key: k, label: t(`counter.kinds.${k}`) }))} />
        {kind === 'own' ? <Stepper label={t('counter.own')} value={Number(s.n) || 30} min={1} max={60} onChange={(n) => set({ n: String(n) })}
                                   format={(n) => t('counter.days', { count: n })} note={t('counter.ownNote')} /> : null}
        <Chips label={t('counter.refused')} value={s.r ? 'yes' : 'no'} onChange={(v) => set({ r: v === 'yes' ? (s.r || today) : '' })}
               options={[{ key: 'no', label: t('counter.refusedNo') }, { key: 'yes', label: t('counter.refusedYes') }]} />
        {s.r ? <DayChips label={t('counter.refusedOn')} value={s.r} onChange={(r) => set({ r })} ago={[0, 7, 15]} /> : null}
      </section>

      <section className="rounded-card bg-sheet px-5 py-5 sm:px-7">
        <Road today={today} lang={lang}
              stops={road.map((x) => ({ key: x.key, date: x.date, title: title(x.key), line: t(`counter.stops.${x.key}.line`),
                                        warn: x.key === 'appeal', chip: <SourceMark path={x.path} label={articleLabel(x.path)} /> }))} />
        <p className="m-0 mt-2 text-meta text-ink-soft">{t('counter.complete')} <SourceMark path={ARTICLES.complete} label={articleLabel(ARTICLES.complete)} /></p>
      </section>

      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <h2 className="m-0 text-h3 font-bold">{t('counter.rights')}</h2>
        <ul className="m-0 flex list-none flex-col gap-1.5 p-0">
          {(['receipt', 'once', 'reasons', 'silence'] as const).map((k) => <li key={k} className="text-body">• {t(`counter.right.${k}`)}</li>)}
        </ul>
        <SourceFold paths={[ARTICLES.receipt, ARTICLES.limit, ARTICLES.appeal, ARTICLES.silence, ARTICLES.deliver]} label={articleLabel} />
        <div className="flex flex-wrap gap-2">
          <Button to={refPath(slug, 'journeys/appeal')}>{t('counter.toJourney')}</Button>
          <Button variant="quiet" to={refPath(slug, 'pages/counter')}>{t('counter.toPage')}</Button>
          <Button variant="quiet" onClick={remind}>{t('counter.remind')}</Button>
          <Button variant="quiet" onClick={() => whatsapp(message)}>{t('counter.share')}</Button>
        </div>
      </section>
    </KitPage>
  );
}
