import { useCallback, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Floating } from '../reading/Popover';
import type { Word } from './words';


/** The words' meanings live with the pages that load apart: a reader who opens none never downloads them (they made
 *  room in the first load for the header's search, UX5 of the phone-test review). */
let meanings: Promise<unknown> | null = null;
const loadMeanings = () => (meanings ??= import('@/shared/locales/pages'));

/** A word with its meaning a tap away (row 11): the word stays as it is, dotted under, and opens a short note. */
export function Explain({ word, children, className = '' }: { word: Word; children: React.ReactNode; className?: string }) {
  const { t } = useTranslation();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const [ready, setReady] = useState(false);
  const close = useCallback(() => setAnchor(null), []);
  const open = (el: HTMLElement) => {
    setAnchor(el);
    void loadMeanings().then(() => setReady(true));
  };
  return (
    <>
      <button type="button" onClick={(e) => (anchor ? close() : open(e.currentTarget))} aria-expanded={Boolean(anchor)} data-hit
              className={`cursor-help underline decoration-dotted decoration-1 underline-offset-4 ${className}`}>
        {children}
        {/* The words on the button stay its name; what it does is said after them. */}
        <span className="sr-only"> ({t('words.whatIs', { word: t(`words.items.${word}.term`) })})</span>
      </button>
      {anchor ? (
        <Floating anchor={anchor} onClose={close} label={t(`words.items.${word}.term`)}>
          <p className="m-0 text-body font-semibold">{t(`words.items.${word}.term`)}</p>
          <p className="m-0 mt-1 max-w-[36ch] text-body leading-relaxed">{ready ? t(`pages:wordMeans.${word}`) : '…'}</p>
          <Link to="/words" onClick={close} className="mt-2 inline-block text-meta no-underline">{t('words.all')}</Link>
        </Floating>
      ) : null}
    </>
  );
}
