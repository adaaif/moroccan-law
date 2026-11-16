import { useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { AR, longDate } from '@/features/corpus/format';
import { KitPage } from '../../../kit/parts';
import { CHANGES, CHOICES, type Text } from '../choices';
import Cites from '../parts/Cites';
import { useT } from '../strings';

/** A day as the page prints it, or the words as written when they are not a day. */
const when = (s: string, lang: string) => (/^\d{4}-\d{2}-\d{2}$/.test(s) ? longDate(s, lang) : s);

/** «اختيارات الحاسبة» (IR11, IR12 of the inheritance review, 14 Nov 2026): where the family code can be read two ways,
 *  the article's words, what the calculator does, the other reading and who holds it, the sources as printed and since
 *  when; each at its own address («…/choices#bequest») so a result that rests on it can link there. Then the record of
 *  what changed in the calculator (`#changes`). Drawn from choices.ts alone; nothing is fetched. */
export default function ChoicesPage({ slug }: { slug: string }) {
  const { t, i18n } = useT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const say = (x: Text) => x[lang] || x.ar;
  const { hash } = useLocation();
  // The page is drawn after the browser looked for its anchor: go to it once it is there.
  useEffect(() => {
    if (hash) document.getElementById(decodeURIComponent(hash.slice(1)))?.scrollIntoView({ block: 'start' });
  }, [hash]);
  return (
    <KitPage slug={slug} title={t('after.choices.title')} lead={t('after.choices.lead')}>
      <Link to={`/topics/${slug}/tools/inheritance`} className="inline-flex min-h-11 items-center self-start text-body font-medium">
        {t('after.choices.back')}
      </Link>
      <section aria-label={t('after.choices.title')} className="rounded-card bg-sheet px-5 py-2 sm:px-7">
        {CHOICES.length ? (
          <ol className="m-0 flex list-none flex-col p-0">
            {CHOICES.map((ch) => (
              <li key={ch.key} id={ch.key} style={{ scrollMarginTop: 16 }}
                  className="flex flex-col gap-3 border-t border-rule py-5 first:border-t-0">
                <h2 className="m-0 text-lead font-semibold">{say(ch.title)}</h2>
                <blockquote {...AR} className="m-0 border-s-[3px] border-stamp-line ps-4 font-law text-law">{ch.words}</blockquote>
                <Cites cites={ch.cites} />
                <dl className="m-0 flex flex-col gap-3">
                  <div className="flex flex-col gap-0.5">
                    <dt className="text-meta font-semibold text-ink-soft">{t('after.choices.does')}</dt>
                    <dd className="m-0 text-body">{say(ch.does)}</dd>
                  </div>
                  <div className="flex flex-col gap-0.5">
                    <dt className="text-meta font-semibold text-ink-soft">{t('after.choices.other')}</dt>
                    <dd className="m-0 text-body">{say(ch.other)}</dd>
                  </div>
                  {ch.sources.length ? (
                    <div className="flex flex-col gap-0.5">
                      <dt className="text-meta font-semibold text-ink-soft">{t('after.choices.sources')}</dt>
                      <dd className="m-0">
                        <ul className="m-0 flex list-none flex-col gap-1 p-0">
                          {ch.sources.map((s) => <li key={s} dir="auto" className="text-body">{s}</li>)}
                        </ul>
                      </dd>
                    </div>
                  ) : null}
                  {ch.since ? (
                    <div className="flex flex-col gap-0.5">
                      <dt className="text-meta font-semibold text-ink-soft">{t('after.choices.since')}</dt>
                      <dd className="m-0 text-body">{when(ch.since, lang)}</dd>
                    </div>
                  ) : null}
                </dl>
              </li>
            ))}
          </ol>
        ) : <p className="m-0 py-3 text-body text-ink-soft">{t('after.choices.none')}</p>}
      </section>
      <section id="changes" aria-labelledby="changes-title" style={{ scrollMarginTop: 16 }}
               className="flex flex-col gap-2 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <h2 id="changes-title" className="m-0 text-lead font-semibold">{t('after.choices.changes')}</h2>
        {CHANGES.length ? (
          <ol className="m-0 flex list-none flex-col p-0">
            {CHANGES.map((ch) => (
              <li key={`${ch.version}-${ch.on}`} className="flex flex-col gap-0.5 border-t border-rule py-3 first:border-t-0">
                <span className="text-meta text-ink-soft tabular-nums">{t('after.choices.version', { v: ch.version })} · {when(ch.on, lang)}</span>
                <span className="text-body">{say(ch.what)}</span>
              </li>
            ))}
          </ol>
        ) : <p className="m-0 text-body text-ink-soft">{t('after.choices.noChanges')}</p>}
      </section>
    </KitPage>
  );
}
