import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import '@/shared/locales/pages';
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { documentFileUrl, pageImageSet, pageImageUrl, savingData, usePage, useRegion, type PageDetail, type Region } from './corpus.api';
import { AR, longDate, issueNo } from './format';
import { LawBody } from './LawBody';
import { usePageTitle } from '@/shared/services/title';
import { Page, PageSkeleton } from '@/shared/components/ui';
import { LoadError } from '@/features/corpus/NotFound';

// The page full screen, when a finger asks for it (N10 of the read-and-trusted review).
const PageZoom = lazy(() => import('./PageZoom'));

/** Who read a page, as a reader is told: Tesseract by its name, any model as «الذكاء الاصطناعي» (a model is never
 *  named to readers: it may change). */
const engineName = (engine: 'ai' | 'tesseract', t: (key: string) => string) => (engine === 'tesseract' ? 'Tesseract' : t('corpus.ai'));

const READ_BY = { page: 'pages:corpus.readBy', columns: 'pages:corpus.readByColumns', turned: 'pages:corpus.readByTurned' } as const;

/** The evidence (P14 of the polish review): the page as printed first, the text read from it beside it on a desk and
 *  one tab away on a phone. A reader who taps «الصفحة 14» to check an article came for the print, not for a reading. */
export default function PageViewer() {
  const { documentId = '', index = '' } = useParams();
  const { t, i18n } = useTranslation();
  const page = usePage(documentId, index);
  // A phone saving data reads the page's text first; its image comes on a tap (U16).
  const [tab, setTab] = useState<'image' | 'text'>(() => (savingData() ? 'text' : 'image'));
  // Opened from an article (?a=المادة 49): its place on the page, lit (U14 of the Moroccan-design review).
  const label = useSearchParams()[0].get('a');
  const region = useRegion(documentId, index, label).data?.region ?? null;
  // Opened from an article on a phone, the print full screen at once, framed on it, the way back named (HM39 of
  // the hard-moment review: the image stood 525 px down, 334 px wide for two columns). `from` is that article's label.
  const [full, setFull] = useState(() => Boolean(label) && !savingData() && !window.matchMedia('(min-width: 64rem)').matches);
  const [from] = useState(full ? label : null);
  const navigate = useNavigate();
  const { key } = useLocation();
  usePageTitle([page.data ? t('corpus.pageLong', { page: page.data.printed_number ?? Number(index) + 1 }) : null]);

  if (page.isLoading) return <Shell><PageSkeleton /></Shell>;
  if (!page.data) return <Shell><LoadError error={page.error} retry={() => void page.refetch()} /></Shell>;
  const p = page.data;
  const n = Number(index);
  const shown = p.printed_number ?? n + 1;
  const file = p.source === 'adala' || p.source === 'sgg_consolidated' || p.source === 'dgi' ? p.source : null;

  return (
    <Shell>
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1.5">
          {p.issue ? (
            <Link to={`/bo/${p.issue.edition}/${p.issue.key}`} className="text-meta no-underline">
              {t('corpus.issueTitle', { number: issueNo(p.issue, t) })}{t('corpus.listSep')}{longDate(p.issue.date, i18n.language)}
            </Link>
          ) : file ? <span className="text-meta text-ink-soft">{t(`pages:corpus.fileOf.${file}`)}</span> : null}
          <h1 className="m-0 text-h1 font-bold leading-tight">{t('corpus.pageAsPrinted', { page: shown })}</h1>
        </div>
        <nav aria-label={t('pages:corpus.pageNav')} className="flex items-center gap-2">
          <PageLink to={n > 0 ? `/pages/${documentId}/${n - 1}` : null} label={t('corpus.previous')} />
          <span className="px-2 text-meta text-ink-soft">{n + 1} / {p.page_count}</span>
          <PageLink to={n + 1 < p.page_count ? `/pages/${documentId}/${n + 1}` : null} label={t('corpus.next')} />
        </nav>
      </header>

      {p.texts.length ? (
        <section className="flex flex-wrap items-center gap-2 text-meta">
          <span className="text-ink-soft">{t('pages:corpus.textsOnPage')}</span>
          {p.texts.map((x) => (
            <Link key={x.id} to={x.path}
                  {...AR} className="max-w-[44ch] truncate rounded-full border border-rule bg-sheet px-3 py-1.5 text-ink no-underline hover:border-stamp">
              {x.title}
            </Link>
          ))}
        </section>
      ) : null}

      {/* A phone: the print first, the reading behind its tab. A desk: both, the print on the reading's start side. */}
      <div role="tablist" aria-label={t('pages:corpus.pageNav')} className="flex gap-1 rounded-full bg-sheet p-1 lg:hidden">
        {(['image', 'text'] as const).map((k) => (
          <button key={k} type="button" role="tab" aria-selected={tab === k} aria-controls={`page-${k}`} onClick={() => setTab(k)}
                  className={`min-h-11 flex-1 rounded-full px-4 text-body font-medium ${tab === k ? 'bg-stamp text-on-stamp' : 'text-ink hover:bg-paper'}`}>
            {t(k === 'image' ? 'pages:corpus.image' : 'pages:corpus.ocrText')}
          </button>
        ))}
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <section id="page-image" role="tabpanel" aria-label={t('pages:corpus.image')}
                 className={`${tab === 'image' ? 'flex' : 'hidden'} min-w-0 flex-col overflow-hidden rounded-card bg-sheet lg:flex`}>
          <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-rule-soft px-5 py-3 text-meta">
            <span className="font-semibold max-lg:sr-only">{t('pages:corpus.image')}</span>
            <a href={documentFileUrl(p.document_id)} target="_blank" rel="noreferrer" className="inline-flex min-h-11 items-center no-underline">
              {file ? t('pages:corpus.openFile') : t('corpus.openPdf')}
            </a>
          </div>
          <PrintedPage src={pageImageUrl(p.document_id, p.index)} set={pageImageSet(p.document_id, p.index)} alt={t('pages:corpus.imageAlt', { page: shown })}
                       region={region} label={label} onOpen={() => setFull(true)} />
        </section>
        <section id="page-text" role="tabpanel" aria-label={t('pages:corpus.ocrText')}
                 className={`${tab === 'text' ? 'flex' : 'hidden'} min-w-0 flex-col overflow-hidden rounded-card bg-sheet lg:flex`}>
          <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-rule-soft px-5 py-3 text-meta">
            <span className="font-semibold">{t('pages:corpus.ocrText')}</span>
            <span className="text-ink-soft">
              {p.read_by
                ? t(READ_BY[p.read_by.variant], { engine: engineName(p.read_by.engine, t) })
                : p.repaired ? t('pages:corpus.layerRepaired') : p.text ? t('pages:corpus.layerOnly') : null}
            </span>
          </div>
          {p.check ? <Check check={p.check} /> : null}
          <div className="max-h-[78vh] overflow-auto px-6 py-5 font-law text-law leading-[1.85]">
            {p.text ? <LawBody text={p.text} lang={p.language} /> : t('pages:corpus.noText')}
          </div>
        </section>
      </div>
      {full ? (
        <Suspense fallback={null}>
          {/* A page turned full screen replaces its address: the phone's back closes the viewer on the page it opened. */}
          <PageZoom src={`${pageImageUrl(p.document_id, p.index)}?w=1600`} alt={t('pages:corpus.imageAlt', { page: shown })} region={region}
                    from={from ? {
                      label: from,
                      // Back to the article it came from; opened by its address alone, to the page and its reading.
                      back: () => (key !== 'default' ? navigate(-1) : setFull(false)),
                      text: () => { setFull(false); setTab('text'); },
                    } : null}
                    previous={n > 0 ? () => navigate(`/pages/${documentId}/${n - 1}`, { replace: true }) : null}
                    next={n + 1 < p.page_count ? () => navigate(`/pages/${documentId}/${n + 1}`, { replace: true }) : null}
                    onClose={() => setFull(false)} />
        </Suspense>
      ) : null}
    </Shell>
  );
}

