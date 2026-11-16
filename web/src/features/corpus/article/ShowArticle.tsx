import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import { useDismiss } from '@/shared/components/dismiss';
import { pageImageUrl, useRegion, type ArticleItem, type TextDetail } from '../corpus.api';
import { articleName, issueNo } from '../format';
import { LawBody } from '../LawBody';
import { textName } from '../names';
import { Stamp } from './Stamp';
import { articleStanding } from './status';
import { correction, generate } from './qr';
import './show.css';
import '@/shared/locales/pages';

const SIZES = ['s', 'm', 'l'] as const;

/** «ورّيه القانون» (HM28 of the hard-moment review): an article shown across a counter, to an employer, a landlord,
 *  an official. The whole screen holds its words in large Markazi, where it stands today, the source mark with its issue
 *  and page and the citation, the printed lines framed under it when the page's reading found the article, and a code
 *  that opens the same address on the other person's phone. The screen stays on while it is shown (Wake Lock, where the
 *  browser has it); the phone's back, Escape or «رجوع» closes it. Loaded with its first use. */
export default function ShowArticle({ a, d, frenchFirst, onClose }: {
  a: ArticleItem; d: TextDetail; frenchFirst: boolean; onClose: () => void;
}) {
  const { t, i18n } = useTranslation();
  const [size, setSize] = useState<(typeof SIZES)[number]>('m');
  const awake = useWakeLock();
  useDismiss(onClose);
  useEffect(() => {
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = overflow; };
  }, []);

  const label = articleName(a.label, t);
  const standing = articleStanding(a, d);
  const consolidated = d.version?.consolidation !== 'as_published';
  const file = d.version && ['adala', 'sgg', 'dgi', 'bill'].includes(d.version.consolidation) ? d.version.consolidation : null;
  const documentId = a.document_id ?? d.issue?.document_id ?? null;
  const step = SIZES.indexOf(size);
  // In force today, said so; amended and in force, said with its amendment; anything else in the site's own words.
  const today = standing === 'in_force' || (standing === 'amended' && d.standing?.status === 'in_force');
  const now = today ? t(`pages:articleUse.show.${standing === 'in_force' ? 'inForce' : 'inForceAmended'}`)
    : standing ? t(`article.standing.${standing}`) : null;
  const tone = today ? 'sh-on' : standing === 'repealed' ? 'sh-off' : 'sh-mid';

  return createPortal(
    <div role="dialog" aria-modal="true" aria-label={t('pages:articleUse.show.label', { label })} className="sh" data-size={size}>
      <div className="sh-bar">
        <button type="button" onClick={onClose} className="sh-btn">
          <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className="rtl:rotate-180"><path d="M15 6l-6 6 6 6" /></svg>
          {t('pages:articleUse.show.back')}
        </button>
        <span className="sh-sizes">
          <button type="button" className="sh-btn sh-sq" disabled={step === 0} onClick={() => setSize(SIZES[step - 1])}
                  aria-label={t('pages:articleUse.show.smaller')} title={t('pages:articleUse.show.smaller')}>
            <span aria-hidden="true" className="sh-a sh-a-s">A</span>
          </button>
          <button type="button" className="sh-btn sh-sq" disabled={step === SIZES.length - 1} onClick={() => setSize(SIZES[step + 1])}
                  aria-label={t('pages:articleUse.show.bigger')} title={t('pages:articleUse.show.bigger')}>
            <span aria-hidden="true" className="sh-a">A</span>
          </button>
        </span>
      </div>

      <div className="sh-page">
        <p className="sh-text" dir="auto">{textName(d, i18n.language)}</p>
        {frenchFirst && a.french ? <h2 className="sh-label" lang="fr" dir="ltr">{articleName(a.french.label, t)}</h2>
          : <h2 className="sh-label" lang="ar" dir="rtl">{label}</h2>}
        {now ? <p className={`sh-now ${tone}`}><span aria-hidden="true" className="sh-dot" />{now}</p> : null}

        {frenchFirst && a.french ? (
          <>
            <LawBody text={a.french.body} lang="fr" className="sh-law sh-law-fr" />
            <p className="sh-label sh-label-ar" lang="ar" dir="rtl">{label}</p>
          </>
        ) : null}
        <LawBody text={a.body} className="sh-law" />

        <div className="sh-source">
          <Stamp issue={d.issue ? issueNo(d.issue, t) : null} page={a.page} consolidated={consolidated}
                 pageWords={file && file !== 'bill' && a.page ? t(`pages:corpus.pageOfFile.${file}`, { page: a.page }) : null}
                 translated={d.version?.consolidation === 'translation'} issued={d.version?.as_issued} />
          <p className="sh-cite" lang="ar" dir="rtl">{a.citation}</p>
        </div>

        {documentId !== null && a.page_index !== null ? (
          <Printed documentId={documentId} index={a.page_index} label={a.label}
                   caption={file ? t(`pages:corpus.pageOfFile.${file}`, { page: a.page }) : t('pages:articleUse.show.printed', { page: a.page })} />
        ) : null}

        <Code url={`${window.location.origin}${a.path}`} />
        {awake ? <p className="sh-awake">{t('pages:articleUse.show.awake')}</p> : null}
      </div>
    </div>,
    document.body,
  );
}

