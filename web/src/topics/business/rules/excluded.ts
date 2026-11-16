/** The 41 trades decree 2.15.263 excludes from the auto-entrepreneur's tax regime (tax code art. 42 ter-III), as the
 *  decree prints them after decree 2.15.942. Pure. */
export const ARTICLE = '/ma/decret/2-15-263/art_1';

export const EXCLUDED = [
  'المهندسون المعماريون',
  'أرباب مؤسسات التأمين',
  'المحامون',
  'الصيارفة',
  'الجراحون',
  'جراحو الأسنان',
  'مراقبو الحسابات',
  'تجار في البضائع بالعمولة',
  'المحاسبون',
  'بائعو التبغ',
  'الناشرون',
  'الخبراء المحاسبون',
  'مستغلو مؤسسات تعليم سياقة السيارات',
  'مستغلو القاعات السينمائية',
  'مستغلو المصحات',
  'مستغلو مختبرات التحاليل الطبية',
  'مستغلو مدارس التعليم الخاص',
  'المساحون',
  'أرباب الفنادق',
  'الأعوان القضائيون',
  'المقاولون في الطباعة',
  'الكتبيون',
  'المجزئون والمستثمرون العقاريون',
  'مؤجرو الطائرات أو الطائرات المروحية',
  'تجار بالوكالات',
  'المتاجرون في العقارات',
  'تجار التفصيل في الذهب والحلي والمجوهرات',
  'تجار الجملة في الذهب والحلي والمجوهرات',
  'تجار مصدرون',
  'تجار مستوردون',
  'المساحون القائسون',
  'الأطباء',
  'الموثقون',
  'مقدمو خدمات مرتبطة بتنظيم الحفلات والاستقبالات',
  'الصيادلة',
  'منظاري وبائع النظارات',
  'الأطباء المتخصصون في التشخيص بالأشعة',
  'مسيرو مكتب دراسات',
  'المقاولون في الأعمال الطبوغرافية',
  'معشرو الجمارك',
  'البياطرة',
] as const;

/** Arabic folded for a search: the hamzas and the alif maqsura as their bare letters, the taa marbuta as haa, no
 *  diacritics, no tatweel. */
export function fold(s: string): string {
  return s.normalize('NFKC').replace(/[ً-ْـ]/g, '').replace(/[أإآٱ]/g, 'ا').replace(/ى/g, 'ي')
    .replace(/ة/g, 'ه').replace(/[ؤ]/g, 'و').replace(/[ئ]/g, 'ي').trim();
}

/** The names people say a listed trade by, in Arabic, Darija and French, each to its line in the decree: a broken
 *  plural («الأطباء») is never found from its singular («طبيب») by its letters. */
const ALIASES: [string, number][] = [
  ['طبيب', 31], ['médecin', 31], ['docteur', 31], ['طبيبة', 31], ['جراح', 4], ['chirurgien', 4], ['dentiste', 5], ['طبيب الأسنان', 5],
  ['radiologue', 36], ['راديو', 36], ['صيدلي', 34], ['فارماسيان', 34], ['pharmacien', 34], ['pharmacie', 34], ['بيطري', 40],
  ['vétérinaire', 40], ['opticien', 35], ['نظاراتي', 35], ['لونيت', 35], ['clinique', 14], ['مصحة', 14], ['laboratoire', 15],
  ['مختبر', 15], ['محامي', 2], ['avocat', 2], ['موثق', 32], ['notaire', 32], ['عون قضائي', 19], ['مفوض قضائي', 19],
  ['huissier', 19], ['محاسب', 8], ['comptable', 8], ['كونطابل', 8], ['expert-comptable', 11], ['commissaire aux comptes', 6],
  ['transitaire', 39], ['معشر', 39], ['ديواني', 39], ['مهندس معماري', 0], ['architecte', 0], ['مساح', 17],
  ['géomètre', 17], ['topographe', 38], ['طوبوغراف', 38], ['bureau d’études', 37], ['bureau d\'études', 37],
  ['bijoutier', 26], ['صائغ', 26], ['بيجوتي', 26], ['ذهايبي', 26], ['importateur', 29], ['import', 29], ['مستورد', 29],
  ['exportateur', 28], ['export', 28], ['مصدر', 28], ['commission', 7], ['agent commercial', 24], ['وكيل تجاري', 24],
  ['promoteur immobilier', 22], ['منعش عقاري', 22], ['lotisseur', 22], ['marchand de biens', 25], ['سمسار عقار', 25],
  ['change', 3], ['صرف العملة', 3], ['صراف', 3], ['tabac', 9], ['دخان', 9], ['éditeur', 10], ['ناشر', 10], ['librairie', 21],
  ['مكتبة', 21], ['imprimerie', 20], ['مطبعة', 20], ['auto-école', 12], ['auto école', 12], ['مدرسة السياقة', 12],
  ['لوطو إيكول', 12], ['cinéma', 13], ['سينما', 13], ['école privée', 16], ['مدرسة خاصة', 16], ['hôtel', 18], ['فندق', 18],
  ['assurance', 1], ['تأمين', 1], ['traiteur', 33], ['حفلات', 33], ['ممون الحفلات', 33], ['نكافة', 33], ['avion', 23],
];

/** The listed trades a typed word finds: by a name people say it by, or by any word of the decree's line that starts
 *  like a word typed. */
export function find(query: string): string[] {
  const q = fold(query).toLowerCase();
  if (q.length < 2) return [];
  const named = ALIASES.filter(([a]) => q.includes(fold(a).toLowerCase()) || (q.length >= 4 && fold(a).toLowerCase().startsWith(q)))
    .map(([, i]) => EXCLUDED[i]);
  const words = q.split(/\s+/).filter((w) => w.length >= 2).map((w) => w.replace(/^ال/, ''));
  const byLetters = EXCLUDED.filter((t) => {
    const its = fold(t).split(/\s+/).map((w) => w.replace(/^(وال|ال|و)/, ''));
    return words.every((w) => its.some((x) => x.startsWith(w)));
  });
  return [...new Set([...named, ...byLetters])];
}
