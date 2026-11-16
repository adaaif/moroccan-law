import { useEffect, type CSSProperties } from 'react';
import { useQuery, type UseQueryResult } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Link, useLocation } from 'react-router-dom';
import { count } from '@/features/budget/money';
import { Stamp } from '@/features/corpus/article/Stamp';
import { AR, issueNo, longDate } from '@/features/corpus/format';
import { pageImageUrl } from '@/features/corpus/corpus.api';
import { ListRow, Page } from '@/shared/components/ui';
import { api } from '@/shared/services/api';
import { usePageTitle } from '@/shared/services/title';
import '@/shared/locales/pages';
import './about.css';

type About = { texts: number; articles: number; issues: number; pages: number; corrections: number; explanations: number; on: string; contact: string };
type Specimen = {
  title: string;
  issue: { number: number; suffix: string; date: string } | null;
  articles: { label: string; body: string; path: string; page: number | null; document_id: number | null; page_index: number | null }[];
};

/** The page shown as printed: law 31.13 on the right to information, its first article at the foot of the left column
 *  of the Bulletin's page 1438 (issue 6655, 12 March 2018). Where it stands on the page, as shares of the page (it
 *  never changes), and where the article starts inside that crop. */
const SPECIMEN = '/ma/loi/31-13/art_1';
const CROP = { x: 0.011, y: 0.65, w: 0.494, h: 0.29 };
const LIT = 0.54;

/** The four steps from the Bulletin to the screen, each with the figure that shows it done. */
const STEPS: { id: string; figures: (keyof About)[] }[] = [
  { id: 'take', figures: ['issues'] },
  { id: 'read', figures: ['pages'] },
  { id: 'cut', figures: ['texts', 'articles'] },
  { id: 'fix', figures: ['corrections'] },
];
/** Who wrote what a reader sees, and whether anyone checked it: said here and nowhere else (an editorial call of
 *  15 Nov 2026; the footer links here). `topics` is the row a tool's «كيفاش حسبنا؟» opens (#ab-tools). */
const WHO = ['law', 'translated', 'explain', 'topics', 'blog', 'talk', 'search'] as const;
const YOURS: [string, string][] = [['/data', 'data'], ['/ai', 'ai'], ['/corrections', 'corrections'], ['/open-source', 'open'],
  ['/rules', 'rules'], ['/privacy', 'privacy']];

/**
 * «عن «قانون»» (P18 of the polish review; drawn again on 31 Oct 2026 from an audit of the code, as /privacy and /rules
 * were). It opens on what the site does, shown rather than said: a page of the Bulletin as printed beside
 * the same article as the site gives it, its stamp and its way back to the page. Then the four steps of a text with the
 * figure of each, who wrote what a reader sees (the law read by a model, the translations, «باختصار» by people, the topics
 * and tools no specialist has reviewed yet, the blog), what is the reader's to take, and how to write. Since 15 Nov 2026
 * the one place that says what the AI did and what no specialist has reviewed: the pages themselves no longer repeat it.
 */
export default function AboutPage() {
  const { t, i18n } = useTranslation();
  usePageTitle([t('pages:about.title')]);
  const about = useQuery({ queryKey: ['about'], queryFn: () => api<About>('/open/about/'), staleTime: 3600_000 });
  const specimen = useQuery({ queryKey: ['about', 'specimen'], queryFn: () => api<Specimen>(`/corpus/at${SPECIMEN}/?window=1`), staleTime: 3600_000 });
  const a = about.data;
  useSection(!about.isPending && !specimen.isPending);
  // The files on offer: none while the downloads are closed (since 2 Nov 2026), and the row says they are coming.
  const data = useQuery({ queryKey: ['openManifest'], queryFn: () => api<object>('/open/'), staleTime: 3_600_000 }).data;
  const lang = i18n.language;
  return (
    <Page width="wide" className="ab">
      <header className="ab-head">
        <span className="wordmark ab-mark" role="img" aria-label="قانون المغرب" />
        <h1>{t('pages:about.title')}</h1>
        <p className="lead">{t('pages:about.lead')}</p>
        <p className="ab-demo">{t('pages:about.address')}</p>
        <p className="ab-demo">{t('pages:about.demo')}</p>
      </header>

      <Specimen q={specimen} />

      <section className="ab-steps" aria-labelledby="ab-steps">
        <div className="ab-part">
          <h2 id="ab-steps">{t('pages:about.stepsTitle')}</h2>
          <p>{t('pages:about.stepsLead')}</p>
        </div>
        <ol>
          {STEPS.map((s, i) => (
            <li key={s.id}>
              <span className="n" aria-hidden="true">{i + 1}</span>
              <h3>{t(`pages:about.steps.${s.id}.t`)}</h3>
              <p>{t(`pages:about.steps.${s.id}.d`)}</p>
              <dl>
                {s.figures.map((f) => (
                  <div key={f}>
                    <dt>{t(`pages:about.figures.${f}`)}</dt>
                    <dd>{a ? count(a[f] as number, lang) : '…'}</dd>
                  </div>
                ))}
              </dl>
            </li>
          ))}
        </ol>
        {a ? <p className="ab-on">{t('pages:about.figuresOn', { date: longDate(a.on, lang) })}</p> : null}
      </section>

      <section className="ab-who" aria-labelledby="ab-who">
        <div className="ab-part">
          <h2 id="ab-who">{t('pages:about.whoTitle')}</h2>
          <p>{t('pages:about.whoLead')}</p>
        </div>
        <ul>
          {WHO.map((w) => (
            <li key={w} data-w={w} id={w === 'topics' ? 'ab-tools' : undefined}>
              <h3>{t(`pages:about.who.${w}.t`)}</h3>
              <p>{t(`pages:about.who.${w}.d`)}</p>
              <span className="ab-state">
                {w === 'explain'
                  ? (a?.explanations ? t('pages:about.who.explain.n', { n: count(a.explanations, lang) }) : t('pages:about.who.explain.none'))
                  : t(`pages:about.who.${w}.s`)}
              </span>
            </li>
          ))}
        </ul>
      </section>

      <div className="ab-end">
        <section aria-labelledby="ab-yours">
          <h2 id="ab-yours">{t('pages:about.yoursTitle')}</h2>
          <ul className="ab-rows">
            {YOURS.map(([to, k]) => (
              <li key={k}><ListRow to={to} title={t(`pages:about.yours.${k}.t`)} lead={t(`pages:about.yours.${k}.${k === 'data' && !data ? 'soon' : 'd'}`)} /></li>
            ))}
          </ul>
          <p className="ab-cite">{t('pages:about.cite')}</p>
          <p className="ab-cite">{t('pages:about.bulk')}</p>
        </section>
        <section aria-labelledby="ab-write">
          <h2 id="ab-write">{t('pages:about.writeTitle')}</h2>
          <p>{t('pages:about.write')}</p>
          {a?.contact ? (
            <p>{t('pages:about.mail')} <a href={`mailto:${a.contact}`} dir="ltr">{a.contact}</a></p>
          ) : null}
        </section>
      </div>
    </Page>
  );
}

