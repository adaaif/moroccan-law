import { shortName } from './article/message';

/** What the API says a text is called (P6 of the polish review): its everyday name when people have one
 *  («قانون الكراء»), else its title cut by words; `fr` when the official French gives one. */
export type TextName = { ar: string; fr: string | null };

/** The name to show for a text, in the page's language: never a formal title clipped by CSS mid-number. An older
 *  answer without `name` falls back to the everyday name, then the title cut by words. */
export function textName(x: { title: string; name?: TextName | null; everyday_name?: { ar: string; fr: string } | null },
                         lang: string, max = 60): string {
  const n = x.name ?? x.everyday_name;
  if (n) return (lang === 'fr' && n.fr) || n.ar;
  return shortName(x.title, max);
}
