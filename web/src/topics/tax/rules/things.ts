/** What one owns, sells, buys and does on one's own (the tax review, T13–T18): the communes' taxes on a home
 *  and a plot (law 47.06), the vehicle tax (CGI 259–262), a property's gain (63, 65, 73, 144) and its purchase's duties
 *  (128, 133), the auto-entrepreneur (42 bis, 42 ter, 73-III) and paying late (CGI 208, 47.06 art. 147). Every figure from
 *  the topic's rates.yaml row in force on the day asked. Pure: `npm run test:tax`. */
import type { Rates } from './income.ts';

const round2 = (x: number) => Math.round(x * 100) / 100;

/** The housing tax (47.06 arts 24, 27): 75% off a main home's rental value, then the scale slice by slice (0 to h1
 *  exempt, r1 to h2, r2 to h3, r3 above); the services tax (art. 36) on the rental value, 10.5% in towns, 6.5% elsewhere. */
export function housingTax(rentalValue: number, main: boolean, urban: boolean, l: Rates) {
  const base = round2(main ? (rentalValue * (100 - l.abatement)) / 100 : rentalValue);
  const parts = [[l.h1, l.h2, l.r1], [l.h2, l.h3, l.r2], [l.h3, Infinity, l.r3]].map(([from, to, rate]) => {
    const amount = Math.max(0, Math.min(base, to) - from);
    return { from, to: to === Infinity ? null : to, rate, base: amount, tax: round2((amount * rate) / 100) };
  });
  const housing = round2(parts.reduce((a, p) => a + p.tax, 0));
  const servicesRate = urban ? l.services_urban : l.services_other;
  return { base, parts, housing, servicesRate, services: round2((rentalValue * servicesRate) / 100) };
}

export type Zone = 'full' | 'mid' | 'low';
/** Urban land (47.06 arts 43, 45): the area in whole square metres times the commune's rate, within the zone's bounds;
 *  under the floor, no tax is issued. */
export function landTax(area: number, zone: Zone, l: Rates) {
  const m2 = Math.ceil(Math.max(0, area));
  const min = round2(m2 * l[`land_${zone}_min`]);
  const max = round2(m2 * l[`land_${zone}_max`]);
  return { m2, min, max, rateMin: l[`land_${zone}_min`], rateMax: l[`land_${zone}_max`], floor: l.land_floor, none: max < l.land_floor };
}

export type Fuel = 'petrol' | 'diesel' | 'electric';
/** The vehicle tax (art. 262-I-A): by fiscal horsepower (under 8, 8–10, 11–14, 15 and up) and fuel; electric and hybrid
 *  exempt (260-15°); a diesel pick-up of a private person at the petrol tariff. A car put on the road during the year
 *  pays a twelfth for each month left, a month begun counted whole (262-II). */
export function carTax(cv: number, fuel: Fuel, pickup: boolean, startMonth: number | null, c: Rates) {
  if (fuel === 'electric') return { band: '', year: 0, due: 0, months: 0 };
  const band = cv < 8 ? 'lt8' : cv <= 10 ? '8_10' : cv <= 14 ? '11_14' : '15';
  const year = c[`${fuel === 'diesel' && !pickup ? 'diesel' : 'petrol'}_${band}`];
  const months = startMonth ? 13 - startMonth : 12;
  return { band, year, due: round2((year * months) / 12), months };
}

export type SellInput = { price: number; bought: number; costs: number | null; works: number; sellCosts: number; years: number; main: boolean; yearSales: number };
/** A property's sale (T13): the profit before the administration's revaluation coefficient (which only lowers it), 20%
 *  of it and never under 3% of the price (73-II-F-6°, 144-II-1°); the main home after five years exempt but for 3% on the
 *  price above 4 million (63-II-B, 144-II-2°); a year's sales at most 140,000 exempt (63-II-A). Acquisition costs 15% of
 *  the purchase price unless the reader gives more (65-II). */
