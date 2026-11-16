import { dayWords } from '../kit/tool/days';
import { fine, type Klass, type Offence, type Start } from './rules/fines';
import { useFines } from './rules/rates';
import { useRoadT } from './strings';
import { todayIso } from '@/shared/services/today';

const CLASSES: Klass[] = [1, 2, 3];

/** The price step of the radar and police journeys, worked out in place (J3 of the road tools review): for the day
 *  the journey asked, each class's price today and the day it rises. The fine tool, with its staircase, one tap on. */
export default function FineInline({ slug, day, journey }: { slug: string; day: string; journey: string }) {
  const { t, i18n } = useRoadT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const nf = new Intl.NumberFormat(lang === 'fr' ? 'fr-MA' : 'ar-MA');
  const rates = useFines(slug, day).values;
  const start: Start = journey === 'ticket' ? 'officer' : 'radar';
  const today = todayIso();
  return (
    <ul className="m-0 flex list-none flex-col gap-1.5 rounded-control bg-paper p-3">
      {CLASSES.map((k) => {
        const r = fine({ key: `c${k}`, klass: k, article: '', points: 0, group: 'signs', icon: '' } as Offence, start, day, rates);
        const at = r.steps.findIndex((s) => today <= s.until);
        const next = at >= 0 ? r.steps[at + 1] : undefined;
        return (
          <li key={k} className="flex flex-wrap items-baseline justify-between gap-x-3">
            <span className="text-body">{t(`classesShort.${k}`)}</span>
            <span className="text-body">
              <b className="tabular-nums">{at >= 0 ? t('dh', { amount: nf.format(r.steps[at].amount) }) : t('fine.lateValue')}</b>
              {at >= 0 ? <span className="text-meta text-ink-soft"> · {next ? t('inline.rises', { amount: nf.format(next.amount), date: dayWords(r.steps[at].until, lang, false) }) : t('fine.till', { date: dayWords(r.steps[at].until, lang, false) })}</span> : null}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
