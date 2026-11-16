import { lazy, Suspense, useCallback, useState, useSyncExternalStore } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { EmbedCode } from '@/features/opendata/EmbedCode';
import ShareImage from '@/features/explain/ShareImage';
import FollowButton from '@/features/follows/FollowButton';
import type { ArticleItem, TextDetail } from '../corpus.api';
import { Floating } from '../reading/Popover';
import { ReportError } from '../reading/ReportError';
import { articleName } from '../format';
import { textName } from '../names';
import { Sheet } from '@/shared/components/Sheet';
import { tick } from '@/shared/services/motion';
import { offerInstall } from '@/shared/services/install';
import { forgetArticle, saveArticle, useSaved } from '@/shared/services/saved';
import { articleMessage, plainBody, sourceLine } from './message';
import { onSpeaking, speak, speaking, stopSpeaking, useVoice } from './speech';
import '@/shared/locales/pages';

// The article's discussion count comes with the discussion's own code.
const ArticleTalk = lazy(() => import('@/features/discussion/ArticleTalk'));
// «ورّيه القانون» (HM28): the article on the whole screen, with its code, loaded with its first use.
const ShowArticle = lazy(() => import('./ShowArticle'));

/** An article's row (P13 of the polish review, 19 Oct 2026): «النقاش · N», «شارك», «احفظ», the same on a phone and a
 *  desk, right under the law (P5); «⋯» sits in the article's top corner, as on a post, and holds the rest. «شارك» opens
 *  one sheet of four ways to share. It used to be eleven actions over two levels, five of them ways to share, and a
 *  second row on a desk. Loaded after the text's words. */
export function ArticleRow({ a, d, frenchFirst, wide, more }: {
  a: ArticleItem;
  d: TextDetail;
  frenchFirst: boolean;
  wide: boolean;
  /** «⋯» is open (its button and the article's number open it). */
  more: boolean;
}) {
  const { t } = useTranslation();
  const [shareAt, setShareAt] = useState<HTMLElement | null>(null);
  const closeShare = useCallback(() => setShareAt(null), []);
  const [show, setShow] = useState(false);
  const closeShow = useCallback(() => setShow(false), []);
  return (
    <div data-noprint>
      <div className="flex flex-wrap items-center gap-1">
        <Suspense fallback={<span className="inline-block h-11 w-28" />}>
          <ArticleTalk textPath={d.path} eid={a.eid} path={a.path} label={articleName(a.label, t)} />
        </Suspense>
        <RowButton onClick={(e) => setShareAt(shareAt ? null : e.currentTarget)} icon={<ShareIcon />} label={t('article.share')}
                   expanded={Boolean(shareAt)} />
        <Save a={a} d={d} phone={!wide} row />
        <RowButton onClick={() => setShow(true)} icon={<ShowIcon />} label={t('pages:articleUse.show.open')} expanded={show} />
        {/* A reading of a scan can be wrong: the reader who compares it with the page says so here (UX4). */}
        {d.version?.read_from_scans ? (
          <ReportError row path={a.path} label={articleName(a.label, t)} articleId={a.eid} pageHref={pageOf(a, d)} />
        ) : null}
      </div>
      {show ? <Suspense fallback={null}><ShowArticle a={a} d={d} frenchFirst={frenchFirst} onClose={closeShow} /></Suspense> : null}
      {shareAt ? <ShareChoices a={a} d={d} frenchFirst={frenchFirst} wide={wide} anchor={shareAt} onClose={closeShare} /> : null}
      {more && wide ? <div className="mt-2 rounded-control bg-paper px-4 py-3"><ArticleMore a={a} d={d} frenchFirst={frenchFirst} /></div> : null}
    </div>
  );
}

/** «شارك»: four large choices, the message for WhatsApp first (row 13), then the picture (R14), the link, the words;
 *  the phone's own share sheet as a fifth when it has one. A sheet from the bottom on a phone, a card by the button on a
 *  desk. */
