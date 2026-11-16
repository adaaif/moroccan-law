/** «مقاول ذاتي، تاجر، ولا شركة؟»: who works, at what, for how much a year, in which trade → the forms the texts allow,
 *  each with the reason it is closed when it is, and what each one obliges. It says what the law permits, never which to
 *  choose. Pure. */
export const ARTICLES = {
  autoWho: '/ma/loi/114-13/art_1',
  autoGives: '/ma/loi/114-13/art_2',
  autoHome: '/ma/loi/114-13/art_4',
  excluded: '/ma/decret/2-15-263/art_1',
  traderBooks: '/ma/loi/15-95/art_19',
  traderRegister: '/ma/loi/15-95/art_75',
  sarlWho: '/ma/loi/5-96/art_44',
  sarlCapital: '/ma/loi/5-96/art_46',
  sarlFifty: '/ma/loi/5-96/art_47',
  coopFive: '/ma/loi/112-12/art_14',
} as const;

export type Who = 'alone' | 'few' | 'five';
export type Activity = 'trade' | 'service';
export type Form = 'auto' | 'trader' | 'sarl' | 'coop';
/** Why a form is closed: alone only, the ceiling, the trade listed, five members at least. */
export type Why = 'alone' | 'ceiling' | 'trade' | 'members';

/** The auto-entrepreneur's ceilings on the turnover collected in a year (114.13 art. 1). */
export const CEILING: Record<Activity, number> = { trade: 500_000, service: 200_000 };

export type Option = { form: Form; open: boolean; why?: Why; path: string };

export function forms(who: Who, activity: Activity, turnover: number, listed: boolean): Option[] {
  const auto: Option = who !== 'alone' ? { form: 'auto', open: false, why: 'alone', path: ARTICLES.autoWho }
    : turnover > CEILING[activity] ? { form: 'auto', open: false, why: 'ceiling', path: ARTICLES.autoWho }
    : listed ? { form: 'auto', open: false, why: 'trade', path: ARTICLES.excluded }
    : { form: 'auto', open: true, path: ARTICLES.autoWho };
  const trader: Option = who === 'alone' ? { form: 'trader', open: true, path: ARTICLES.traderRegister }
    : { form: 'trader', open: false, why: 'alone', path: ARTICLES.traderRegister };
  // One to fifty associates (5.96 arts 44 and 47); fifty and more is not asked here.
  const sarl: Option = { form: 'sarl', open: true, path: ARTICLES.sarlWho };
  const coop: Option = who === 'five' ? { form: 'coop', open: true, path: ARTICLES.coopFive }
    : { form: 'coop', open: false, why: 'members', path: ARTICLES.coopFive };
  return [auto, trader, sarl, coop];
}