/** The page as printed; opened from an article, it opens on that article, a band around it, as wide as the screen
 *  allows (U14 of the Moroccan-design review). «الصفحة كاملة» shows it whole again; the image opens apart too. */
function PrintedPage({ src, set, alt, region, label, onOpen }: {
  src: string; set: string; alt: string; region: Region | null; label: string | null;
  /** A tap opens the page full screen (N10). */
  onOpen: () => void;
}) {
  const { t } = useTranslation();
  const [zoom, setZoom] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [wanted, setWanted] = useState(() => !savingData());
  const band = useRef<HTMLSpanElement>(null);
  const width = region && zoom ? Math.min(300, 100 / Math.max(0.34, region.right - region.left)) : 100;
  useEffect(() => {
    if (region && loaded) band.current?.scrollIntoView({ block: 'center', inline: 'center' });
  }, [region, loaded, zoom]);
  return (
    <>
      {region && label ? (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-rule-soft px-5 py-2 text-meta">
          <span className="flex items-center gap-2 font-medium text-stamp">
            <span aria-hidden="true" className="size-3 rounded-sm border-2 border-stamp bg-wash" />
            {t('pages:corpus.lit', { label })}
          </span>
          <button type="button" onClick={() => setZoom((z) => !z)} className="ms-auto inline-flex min-h-11 items-center font-medium text-stamp">
            {zoom ? t('pages:corpus.wholePage') : t('pages:corpus.zoomArticle')}
          </button>
        </div>
      ) : null}
      <div className="max-h-[78vh] overflow-auto bg-paper p-3">
        <div className="relative" style={{ width: `${width}%` }}>
          {wanted ? (
            <button type="button" onClick={onOpen} aria-label={t('pages:corpus.zoomOpen')} title={t('pages:corpus.zoomOpen')}
                    className="block w-full" style={{ cursor: 'zoom-in' }}>
              <img src={`${src}?w=900`} srcSet={set} sizes={`(min-width: 1024px) ${Math.round(width / 2)}vw, ${Math.round(width)}vw`} alt={alt}
                   onLoad={() => setLoaded(true)} className="block h-auto w-full rounded border border-rule bg-white" />
            </button>
          ) : (
            <button type="button" onClick={() => setWanted(true)}
                    className="flex aspect-[1/1.41] w-full items-center justify-center rounded border border-dashed border-field bg-sheet text-body font-medium text-stamp">
              {t('pages:corpus.showImage')}
            </button>
          )}
          {region && wanted ? (
            <span ref={band} aria-hidden="true"
                  className="pointer-events-none absolute rounded-[4px] border-2 border-stamp bg-[color-mix(in_srgb,var(--color-stamp)_10%,transparent)] motion-safe:animate-[fade-in_400ms_ease-out]"
                  style={{ top: `${region.top * 100}%`, height: `${(region.bottom - region.top) * 100}%`,
                           left: `${region.left * 100}%`, width: `${(region.right - region.left) * 100}%` }} />
          ) : null}
        </div>
      </div>
      <a href={src} target="_blank" rel="noreferrer" className="inline-flex min-h-11 items-center self-start px-5 text-meta no-underline">
        {t('pages:corpus.imageWhole')}
      </a>
    </>
  );
}

