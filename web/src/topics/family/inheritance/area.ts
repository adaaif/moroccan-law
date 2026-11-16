import type { Case } from './case';
import type { Answer } from './solve';

/** The parts of the page a reader opened by an answer: an heir who died since, a will, a «تنزيل», the tree to edit. */
export type Open = { later: boolean; will: boolean; tanzil: boolean; tree: boolean };
/** What every area of the page is given: the case, the way to change it, its answer, and what is open. */
export type Area = { c: Case; set: (patch: Partial<Case>) => void; answer: Answer; open: Open; setOpen: (o: Partial<Open>) => void };
