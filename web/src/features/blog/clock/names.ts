import type { ClockText } from '../blog.api';

/** A text named as a Moroccan reader names it: «ظهير 10 مايو 1918», «المرسوم 2.26.530», «قرار رئيس الحكومة 3.06.26». */
export function textName(t: ClockText, lang: string): string {
  const fr = lang === 'fr';
  const n = t.number ?? '';
  const dashed = n.replace(/\./g, '-');
  switch (t.kind) {
    case 'dahir': return fr ? `dahir du ${day(t.signed, lang)}` : `ظهير ${day(t.signed, lang)}`;
    case 'royal': return fr ? `décret royal n° ${dashed}` : `المرسوم الملكي ${n}`;
    case 'decree': return fr ? `décret n° ${dashed}` : `المرسوم ${n}`;
    case 'decision': return fr ? `arrêté du Chef du gouvernement n° ${dashed}` : `قرار رئيس الحكومة ${n}`;
    default: return fr ? `décision de la Cour constitutionnelle n° ${dashed}` : `قرار المحكمة الدستورية ${n}`;
  }
}

const fmt = (lang: string, o: Intl.DateTimeFormatOptions) => new Intl.DateTimeFormat(lang === 'fr' ? 'fr-MA' : 'ar-MA', { timeZone: 'UTC', ...o });
const utc = (isoDay: string) => new Date(`${isoDay.slice(0, 10)}T00:00:00Z`);

/** «20 شتنبر 2026», «20 septembre 2026». */
export const day = (isoDay: string, lang: string) => {
  const s = fmt(lang, { day: 'numeric', month: 'long', year: 'numeric' }).format(utc(isoDay));
  // French writes the first of a month «1er»; Arabic, as the Bulletin, «فاتح».
  return lang === 'fr' ? s.replace(/^1 /, '1er ') : s.replace(/^1 /, 'فاتح ');
};
/** «الأحد 20 شتنبر 2026», «dimanche 20 septembre 2026». */
export const weekdayDay = (isoDay: string, lang: string) =>
  `${fmt(lang, { weekday: 'long' }).format(utc(isoDay))} ${day(isoDay, lang)}`;
/** «شتنبر 2026». */
export const monthYear = (isoDay: string, lang: string) => fmt(lang, { month: 'long', year: 'numeric' }).format(utc(isoDay));
/** The hour of an instant as the texts write it, «02:00». */
export const hourOf = (instant: string) => instant.slice(11, 16);

/** The short month names along the grid's top, January at the left. */
export function months(lang: string): string[] {
  const f = fmt(lang, { month: lang === 'fr' ? 'short' : 'long' });
  return Array.from({ length: 12 }, (_, m) => f.format(new Date(Date.UTC(2001, m, 15))).replace('.', ''));
}
