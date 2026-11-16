import DatesTool from '../kit/DatesTool';
import { EVENTS } from './rules/dates';
import { useWorkT } from './strings';

/** «الآجال» (T10 of the work plan): the kit's dates tool on the work texts' events. */
export default function DatesPage({ slug }: { slug: string }) {
  const { t } = useWorkT();
  return <DatesTool slug={slug} events={EVENTS} t={t} />;
}
