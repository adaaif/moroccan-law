import { Button } from '@/shared/components/ui';
import { KitPage } from '../kit/parts';
import { whatsapp, here } from '../kit/share';
import { Chips, SourceMark } from '../kit/tool/parts';
import { useToolState } from '../kit/tool/state';
import { BRING, DOORS, SECTORS, type Sector } from './rules/where';
import { articleLabel, useConsumerT } from './strings';

/** «شكون نشكي ليه؟» (T5 of the consumer plan): the sector → the doors in order, the supplier first, each with
 *  its official service where an official page gives one and the article it rests on, and what to bring. */
export default function WherePage({ slug }: { slug: string }) {
  const { t } = useConsumerT();
  const [s, set] = useToolState({ s: 'shop' });
  const sector = (SECTORS.includes(s.s as Sector) ? s.s : 'shop') as Sector;
  const doors = DOORS[sector];
  const message = [t('where.message', { sector: t(`where.sectors.${sector}`) }),
    ...doors.map((d, i) => `${i + 1}. ${t(`where.doors.${d.key}.title`)}${d.url ? ` — ${d.url}` : ''}`), here()].join('\n');
  return (
    <KitPage slug={slug} title={t('where.title')} lead={t('where.lead')}>
      <section className="flex flex-col gap-4 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <Chips label={t('where.sector')} value={sector} onChange={(v) => set({ s: v })}
               options={SECTORS.map((x) => ({ key: x, label: t(`where.sectors.${x}`) }))} />
      </section>
      <ol className="m-0 flex list-none flex-col gap-3 p-0" aria-live="polite">
        {doors.map((d, i) => (
          <li key={`${sector}-${d.key}`} style={{ animationDelay: `${i * 60}ms` }}
              className="flex gap-4 rounded-card bg-sheet px-5 py-4 motion-safe:animate-[rise_220ms_ease-out_both] sm:px-7">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-[var(--t)] text-body font-bold text-sheet">{i + 1}</span>
            <div className="flex min-w-0 flex-1 flex-col gap-2">
              <h2 className="m-0 text-lead font-semibold">{t(`where.doors.${d.key}.title`)}</h2>
              <p className="m-0 text-body">{t(`where.doors.${d.key}.what`)}</p>
              {d.cites?.length ? <span className="flex flex-wrap gap-1.5">{d.cites.map((p) => <SourceMark key={p} path={p} label={articleLabel(p)} />)}</span> : null}
              {d.url ? <Button href={d.url} target="_blank" rel="noreferrer" className="self-start">{t(`where.doors.${d.key}.link`, { defaultValue: t('where.open') })} ↗</Button> : null}
            </div>
          </li>
        ))}
      </ol>
      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <h2 className="m-0 text-lead font-semibold">{t('where.bring')}</h2>
        <ul className="m-0 flex flex-col gap-1.5 ps-5">
          {BRING[sector].map((b) => <li key={b} className="text-body">{t(`where.papers.${b}`)}</li>)}
        </ul>
        <p className="m-0 text-meta text-ink-soft">{t('where.practice')}</p>
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => whatsapp(message)}>{t('share')}</Button>
          <Button to={`/topics/${slug}/pages/where`}>{t('where.toPage')}</Button>
        </div>
      </section>
    </KitPage>
  );
}
