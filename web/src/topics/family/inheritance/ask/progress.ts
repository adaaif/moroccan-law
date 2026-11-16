import { useSyncExternalStore } from 'react';
import type { Step } from '../flow';

/** Where the questions stand (IR13 of the inheritance review), shared by the questions and the tree, which are two
 *  sections of one page: the question open (null when every one is folded), the questions already asked, and whether
 *  the reader asked to see the tree whole while answering. */
export const ORDER: Step[] = ['who', 'spouse', 'children', 'parents', 'elders', 'siblings', 'agnates', 'checks'];
export type Progress = { step: Step | null; seen: Step[]; big: boolean };

const FRESH: Progress = { step: 'who', seen: ['who'], big: false };
/** A family that came whole (a link, a kept family): every question answered, all folded. */
export const FOLDED: Progress = { step: null, seen: ORDER, big: false };

let state: Progress = FRESH;
const listeners = new Set<() => void>();
const subscribe = (l: () => void) => { listeners.add(l); return () => { listeners.delete(l); }; };
const read = () => state;

/** The page opens: on its first question for a new family, every question folded for one that came with a link. Called
 *  once as the questions mount, before the tree renders, so both draw the same state from the first frame. */
export function begin(folded: boolean): Progress {
  state = folded ? FOLDED : FRESH;
  return state;
}

export function move(patch: Partial<Progress>) {
  state = { ...state, ...patch };
  listeners.forEach((l) => l());
}
export const restart = () => move(FRESH);

export const useProgress = () => useSyncExternalStore(subscribe, read, read);
