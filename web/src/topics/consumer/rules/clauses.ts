/** «واش هاد الشرط تعسفي؟» (T6 of the consumer plan): the seventeen kinds art. 18 of law 31.08 lists, as plain
 *  sentences (the locales' `clause.kinds.<n>`), each with the words of the article it comes from. The reader picks the
 *  kind that looks like their clause; the page says what the law says of that kind and of every abusive clause
 *  (art. 19: void, the rest of the contract kept; the supplier proves it is not abusive), and never «your clause is
 *  abusive»: a court decides. A few words a clause often uses lead to its kind. */
export const KINDS = Array.from({ length: 17 }, (_, i) => i + 1);

/** The words that, typed, point to a kind (folded the road's way). */
export const CLAUSE_WORDS: Record<number, string[]> = {
  1: ['تعويض', 'indemnite', 'indemnisation', 'dedommagement'],
  2: ['تغيير المنتوج', 'خصائص', 'modifier le produit', 'caracteristiques'],
  3: ['وفاة', 'اصابة', 'جسمانية', 'deces', 'dommage corporel'],
  5: ['ارادته', 'volonte'],
  6: ['غرامة', 'جزاء', 'penalite', 'penalites'],
  7: ['فسخ', 'résiliation', 'resiliation', 'nous pouvons resilier'],
  8: ['انهاء', 'sans preavis'],
  9: ['تجديد', 'تمديد', 'tacite', 'reconduction'],
  10: ['اطلع', 'conditions generales', 'non lues'],
  11: ['تغيير بنود', 'modifier le contrat', 'modification unilaterale'],
  12: ['الزيادة في الثمن', 'زيادة الثمن', 'augmenter le prix', 'prix au moment de la livraison'],
  13: ['مطابقة', 'conformite'],
  15: ['ولو لم', 'meme si'],
  16: ['تفويت', 'cession'],
  17: ['محكمة', 'القضاء', 'tribunal', 'recours', 'preuve'],
};

export const CLAUSE_CITES = ['/ma/loi/31-08/art_18', '/ma/loi/31-08/art_19', '/ma/loi/31-08/art_15', '/ma/loi/31-08/art_20'];