/** What the file's own text layer confirms of the reading: its letters on a text page, its amounts on a table. */
function Check({ check }: { check: NonNullable<PageDetail['check']> }) {
  const { t } = useTranslation();
  const [line, good] = 'letters' in check
    ? [t('pages:corpus.checkLetters', { share: Math.round(check.letters * 100) }), check.letters >= 0.9 && check.letters <= 1.1]
    : 'amounts_read' in check
      ? [t('pages:corpus.checkAmounts', { inLayer: check.amounts_in_layer, read: check.amounts_read }),
         check.amounts_read > 0 && check.amounts_in_layer / check.amounts_read >= 0.98]
      : [null, true];
  return (
    <div className="flex flex-col gap-1 border-b border-rule-soft px-5 py-2 text-meta">
      {line ? (
        <p className={`m-0 flex items-center gap-2 ${good ? 'text-in-force' : 'text-amended'}`}>
          <span aria-hidden="true" className={`size-1.5 rounded-full ${good ? 'bg-in-force' : 'bg-amended'}`} />
          {line}
        </p>
      ) : null}
      {check.suspect?.length ? (
        <p className="m-0 flex flex-wrap items-center gap-x-2 gap-y-1 text-amended">
          <span aria-hidden="true" className="size-1.5 rounded-full bg-amended" />
          {t('pages:corpus.suspect', { count: check.suspect.length })}
          {check.suspect.map((w) => <bdi key={w} className="rounded bg-amended-wash px-1.5 font-law text-law">{w}</bdi>)}
        </p>
      ) : null}
    </div>
  );
}

function PageLink({ to, label }: { to: string | null; label: string }) {
  const cls = 'inline-flex h-11 items-center rounded-control border border-rule bg-sheet px-4 text-body no-underline';
  return to ? <Link to={to} className={`${cls} text-ink hover:border-stamp`}>{label}</Link>
    : <span aria-disabled="true" className={`${cls} text-muted`}>{label}</span>;
}

function Shell({ children }: { children: React.ReactNode }) {
  return <Page width="wide" className="gap-6">{children}</Page>;
}
