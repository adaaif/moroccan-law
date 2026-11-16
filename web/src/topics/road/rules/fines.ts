/** «شحال غادي نخلص؟» (R11 of the road plan): an offence's class and points, then the three prices of its settlement
 *  as dates from the day that starts them, the deposit to contest and the two thirds that end a contest. Law 52.05 as
 *  the SGG consolidated it (law 116.14): arts 184–187 for the classes, 219, 221 and 222 for the prices and their days,
 *  230, 231 and 234 for contesting, 99 for the points. The amounts come from rates.yaml. */
import { due } from '../../kit/dates.ts';

export type Klass = 1 | 2 | 3 | 'walk';
export type Group = 'speed' | 'signs' | 'inside' | 'vehicle' | 'parking' | 'walking';
export type Offence = {
  key: string; klass: Klass; article: string; points: number; pointsRow?: string;
  /** Where it sits among the tiles, and its pictogram (icons.tsx). */
  group: Group; icon: string;
};

const code = (n: string) => `/ma/loi/52-05/art_${n}`;

/** The offences people ask about, each with the article and item that class it and the row of art. 99 that takes its
 *  points (none when the table has no row for it). */
export const OFFENCES: Offence[] = [
  { key: 'speed20', klass: 2, article: '185', points: 2, pointsRow: '28', group: 'speed', icon: 'speed' },
  { key: 'speed30', klass: 1, article: '184', points: 4, pointsRow: '20', group: 'speed', icon: 'speed' },
  { key: 'redLight', klass: 1, article: '184', points: 4, pointsRow: '19', group: 'signs', icon: 'light' },
  { key: 'priority', klass: 2, article: '185', points: 2, pointsRow: '22', group: 'signs', icon: 'priority' },
  { key: 'pedestrians', klass: 2, article: '185', points: 0, group: 'signs', icon: 'crossing' },
  // Art. 185 item 5: not giving way to the police, the gendarmerie, civil protection or an ambulance using its signals;
  // art. 99 has no row for it.
  { key: 'sirens', klass: 2, article: '185', points: 0, group: 'signs', icon: 'siren' },
  { key: 'overtaking', klass: 1, article: '184', points: 4, pointsRow: '23', group: 'signs', icon: 'overtaking' },
  { key: 'line', klass: 1, article: '184', points: 0, group: 'signs', icon: 'line' },
  { key: 'wrongWay', klass: 1, article: '184', points: 4, pointsRow: '21', group: 'signs', icon: 'wrongWay' },
  { key: 'phone', klass: 2, article: '185', points: 1, pointsRow: '32', group: 'inside', icon: 'phone' },
  { key: 'belt', klass: 2, article: '185', points: 1, pointsRow: '30', group: 'inside', icon: 'belt' },
  { key: 'child', klass: 2, article: '185', points: 1, pointsRow: '31', group: 'inside', icon: 'child' },
  { key: 'inspection', klass: 1, article: '184', points: 3, pointsRow: '25', group: 'vehicle', icon: 'inspection' },
  { key: 'nightLights', klass: 1, article: '184', points: 3, pointsRow: '24', group: 'vehicle', icon: 'nightLights' },
  { key: 'medical', klass: 1, article: '184', points: 0, group: 'vehicle', icon: 'medical' },
  { key: 'pavement', klass: 2, article: '185', points: 0, group: 'parking', icon: 'pavement' },
  { key: 'walk', klass: 'walk', article: '187', points: 0, group: 'walking', icon: 'walk' },
];

export const GROUPS: Group[] = ['speed', 'signs', 'inside', 'vehicle', 'parking', 'walking'];

export type Start = 'officer' | 'radar';
export type Step = { amount: number; until: string; cite: string };
export type FineResult = {
  steps: Step[]; deposit: number; twoThirds: number; contestBy: string; points: number; cites: string[];
};

/** The price by the day it is paid. An officer's offence: the same day, then 15 full days from the next day, then 30
 *  full days from the next day (arts 219, 221). A radar's notice: 24 hours from the day after it was served, then 15
 *  full days from the end of those 24 hours, then 30 full days from the day after it was served (arts 219, 222). A
 *  pedestrian's 25 dirhams has no reduced price. */
export function fine(o: Offence, start: Start, day: string, r: Record<string, number>): FineResult {
  const k = o.klass === 'walk' ? 'walk' : `c${o.klass}`;
  const last = due(day, { key: '', path: '', label: '', days: 30 });
  const steps: Step[] = o.klass === 'walk'
    ? [{ amount: r.walk_30, until: last, cite: code('219') }]
    : start === 'officer'
      ? [{ amount: r[`${k}_day`], until: day, cite: code('219') },
         { amount: r[`${k}_15`], until: due(day, { key: '', path: '', label: '', days: 15 }), cite: code('219') },
         { amount: r[`${k}_30`], until: last, cite: code('221') }]
      : [{ amount: r[`${k}_day`], until: due(day, { key: '', path: '', label: '', days: 1 }), cite: code('219') },
         { amount: r[`${k}_15`], until: due(day, { key: '', path: '', label: '', days: 16 }), cite: code('219') },
         { amount: r[`${k}_30`], until: last, cite: code('222') }];
  const deposit = r[`${k}_max`];
  return {
    steps, deposit, twoThirds: Math.round((deposit * 2) / 3), contestBy: last, points: o.points,
    cites: [code(o.article), code('219'), code(start === 'officer' ? '221' : '222'), code('230'), code('231'), code('234'),
            ...(o.points ? [code('99'), code('28')] : [])],
  };
}
