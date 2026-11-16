import { Fragment } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Stamp } from '@/features/corpus/article/Stamp';
import { AR, articleName } from '@/features/corpus/format';
import { textName } from '@/features/corpus/names';
import type { FamousCard as Card, SearchResponse } from './search.api';

/** The public's names for an article in the reader's language, the Arabic ones when it has none in French. */
function knownNames(known: { ar: string[]; fr: string[] } | null | undefined, lang: string): string[] {
  if (!known) return [];
  return lang === 'fr' && known.fr.length ? known.fr : known.ar;
}

/** «العلاقات الرضائية» و«وكالين رمضان», each quoted, in the page's language. */
function Names({ names }: { names: string[] }) {
  const { t } = useTranslation();
  return (
    <>
      {names.map((n, i) => (
        <Fragment key={n}>
          {i ? t('pages:famous.and') : null}
          <bdi dir="auto" className="font-semibold">«{n}»</bdi>
        </Fragment>
      ))}
    </>
  );
}

/** An article people know by its number or by a name (F5, F8 of the famous-articles review, 9 Nov 2026): shown first, in the law's
 *  own words, with where the Bulletin printed it, the name the public debate gives it said as such (C3), never an opinion
 *  or a «controversial» badge; then what changed it, any bill that would (a proposal, never law), and the articles that
 *  cite it, read from the law's words (F9). */
export function FamousCard({ c, onOpen }: { c: Card; onOpen: () => void }) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const names = knownNames(c.known_as, lang);
  const french = lang === 'fr' ? c.french : null;
  const consolidated = !!c.text?.consolidation && c.text.consolidation !== 'as_published';
  const id = `famous-${c.code}-${c.number}`;
  return (
    <section aria-labelledby={id} className="flex flex-col gap-3 rounded-control border-2 border-stamp bg-sheet px-5 py-4 sm:px-6">
      <h2 id={id} className="m-0 flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <bdi {...AR} className="font-law text-h2 font-semibold leading-snug text-ink">{articleName(c.label, t)}</bdi>
        {c.text ? <span className="text-body text-ink-soft">{t('pages:famous.of', { name: textName(c.text, lang, 90) })}</span> : null}
      </h2>
      {names.length ? (
        <p className="m-0 text-body text-ink">{t('pages:famous.knownAs')} <Names names={names} /></p>
      ) : null}
      {french ? (
        <blockquote lang="fr" className="m-0 max-w-[66ch] font-law-fr text-law leading-[1.7] text-ink">{french.body}</blockquote>
      ) : (
        <blockquote {...AR} className="m-0 max-w-[66ch] whitespace-pre-line font-law text-law leading-[1.8] text-ink">{c.body}</blockquote>
      )}
      <p className="m-0 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-meta text-ink-soft">
        {consolidated ? <Stamp line consolidated /> : c.page ? <Stamp line page={c.page} /> : c.text?.issue ? <Stamp line issue={c.text.issue} /> : null}
        {french ? <span>{t('pages:famous.frenchNote')}</span> : null}
      </p>
      {c.changes.length ? (
        <p className="m-0 text-meta text-ink-soft">
          {t('pages:famous.changed')}{' '}
          {c.changes.map((x, i) => (
            <Fragment key={`${x.by?.path ?? ''}${x.issue ?? i}`}>
              {i ? t('corpus.listSep') : null}
              {/* By kind and number («قانون 15.14»): an amending law's title runs to two lines. */}
              {x.by ? <Link to={x.by.path} className="font-medium">{x.by.number_as_printed ? `${t(`corpus.types.${x.by.type}`)} ${x.by.number_as_printed}` : textName(x.by, lang, 40)}</Link> : null}
              {x.issue || x.published ? <span>{' '}({[x.published?.slice(0, 4), x.issue ? t('stamp.issue', { number: x.issue }) : '', x.page ? t('stamp.page', { page: x.page }) : ''].filter(Boolean).join(t('corpus.listSep'))})</span> : null}
            </Fragment>
          ))}
        </p>
      ) : null}
      {c.proposed.length ? (
        <p className="m-0 text-meta text-amended">
          {t('pages:famous.proposed')}{' '}
          {c.proposed.map((x, i) => x.by ? <Fragment key={x.by.path}>{i ? t('corpus.listSep') : null}<Link to={x.by.path} className="font-medium text-amended">{textName(x.by, lang, 50)}</Link></Fragment> : null)}
        </p>
      ) : null}
      {c.cited_by.length ? (
        <p className="m-0 text-meta text-ink-soft">
          {t('pages:famous.citedBy')}{' '}
          {c.cited_by.map((x, i) => (
            <Fragment key={x.path}>
              {i ? t('corpus.listSep') : null}
              <Link to={x.path} className="font-medium"><bdi {...AR}>{articleName(x.label, t)}</bdi></Link>
              {x.text ? <span>{' '}{t('pages:famous.of', { name: textName(x.text, lang, 40) })}</span> : null}
            </Fragment>
          ))}
          {c.cited_more ? <span>{t('corpus.listSep')}{t('pages:famous.citedMore', { count: c.cited_more })}</span> : null}
        </p>
      ) : null}
      <div>
        <Link to={c.path} onClick={onOpen}
              className="inline-flex min-h-11 items-center rounded-control bg-stamp px-5 font-medium text-on-stamp no-underline hover:bg-stamp-deep hover:text-on-stamp">
          {t('pages:famous.read', { label: articleName(c.label, t) })}
        </Link>
      </div>
    </section>
  );
}

