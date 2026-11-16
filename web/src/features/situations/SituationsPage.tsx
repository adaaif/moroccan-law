import { useTranslation } from 'react-i18next';
import { Link, Navigate, useParams } from 'react-router-dom';
import { useSituations, type GuideLine, type Situation } from '@/features/corpus/corpus.api';
import { addressLabel } from '@/features/corpus/addressLabel';
import { AR } from '@/features/corpus/format';
import '@/shared/locales/pages';
import { SituationArt } from './SituationArt';
import { SITUATION_TO, situationPath } from './to';
import { usePageTitle } from '@/shared/services/title';
import { Page, PageSkeleton } from '@/shared/components/ui';
import { textName } from '@/features/corpus/names';
import NotFound from '@/features/corpus/NotFound';

/** /situations and /situations/:slug (row 4; R10 of the for-everyone review): situations people live, each a guide — what
 *  to do first, the deadlines in a box, what the texts say, who can help — every line naming the article it restates.
 *  Never advice: what the law says, and where. A guide reaches readers once a lawyer reviewed it. */
export default function SituationsPage() {
  const { slug } = useParams();
  // A situation answered by a topic's page leads there (HM4 of the hard-moment review): links shared before keep working.
  const to = slug ? SITUATION_TO[slug] : undefined;
  const { t, i18n } = useTranslation();
  const situations = useSituations();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const s = situations.data?.find((x) => x.slug === slug);
  usePageTitle([s ? s.title[i18n.language === 'fr' ? 'fr' : 'ar'] : null, t('pages:situations.title')]);
  if (to) return <Navigate to={to.path} replace />;

  if (!slug) {
    return (
      <Page width="wide" className="gap-6">
        <header className="flex flex-col gap-2 px-1">
          <h1 className="m-0 text-h2 font-bold">{t('pages:situations.title')}</h1>
          <p className="m-0 max-w-[62ch] text-body text-ink-soft">{t('pages:situations.lead')}</p>
        </header>
        {situations.isLoading ? <PageSkeleton /> : (
          <ul className="m-0 grid list-none gap-3 p-0 sm:grid-cols-2 lg:grid-cols-3">
            {(situations.data ?? []).map((x) => (
              <li key={x.slug}>
                <Link to={situationPath(x.slug)} lang={lang}
                      className="flex h-full items-center gap-4 rounded-card bg-sheet px-4 py-4 text-ink no-underline ring-1 ring-transparent hover:ring-stamp-line">
                  <SituationArt slug={x.slug} topic={x.topic} size={64} />
                  <span className="flex min-w-0 flex-col gap-1">
                    <span className="text-lead font-semibold leading-snug">{x.title[lang]}</span>
                    <span className="text-meta text-ink-soft">
                      {x.guide ? t('pages:guide.hasGuide') : t('pages:guide.articles', { count: x.articles.length })}
                    </span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Page>
    );
  }
  if (!s) return <Page width="reading">{situations.isLoading ? <PageSkeleton kind="text" /> : <NotFound inPage />}</Page>;
  return <Guide s={s} />;
}

function Guide({ s }: { s: Situation }) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const g = s.guide;
  return (
    <Page width="reading" className="gap-4">
      <Link to="/situations" className="px-1 text-body text-ink-soft no-underline hover:text-stamp">{t('situations.all')}</Link>
      <header className="flex flex-col gap-4 rounded-card bg-sheet px-5 py-6 sm:px-8">
        <div className="flex items-center gap-4">
          <SituationArt slug={s.slug} topic={s.topic} />
          <h1 lang={lang} className="m-0 text-h2 font-bold leading-tight">{s.title[lang]}</h1>
        </div>
        <p lang={lang} className="m-0 max-w-[65ch] text-lead leading-relaxed">{s.intro[lang]}</p>
      </header>

      {g?.steps?.length ? (
        <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-6 sm:px-8">
          <h2 className="m-0 text-h3 font-bold">{t('pages:guide.steps')}</h2>
          <ol className="m-0 flex list-none flex-col gap-4 p-0">
            {g.steps.map((x, i) => (
              <li key={i} className="flex gap-3">
                <span className="grid size-9 shrink-0 place-items-center rounded-full bg-stamp text-body font-bold text-on-stamp">{i + 1}</span>
                <Line x={x} lang={lang} />
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      {g?.deadlines?.length ? (
        <section className="flex flex-col gap-3 rounded-card bg-people-wash px-5 py-6 sm:px-8">
          <h2 className="m-0 flex items-center gap-2 text-h3 font-bold text-people">
            <svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <circle cx="12" cy="13" r="8" /><path d="M12 9v4l2.5 2.5M9 2h6" />
            </svg>
            {t('pages:guide.deadlines')}
          </h2>
          <ul className="m-0 flex list-none flex-col gap-3 p-0">{g.deadlines.map((x, i) => <li key={i}><Line x={x} lang={lang} /></li>)}</ul>
        </section>
      ) : null}

      {(['documents', 'where', 'costs'] as const).map((k) => g?.[k]?.length ? (
        <section key={k} className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-6 sm:px-8">
          <h2 className="m-0 text-h3 font-bold">{t(`pages:guide.${k}`)}</h2>
          <ul className="m-0 flex list-none flex-col gap-3 p-0">{g[k]!.map((x, i) => <li key={i}><Line x={x} lang={lang} /></li>)}</ul>
        </section>
      ) : null)}

      {s.articles.length ? (
        <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-6 sm:px-8">
          <h2 className="m-0 text-h3 font-bold">{t('pages:situations.readFirst')}</h2>
          <ol className="m-0 flex list-none flex-col gap-3 p-0">
            {s.articles.map((a) => (
              <li key={a.path} className="flex flex-col gap-1.5 rounded-card bg-paper px-4 py-3">
                <span className="flex flex-wrap items-baseline gap-2">
                  <Link {...AR} to={a.path} className="font-semibold no-underline">{a.label}</Link>
                  <span dir="auto" className="text-meta text-ink-soft">{textName(a.text, i18n.language)}</span>
                </span>
                <p lang={lang} className="m-0 max-w-[65ch] text-body leading-relaxed">{a.says[lang]}</p>
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      <section className="flex flex-col gap-2 rounded-card bg-talk-wash px-5 py-5 sm:px-8">
        <h2 className="m-0 text-lead font-bold text-talk">{t('pages:guide.help')}</h2>
        {(g?.help?.length ? g.help.map((x) => x[lang]) : [t('pages:guide.helpLegalAid'), t('pages:guide.helpLawyer')]).map((line, i) => (
          <p key={i} className="m-0 text-body leading-relaxed">{line}</p>
        ))}
        <Link to="/talk" className="self-start text-body font-medium no-underline">{t('pages:guide.ask')}</Link>
      </section>

      {s.shelf.some((b) => b.state !== 'in_corpus') ? (
        <section className="flex flex-col gap-2 rounded-card bg-sheet px-5 py-5 sm:px-8">
          <h2 className="m-0 text-lead font-semibold">{t('pages:situations.notYet')}</h2>
          {s.shelf.filter((b) => b.state !== 'in_corpus').map((b) => (
            <p key={b.key} className="m-0 text-body">
              <span lang={lang} className="font-semibold">{b.name[lang]}</span>{' '}
              <a href={b.official ?? 'https://adala.justice.gov.ma'} target="_blank" rel="noreferrer">{t('pages:shelf.onAdala')}</a>
            </p>
          ))}
        </section>
      ) : null}
      <p className="m-0 px-1 text-meta text-ink-soft">{t('pages:situations.notAdvice')}</p>
    </Page>
  );
}

/** A guide's line, then the articles it restates as small doors. */
function Line({ x, lang }: { x: GuideLine; lang: 'ar' | 'fr' }) {
  const { i18n } = useTranslation();
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <p lang={lang} className="m-0 text-body leading-relaxed">{x[lang]}</p>
      {x.paths?.length ? (
        <span className="flex flex-wrap gap-1.5">
          {x.paths.map((p) => (
            <Link key={p} to={p} className="inline-flex rounded-full bg-wash px-2.5 py-0.5 text-meta font-medium no-underline">
              {addressLabel(p, i18n.language)}
            </Link>
          ))}
        </span>
      ) : null}
    </div>
  );
}
