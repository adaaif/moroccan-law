/** The long-illness finder (S19 of the health review): the words people use for the illnesses of order 2518-05's
 *  list, by the list's number, so «السكر» finds n° 9 and «الكلاوي» n° 16 and 17. The list itself is the topic's page
 *  (pages/illnesses), as the BO printed it; this only adds the everyday words. */
export const EVERYDAY: Record<number, string[]> = {
  1: ['جلطة', 'الجلطة الدماغية', 'avc'], 2: ['سرطان الدم', 'لوكيميا', 'leucémie', 'lymphome'], 6: ['الضيقة', 'الربو', 'asthme'],
  7: ['القلب', 'قلب الولد'], 8: ['الكبد', 'cirrhose'], 9: ['السكر', 'السكري', 'diabète', 'الأنسولين'], 10: ['الصرع', 'épilepsie'],
  14: ['الضغط', 'ضغط الدم', 'tension'], 15: ['القلب', 'cœur'], 16: ['الكلاوي', 'الكلية', 'rein'], 17: ['الكلاوي', 'الدياليز', 'dialyse', 'rein'],
  18: ['التنفس', 'respiration'], 20: ['القلب', 'الشريان', 'coronaire'], 22: ['باركنسون', 'الرعاشة', 'parkinson'], 23: ['بوصفير', 'الكبد', 'hépatite'],
  26: ['الروماتيزم', 'المفاصل', 'rhumatisme'], 27: ['الأمراض العقلية', 'psychose', 'schizophrénie'], 31: ['sep', 'التصلب'],
  33: ['السيدا', 'الإيدز', 'sida', 'vih'], 35: ['الأمراض النفسية', 'personnalité'], 39: ['السرطان', 'الكونسير', 'cancer', 'ورم'],
};

/** Arabic and Latin text folded for matching: no diacritics, alif and ya forms joined, lower case. */
export function fold(s: string): string {
  return s.toLowerCase().normalize('NFKD').replace(/\p{M}/gu, '').replace(/\u0640/g, '')
    .replace(/[أإآ]/g, 'ا').replace(/ى/g, 'ي').replace(/ة/g, 'ه').replace(/\s+/g, ' ').trim();
}

/** The rows a query finds: by the list's words in either language, or by the everyday words. */
export function find<R extends [string, string, string]>(rows: R[], q: string): R[] {
  const f = fold(q);
  if (!f) return rows;
  return rows.filter((r) => fold(`${r[1]} ${r[2]}`).includes(f) || (EVERYDAY[Number(r[0])] ?? []).some((w) => fold(w).includes(f) || f.includes(fold(w))));
}
