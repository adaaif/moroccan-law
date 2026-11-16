import type { Case } from '../case';
import type { Answer } from '../solve';
import House from './House';
import Road from './Road';

/** After the shares (IR24, IR25 of the inheritance review, 14 Nov 2026): the house that cannot be cut, then the road,
 *  the papers and what they cost. Only once there is an answer. */
export default function After({ answer }: { c: Case; answer: Answer }) {
  if (answer.state !== 'ok') return null;
  return (
    <>
      <House answer={answer} />
      <Road money={answer.money} />
    </>
  );
}
