import { Button } from '@/shared/components/ui';
import { todayIso } from '@/shared/services/today';
import { refPath } from '../kit/api';
import { KitPage } from '../kit/parts';
import { AnswerCard, Chips, DayChips, SourceFold, SourceMark } from '../kit/tool/parts';
import { dayWords, daysUntil } from '../kit/tool/days';
import { useToolState } from '../kit/tool/state';
import { ARTICLES, KINDS, byLaw, byRequest, onCard3, type Kind } from './rules/rehab';
import { articleLabel, usePapersT } from './strings';

/** «فوقاش يتمسح الحكم؟» (the papers review): what the sentence was and the day it ended → whether card no. 3 ever
 *  shows it, the day rehabilitation comes by law, the day a request may be made, on one line from the end to the day
 *  (criminal procedure 22.01 arts 667, 688, 689, 692, 702). It says the law's periods, never a court's decision. It waits
 *  for a person's check. The inputs live in the address. */
export default function RehabPage({ slug }: { slug: string }) {
  const { t, i18n } = usePapersT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const today = todayIso();
  const [s, set] = useToolState({ k: 'short', d: today });
  const kind = (KINDS.includes(s.k as Kind) ? s.k : 'short') as Kind;
  const law = byLaw(kind, s.d);
  const ask = byRequest(kind, s.d);
  const shows = onCard3(kind);
  const left = daysUntil(law.date);
  const value = !shows ? t('rehab.never') : left > 0 ? t('rehab.left', { count: left }) : t('rehab.done');
  const at = (d: string) => Date.parse(`${d}T12:00:00Z`);
  const share = Math.min(1, Math.max(0, (at(today) - at(s.d)) / Math.max(1, at(law.date) - at(s.d))));
  return (
    <KitPage slug={slug} title={t('rehab.title')} lead={t('rehab.lead')}>
      <AnswerCard share over={shows ? t('rehab.over', { date: dayWords(law.date, lang) }) : t('rehab.neverOver')} value={value}
                  under={<p className="m-0">{t(shows ? 'rehab.under' : 'rehab.neverUnder')}</p>}>
        {shows ? (
          <div className="flex flex-col gap-1 pt-2" aria-hidden="true">
            <div className="relative h-3 overflow-hidden rounded-full bg-rule">
              <div className="absolute inset-y-0 start-0 bg-ink transition-[width] duration-500 motion-reduce:transition-none" style={{ width: `${share * 100}%` }} />
              <div className="absolute inset-y-0 end-0 bg-[var(--t)]" style={{ width: `${(1 - share) * 100}%` }} />
            </div>
            <div className="flex justify-between text-meta text-ink-soft">
              <span>{dayWords(s.d, lang)}</span>
              <span className="font-semibold text-ink">{dayWords(law.date, lang)}</span>
            </div>
          </div>
        ) : null}
      </AnswerCard>

      <section className="flex flex-col gap-5 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <Chips label={t('rehab.kind')} value={kind} onChange={(k) => set({ k })}
               options={KINDS.map((k) => ({ key: k, label: t(`rehab.kinds.${k}`) }))} />
        <DayChips label={t(`rehab.ended.${kind === 'fine' ? 'fine' : kind === 'suspended' ? 'suspended' : 'served'}`)} value={s.d} onChange={(d) => set({ d })} ago={[0, 180, 365]} />
      </section>

      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <p className="m-0 text-body">{t('rehab.byLaw', { date: dayWords(law.date, lang) })} <SourceMark path={law.path} label={articleLabel(law.path)} /></p>
        {ask ? <p className="m-0 text-body">{t('rehab.byRequest', { date: dayWords(ask, lang) })} <SourceMark path={ARTICLES.ask} label={articleLabel(ARTICLES.ask)} /></p> : null}
        <p className="m-0 text-body">{t('rehab.condition')}</p>
        <p className="m-0 text-body">{t('rehab.after')} <SourceMark path={ARTICLES.after} label={articleLabel(ARTICLES.after)} /></p>
        <p className="m-0 text-meta text-ink-soft">{t('rehab.card2')}</p>
        <SourceFold paths={[ARTICLES.card3, ARTICLES.law, ARTICLES.suspended, ARTICLES.ask, ARTICLES.after]} label={articleLabel} />
        <div className="flex flex-wrap gap-2">
          <Button to={refPath(slug, 'journeys/record')}>{t('rehab.toJourney')}</Button>
        </div>
      </section>
    </KitPage>
  );
}
