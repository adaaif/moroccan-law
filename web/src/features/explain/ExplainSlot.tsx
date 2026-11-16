import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { longDate } from '@/features/corpus/format';
import '@/shared/locales/pages';
import { firstRegister, useBundle, type Register, type Short } from './explain.api';
import ShareImage from './ShareImage';
import Cites from '@/features/corpus/article/Cites';
import { Note } from '@/shared/components/ui';

/** «باختصار» beside the law (R5, R8 of the for-everyone review): what a text or an article means in plain words, as people
 *  wrote it and a reviewer checked it, in plain Arabic, Darija or French. It never looks like the law: saffron, the
 *  people's font, its date and its history a tap away. One request for the whole text (the bundle). */
export function ExplainText({ path }: { path: string }) {
  const bundle = useBundle(path);
  const text = bundle.data?.text;
  if (!text || !Object.keys(text).length) return null;
  return <Card path={path} registers={text} />;
}

/** Under each article: its «باختصار» when someone explained it, then what answers with it in the topics (HM20 of
 *  the hard-moment review), the people's saffron both. */
export function ExplainArticle({ textPath, eid, path }: { textPath: string; eid: string; path: string }) {
  const bundle = useBundle(textPath);
  const here = bundle.data?.articles[eid];
  return (
    <>
      {here && Object.keys(here.registers).length ? <Card path={path} registers={here.registers} quiet /> : null}
      <Cites textPath={textPath} eid={eid} path={path} />
    </>
  );
}

/** A «باختصار». Under an article it is `quiet` (P5 of the polish review): saffron only as its rule and its label, the
 *  people's 16 px regular, three lines and «اقرأ الشرح كاملا», so it never outshouts the law above it. A text's own
 *  summary keeps its tint, at the top of its page. */
function Card({ path, registers, quiet = false }: { path: string; registers: Partial<Record<Register, Short>>; quiet?: boolean }) {
  const { t, i18n } = useTranslation();
  const first = firstRegister(registers, i18n.language);
  const [chosen, setChosen] = useState<Register | null>(null);
  const [whole, setWhole] = useState(false);
  const register = chosen && registers[chosen] ? chosen : first;
  if (!register) return null;
  const e = registers[register]!;
  const have = (['ar', 'darija', 'fr'] as Register[]).filter((r) => registers[r]);
  const long = e.body.length > 170;
  return (
    <Note tone="people" quiet={quiet} aria-label={t('pages:explain.short')} className={`mt-3 max-w-[64ch] ${quiet ? 'py-1' : ''}`} data-noprint>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <h3 className="m-0 text-body font-bold text-people">{t('pages:explain.short')}</h3>
        {have.length > 1 ? (
          // One control for the three registers (P5): a menu, not three tabs.
          <label className="relative inline-flex min-h-10 items-center">
            <span className="sr-only">{t('pages:explain.registers')}</span>
            <select value={register} onChange={(ev) => setChosen(ev.target.value as Register)}
                    className="h-10 cursor-pointer appearance-none rounded-full bg-transparent pe-3 ps-7 text-meta text-ink-soft hover:text-ink">
              {have.map((r) => <option key={r} value={r}>{t(`pages:explain.register.${r}`)}</option>)}
            </select>
            <svg aria-hidden="true" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"
                 strokeLinecap="round" className="pointer-events-none absolute start-2 text-ink-soft"><path d="m6 9 6 6 6-6" /></svg>
          </label>
        ) : null}
      </div>
      {e.headline ? <p dir="auto" className="m-0 text-body font-semibold leading-snug">{e.headline}</p> : null}
      <p dir={register === 'fr' ? 'ltr' : 'rtl'} lang={register === 'fr' ? 'fr' : 'ar'}
         className={`m-0 text-body leading-[1.75] ${long && !whole ? 'line-clamp-3' : ''}`}>{e.body}</p>
      {long ? (
        <button type="button" onClick={() => setWhole((w) => !w)} aria-expanded={whole}
                className="inline-flex min-h-10 items-center self-start text-meta font-semibold text-stamp hover:text-stamp-deep">
          {whole ? t('pages:explain.less') : t('pages:explain.whole')}
        </button>
      ) : null}
      {e.outdated ? <p className="m-0 rounded-control bg-sheet px-3 py-2 text-meta text-amended">{t('pages:explain.outdated')}</p> : null}
      <p className="m-0 flex flex-wrap items-center gap-x-3 gap-y-0 text-meta text-ink-soft">
        {e.checked_on ? <span>{t('pages:explain.checkedOn', { date: longDate(e.checked_on, i18n.language) })}</span> : null}
        <span>{t('pages:explain.editors', { count: e.editors })}</span>
        {e.helpful ? <span>{t('pages:explain.helpfulCount', { count: e.helpful })}</span> : null}
        <Link to={`/explain${path}`} className="inline-flex min-h-10 items-center font-medium no-underline">{t('pages:explain.more')}</Link>
        <ShareImage path={path} register={register} />
      </p>
      <p className="m-0 text-meta text-ink-soft">{t('pages:explain.notLaw')}</p>
    </Note>
  );
}

