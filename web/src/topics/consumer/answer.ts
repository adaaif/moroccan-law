import { fold } from '../road/fold.ts';

/** The three consumer questions search answers itself (S2 of the consumer plan): how long to send back, how long
 *  the guarantee runs, what a late delivery allows. Each by the words people type; none when the question asks
 *  something else or two of them at once. */
export type Asked = 'return' | 'guarantee' | 'late';

const WORDS: Record<Asked, string[]> = {
  return: ['نرجع', 'نرجعها', 'نرجعو', 'نرد', 'التراجع', 'تراجع', 'نتراجع', 'retour', 'retourner', 'renvoyer', 'retractation', 'rétractation', 'rembourse'],
  guarantee: ['الضمان', 'الضمانه', 'ضمان', 'الكارانتي', 'كارانتي', 'garantie'],
  late: ['تعطلات', 'تعطل', 'تاخر', 'تأخر', 'ما وصلات', 'ما وصلاتش', 'ماوصلاتش', 'retard', 'livraison', 'ليفريزون'],
};
const ASKS = ['شحال', 'كم', 'اجل', 'أجل', 'مده', 'مدة', 'يوم', 'ايام', 'combien', 'delai', 'délai', 'jours', 'quand', 'امتى', 'إمتى', 'واش', 'هل', 'نقدر', 'يمكن', 'peut', 'puis'];

export function askedIn(q: string): Asked | null {
  const f = fold(q);
  const words = f.split(/\s+/).filter(Boolean);
  if (!ASKS.some((a) => words.includes(fold(a)) || f.includes(fold(a)))) return null;
  const hit = (Object.keys(WORDS) as Asked[]).filter((k) => WORDS[k].some((w) => f.includes(fold(w))));
  return hit.length === 1 ? hit[0] : null;
}
