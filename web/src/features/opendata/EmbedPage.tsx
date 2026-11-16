import { useTranslation } from 'react-i18next';
import { useLocation } from 'react-router-dom';
import { useTextAt } from '@/features/corpus/corpus.api';
import { AR, articleName, splitAddress } from '@/features/corpus/format';
import { LawBody } from '@/features/corpus/LawBody';

/** /embed/ma/…/art_6: one article for another site's page (an iframe) — its words, its reference, a link to
 *  the whole text on the site. No header, no tools; links open the site in a new tab. */
export default function EmbedPage() {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const { textPath, focus } = splitAddress(pathname.replace(/^\/embed/, ''));
  const text = useTextAt(textPath, focus);
  const d = text.data;
  const a = d?.articles.find((x) => x.eid === focus) ?? d?.articles[0];
  return (
    <main className="flex min-h-screen flex-col gap-3 bg-sheet p-5 text-ink">
      {!d ? (
        <p className="m-0 text-ink-soft">{text.isError ? t('corpus.notFound') : t('corpus.loading')}</p>
      ) : (
        <>
          <p {...AR} className="m-0 text-meta text-ink-soft">{d.title}</p>
          {a ? (
            <>
              <h1 {...AR} className="m-0 font-law text-h2 font-semibold">{articleName(a.label, t)}</h1>
              <LawBody text={a.body} className="max-w-[70ch] font-law text-law leading-relaxed" />
              <p {...AR} className="m-0 text-meta text-ink-soft">{a.citation}</p>
            </>
          ) : null}
          <a href={`${window.location.origin}${a?.path ?? d.path}`} target="_blank" rel="noopener"
             className="mt-auto self-start font-medium">{t('data.readOnSite')}</a>
        </>
      )}
    </main>
  );
}
