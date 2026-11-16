/** The words a reader meets on a text's page («ظهير», «مرسوم», «نافذ», «الصيغة المحينة») and what they mean. */
export const WORDS = ['bo', 'constitution', 'organic_law', 'law', 'code', 'dahir', 'promulgation', 'decree_law', 'decree',
  'order', 'decision', 'circular', 'convention', 'in_force', 'none_found', 'amended', 'repealed', 'not_yet_in_force', 'as_published',
  'consolidated'] as const;
export type Word = (typeof WORDS)[number];