/** A link to one of the page's sections (the footer's «من كتب ماذا», #ab-who; a tool's «كيفاش حسبنا؟», #ab-tools) lands
 *  on it. The app leaves a #section where it is (App's useTopOnNewPage), but the page loads after its link and is not
 *  there when the browser looks; and the specimen and the figures above it grow when their answers come. So it is found
 *  once the page stands, and again once those answers are in (`settled`); the same link followed twice finds it again. */
function useSection(settled: boolean) {
  const { hash, key } = useLocation();
  useEffect(() => {
    if (hash) document.getElementById(decodeURIComponent(hash.slice(1)))?.scrollIntoView();
  }, [hash, key, settled]);
}

/** The Bulletin's page as printed, its article lit, beside the same article on the site. */
function Specimen({ q }: { q: UseQueryResult<Specimen> }) {
  const { t, i18n } = useTranslation();
  const art = q.data?.articles[0];
  const issue = q.data?.issue;
  const hasPage = art && art.document_id !== null && art.page_index !== null;
  // The crop as the image's own size and place inside its frame: the frame shows CROP of the page.
  const crop = { width: `${100 / CROP.w}%`, left: `${(-CROP.x / CROP.w) * 100}%`, right: 'auto', top: `${(-CROP.y / CROP.h) * 100}%` } as CSSProperties;
  return (
    <section className="ab-specimen" aria-labelledby="ab-specimen">
      <div className="ab-part">
        <h2 id="ab-specimen">{t('pages:about.specimenTitle')}</h2>
        <p>{t('pages:about.specimenLead')}</p>
      </div>
      <div className="ab-pair">
        <figure className="ab-printed">
          <span className="ab-tag">{t('pages:about.printed')}</span>
          <Link to={hasPage ? `/pages/${art.document_id}/${art.page_index}?a=${encodeURIComponent(art.label)}` : SPECIMEN}
                className="ab-crop" style={{ '--ratio': `${(CROP.w * 900) / (CROP.h * 1276)}` } as CSSProperties}
                aria-label={t('pages:about.openPage')}>
            {hasPage ? (
              <img src={`${pageImageUrl(art.document_id!, art.page_index!)}?w=900`} alt="" style={crop} loading="eager" decoding="async" />
            ) : null}
            <span className="ab-lit" style={{ top: `${LIT * 100}%` }} aria-hidden="true" />
          </Link>
          <figcaption>
            {issue && art ? t('pages:about.caption', { issue: issueNo(issue, (k) => t(k)), date: longDate(issue.date, i18n.language), page: art.page }) : '…'}
          </figcaption>
        </figure>
        <div className="ab-ours">
          <span className="ab-tag">{t('pages:about.ours')}</span>
          {art ? (
            <article {...AR}>
              <p className="ab-text">{q.data?.title}</p>
              <h3>{art.label}</h3>
              <p className="ab-body">{art.body}</p>
              <Stamp issue={issue ? issueNo(issue, (k) => t(k)) : null} page={art.page} />
            </article>
          ) : <p className="ab-body">…</p>}
          <span className="ab-links">
            {hasPage ? <Link to={`/pages/${art.document_id}/${art.page_index}?a=${encodeURIComponent(art.label)}`}>{t('pages:about.openPage')}</Link> : null}
            <Link to={SPECIMEN}>{t('pages:about.openArticle')}</Link>
          </span>
        </div>
      </div>
      {/* How an article's source mark reads, moved here from the library (LB1 of the every-code review). */}
      <dl className="ab-marks">
        <div><dt className="p">✓</dt><dd>{t('pages:library.markPrinted')}</dd></div>
        <div><dt className="c">↻</dt><dd>{t('pages:library.markConsolidated')}</dd></div>
        <div><dt aria-hidden="true">↗</dt><dd>{t('pages:library.markPage')}</dd></div>
      </dl>
    </section>
  );
}
