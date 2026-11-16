import { Button } from '@/shared/components/ui';
import { todayIso } from '@/shared/services/today';
import { refPath } from '../kit/api';
import { KitPage } from '../kit/parts';
import { calendarFile, here } from '../kit/share';
import { AnswerCard, Chips, SourceFold, SourceMark } from '../kit/tool/parts';
import { dayWords, daysUntil } from '../kit/tool/days';
import { useToolState } from '../kit/tool/state';
import { DateField, Road } from '../papers/parts';
import { addMonths } from '../papers/rules/dates';
import { ARTICLES, fromClose, fromCreation } from './rules/year';
import { Sheet } from './parts';
import { articleLabel, useBusinessT } from './strings';

/** The 31 December whose assembly is still ahead (the close most companies keep): last year's until its six months
 *  pass, then this year's. */
const closeAhead = (today: string) => {
  const year = Number(today.slice(0, 4));
  return addMonths(`${year - 1}-12-31`, 6) >= today ? `${year - 1}-12-31` : `${year}-12-31`;
};

/** «التواريخ ديال الشركة» (the business review): from the creation, the tax declaration, the register and the
 *  capital's balance; from the financial year's close, the tax return, the papers to the partners and the assembly, on
 *  one dated road with the next one said on top (15.95 art. 75, tax code arts 20 and 148, 5.96 arts 51, 70, 86). It
 *  waits for a person's check. The inputs live in the address. */
export default function YearPage({ slug }: { slug: string }) {
  const { t, i18n } = useBusinessT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const today = todayIso();
  const [s, set] = useToolState({ y: closeAhead(today), c: '', g: '' });
  const stops = [...(s.c ? fromCreation(s.c, s.g || null) : []), ...fromClose(s.y)]
    .sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0));
  const next = stops.find((x) => x.date >= today && x.key !== 'created' && x.key !== 'close');
  const title = (k: string) => t(`year.stops.${k}.title`);
  const remind = () => calendarFile(stops.filter((x) => x.date >= today && x.key !== 'created' && x.key !== 'close')
    .map((x) => ({ date: x.date, title: title(x.key), detail: here() })), 'company');
  return (
    <KitPage slug={slug} title={t('year.title')} lead={t('year.lead')}>
      <AnswerCard share over={next ? t('year.nextOver', { what: title(next.key) }) : t('year.noneOver')}
                  value={next ? t('year.daysLeft', { count: daysUntil(next.date) }) : t('year.none')}
                  under={<p className="m-0">{next ? dayWords(next.date, lang) : t('year.noneUnder')}</p>} />

      <Sheet>
        <DateField label={t('year.close')} value={s.y} onChange={(y) => set({ y })} lang={lang} future note={t('year.closeNote')} />
        <Chips label={t('year.new')} value={s.c ? 'yes' : 'no'} onChange={(v) => set({ c: v === 'yes' ? (s.c || today) : '', g: v === 'yes' ? s.g : '' })}
               options={[{ key: 'no', label: t('year.newNo') }, { key: 'yes', label: t('year.newYes') }]} />
        {s.c ? <DateField label={t('year.created')} value={s.c} onChange={(c) => set({ c })} lang={lang} note={t('year.createdNote')} /> : null}
        {s.c ? <DateField label={t('year.registered')} value={s.g} onChange={(g) => set({ g })} lang={lang} note={t('year.registeredNote')} /> : null}
      </Sheet>

      <section className="rounded-card bg-sheet px-5 py-5 sm:px-7">
        <Road today={today} lang={lang}
              stops={stops.map((x) => ({ key: x.key, date: x.date, title: title(x.key), line: t(`year.stops.${x.key}.line`),
                                        chip: <SourceMark path={x.path} label={articleLabel(x.path)} /> }))} />
      </section>

      <Sheet>
        <p className="m-0 text-body">{t('year.losses')} <SourceMark path={ARTICLES.losses} label={articleLabel(ARTICLES.losses)} /></p>
        <SourceFold paths={Object.values(ARTICLES)} label={articleLabel} />
        <div className="flex flex-wrap gap-2">
          <Button onClick={remind}>{t('year.remind')}</Button>
          <Button variant="quiet" to={refPath(slug, 'journeys/sarl-start')}>{t('year.toSarl')}</Button>
          <Button variant="quiet" to={refPath(slug, 'tax:pages/business')}>{t('year.toTax')}</Button>
        </div>
      </Sheet>
    </KitPage>
  );
}
