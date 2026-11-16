import { lazy, Suspense, useCallback, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router-dom';
import type { ArticleItem, OutlineEntry } from '../corpus.api';
import { AR, articleName } from '../format';
import { icon } from './navigation';
import { Floating } from './Popover';
import { useCurrentArticle } from './useCurrentArticle';

// The outline and the search in the text come when first opened: the text page is the first page most readers load.
const Panel = lazy(() => import('./Panel'));
const ReadingSettings = lazy(() => import('./ReadingSettings').then((m) => ({ default: m.ReadingSettings })));

/** Held under the header while reading on a phone: which law and where you are in it (its name, then the article and its
 *  part: N6 of the read-and-trusted review), then three
 *  tools in words — «الفهرس» (with the jump by number inside it), «ابحث» in this text, «Aa» for the size and the night
 *  — and «⋯» for choosing articles to export (P10 of the polish review: four bare icons said nothing).
 *  Two rows of 44 px, the bar's own padding gone, so it is no taller than when the place row had 32 (RD21 of the
 *  readers review, 9 Nov 2026). At 360 px the tools took 265 of the row's 336 px and «مدونة الشغل» read «مدونة ا…»: the
 *  row goes nearer the screen's edge (352) and the tools stand closer (229), so the name's words have 107 px where they
 *  had 63, and a name longer than that takes two lines before it is cut (15 of the shelf's 20 names whole, none before). */
export function ReadingBar({ name, index, loaded, textPath, selecting, onSelecting }: {
  /** The law's everyday name: its first line, so a reader who landed in the middle knows which law (N6). */
  name: string;
  /** Every article of the text, loaded or not. */
  index: OutlineEntry[];
  /** The articles on the page. */
  loaded: ArticleItem[];
  textPath: string;
  selecting: boolean;
  onSelecting: (on: boolean) => void;
}) {
  const { t, i18n } = useTranslation();
  const french = i18n.language === 'fr';
  const eids = useMemo(() => loaded.map((a) => a.eid), [loaded]);
  const currentEid = useCurrentArticle(eids);
  const current = loaded.find((a) => a.eid === currentEid);
  // Sent here from the search results («و32 مادة أخرى فيه»): the search in the text opens with the words.
  const [params] = useSearchParams();
  const asked = params.get('find') ?? '';
  const [panel, setPanel] = useState<'outline' | 'find' | null>(asked ? 'find' : null);
  const close = useCallback(() => setPanel(null), []);
  return (
    <div data-noprint className="sticky top-0 z-20 border-b border-rule-soft bg-sheet/95 px-1 backdrop-blur sm:px-6">
      <div className="flex items-center">
        <span dir="auto" className="line-clamp-2 min-w-0 flex-1 ps-4 text-meta font-semibold leading-tight text-ink">{name}</span>
        {/* French words are longer: their icons alone, so the law's name keeps its line (N6). */}
        <Tool label={t('reading.outline')} quiet={french} onClick={() => setPanel('outline')}><ListIcon /></Tool>
        <Tool label={t('reading.findShort')} name={t('reading.find')} quiet={french} onClick={() => setPanel('find')}><FindIcon /></Tool>
        <Settings />
        <More selecting={selecting} onSelecting={onSelecting} />
      </div>
      {/* Where you are, on its own row at the bar's width (HM31 of the hard-moment review: beside the tools it had
          93 px, «المادة 49 · الق…»); a tap opens «الفهرس» there. Not a live region: it changed at every scroll. */}
      {current ? (
        <button type="button" onClick={() => setPanel('outline')}
                className="flex min-h-11 w-full items-center ps-4 text-start text-meta leading-tight text-ink-soft hover:text-stamp">
          <span className="sr-only">{t('reading.where')} </span>
          <span {...AR} className="truncate">
            {articleName(current.label, t)}{current.heading_path.length ? ` · ${current.heading_path.at(-1)}` : ''}
          </span>
        </button>
      ) : null}
      {panel ? (
        <Suspense fallback={null}>
          <Panel kind={panel} index={index} textPath={textPath} current={current?.eid ?? ''} asked={asked} onClose={close} />
        </Suspense>
      ) : null}
    </div>
  );
}

/** A reading tool: its icon and its word (and a longer name for the ear when the word is short). */
export function Tool({ label, name, onClick, pressed, quiet = false, children }: {
  label: string;
  name?: string;
  onClick: (e: React.MouseEvent<HTMLButtonElement>) => void;
  pressed?: boolean;
  /** Its icon alone (with its name for the ear): «⋯». */
  quiet?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button type="button" onClick={onClick} aria-label={name ?? (quiet ? label : undefined)} aria-pressed={pressed} title={name ?? label}
            className={`flex h-11 min-w-11 shrink-0 items-center justify-center gap-1 rounded-control px-1 text-meta font-medium ${pressed ? 'bg-wash text-stamp' : 'text-ink hover:bg-paper'}`}>
      {children}
      {quiet ? null : <span aria-hidden={name ? true : undefined}>{label}</span>}
    </button>
  );
}

/** «Aa»: the law's size and the night, over the page. */
export function Settings() {
  const { t } = useTranslation();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const close = useCallback(() => setAnchor(null), []);
  return (
    <>
      <button type="button" onClick={(e) => setAnchor(anchor ? null : e.currentTarget)} aria-label={t('reading.settings')}
              title={t('reading.settings')} aria-expanded={Boolean(anchor)}
              className="flex h-11 min-w-11 shrink-0 items-center justify-center rounded-control px-2 text-lead font-bold text-ink hover:bg-paper" style={{ fontFamily: 'ui-serif, Georgia, serif' }}>
        {t('reading.sizeShort')}
      </button>
      {anchor ? (
        <Floating anchor={anchor} onClose={close} label={t('reading.settings')}>
          <Suspense fallback={<div className="h-40" />}><ReadingSettings /></Suspense>
        </Floating>
      ) : null}
    </>
  );
}

/** «⋯»: what is done with the text less often — choosing articles to export. */
export function More({ selecting, onSelecting }: { selecting: boolean; onSelecting: (on: boolean) => void }) {
  const { t } = useTranslation();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const close = useCallback(() => setAnchor(null), []);
  return (
    <>
      <Tool label={t('reading.moreTools')} quiet pressed={selecting} onClick={(e) => setAnchor(anchor ? null : e.currentTarget)}><MoreIcon /></Tool>
      {anchor ? (
        <Floating anchor={anchor} onClose={close} label={t('reading.moreTools')}>
          <button type="button" aria-pressed={selecting} onClick={() => { onSelecting(!selecting); close(); }}
                  className="flex min-h-11 w-full items-center gap-3 rounded-control px-2 text-start hover:bg-paper">
            <CheckIcon />{selecting ? t('reading.selectDone') : t('reading.select')}
          </button>
        </Floating>
      ) : null}
    </>
  );
}

const ListIcon = () => <svg {...icon}><path d="M9 6h11M9 12h11M9 18h11M4 6h.01M4 12h.01M4 18h.01" /></svg>;
const FindIcon = () => <svg {...icon}><path d="m10.5 17.5a7 7 0 1 1 0-14 7 7 0 0 1 0 14zM15.5 15.5 20 20" /></svg>;
const CheckIcon = () => <svg {...icon}><rect x="4" y="4" width="16" height="16" rx="3" /><path d="m8.5 12 2.5 2.5 4.5-5" /></svg>;
const MoreIcon = () => <svg {...icon}><circle cx="5" cy="12" r="1.3" /><circle cx="12" cy="12" r="1.3" /><circle cx="19" cy="12" r="1.3" /></svg>;