/** The article as the page printed it: the page's image framed on the article's place (its shares of the page), drawn
 *  wider than the frame and moved by margins, which are shares of the frame's width; shown only when the reading of
 *  the page found the article. */
function Printed({ documentId, index, label, caption }: { documentId: number; index: number; label: string; caption: string }) {
  const region = useRegion(String(documentId), String(index), label).data?.region ?? null;
  const [ratio, setRatio] = useState(1.414);
  if (!region) return null;
  const w = Math.max(0.2, region.right - region.left);
  const h = Math.max(0.04, region.bottom - region.top) * ratio;
  const src = pageImageUrl(documentId, index);
  return (
    <figure className="sh-print">
      <div className="sh-crop" style={{ aspectRatio: `${w} / ${h}` }} dir="ltr">
        <img src={`${src}?w=1600`} srcSet={`${src}?w=900 900w, ${src}?w=1600 1600w`} sizes={`${Math.round(100 / w)}vw`} alt=""
             decoding="async" onLoad={(e) => setRatio(e.currentTarget.naturalHeight / e.currentTarget.naturalWidth || 1.414)}
             style={{ width: `${100 / w}%`, marginLeft: `${(-region.left / w) * 100}%`, marginTop: `${((-region.top * ratio) / w) * 100}%` }} />
      </div>
      <figcaption>{caption}</figcaption>
    </figure>
  );
}

/** A code the other person's phone reads to open the same article (lean-qr's nano encoder, level M, its quiet zone of
 *  four modules), drawn as one path, dark on white in either theme: a reader's camera needs the contrast. */
function Code({ url }: { url: string }) {
  const { t } = useTranslation();
  const path = useMemo(() => {
    const q = generate(url, { minCorrectionLevel: correction.M });
    let p = '';
    for (let y = 0; y < q.size; y++) for (let x = 0; x < q.size; x++) if (q.get(x, y)) p += `M${x + 4} ${y + 4}h1v1h-1z`;
    return { p, n: q.size + 8 };
  }, [url]);
  return (
    <figure className="sh-qr">
      <svg viewBox={`0 0 ${path.n} ${path.n}`} role="img" aria-label={t('pages:articleUse.show.qr')} shapeRendering="crispEdges">
        <rect width={path.n} height={path.n} fill="#fff" />
        <path d={path.p} fill="#000" />
      </svg>
      <figcaption>{t('pages:articleUse.show.qr')}</figcaption>
      <p className="sh-url"><bdi dir="ltr">{url.replace(/^https?:\/\//, '')}</bdi></p>
    </figure>
  );
}

/** The screen kept on while the article is shown, asked again when the page comes back (a lock ends when it hides). */
function useWakeLock(): boolean {
  const [on, setOn] = useState(false);
  useEffect(() => {
    let lock: WakeLockSentinel | null = null;
    let gone = false;
    const ask = () => {
      if (gone || document.visibilityState !== 'visible' || !('wakeLock' in navigator)) return;
      navigator.wakeLock.request('screen').then((l) => {
        if (gone) { void l.release(); return; }
        lock = l;
        setOn(true);
        l.addEventListener('release', () => { if (!gone) setOn(false); });
      }).catch(() => setOn(false));
    };
    ask();
    document.addEventListener('visibilitychange', ask);
    return () => {
      gone = true;
      document.removeEventListener('visibilitychange', ask);
      void lock?.release().catch(() => undefined);
    };
  }, []);
  return on;
}
