import DatesTool from '../../kit/DatesTool';
import { useFamilyT } from '../strings';
import { EVENTS } from './rules';

/** «تواريخ يحددها القانون» (F7 of the family plan): the kit's dates tool on the family's events. */
export default function DatesPage({ slug }: { slug: string }) {
  const { t } = useFamilyT();
  return <DatesTool slug={slug} events={EVENTS} t={t} />;
}
