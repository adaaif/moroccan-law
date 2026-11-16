import { Button } from '@/shared/components/ui';
import { refPath } from '../kit/api';
import { KitPage } from '../kit/parts';
import { AnswerCard, Chips, SourceFold } from '../kit/tool/parts';
import Stepper from '../kit/tool/Stepper';
import { useToolState } from '../kit/tool/state';
import { ARTICLES, DAY_FINE, EXCLUDED, HOURS, MAX_DAYS, alternatives } from './rules/alternative';
import { HoursBar, Sheet } from './parts';
import { articleLabel, grouped, useJusticeT, useMoney } from './strings';

const QUICK = [30, 90, 180, 365, 730];

/** «واش كاينة عقوبة بديلة؟» (the justice review): the prison term a court would set, in days, the offence and the
 *  reader's situation → whether the penal code opens an alternative, the hours of community work (three a day, 40 to
 *  3,600) on one bar, the day-fine's range and its condition, and the other two kinds (arts 35-1 to 35-15). It says what
 *  the code opens; the court decides. It waits for a person's check. The inputs live in the address. */
export default function AlternativePage({ slug }: { slug: string }) {
  const { t, i18n } = useJusticeT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const money = useMoney();
  const [s, set] = useToolState({ d: '90', r: 'no', x: 'no', g: 'adult', f: 'no' });
  const days = Math.min(MAX_DAYS + 365, Math.max(1, Number(s.d) || 1));
  const a = alternatives(days, s.r === 'yes', s.x === 'yes', s.g === 'minor' ? 14 : 18, s.f === 'yes');
  const yesNo = [{ key: 'no', label: t('alt.no') }, { key: 'yes', label: t('alt.yes') }];
  return (
    <KitPage slug={slug} title={t('alt.title')} lead={t('alt.lead')}>
      <AnswerCard share over={t('alt.over')} tone={a.open ? 'good' : 'warn'} value={t(a.open ? 'alt.open' : 'alt.closed')}
                  under={<p className="m-0">{a.why ? t(`alt.why.${a.why}`) : t('alt.openLine', { hours: grouped(a.work.hours, lang) })}</p>} />
      <Sheet>
        <Stepper label={t('alt.days')} value={days} min={1} max={MAX_DAYS + 365} step={days >= 365 ? 30 : days >= 60 ? 15 : 1}
                 format={(v) => t('alt.daysValue', { count: v })} onChange={(v) => set({ d: String(v) })} note={t('alt.daysNote')} />
        <div className="flex flex-wrap gap-2">
          {QUICK.map((q) => (
            <button key={q} type="button" aria-pressed={q === days} onClick={() => set({ d: String(q) })}
                    className={`min-h-11 rounded-full border px-4 text-body ${q === days ? 'border-ink bg-ink font-semibold text-sheet' : 'border-field bg-sheet'}`}>
              {t(`alt.quick.${q}`)}
            </button>
          ))}
        </div>
        <Chips label={t('alt.repeat')} value={s.r} onChange={(r) => set({ r })} options={yesNo} />
        <Chips label={t('alt.excluded')} value={s.x} onChange={(x) => set({ x })} options={yesNo} />
        <p className="m-0 text-meta text-ink-soft">{EXCLUDED.map((k) => t(`alt.list.${k}`)).join(t('alt.sep'))}</p>
        <Chips label={t('alt.age')} value={s.g} onChange={(g) => set({ g })} options={[{ key: 'adult', label: t('alt.adult') }, { key: 'minor', label: t('alt.minor') }]} />
        <Chips label={t('alt.settled')} value={s.f} onChange={(f) => set({ f })} options={yesNo} />
      </Sheet>
      <section className="grid gap-3 sm:grid-cols-2">
        <article className={`flex flex-col gap-2 rounded-card bg-sheet px-5 py-4 ${a.work.open ? '' : 'opacity-60'}`}>
          <h3 className="m-0 text-h3 font-bold">{t('alt.work')}</h3>
          <p className="m-0 text-h2 font-bold tabular-nums">{t('alt.hours', { count: a.work.hours, n: grouped(a.work.hours, lang) })}</p>
          <HoursBar hours={a.work.hours} max={HOURS.max} floor={HOURS.min}
                    label={a.work.capped ? t(`alt.capped.${a.work.capped}`) : t('alt.perDay', { days: grouped(days, lang) })} />
          <p className="m-0 text-meta text-ink-soft">{a.work.open ? t('alt.workLine') : s.g === 'minor' ? t('alt.workMinor') : t('alt.notOpen')}</p>
        </article>
        <article className={`flex flex-col gap-2 rounded-card bg-sheet px-5 py-4 ${a.dayFine.open ? '' : 'opacity-60'}`}>
          <h3 className="m-0 text-h3 font-bold">{t('alt.dayFine')}</h3>
          <p className="m-0 text-h3 font-bold tabular-nums">{money(a.dayFine.min)} – {money(a.dayFine.max)}</p>
          <p className="m-0 text-meta text-ink-soft">{t('alt.dayFineLine', { min: money(DAY_FINE.min), max: money(DAY_FINE.max), days: grouped(days, lang) })}</p>
          {!a.dayFine.open && a.open ? <p className="m-0 text-meta font-semibold">{t('alt.dayFineCondition')}</p> : null}
        </article>
        <article className={`flex flex-col gap-1 rounded-card bg-sheet px-5 py-4 ${a.open ? '' : 'opacity-60'}`}>
          <h3 className="m-0 text-h3 font-bold">{t('alt.monitoring')}</h3>
          <p className="m-0 text-body">{t('alt.monitoringLine')}</p>
        </article>
        <article className={`flex flex-col gap-1 rounded-card bg-sheet px-5 py-4 ${a.open ? '' : 'opacity-60'}`}>
          <h3 className="m-0 text-h3 font-bold">{t('alt.measures')}</h3>
          <p className="m-0 text-body">{t('alt.measuresLine')}</p>
        </article>
      </section>
      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <p className="m-0 text-body">{t('alt.court')}</p>
        <SourceFold paths={Object.values(ARTICLES)} label={articleLabel} />
        <div className="flex flex-wrap gap-2">
          <Button to={refPath(slug, 'pages/alternatives')}>{t('alt.toPage')}</Button>
          <Button variant="quiet" to={refPath(slug, 'journeys/trial')}>{t('alt.toTrial')}</Button>
        </div>
      </section>
    </KitPage>
  );
}
