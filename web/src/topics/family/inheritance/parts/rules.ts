import { createContext } from 'react';
import type { Rules } from '../engine';

/** The code the case in hand is counted by: the page's frame sets it, so every citation names the right book (IR27). */
export const RulesContext = createContext<Rules['code']>('70-03');

export { inBook, treasuryCites } from '../book';