function ShareChoices({ a, d, frenchFirst, wide, anchor, onClose }: {
  a: ArticleItem;
  d: TextDetail;
  frenchFirst: boolean;
  wide: boolean;
  anchor: HTMLElement;
  onClose: () => void;
}) {
  const { t, i18n } = useTranslation();
  const [copied, setCopied] = useState<'' | 'link' | 'words'>('');
  const message = () => articleMessage(a, d, window.location.origin, frenchFirst ? 'fr' : 'ar', t);
  const copy = (what: 'link' | 'words', words: string) => {
    void navigator.clipboard?.writeText(words);
    fromSearch('copied', a.path);
    setCopied(what);
    window.setTimeout(() => setCopied(''), 1600);
  };
  const tile = 'flex min-h-24 flex-col items-start gap-1 rounded-card border border-rule bg-sheet p-3.5 text-start text-ink no-underline hover:border-stamp hover:text-ink';
  const body = (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-2.5">
        <a href={`https://wa.me/?text=${encodeURIComponent(message())}`} target="_blank" rel="noreferrer"
           onClick={() => { fromSearch('shared', a.path); onClose(); }} className={tile}>
          <WhatsAppIcon /><b className="text-body">{t('article.shareWhatsapp')}</b>
          <span className="text-meta text-ink-soft">{t('article.shareWhatsappLead')}</span>
        </a>
        <ShareImage path={a.path} register={frenchFirst ? 'fr' : 'ar'} className={tile}>
          <PictureIcon /><b className="text-body">{t('article.sharePicture')}</b>
          <span className="text-meta text-ink-soft">{t('article.sharePictureLead')}</span>
        </ShareImage>
        <button type="button" onClick={() => copy('link', `${window.location.origin}${a.path}`)} className={tile}>
          <LinkIcon /><b className="text-body" aria-live="polite">{copied === 'link' ? t('article.done') : t('article.shareLink')}</b>
          <span className="text-meta text-ink-soft">{t('article.shareLinkLead')}</span>
        </button>
        <button type="button" onClick={() => copy('words', `${articleName(a.label, t)}\n${plainBody(a.body)}\n\n(${a.citation})`)} className={tile}>
          <CopyIcon /><b className="text-body" aria-live="polite">{copied === 'words' ? t('article.done') : t('article.shareText')}</b>
          <span className="text-meta text-ink-soft">{t('article.shareTextLead')}</span>
        </button>
      </div>
      {typeof navigator !== 'undefined' && 'share' in navigator ? (
        <button type="button" className="inline-flex min-h-11 items-center self-start text-body font-medium text-stamp"
                onClick={() => { fromSearch('shared', a.path); void navigator.share({ text: message() }).catch(() => undefined); }}>
          {t('article.shareOther')}
        </button>
      ) : null}
    </div>
  );
  const title = t('article.shareTitle', { label: articleName(a.label, t) });
  if (wide) return <Floating anchor={anchor} onClose={onClose} label={title}>{body}</Floating>;
  return (
    <Sheet label={title} onClose={onClose} closeButton>
      <div className="mb-3 flex flex-col">
        <span className="text-lead font-bold">{title}</span>
        <span dir="auto" className="text-meta text-ink-soft">{textName(d, i18n.language)}</span>
      </div>
      {body}
    </Sheet>
  );
}

/** «⋯»: the rest of an article's tools, for the few who need them: its voice, following it, the printed page,
 *  an error to report, the code for another site, and how its page was read. */
/** The printed page an article stands on, with the article named for the page's viewer to frame. */
function pageOf(a: ArticleItem, d: TextDetail): string | null {
  const documentId = a.document_id ?? d.issue?.document_id;
  return a.page_index !== null && documentId ? `/pages/${documentId}/${a.page_index}?a=${encodeURIComponent(a.label)}` : null;
}

