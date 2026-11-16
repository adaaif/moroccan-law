/** A first name against the rules of law 36.21 art. 34 a machine can read: at most two names, no title before it, no
 *  number after it. The rest (morals, public order, ridicule, a family name, a town's, a village's or a tribe's) is the
 *  officer's to judge, and the High Commission's when the declarant holds to it (decree 2.22.04 art. 33). Pure. */
export const ARTICLES = { rules: '/ma/loi/36-21/art_34', commission: '/ma/decret/2-22-04/art_33', scripts: '/ma/loi/36-21/art_19' } as const;

/** The titles the article names («مولاي», «سيدي», «لالة») and their usual spellings. */
const TITLES = ['مولاي', 'مولاى', 'سيدي', 'سيدى', 'لالة', 'للا', 'لالا', 'moulay', 'mulay', 'sidi', 'lalla', 'lala'];
const NUMBERS = /^(?:[0-9٠-٩]+|[ivx]+|الأول|الثاني|الثالث|الرابع|الأولى|الثانية|الثالثة|premier|second|deux|trois)$/i;

export type Check = { key: 'two' | 'title' | 'number'; ok: boolean; found?: string };

export function words(name: string): string[] {
  return name.trim().split(/[\s\-_]+/).filter(Boolean);
}

export function check(name: string): Check[] {
  const w = words(name);
  const title = w.find((x) => TITLES.includes(x.toLowerCase()));
  const number = w.find((x) => NUMBERS.test(x));
  const names = w.filter((x) => x !== title && x !== number);
  return [
    { key: 'two', ok: names.length <= 2, found: names.length > 2 ? String(names.length) : undefined },
    { key: 'title', ok: !title, found: title },
    { key: 'number', ok: !number, found: number },
  ];
}
