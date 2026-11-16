/** «بغا يخرجني» (H11 of the housing plan): a landlord's notice read against the law, the earliest day to leave, and what
 *  the law sets if a court validates it. Law 67.12 for a home (arts 45–52), law 49.16 for a shop (arts 4, 7–9, 26).
 *  It reads the notice; validating it, and every sum the law leaves to the court, stay the court's. Art. 51's year of
 *  rent is shown as the article says it, for every validated notice: the article names no ground apart, and whether it
 *  follows an eviction for unpaid rent is the court's to say (an editorial call, 20 Oct 2026). */
import { plus } from './rent.ts';

export type Premises = 'home' | 'shop';
export type Reason = 'live' | 'rebuild' | 'arrears' | 'other';
export type NoticeInput = {
  premises: Premises; reason: Reason; dated: string; received: string; months: number; days: number; reasonStated: boolean;
  wholePremises: boolean; ownedSince: string; offeredSimilar: boolean; rent: number; tenantSince: string;
};
/** `met` is null when the reader did not know the fact (HM15 of the hard-moment review): neither ✓ nor ✗, left to the
 *  court, and out of the verdict. */
export type Check = { key: string; met: boolean | null; cites: string[] };
export type NoticeResult = {
  checks: Check[]; valid: boolean; leaveBy: string; lapsesOn: string | null;
  sums: { key: string; amount: number | null; cites: string[]; court?: boolean }[];
};

const lease = (n: number) => `/ma/loi/67-12/art_${n}`;
const shop = (n: number) => `/ma/loi/49-16/art_${n}`;
const round2 = (x: number) => Math.round(x * 100) / 100;

export function noticeCheck(i: NoticeInput, r: { home: Record<string, number>; shop: Record<string, number> }): NoticeResult {
  return i.premises === 'home' ? homeNotice(i, r.home) : shopNotice(i, r.shop);
}

function homeNotice(i: NoticeInput, r: Record<string, number>): NoticeResult {
  const notice = plus(i.received, { months: r.notice_months });
  const given = plus(i.received, { months: i.months, days: i.days });
  const checks: Check[] = [
    { key: 'reasonStated', met: i.reasonStated, cites: [lease(46)] },
    { key: 'lawfulReason', met: i.reason !== 'other', cites: [lease(45), lease(48)] },
    { key: 'wholePremises', met: i.wholePremises, cites: [lease(46)] },
    { key: 'twoMonths', met: given >= notice, cites: [lease(46)] },
  ];
  if (i.reason === 'live') {
    // Art. 49: eighteen months of ownership on the notice's own date; the two months run from its receipt (art. 46).
    const owned = Boolean(i.ownedSince) && plus(i.ownedSince, { months: r.owned_months }) <= (i.dated || i.received);
    // A tenant rarely knows since when the landlord owns the house: unknown is not «missed».
    checks.push({ key: 'owned', met: i.offeredSimilar || owned ? true : i.ownedSince ? false : null, cites: [lease(49)] });
  }
  const sums = [
    { key: 'yearOfRent', amount: round2(i.rent * r.indemnity_months), cites: [lease(51)], court: i.reason === 'arrears' },
    { key: 'moving', amount: null, cites: [lease(51)] },
    ...(i.reason !== 'arrears' ? [{ key: 'falseReason', amount: round2(i.rent * r.false_reason_months), cites: [lease(52)] }] : []),
  ];
  return { checks, valid: checks.every((c) => c.met !== false), leaveBy: given > notice ? given : notice, lapsesOn: null, sums };
}

/** 49.16 art. 26: fifteen days for unpaid rent or a building in ruin, three months for the other grounds; the right to
 *  have the notice validated lapses six months after the period ends. Art. 4: renewal after two years' use. */
function shopNotice(i: NoticeInput, r: Record<string, number>): NoticeResult {
  const short = i.reason === 'arrears';
  const needed = short ? plus(i.received, { days: r.shop_short_days }) : plus(i.received, { months: r.shop_long_months });
  const given = plus(i.received, { months: i.months, days: i.days });
  const leaveBy = given > needed ? given : needed;
  const renewal = Boolean(i.tenantSince) && plus(i.tenantSince, { months: 12 * r.shop_years }) <= i.received;
  const checks: Check[] = [
    { key: 'reasonStated', met: i.reasonStated, cites: [shop(26)] },
    { key: short ? 'fifteenDays' : 'threeMonths', met: given >= needed, cites: [shop(26)] },
  ];
  const sums = [
    ...(i.reason === 'rebuild' ? [{ key: 'threeYears', amount: round2(i.rent * 12 * r.shop_rebuild_years_rent), cites: [shop(9)] }] : []),
    { key: 'harm', amount: null, cites: [shop(7), shop(8)], court: true },
  ];
  return { checks: [...checks, { key: 'renewal', met: renewal, cites: [shop(4)] }], valid: checks.every((c) => c.met),
           leaveBy, lapsesOn: plus(leaveBy, { months: r.shop_lapse_months }), sums };
}
