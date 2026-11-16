/** «شكون نشكي ليه؟» (T5 of the consumer plan): by sector, the doors in order — the supplier first —, each with
 *  its official service (a link only where an official page gives it) and the article it rests on. The words are the
 *  locales' (`where.doors.<key>`); what to bring is said once per sector. Nothing here decides a case. */
export type Sector = 'shop' | 'online' | 'bank' | 'telecom' | 'utility' | 'insurance' | 'food' | 'prices';
export type Door = { key: string; url?: string; cites?: string[] };

const art = (n: string) => `/ma/loi/31-08/art_${n}`;
const PORTAL = { key: 'portal', url: 'http://reclamation.khidmat-almostahlik.ma/', cites: [art('166')] };
const CHIKAYA = { key: 'chikaya', url: 'https://www.chikaya.ma' };
const ASSOCIATION = { key: 'association', cites: [art('157'), art('158'), '/ma/arrete/504-24/art_1'] };
const COURT = { key: 'court', cites: [art('202')] };

export const SECTORS: Sector[] = ['shop', 'online', 'bank', 'telecom', 'utility', 'insurance', 'food', 'prices'];

export const DOORS: Record<Sector, Door[]> = {
  shop: [{ key: 'supplier', cites: [art('4'), art('65')] }, PORTAL, ASSOCIATION, COURT],
  online: [{ key: 'supplierOnline', cites: [art('32'), art('34')] }, PORTAL, CHIKAYA, ASSOCIATION, COURT],
  bank: [{ key: 'bank', cites: [art('77'), art('103')] }, { key: 'cmmb', url: 'https://cmmb.ma' },
    { key: 'bkam', url: 'https://www.bkam.ma/Trouvez-l-information-concernant/Services-rendus-au-public/Resolution-des-differends-entre-les-etablissements-de-credit-et-leur-clientele/Traitement-des-reclamations-de-la-clientele-des-etablissements-de-credit' }, COURT],
  telecom: [{ key: 'operator', cites: [art('2'), art('32')] }, { key: 'anrt', url: 'https://www.anrt.ma' }, CHIKAYA, COURT],
  utility: [{ key: 'company', cites: [art('2'), art('4')] }, CHIKAYA, ASSOCIATION, COURT],
  insurance: [{ key: 'insurer' }, { key: 'acaps', url: 'https://www.acaps.ma' }, COURT],
  food: [{ key: 'seller', cites: ['/ma/loi/28-07/art_4'] }, { key: 'onssa', url: 'https://www.onssa.gov.ma', cites: ['/ma/loi/28-07/art_10'] }, PORTAL, COURT],
  prices: [{ key: 'pricesShop', cites: [art('5'), art('57')] }, PORTAL, { key: 'competition', url: 'https://conseil-concurrence.ma', cites: ['/ma/loi/104-12/art_2'] }],
};

/** What to bring, the same for every sector: the paper that proves the purchase, the contract, the dates. */
export const BRING: Record<Sector, string[]> = {
  shop: ['invoice', 'guaranteeCard', 'dates'],
  online: ['order', 'confirmation', 'messages', 'dates'],
  bank: ['contract', 'offer', 'statements', 'letters'],
  telecom: ['contract', 'bills', 'messages'],
  utility: ['bills', 'contract', 'meter'],
  insurance: ['policy', 'letters', 'dates'],
  food: ['invoice', 'product', 'dates'],
  prices: ['invoice', 'photo', 'dates'],
};
