import { Fragment } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { longDate } from '../format';

/** Where the words come from, as a mark people already trust (R6 of the for-everyone review, 19 Oct 2026): a tick and
 *  «الجريدة الرسمية 7533 · الصفحة 2168» for the text as printed; for a version assembled from later amendments (the
 *  SGG's, Adala's, the site's own), an amber ↻ «نص بعد التعديلات», since the BO prevails. It used to be an office stamp
 *  in a double rule. With `to`, a tap opens the printed page: the proof, like a screenshot. `line` is kept for the
 *  call sites; the mark is one line everywhere now. */
export function Stamp({ issue, page, pageWords, consolidated, translated, issued, asOf, to, className = '' }: {
  issue?: string | null;
  page?: number | null;
  /** Whose page it is, when it is not the Bulletin's: «الصفحة 14 من ملف بوابة عدالة» (RD5 of the readers review:
   *  under the family code «الصفحة 14» read as the Bulletin's, and opened the ministry's file). */
  pageWords?: string | null;
  consolidated?: boolean;
  /** A version a model translated from the official French (BO 7410): said so, never «نص بعد التعديلات». */
  translated?: boolean;
  /** With `consolidated`: an unofficial copy of the text as first issued, not one assembled from amendments. */
  issued?: boolean;
  /** With `consolidated`: the day the copy was brought up to, said in the chip (N4 of the read-and-trusted review). */
  asOf?: string | null;
  line?: boolean;
  /** The printed page, when the reader can open it. */
  to?: string | null;
  className?: string;
}) {
  const { t, i18n } = useTranslation();
  if (translated) {
    return <span data-stamp className={`inline-flex max-w-full items-center rounded-full bg-amended-wash px-2.5 py-1 text-meta font-medium leading-tight text-amended ${className}`}>{t('corpus.translatedShort')}</span>;
  }
  const words = consolidated
    ? [issued ? t('stamp.asIssued') : asOf ? t('stamp.consolidatedTo', { date: longDate(asOf, i18n.language) }) : t('stamp.consolidated'),
       page ? pageWords ?? t('stamp.page', { page }) : t('stamp.unofficial')]
    : [issue ? t('stamp.issue', { number: issue }) : '', page ? t('stamp.page', { page }) : ''].filter(Boolean);
  if (!words.length) return null;
  const look = consolidated ? 'bg-amended-wash text-amended' : 'bg-wash text-stamp';
  const cls = `inline-flex max-w-full items-center gap-1.5 rounded-full px-2.5 py-1 text-meta font-medium leading-tight no-underline ${look} ${className}`;
  const inner = (
    <>
      {consolidated && !issued ? <Again /> : <Tick />}
      {/* Each part whole, the line breaking between them (HM42: «غير / رسمي» left «رسمي» alone on a line). */}
      <span className="min-w-0">{words.map((w, i) => <Fragment key={i}>{i ? ' · ' : null}<span className="inline-block max-w-full">{w}</span></Fragment>)}</span>
    </>
  );
  return to ? (
    <Link to={to} title={t('article.seePage')} data-stamp data-hit
          className={`${cls} ${consolidated ? 'hover:text-amended hover:ring-1 hover:ring-amended' : 'hover:text-stamp-deep hover:ring-1 hover:ring-stamp-line'}`}>{inner}</Link>
  ) : <span data-stamp className={cls}>{inner}</span>;
}

const mark = { width: 15, height: 15, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2.4,
               strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, 'aria-hidden': true, className: 'shrink-0' };
/** As printed in the Bulletin. */
const Tick = () => <svg {...mark}><path d="m5 12.5 4.5 4.5L19 7.5" /></svg>;
/** Assembled from the amendments that came after. */
const Again = () => <svg {...mark}><path d="M20 12a8 8 0 1 1-2.3-5.7M20 4v5h-5" /></svg>;