export function ArticleMore({ a, d, frenchFirst, save = false }: {
  a: ArticleItem; d: TextDetail; frenchFirst: boolean;
  /** A phone's sheet: «حفظ» first. The row holds it only under the article in focus, and a reader who opened another
   *  article's sheet by its number found no way to keep it there (RD19 of the readers review, 9 Nov 2026). */
  save?: boolean;
}) {
  const { t, i18n } = useTranslation();
  const documentId = a.document_id ?? d.issue?.document_id;
  // A compiler's file is no print of the Bulletin (HM37 of the hard-moment review): «الصفحة 27 من ملف بوابة عدالة».
  const file = d.version && ['adala', 'sgg', 'dgi', 'bill'].includes(d.version.consolidation) ? d.version.consolidation : null;
  return (
    <div className="flex flex-col items-start gap-1 text-body">
      {save ? <Save a={a} d={d} phone /> : null}
      <Listen a={a} french={frenchFirst} />
      <FollowButton path={a.path} quiet />
      {a.page_index !== null && documentId ? (
        <Link to={`/pages/${documentId}/${a.page_index}?a=${encodeURIComponent(a.label)}`} className="inline-flex min-h-11 items-center gap-2 px-3 no-underline">
          <PageIcon />{file ? t(`pages:corpus.pageOfFile.${file}`, { page: a.page }) : t('article.seePage')}
        </Link>
      ) : null}
      <span className="inline-flex min-h-11 items-center px-3"><ReportError path={a.path} label={articleName(a.label, t)} articleId={a.eid} /></span>
      <span className="inline-flex min-h-11 items-center px-3"><EmbedCode path={a.path} label={articleName(a.label, t)} /></span>
      {a.reading ? (
        <span className={`px-3 text-meta ${a.reading === 'unconfirmed' || a.reading === 'short' ? 'text-amended' : 'text-ink-soft'}`}>{t(`pages:quality.reading.${a.reading}`)}</span>
      ) : null}
      {i18n.language === 'fr' && !a.french ? <span className="px-3 text-meta text-ink-soft">{t('corpus.frenchMissing')}</span> : null}
    </div>
  );
}

/** «احفظ»: the article kept whole on this device, to read in «محفوظاتي» without a connection (row 14). */
/** An answer a search led to, saved, shared or copied (B3 of the search plan): the search's own module loads only now. */
const fromSearch = (kind: 'saved' | 'shared' | 'copied', path: string) => {
  void import('@/features/search/events').then((m) => m.noteFromSearch(kind, path)).catch(() => undefined);
};

/** Where saved articles live, said once on this device, at its first save (RD19): nothing said they stay on the phone
 *  and open without a connection. Remembered on the device; a refused storage says it once a visit. */
const TOLD = 'law.saved.told';
let told = false;
function firstSave(): boolean {
  if (told) return false;
  told = true;
  try {
    if (localStorage.getItem(TOLD)) return false;
    localStorage.setItem(TOLD, '1');
  } catch { /* refused storage */ }
  return true;
}

function Save({ a, d, phone, row = false }: {
  a: ArticleItem; d: TextDetail;
  /** «على هاتفك», or «على هذا الجهاز» on a wider screen. */
  phone: boolean;
  /** In the article's row: the line goes under the row, not between its buttons. */
  row?: boolean;
}) {
  const { t } = useTranslation();
  const saved = useSaved().some((x) => x.path === a.path);
  const [first, setFirst] = useState(false);
  const toggle = () => {
    if (saved) { void forgetArticle(a.path); return; }
    fromSearch('saved', a.path); tick(12); offerInstall();   // kept: a tick (U7), and the app offered once (U8)
    void saveArticle({
      path: a.path, label: articleName(a.label, t), body: a.body, text: textName(d, 'ar'), textPath: d.path, source: sourceLine(a, d, t),
      citation: a.citation, french: a.french ? { label: a.french.label, body: a.french.body } : null,
    }).then(() => { if (firstSave()) setFirst(true); }, () => undefined);   // a device that refuses to keep: nothing claimed
  };
  return (
    <>
      <RowButton onClick={toggle} icon={<BookmarkIcon filled={saved} />} label={saved ? t('article.saved') : t('article.save')} pressed={saved} />
      {first && saved ? (
        <p role="status" className="m-0 flex w-full flex-wrap items-center gap-x-2 px-3 text-meta text-ink-soft" style={row ? { order: 1 } : undefined}>
          {t(phone ? 'pages:saved.onPhone' : 'pages:saved.onDevice')}
          <Link to="/saved" className="inline-flex min-h-11 items-center font-medium">{t('pages:saved.title')}</Link>
        </p>
      ) : null}
    </>
  );
}

