import type { Case } from '../case';
import { sayShare } from '../parts/say';
import type { Answer } from '../solve';
import { useT } from '../strings';
import { bare, eachName, heirName } from './names';

/** Who takes what so far, under the question in hand (IR13): each tap shows its effect where the finger is. On a phone
 *  it holds above the bottom bar while the question runs below the screen (a dead child's questions are long), so a tap
 *  far down still shows what it changed. Shares in words, one person's each («كل بنت: 2 من 9»), never a bare number. */
const HOLD = 'm-0 sticky bottom-[calc(3.5rem+env(safe-area-inset-bottom))] z-10 lg:bottom-0';
/** A rule above it, for when the question scrolls under it. */
const EDGE = { boxShadow: '0 -1px 0 var(--color-rule)' };

export default function Running({ c, answer }: { c: Case; answer: Answer }) {
  const { t } = useT();
  if (answer.state !== 'ok') {
    return <p aria-live="polite" className={`${HOLD} rounded-control bg-paper px-3 py-2 text-meta text-ink-soft`}>{t(answer.state === 'stop' ? 'ask.run.stop' : 'ask.run.empty')}</p>;
  }
  const items: [string, string][] = [];
  const laters = new Set<number>();
  for (const s of answer.shares) {
    if (s.group === 'heir' && s.heir) items.push([bare(eachName(s.heir, s.count, c.deceased, t)), sayShare(s.each, t)]);
    else if (s.group === 'bequest') {
      const girl = s.key.endsWith('.daughter');
      items.push([t(`ask.run.${girl ? 'granddaughter' : 'grandson'}${s.count > 1 ? 's' : ''}`), sayShare(s.each, t)]);
    } else if (s.group === 'will') items.push([t('ask.run.will'), sayShare(s.each, t)]);
    else if (s.group === 'tanzil') items.push([t(s.count > 1 ? 'ask.run.tanzils' : 'ask.run.tanzil'), sayShare(s.each, t)]);
    else if (s.group === 'treasury') items.push([t('ask.run.treasury'), sayShare(s.each, t)]);
    else if (s.group === 'later' && s.later !== undefined && !laters.has(s.later)) {
      // An heir who died since: their part, said once; who it goes to is the office's part of the page.
      laters.add(s.later);
      const la = answer.later[s.later];
      items.push([t('ask.run.later', { name: bare(heirName(la.later.heir, 1, c.deceased, t)) }), sayShare(la.share, t)]);
    }
  }
  return (
    <p aria-live="polite" style={EDGE} className={`${HOLD} rounded-control bg-paper px-3 py-2 text-meta leading-snug`}>
      {items.map(([who, share], i) => (
        <span key={i}>
          {i ? <span aria-hidden="true" className="text-ink-soft">{'\u00a0· '}</span> : null}
          <span className="inline-block">{who}{t('ask.fold.colon')}<span className="font-semibold">{share}</span></span>
        </span>
      ))}
    </p>
  );
}
