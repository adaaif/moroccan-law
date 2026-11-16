import { Button } from '@/shared/components/ui';
import { refPath } from '../kit/api';
import { KitPage } from '../kit/parts';
import { AnswerCard, SourceFold, SourceMark } from '../kit/tool/parts';
import { useToolState } from '../kit/tool/state';
import { ARTICLES, check, words } from './rules/names';
import { articleLabel, usePapersT } from './strings';

/** «واش هاد السمية مقبولة؟» (the papers review): a first name → the three rules of law 36.21 art. 34 a machine can
 *  read (two names at most, no title, no number), each ticked or named; then what only the officer judges, and the High
 *  Commission when the declarant holds to the name (decree 2.22.04 art. 33). It never says a name is accepted. It waits
 *  for a person's check. The name lives in the address. */
export default function NamesPage({ slug }: { slug: string }) {
  const { t, i18n } = usePapersT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const [s, set] = useToolState({ n: '' });
  const has = words(s.n).length > 0;
  const checks = check(s.n);
  const broken = checks.filter((c) => !c.ok);
  return (
    <KitPage slug={slug} title={t('names.title')} lead={t('names.lead')}>
      <AnswerCard share over={has ? t('names.over', { name: s.n.trim() }) : t('names.startOver')}
                  value={!has ? t('names.start') : broken.length ? t('names.broken', { count: broken.length }) : t('names.clear')}
                  tone={has && broken.length ? 'warn' : 'stamp'}
                  under={has ? <p className="m-0">{broken.length ? t('names.brokenUnder') : t('names.clearUnder')}</p> : null} />

      <section className="flex flex-col gap-4 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <label className="flex flex-col gap-1.5">
          <span className="text-body font-semibold">{t('names.field')}</span>
          <input type="text" dir="auto" value={s.n} onChange={(e) => set({ n: e.target.value })} placeholder={t('names.placeholder')}
                 className="h-12 w-full max-w-md rounded-control border border-field bg-sheet px-3 text-lead" />
        </label>
        <ul className="m-0 flex list-none flex-col gap-2 p-0">
          {checks.map((c) => (
            <li key={c.key} className="flex items-start gap-3">
              <span aria-hidden="true" className={`mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full text-meta font-bold ${!has ? 'border border-field text-ink-soft' : c.ok ? 'bg-in-force text-sheet' : 'bg-sign-red text-on-sign'}`}>
                {!has ? '' : c.ok ? '✓' : '✗'}
              </span>
              <span className="text-body">
                {t(`names.rules.${c.key}`)}
                {has && !c.ok ? <span className="block text-meta text-ink-soft">{t(`names.found.${c.key}`, { found: c.found })}</span> : null}
              </span>
            </li>
          ))}
        </ul>
        <p className="m-0 text-meta text-ink-soft">{t('names.rulesFrom')} <SourceMark path={ARTICLES.rules} label={articleLabel(ARTICLES.rules)} /></p>
      </section>

      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <h2 className="m-0 text-h3 font-bold">{t('names.officerTitle')}</h2>
        <ul className="m-0 flex list-none flex-col gap-1.5 p-0">
          {(['morals', 'family', 'ridicule', 'place'] as const).map((k) => <li key={k} className="text-body">• {t(`names.officer.${k}`)}</li>)}
        </ul>
        <p className="m-0 text-body">{t('names.commission')} <SourceMark path={ARTICLES.commission} label={articleLabel(ARTICLES.commission)} /></p>
        <p className="m-0 text-body">{t('names.scripts')} <SourceMark path={ARTICLES.scripts} label={articleLabel(ARTICLES.scripts)} /></p>
        <SourceFold paths={[ARTICLES.rules, ARTICLES.commission, ARTICLES.scripts]} label={articleLabel} />
        <div className="flex flex-wrap gap-2">
          <Button to={refPath(slug, 'family:journeys/birth')}>{t('names.toBirth')}</Button>
          <Button variant="quiet" to={refPath(slug, 'journeys/name')}>{t('names.toChange')}</Button>
        </div>
      </section>
      <p lang={lang} className="m-0 text-meta text-ink-soft">{t('names.never')}</p>
    </KitPage>
  );
}
