import { useTopic } from '@/features/topics/topics.api';
import type { Named } from './api';
import { noteUse } from './use';
import i18n from '@/shared/locales/i18n';
import { signature } from '@/features/corpus/article/message';
import { SITE_NAME, fileName } from '@/shared/services/fileName';

/** The topic's doors and tools by reference, to name a page's next steps. */
export function useRefTitles(slug: string): Record<string, Named | undefined> {
  const topic = useTopic(slug);
  const m = topic.data?.module;
  const out: Record<string, Named | undefined> = {};
  for (const d of [...(m?.events ?? []), ...(m?.tools ?? [])]) out[d.to ?? `tools/${d.key}`] = d.title;
  return out;
}

/** This page's address and the site's, read while rendering: '' on the server, where the landing pages are drawn at
 *  each deploy (HM2 of the hard-moment review). */
export const here = () => (typeof window === 'undefined' ? '' : window.location.href);
export const origin = () => (typeof window === 'undefined' ? '' : window.location.origin);

/** Text to WhatsApp, as the reader's own message (no tracking, no name). */
export function whatsapp(text: string) {
  noteUse('share');
  window.open(`https://wa.me/?text=${encodeURIComponent(`${text}\n\n${signature(i18n.language)}`)}`, '_blank', 'noopener');
}

/** A calendar file of all-day events, made on the phone and saved by it («أضفها إلى التقويم», F7). */
export function calendarFile(events: { date: string; title: string; detail: string }[], name: string) {
  noteUse('remind');
  const day = (iso: string) => iso.replaceAll('-', '');
  const esc = (s: string) => s.replace(/[\\;,]/g, (m) => `\\${m}`).replace(/\n/g, '\\n');
  const stamp = new Date().toISOString().replace(/[-:]/g, '').slice(0, 15) + 'Z';
  const body = events.map((e, i) => [
    'BEGIN:VEVENT', `UID:${day(e.date)}-${i}@law`, `DTSTAMP:${stamp}`, `DTSTART;VALUE=DATE:${day(e.date)}`,
    `SUMMARY:${esc(e.title)}`, `DESCRIPTION:${esc(e.detail)}`, 'END:VEVENT',
  ].join('\r\n'));
  const ics = ['BEGIN:VCALENDAR', 'VERSION:2.0', `PRODID:-//${SITE_NAME}//family//AR`, 'CALSCALE:GREGORIAN', ...body, 'END:VCALENDAR'].join('\r\n');
  const url = URL.createObjectURL(new Blob([ics], { type: 'text/calendar;charset=utf-8' }));
  const a = Object.assign(document.createElement('a'), { href: url, download: fileName(`${name}.ics`) });
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