export function sellTax(i: SellInput, p: Rates) {
  const costs = i.costs ?? round2((i.bought * p.costs) / 100);
  const profit = Math.max(0, round2(i.price - i.sellCosts - (i.bought + costs + i.works)));
  const minimum = round2((i.price * p.minimum) / 100);
  const onProfit = round2((profit * p.rate) / 100);
  if (i.yearSales + i.price <= p.small) return { case: 'small' as const, costs, profit, onProfit, minimum, tax: 0 };
  if (i.main && i.years >= p.home_years) {
    return { case: 'home' as const, costs, profit, onProfit, minimum, tax: round2((Math.max(0, i.price - p.home_cap) * p.minimum) / 100) };
  }
  return { case: onProfit >= minimum ? 'profit' as const : 'minimum' as const, costs, profit, onProfit, minimum, tax: Math.max(onProfit, minimum) };
}

export type Kind = 'built' | 'land' | 'social' | 'family_gift';
/** Registration duties (art. 133): 4% on built premises, 5% on bare land, 3% on the first sale of social housing, 1.5%
 *  on a gift in the family; registered within 30 days (art. 128). */
export function buyDuties(price: number, kind: Kind, r: Rates) {
  return { rate: r[kind], duties: round2((price * r[kind]) / 100), days: r.days };
}

export type Activity = 'trade' | 'service';
/** The auto-entrepreneur (T17): the rate on turnover collected (73-III), the complementary duty by the year's tax (the
 *  scale of 73-II-B-6°), the ceiling (42 ter), and for services one client's turnover above 80,000 withheld at 30% by that
 *  client (42 bis). */
export function autoEntrepreneur(turnover: number, activity: Activity, topClient: number, o: Rates) {
  const rate = activity === 'trade' ? o.trade : o.service;
  const cap = activity === 'trade' ? o.trade_cap : o.service_cap;
  const tax = round2((turnover * rate) / 100);
  const bounds = [o.d1, o.d2, o.d3, o.d4, o.d5, o.d6, o.d7];
  const tier = bounds.findIndex((b) => tax <= b);
  const complementary = turnover > 0 ? o[`c${(tier < 0 ? bounds.length : tier) + 1}`] : 0;
  const excess = activity === 'service' ? Math.max(0, topClient - o.client) : 0;
  return { rate, cap, over: turnover > cap, tax, complementary, total: round2(tax + complementary), excess, withheld: round2((excess * o.client_rate) / 100) };
}

export type LateKind = 'state' | 'local' | 'registration';
/** Paying late (CGI 208; 47.06 art. 147): a penalty of 10% (5% when paid within 30 days), 5% for the first month and
 *  0.5% for each month or part of a month after; a commune's housing or services tax of 1,000 dirhams or less bears
 *  none; registration duties at least 100 dirhams. Months are counted from the due day, a month begun counted whole. */
export function lateCost(amount: number, due: string, paid: string, kind: LateKind, l: Rates) {
  const days = Math.max(0, Math.round((Date.parse(paid) - Date.parse(due)) / 86_400_000));
  if (!days || (kind === 'local' && amount <= l.local_free)) return { days, months: 0, penalty: 0, increase: 0, total: 0, free: days > 0 };
  const [y1, m1, d1] = due.split('-').map(Number);
  const [y2, m2, d2] = paid.split('-').map(Number);
  const whole = (y2 - y1) * 12 + (m2 - m1) - (d2 < d1 ? 1 : 0);
  const begun = d2 === d1 && whole > 0 ? whole : whole + 1;
  const months = Math.max(1, begun);
  const penaltyRate = days <= 30 ? l.penalty_30 : l.penalty;
  const penalty = round2((amount * penaltyRate) / 100);
  const increase = round2((amount * (l.first_month + l.per_month * (months - 1))) / 100);
  const raw = penalty + increase;
  const total = round2(kind === 'registration' ? Math.max(raw, l.registration_min) : raw);
  return { days, months, penaltyRate, penalty, increase, total, free: false };
}
