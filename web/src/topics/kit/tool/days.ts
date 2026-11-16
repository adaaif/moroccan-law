import { todayIso } from '@/shared/services/today';

/** «الخميس 24 أكتوبر 2026»: a day in words, the weekday first, as people say a date. */
export function dayWords(day: string, lang: string, year = true): string {
  return new Date(`${day}T12:00:00Z`).toLocaleDateString(lang === 'fr' ? 'fr-MA' : 'ar-MA',
    { weekday: 'long', day: 'numeric', month: 'long', ...(year ? { year: 'numeric' } : {}), timeZone: 'UTC' });
}

/** The whole days from today to `day` (negative once it has passed). */
export function daysUntil(day: string): number {
  const today = new Date(`${todayIso()}T12:00:00Z`).getTime();
  return Math.round((new Date(`${day}T12:00:00Z`).getTime() - today) / 864e5);
}
