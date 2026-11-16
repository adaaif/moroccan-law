import { Button } from '@/shared/components/ui';
import { todayIso } from '@/shared/services/today';
import { refPath } from '../kit/api';
import { KitPage } from '../kit/parts';
import { AnswerCard, Chips, SourceFold } from '../kit/tool/parts';
import { dayWords } from '../kit/tool/days';
import { useToolState } from '../kit/tool/state';
import { DateField } from '../papers/parts';
import { AFTER, FROM_DEATH, KINDS, PATHS, term, type Kind } from './rules/copyright';
import { Sheet } from './parts';
import { articleLabel, useDigitalT } from './strings';

/** «واش هاد العمل مازال محمي؟» (the digital review): the kind of work and the author's death or the year of first
 *  publication → the last day of protection and the first it is free, on one bar from that day to the end of the term with
 *  today on it; and that commercial use still needs the copyright office's licence (2.00 arts 25–29, 7-1). It waits for
 *  a person's check. The inputs live in the address. */
export default function CopyrightPage({ slug }: { slug: string }) {
  const { t, i18n } = useDigitalT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const today = todayIso();
  const [s, set] = useToolState({ k: 'author', d: '1960-01-01', y: '1960' });
  const kind = (KINDS.includes(s.k as Kind) ? s.k : 'author') as Kind;
  const death = FROM_DEATH[kind];
  const from = death ? s.d : String(Math.max(1900, Math.min(Number(today.slice(0, 4)), Number(s.y) || 1960)));
  const r = term(kind, from);
  const open = today <= r.until;
  const start = death ? from : `${from}-01-01`;
  const span = (new Date(r.until).getTime() - new Date(start).getTime()) || 1;
  const share = Math.min(1, Math.max(0, (new Date(today).getTime() - new Date(start).getTime()) / span));
  return (
    <KitPage slug={slug} title={t('copyright.title')} lead={t('copyright.lead')}>
      <AnswerCard share over={t(open ? 'copyright.overOpen' : 'copyright.overFree')} tone={open ? 'stamp' : 'good'}
                  value={dayWords(open ? r.until : r.free, lang)}
                  under={<p className="m-0">{open ? t('copyright.freeFrom', { date: dayWords(r.free, lang) }) : t('copyright.after')}</p>}>
        <div className="flex flex-col gap-1 pt-2" aria-hidden="true">
          <div className="relative h-3 overflow-hidden rounded-full bg-rule">
            <div className="absolute inset-y-0 start-0 bg-[var(--t)] transition-[width] duration-500 motion-reduce:transition-none" style={{ width: `${share * 100}%` }} />
          </div>
          <div className="flex justify-between text-meta text-ink-soft">
            <span>{death ? dayWords(start, lang, true) : from}</span>
            <span className="font-semibold text-ink">{r.until.slice(0, 4)}</span>
          </div>
        </div>
      </AnswerCard>
      <Sheet>
        <Chips label={t('copyright.which')} value={kind} onChange={(k) => set({ k })}
               options={KINDS.map((k) => ({ key: k, label: t(`copyright.kinds.${k}`) }))} />
        {death ? (
          <DateField label={t(kind === 'joint' ? 'copyright.lastDeath' : 'copyright.death')} value={s.d} onChange={(d) => set({ d })} lang={lang} />
        ) : (
          <label className="flex flex-col gap-1.5">
            <span className="text-body font-semibold">{t('copyright.published')}</span>
            <input type="number" inputMode="numeric" min={1900} max={Number(today.slice(0, 4))} value={s.y} dir="ltr"
                   onChange={(e) => set({ y: e.target.value })} className="h-12 w-32 rounded-control border border-field bg-sheet px-3 text-body tabular-nums" />
          </label>
        )}
      </Sheet>
      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <p className="m-0 text-body">{t(`copyright.rule.${kind}`)}</p>
        <p className="m-0 text-body">{t('copyright.commercial')}</p>
        <p className="m-0 text-body text-ink-soft">{t('copyright.moral')}</p>
        <SourceFold paths={[PATHS[kind], AFTER, '/ma/loi/2-00/art_25']} label={articleLabel} />
        <div className="flex flex-wrap gap-2">
          <Button to={refPath(slug, 'pages/copyright')}>{t('copyright.toPage')}</Button>
          <Button variant="quiet" to={refPath(slug, 'journeys/copyright')}>{t('copyright.toJourney')}</Button>
        </div>
      </section>
    </KitPage>
  );
}
