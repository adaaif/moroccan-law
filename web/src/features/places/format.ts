import { num } from '@/topics/kit/viz/viz';

/** A whole number as the Bulletin prints it: «1.524», «1 524». */
export const n = (v: number, lang: string) => num(v, lang);

/** A place's name in the reader's language: the French (or English) for French readers. */
export const named = (p: { ar: string; fr: string }, lang: string) => (lang === 'fr' && p.fr ? p.fr : p.ar);
