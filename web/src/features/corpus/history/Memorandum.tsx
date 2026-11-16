import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { TextDetail } from '../corpus.api';
import { AR, paragraphs } from '../format';
import '@/shared/locales/pages';

/** The government's explanatory memorandum, as filed with the bill (row 11): official, but no part of the law —
 *  said so above it, with the bill it comes from. Its first paragraph shown, the rest on request. */
export function Memorandum({ d }: { d: TextDetail }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const memo = d.explanations.find((e) => e.kind === 'memorandum');
  if (!memo) return null;
  const parts = paragraphs(memo.body);
  return (
    <section aria-labelledby="memorandum" className="mt-6 border-y border-rule-soft py-5" data-noprint>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 id="memorandum" className="m-0 text-body font-semibold">{t('pages:memorandum.title')}</h2>
        <a href={memo.source_url} target="_blank" rel="noreferrer" className="text-meta no-underline">{t('pages:memorandum.source')}</a>
      </div>
      <p className="m-0 mt-1 text-meta text-ink-soft">{t('pages:memorandum.what')}</p>
      <div {...AR} className="mt-4 flex max-w-[70ch] flex-col gap-3 font-law text-law leading-relaxed">
        {(open ? parts : parts.slice(0, 1)).map((p, i) => <p key={i} className="m-0">{p}</p>)}
      </div>
      {parts.length > 1 ? (
        <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} className="mt-3 min-h-11 text-meta font-medium text-stamp">
          {open ? t('pages:memorandum.less') : t('pages:memorandum.more', { count: parts.length })}
        </button>
      ) : null}
    </section>
  );
}

/** The bill as filed with Parliament, beside the text's links. */
export function Bill({ d }: { d: TextDetail }) {
  const { t } = useTranslation();
  if (!d.bill) return null;
  return (
    <section className="flex flex-col gap-2">
      <h2 className="m-0 text-body font-semibold">{t('pages:memorandum.parliament')}</h2>
      <a href={`/api/sources/documents/${d.bill.document_id}/file/`} target="_blank" rel="noreferrer" className="no-underline">
        {t('pages:memorandum.bill')}
      </a>
      {d.bill.page ? <a href={d.bill.page} target="_blank" rel="noreferrer" className="text-meta no-underline">{t('pages:memorandum.billPage')}</a> : null}
    </section>
  );
}