/** «490 في نصوص أخرى» (F3, F5): the shelf's other codes with an article of that number, a tap each. Alone, without a
 *  card, it answers «الفصل 1234»: which code? */
export function Choices({ ch, alone }: { ch: NonNullable<SearchResponse['choices']>; alone: boolean }) {
  const { t, i18n } = useTranslation();
  if (!ch.texts.length) return null;
  return (
    <nav aria-label={t(alone ? 'pages:famous.whichCode' : 'pages:famous.elsewhere', { number: ch.number })} className="flex flex-col gap-2">
      <p className="m-0 text-meta font-semibold text-ink-soft">{t(alone ? 'pages:famous.whichCode' : 'pages:famous.elsewhere', { number: ch.number })}</p>
      <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
        {ch.texts.map((x) => (
          <li key={x.path}>
            {/* The code's name alone, its article's label for a screen reader and a pointer: two chips to a phone's row. */}
            <Link to={x.path} title={x.label} aria-label={`${x.label} — ${textName(x.text, i18n.language, 80)}`}
                  className="inline-flex min-h-11 items-center rounded-full border border-rule bg-sheet px-4 text-body text-ink no-underline hover:border-stamp hover:text-stamp">
              {textName(x.text, i18n.language, 40)}
            </Link>
          </li>
        ))}
        {ch.more ? <li className="inline-flex min-h-11 items-center px-1 text-meta text-ink-soft">{t('pages:famous.moreCodes', { count: ch.more })}</li> : null}
      </ul>
    </nav>
  );
}

/** A word the law uses that everyday speech reads otherwise (F6): «الفساد» is corruption to most, and art. 490's name in
 *  the penal code. Both are offered: this line, then the texts the word finds. */
export function Maybe({ m }: { m: NonNullable<SearchResponse['maybe']>[number] }) {
  const { t, i18n } = useTranslation();
  return (
    <p className="m-0 rounded-control bg-wash px-5 py-3 text-body">
      {t('pages:famous.maybe')}{' '}
      <Link to={m.path} className="font-semibold"><bdi {...AR}>{articleName(m.label, t)}</bdi></Link>
      {m.text ? <span>{' '}{t('pages:famous.of', { name: textName(m.text, i18n.language, 60) })}</span> : null}
      {t('pages:famous.maybeEnd')}
    </p>
  );
}
