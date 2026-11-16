/** «الكريدي» (T4 of the consumer plan): law 31.08 as the SGG consolidated it. A consumer credit (arts 74–111):
 *  seven days to withdraw from the offer's acceptance (art. 85), early repayment free at any time (art. 103), and when
 *  payments stop the most a lender may ask: late interest within 4 % of the capital left when it asks for all of it at
 *  once (art. 104; its exact maximum rate is set by a joint order, decree 2.12.503 art. 33), or else an indemnity within
 *  4 % of the instalments due and unpaid, 2 % of those it agreed to defer (art. 105), and nothing more but costs it
 *  proves (arts 108, 110). A home loan (arts 113–134): early repayment's indemnity within 2 % of the capital left when
 *  the contract provides one (art. 132), late interest within 2 % of the capital left (art. 133). These are the law's
 *  ceilings, worked out in dirhams; a contract may ask less, never more. */
import { due } from '../../kit/dates.ts';

const art = (n: string) => `/ma/loi/31-08/art_${n}`;
const round = (n: number) => Math.round(n * 100) / 100;

export type Loan = 'consumer' | 'home';

export function withdrawBy(accepted: string): string {
  return due(accepted, { key: '', path: '', label: '', days: 7 });
}

export type Ceilings = {
  /** Asked all at once: the late interest's ceiling on the capital left. */
  lateInterest: number;
  /** Not asked all at once (consumer credit only): the indemnity's ceiling on the unpaid instalments, or on the
   *  deferred ones when the lender agreed to defer them. */
  indemnity: number | null;
  /** Early repayment: what the lender may ask (0 for a consumer credit). */
  early: number;
  cites: string[];
};

export function ceilings(loan: Loan, capitalLeft: number, unpaid = 0, deferred = 0): Ceilings {
  const k = Math.max(0, capitalLeft);
  if (loan === 'home') {
    return { lateInterest: round(k * 0.02), indemnity: null, early: round(k * 0.02), cites: [art('132'), art('133'), art('134')] };
  }
  const indemnity = deferred > 0 ? round(deferred * 0.02) : round(Math.max(0, unpaid) * 0.04);
  return { lateInterest: round(k * 0.04), indemnity, early: 0,
    cites: [art('103'), art('104'), art('105'), art('108'), art('109'), art('110'), '/ma/decret/2-12-503/art_33'] };
}

/** A borrower is in default after three successive instalments unpaid and a notice left unanswered (art. 109). */
export const inDefault = (missed: number, noticeAnswered: boolean) => missed >= 3 && !noticeAnswered;
