import { useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';
import { Sheet } from '@/shared/components/Sheet';
import { Stamp } from '../article/Stamp';
import { usePreview } from '../corpus.api';
import { AR } from '../format';
import { textName } from '../names';
import { openArticle, warmArticle } from './open';

/** An article the law names, read where the reader is (U6 of the Moroccan-design review): on a phone a tap on «المادة
 *  29» opens a half sheet with its words and its source; «فتح المادة» goes there. The phone's back closes it. Loaded
 *  when first opened. */
export default function Peek({ to, onClose }: { to: string; onClose: () => void }) {
  const { t, i18n } = useTranslation();
  const q = usePreview(to);
  const p = q.data;
  const navigate = useNavigate();
  const qc = useQueryClient();
  const label = useRef<HTMLSpanElement>(null);
  const warm = () => warmArticle(qc, to);
  return (
    <Sheet half label={p?.label ?? t('reading.preview')} onClose={onClose}>
      <div className="flex flex-col gap-3 pb-2">
        <div className="flex flex-col">
          {p?.label ? <span ref={label} {...AR} className="font-law text-h2 font-bold leading-tight">{p.label}</span> : null}
          {p ? <span dir="auto" className="text-meta text-ink-soft">{textName(p.text, i18n.language)}</span> : null}
        </div>
        {q.isLoading ? <p className="m-0 text-body text-ink-soft">{t('corpus.loading')}</p> : null}
        {p?.excerpt ? (
          <p {...AR} className="m-0 whitespace-pre-line border-s-[3px] border-stamp-line ps-4 font-law text-law leading-[1.85]">{p.excerpt}</p>
        ) : null}
        {p ? <span className="self-start"><Stamp issue={p.issue} page={p.page} consolidated={Boolean(p.consolidation && p.consolidation !== 'as_published')} translated={p.consolidation === 'translation'} /></span> : null}
        {/* Its label flies to the article's number, where the article lands lit (./open.ts). */}
        <Link to={to} onPointerEnter={warm} onPointerDown={warm} onFocus={warm}
              onClick={(e) => { if (e.metaKey || e.ctrlKey || e.shiftKey) return; e.preventDefault(); openArticle(navigate, to, label.current, onClose); }}
              className="inline-flex min-h-11 items-center self-start text-body font-semibold">{t('reading.openArticle')}</Link>
      </div>
    </Sheet>
  );
}
