/** «رسائل كتذكر القانون» (T8 of the consumer plan, K2): letters a reader fills on the phone — a withdrawal (an
 *  online purchase, a door sale, a credit), ending a contract for late delivery, a guarantee claim, ending a renewed
 *  subscription. Each quotes the articles it rests on; the words are the locales' (`letters.<key>.body`), written by a
 *  person and checked like the journeys. The site sends nothing: the letter is copied or shared from the phone, and the law
 *  asks for «any means that proves receipt». */
export type LetterKey = 'online' | 'door' | 'credit' | 'late' | 'guarantee' | 'subscription';
export type Field = 'name' | 'supplier' | 'item' | 'day' | 'order' | 'city';

export const LETTERS: { key: LetterKey; fields: Field[]; cites: string[] }[] = [
  { key: 'online', fields: ['name', 'supplier', 'item', 'order', 'day', 'city'], cites: ['/ma/loi/31-08/art_36', '/ma/loi/31-08/art_37'] },
  { key: 'door', fields: ['name', 'supplier', 'item', 'day', 'city'], cites: ['/ma/loi/31-08/art_49', '/ma/loi/31-08/art_50'] },
  { key: 'credit', fields: ['name', 'supplier', 'order', 'day', 'city'], cites: ['/ma/loi/31-08/art_85', '/ma/loi/31-08/art_97'] },
  { key: 'late', fields: ['name', 'supplier', 'item', 'order', 'day', 'city'], cites: ['/ma/loi/31-08/art_13', '/ma/loi/31-08/art_14'] },
  { key: 'guarantee', fields: ['name', 'supplier', 'item', 'day', 'city'], cites: ['/ma/loi/31-08/art_65', '/ma/code/doc/art_549', '/ma/code/doc/art_556'] },
  { key: 'subscription', fields: ['name', 'supplier', 'order', 'day', 'city'], cites: ['/ma/loi/31-08/art_7'] },
];

/** The letter's fields filled, an empty one left as dots so it is seen and written by hand. */
export function filled(values: Partial<Record<Field, string>>, fields: Field[]): Record<Field, string> {
  return Object.fromEntries(fields.map((f) => [f, values[f]?.trim() || '……………'])) as Record<Field, string>;
}
