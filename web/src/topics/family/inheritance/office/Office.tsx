import type { Area } from '../area';
import Later from './Later';
import Tanzil from './Tanzil';

/** For the office (IR26 of the inheritance review, 14 Nov 2026): an heir who died after the deceased and before the
 *  division, and a «تنزيل». Each part shows once the family said so (IR7's questions open it) or the case already
 *  holds it, and closes by clearing what it held. */
export default function Office(area: Area) {
  const { c, open, answer } = area;
  if (answer.state === 'empty') return null;
  const later = open.later || c.later.length > 0;
  const tanzil = open.tanzil || c.tanzil !== null;
  if (!later && !tanzil) return null;
  return (
    <>
      {later ? <Later {...area} /> : null}
      {tanzil ? <Tanzil {...area} /> : null}
    </>
  );
}
