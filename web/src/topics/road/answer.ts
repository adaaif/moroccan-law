import { fold } from './fold.ts';
import { OFFENCES, type Offence } from './rules/fines.ts';

/** Words that ask what something costs: the answer is then a price, not a text. */
const ASKS = ['شحال', 'بشحال', 'ثمن', 'الثمن', 'غرامه', 'الغرامه', 'مخالفه', 'المخالفه', 'نخلص', 'كنخلص', 'combien', 'amende', 'prix', 'tarif'];

/** The offence a question names, by its words, when the question asks a price: «شحال المخالفة ديال التيليفون». */
export function offenceIn(q: string, words: (o: Offence) => string): Offence | null {
  const asked = fold(q).split(/\s+/).filter(Boolean);
  if (!asked.some((w) => ASKS.some((a) => w === fold(a) || w.endsWith(fold(a))))) return null;
  const scored = OFFENCES.map((o) => {
    const own = fold(words(o)).split(/\s+/).filter((w) => w.length > 2 && !ASKS.map(fold).includes(w));
    return { o, n: asked.filter((w) => own.includes(w)).length };
  }).filter((x) => x.n > 0).sort((a, b) => b.n - a.n);
  return scored.length && (scored.length === 1 || scored[0].n > scored[1].n) ? scored[0].o : null;
}