function Listen({ a, french }: { a: ArticleItem; french: boolean }) {
  const { t } = useTranslation();
  const voice = useVoice(french ? 'fr' : 'ar');
  // The voice outlives this button (PX21): it goes on when the sheet closes, and the button reads its state back.
  const on = useSyncExternalStore(onSpeaking, () => speaking() === a.path, () => false);
  if (!voice) return null;
  const toggle = () => {
    if (on) {
      stopSpeaking();
      return;
    }
    const label = articleName(french && a.french ? a.french.label : a.label, t);
    const words = french && a.french ? `${label}. ${plainBody(a.french.body)}` : `${label}. ${plainBody(a.body)}`;
    speak(words, voice, () => {}, a.path, { title: label, stop: t('article.stop') });
  };
  return <RowButton onClick={toggle} icon={on ? <StopIcon /> : <SpeakerIcon />} label={on ? t('article.stop') : t('article.listen')} pressed={on} />;
}

function RowButton({ onClick, icon, label, pressed, expanded, iconOnly }: {
  onClick: (e: React.MouseEvent<HTMLButtonElement>) => void;
  icon: React.ReactNode;
  label: string;
  pressed?: boolean;
  expanded?: boolean;
  iconOnly?: boolean;
}) {
  const on = pressed || expanded;
  return (
    <button type="button" onClick={onClick} aria-pressed={pressed} aria-expanded={expanded}
            aria-label={iconOnly ? label : undefined} title={iconOnly ? label : undefined}
            className={`inline-flex h-11 min-w-11 items-center justify-center gap-2 rounded-control px-3 text-body ${on ? 'bg-wash text-stamp' : 'text-ink hover:bg-paper hover:text-stamp'}`}>
      {icon}
      {iconOnly ? null : <span aria-live="polite">{label}</span>}
    </button>
  );
}

/** A sheet from the bottom of a phone: closed by Escape, a tap outside or a swipe of the hand to its handle. Slides in
 *  (P19), still with reduced motion. */
const icon = { width: 18, height: 18, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.8,
               strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, 'aria-hidden': true };
const big = { ...icon, width: 22, height: 22 };
/** The four corners of a screen turned outward: the article shown whole. */
const ShowIcon = () => <svg {...icon}><path d="M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5" /></svg>;
const ShareIcon = () => <svg {...icon}><path d="M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7M12 15V3M7.5 7.5 12 3l4.5 4.5" /></svg>;
const SpeakerIcon = () => <svg {...icon}><path d="M4 9v6h4l5 4V5L8 9H4ZM16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12" /></svg>;
const BookmarkIcon = ({ filled }: { filled: boolean }) => (
  <svg {...icon} fill={filled ? 'currentColor' : 'none'}><path d="M6 4h12v16l-6-4-6 4V4Z" /></svg>
);
const StopIcon = () => <svg {...icon}><rect x="6" y="6" width="12" height="12" rx="2" /></svg>;
const PageIcon = () => <svg {...icon}><path d="M6 3h9l4 4v14H6z" /><path d="M15 3v4h4M9 12h6M9 16h6" /></svg>;
const WhatsAppIcon = () => (
  <svg {...big} className="text-[#128c4a]"><path d="M4.5 20l1.3-4A8 8 0 1 1 8.6 19z" /><path d="M9.2 8.6c.3 2.6 2.4 4.9 5.2 5.4l1.1-1.3-1.8-.9-.8.8a4 4 0 0 1-2.4-2.4l.8-.8-.9-1.8z" /></svg>
);
const PictureIcon = () => <svg {...big} className="text-stamp"><rect x="3" y="5" width="18" height="14" rx="2" /><circle cx="9" cy="10" r="2" /><path d="m21 16-5-5-8 8" /></svg>;
const LinkIcon = () => <svg {...big}><path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1" /></svg>;
const CopyIcon = () => <svg {...big}><rect x="8" y="8" width="12" height="12" rx="2" /><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3" /></svg>;
