/** The custody clock (22.01 arts 66, 66-2, 80, as law 03.23 left them): from the hour of arrest, the end of the custody,
 *  the end with the extensions a written, reasoned permission of the prosecution allows, and the lawyer's contact from
 *  the first hour. Hours as wall-clock time in Morocco: an ISO «YYYY-MM-DDTHH:MM» plus hours. Pure. */
export type Case = 'ordinary' | 'state' | 'terror';

export const ARTICLES = { duration: '/ma/loi/22-01/art_66', extend: '/ma/loi/22-01/art_66-2', family: '/ma/loi/22-01/art_67', present: '/ma/loi/22-01/art_80', minor: '/ma/loi/22-01/art_460' } as const;

/** The first period and each extension, in hours: 48 then 24 once; state security 96 then 96 once; terrorism 96 then
 *  96 twice (art. 66-2). */
export const PERIODS: Record<Case, { first: number; extensions: number[] }> = {
  ordinary: { first: 48, extensions: [24] },
  state: { first: 96, extensions: [96] },
  terror: { first: 96, extensions: [96, 96] },
};

const pad = (n: number) => String(n).padStart(2, '0');
/** A wall-clock time plus hours, as wall-clock time (computed as UTC so no clock change moves it). */
export function plusHours(at: string, hours: number): string {
  const x = new Date(`${at}:00Z`);
  const y = new Date(x.getTime() + hours * 3_600_000);
  return `${y.getUTCFullYear()}-${pad(y.getUTCMonth() + 1)}-${pad(y.getUTCDate())}T${pad(y.getUTCHours())}:${pad(y.getUTCMinutes())}`;
}

export const hoursBetween = (a: string, b: string) => (new Date(`${b}:00Z`).getTime() - new Date(`${a}:00Z`).getTime()) / 3_600_000;

export type Stop = { key: 'arrest' | 'lawyer' | 'end' | 'ext1' | 'ext2'; at: string; hours: number; path: string };

/** A minor (art. 460, as law 03.23 left it, HM6 of the hard-moment review): held in a place for minors «for the original
 *  period of custody, without its extension, unless the case is one of the crimes of art. 108» (state security and
 *  terrorism are among them, so their extensions stand); an ordinary felony or misdemeanour has none. */
export function periods(kind: Case, minor: boolean): { first: number; extensions: number[] } {
  return minor && kind === 'ordinary' ? { first: PERIODS.ordinary.first, extensions: [] } : PERIODS[kind];
}

export function clock(arrest: string, kind: Case, minor = false): Stop[] {
  const p = periods(kind, minor);
  const out: Stop[] = [
    { key: 'arrest', at: arrest, hours: 0, path: ARTICLES.duration },
    { key: 'lawyer', at: plusHours(arrest, 1), hours: 1, path: ARTICLES.extend },
    { key: 'end', at: plusHours(arrest, p.first), hours: p.first, path: minor ? ARTICLES.minor : kind === 'ordinary' ? ARTICLES.duration : ARTICLES.extend },
  ];
  let h = p.first;
  p.extensions.forEach((e, i) => {
    h += e;
    out.push({ key: i === 0 ? 'ext1' : 'ext2', at: plusHours(arrest, h), hours: h, path: ARTICLES.extend });
  });
  return out;
}

/** The longest the custody can last, every extension granted. */
export const longest = (kind: Case) => PERIODS[kind].first + PERIODS[kind].extensions.reduce((a, b) => a + b, 0);
