import { useRates } from '../../kit/api';
import { SUGAR, type RateRow } from './sugar';

/** Sugar's rows from the server once it answers, the copy shipped with the tool before and without it. */
export function useSugar(slug: string): RateRow[] {
  const q = useRates(slug, 'sugar');
  return (q.data?.rows as RateRow[] | undefined) ?? SUGAR;
}
