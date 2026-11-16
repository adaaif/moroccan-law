/** «فين نمشي؟»: what a dispute is about and how much → the court that decides it, whether its judgment can be appealed or
 *  taken to cassation, whether a lawyer is needed, and what the law says it costs (the civil procedure 58.25, in force since
 *  23 Aug 2026; the criminal procedure 22.01 for a complaint). It names the court; it never says who is right. Pure. */
export type Subject = 'debt' | 'damages' | 'rent' | 'trade' | 'work' | 'family' | 'land' | 'admin' | 'crime';
export const SUBJECTS: Subject[] = ['debt', 'damages', 'rent', 'trade', 'work', 'family', 'land', 'admin', 'crime'];

/** The subjects whose amount decides the court and the recourse. */
export const COUNTED: Record<Subject, boolean> = {
  debt: true, damages: true, rent: true, trade: true, work: true, family: false, land: false, admin: false, crime: false,
};

export const PROXIMITY = 5_000;      // art. 331: below it
export const FINAL = 10_000;         // art. 30: up to it, no appeal
export const CASSATION = 30_000;     // art. 375: up to it, no cassation
export const TRADE_FIRST = 80_000;   // art. 31: where no commercial court sits

export type Court = 'proximity' | 'first' | 'social' | 'family' | 'trade' | 'admin' | 'prosecutor';
export type Recourse = { kind: 'annul' | 'appeal' | 'none'; days: number; path: string };

export type Answer = {
  court: Court; path: string;
  /** The first instance's recourse, then whether cassation is open. */
  recourse: Recourse;
  cassation: { open: boolean; path: string };
  /** Free of court fees for a person (proximity, art. 329), or the appeal exempt (administrative, art. 215). */
  free: 'proximity' | 'admin-appeal' | null;
  /** The oral procedure (art. 96) or the written one (art. 95). */
  oral: boolean;
  /** A lawyer: needed at the Court of cassation (art. 376); the reader's own choice before the first courts (art. 79);
   *  the worker has legal aid by law (art. 311). */
  lawyer: 'own' | 'aid';
};

export function court(subject: Subject, amount: number): Answer {
  const counted = COUNTED[subject];
  const a = counted ? amount : Infinity;
  const no = { open: false, path: '/ma/loi/58-25/art_375' };
  if (subject === 'crime') {
    return { court: 'prosecutor', path: '/ma/loi/22-01/art_40', recourse: { kind: 'none', days: 0, path: '/ma/loi/22-01/art_40' },
             cassation: no, free: null, oral: false, lawyer: 'own' };
  }
  // Proximity: personal and movable claims below 5,000 DH, never family, land, social, administrative or evictions.
  if ((subject === 'debt' || subject === 'damages') && a < PROXIMITY) {
    return { court: 'proximity', path: '/ma/loi/58-25/art_331', recourse: { kind: 'annul', days: 15, path: '/ma/loi/58-25/art_32' },
             cassation: no, free: 'proximity', oral: true, lawyer: 'own' };
  }
  const which: Court = subject === 'work' ? 'social' : subject === 'family' ? 'family' : subject === 'trade' ? 'trade'
    : subject === 'admin' ? 'admin' : 'first';
  const path = which === 'social' ? '/ma/loi/58-25/art_33' : which === 'trade' ? '/ma/loi/58-25/art_31'
    : which === 'admin' ? '/ma/loi/58-25/art_38' : '/ma/loi/58-25/art_29';
  const recourse: Recourse = counted && a <= FINAL
    ? { kind: 'annul', days: 15, path: '/ma/loi/58-25/art_32' }
    : { kind: 'appeal', days: 30, path: '/ma/loi/58-25/art_204' };
  // No cassation up to 30,000 DH, nor on collecting or revising a rent (art. 375).
  const cassation = { open: !(counted && a <= CASSATION) && subject !== 'rent', path: '/ma/loi/58-25/art_375' };
  // Oral up to 10,000 DH, in social cases and for rents; in family cases only for those art. 96 names (said apart).
  const oral = (counted && a <= FINAL) || subject === 'work' || subject === 'rent';
  return { court: which, path, recourse, cassation, free: which === 'admin' ? 'admin-appeal' : null, oral,
           lawyer: subject === 'work' ? 'aid' : 'own' };
}
