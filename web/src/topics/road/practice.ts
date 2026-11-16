/** Practice remembered on the phone (Q2 of the road tools review): a small Leitner box. A card answered right moves up
 *  a box and waits longer before it comes back; a card missed goes back to the first box and comes first. Nothing is
 *  sent. The box of each card under one key per deck. */
const KEY = (deck: string) => `law.road.practice.${deck}`;
export type Boxes = Record<string, { box: number; seen: number }>;

export function readBoxes(deck: string): Boxes {
  try { return JSON.parse(localStorage.getItem(KEY(deck)) ?? '{}') as Boxes; } catch { return {}; }
}

export function answer(deck: string, key: string, right: boolean, turn: number): Boxes {
  const boxes = readBoxes(deck);
  boxes[key] = { box: right ? Math.min(5, (boxes[key]?.box ?? 1) + 1) : 1, seen: turn };
  try { localStorage.setItem(KEY(deck), JSON.stringify(boxes)); } catch { /* private window: the order stays plain */ }
  return boxes;
}

/** The cards in the order to show them: never seen and missed first, then the ones whose box has waited long enough
 *  (box n waits 2^(n−1) turns), then the rest. */
export function order<T extends { key: string }>(cards: T[], boxes: Boxes, turn: number): T[] {
  const due = (k: string) => { const b = boxes[k]; return !b ? 0 : b.box === 1 ? 1 : turn - b.seen >= 2 ** (b.box - 1) ? 2 : 3; };
  return [...cards].sort((a, b) => due(a.key) - due(b.key));
}

/** How many cards a deck has moved past the first box: the progress ring. */
export const learned = (boxes: Boxes) => Object.values(boxes).filter((b) => b.box >= 3).length;

/** A stable shuffle of a card's choices, the right one somewhere among them. */
export function shuffled<T>(items: T[], seed: string): T[] {
  let h = 0;
  for (const c of seed) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return items.map((x, i) => ({ x, k: (h ^ (i * 2654435761)) >>> 0 })).sort((a, b) => a.k - b.k).map((y) => y.x);
}
