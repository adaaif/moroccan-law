/** What the measures keep on this device, in its own storage, never sent (the analytics review, 15 Nov 2026): the
 *  Moroccan day it last opened the site (visit.ts), and two marks that stop every measure on it: the reader's refusal,
 *  set by «لا تحسبني» on /privacy, and a team account seen signed in here (staff test the site; their pages are not
 *  readers'). A refusal or a team account also removes the day. Every access is tried: a private window may refuse
 *  storage, and then nothing is kept. */

const DAY = 'law.measure.day';
const OFF = 'law.measure.off';
const STAFF = 'law.measure.staff';

/** A stored value: null when none, undefined when the device keeps nothing. */
function read(key: string): string | null | undefined {
  try {
    return localStorage.getItem(key);
  } catch {
    return undefined;
  }
}

function write(key: string, value: string | null): void {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch { /* nothing kept */ }
}

/** The day this device last opened the site: null for never, undefined when it keeps nothing. */
export const lastDay = (): string | null | undefined => read(DAY);
export const keepDay = (day: string): void => write(DAY, day);
export const forgetDay = (): void => write(DAY, null);

/** Whether the reader asked not to be counted on this device. */
export const refused = (): boolean => read(OFF) === '1';

/** «لا تحسبني» on or off; on, the day kept for the measures goes too. */
export function refuse(on: boolean): void {
  write(OFF, on ? '1' : null);
  if (on) forgetDay();
}

/** Whether a team account was seen on this device. */
export const staffDevice = (): boolean => read(STAFF) === '1';

/** A team account seen signed in here (an answer of the discussion or the review desk says `staff`): never counted
 *  again. */
export function markStaff(): void {
  if (staffDevice()) return;
  write(STAFF, '1');
  forgetDay();
}
