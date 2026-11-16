import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { HOLIDAYS_PATH, type Holiday } from './holidays';

/** A limit and the public holidays (U12 of the Moroccan-design review): moved past one where the law moves it, or
 *  ending on one where it does not; a religious feast's day is the expected one until the Ministry of Habous says. */
export function HolidayLine({ moved, on }: { moved: Holiday[]; on: Holiday | null }) {
  const { t } = useTranslation('topicKit');
  const names = (hs: Holiday[]) => [...new Set(hs.map((h) => t(`holidays.${h.key}`)))].join(t('corpus.listSep', { ns: 'translation' }));
  const expected = [...moved, ...(on ? [on] : [])].some((h) => h.expected);
  if (!moved.length && !on) return null;
  return (
    <span className="basis-full text-meta text-people">
      {moved.length ? t('holidays.moved', { names: names(moved) }) : t('holidays.on', { name: names([on!]) })}
      {expected ? ` ${t('holidays.expected')}` : ''}{' '}
      <Link to={HOLIDAYS_PATH} lang="ar" dir="rtl" className="whitespace-nowrap">{t('holidays.source')}</Link>
    </span>
  );
}
