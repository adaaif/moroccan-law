import { useState } from 'react';
import { chipClass } from '@/shared/components/buttons';
import { LinesSkeleton } from '@/shared/components/ui';
import { ACCESS_FILTERS, bytes, dateOf, doorName, eventLine, momentOf, num, type AccessFilter, type DeskEvent } from '../desk';
import { useAccesses, useEditions, useLog, useUse } from '../desk.api';
import { useD } from '../desk.strings';
import { Bars, Block, Copy, DayNumbers, DoorList, Failed, More } from './bits';
import { AccessLine } from './rows';
import { useSearch } from './hooks';
import { Search } from './Search';
import type { Open } from './types';

type Opens = { open: Open | null; onOpen: (o: Open) => void };

/** «الوصولات»: the ledger of accesses, live, ending, ended or never used, with a search box; a page at a time. */
export function Accesses({ open, onOpen }: Opens) {
  const { t, i18n } = useD();
  const [state, setState] = useState<AccessFilter>('live');
  const search = useSearch();
  const q = useAccesses(state, search.q);
  const counts = q.data?.pages[0]?.counts;
  const rows = q.data?.pages.flatMap((p) => p.results) ?? [];
  return (
    <Block title={t('accesses.title')}>
      <div className="dk-filters" role="group" aria-label={t('filters.label')}>
        {ACCESS_FILTERS.map((k) => (
          <button key={k} type="button" aria-pressed={state === k} className={chipClass(state === k)} onClick={() => setState(k)}>
            {t(`filters.accesses.${k}`)}
            {counts && k !== 'all' ? <span className="n">{num(counts[k], i18n.language)}</span> : null}
          </button>
        ))}
      </div>
      <Search search={search} />
      {q.isPending ? <LinesSkeleton lines={4} /> : null}
      {q.isError ? <Failed error={q.error} retry={() => void q.refetch()} /> : null}
      {q.isSuccess && !rows.length ? <p className="dk-none">{search.q ? t('filters.nothingFound', { q: search.q }) : t('filters.nothing')}</p> : null}
      {rows.length ? (
        <ul className="dk-rows">
          {rows.map((a) => <AccessLine key={a.id} a={a} open={open?.kind === 'access' && open.id === a.id} onOpen={() => onOpen({ kind: 'access', id: a.id })} />)}
        </ul>
      ) : null}
      <More has={Boolean(q.hasNextPage)} busy={q.isFetchingNextPage} onMore={() => void q.fetchNextPage()} />
    </Block>
  );
}

/** «الاستعمال»: calls and articles a day for 30 days, calls by door, the five busiest accesses, who reached a limit
 *  today. Never what was asked. */
export function UsePart({ onOpen }: Opens) {
  const { t, i18n } = useD();
  const lang = i18n.language;
  const q = useUse();
  if (q.isPending) return <LinesSkeleton lines={6} />;
  if (q.isError) return <Failed error={q.error} retry={() => void q.refetch()} />;
  const u = q.data;
  const limited = u.limited_today;
  return (
    <div className="dk-parts">
      <Block title={t('use.title')} lead={u.totals.calls ? t('use.totals', { calls: num(u.totals.calls, lang), articles: num(u.totals.articles, lang),
                                                                         accesses: num(u.totals.accesses, lang) }) : undefined}>
        {u.days.length ? (
          <div className="dk-charts">
            <Bars days={u.days} field="calls" title={t('use.calls')} />
            <Bars days={u.days} field="articles" title={t('use.articles')} />
          </div>
        ) : <p className="dk-none">{t('use.nothing')}</p>}
        <DayNumbers days={u.days} />
      </Block>
      {Object.keys(u.doors).length ? (
        <Block title={t('use.doors')} lead={t('use.doorsLead')}>
          <DoorList doors={u.doors} name={(door) => doorName(t, door)} />
        </Block>
      ) : null}
      {u.busiest.length ? (
        <Block title={t('use.busiest')}>
          <ul className="dk-rows">
            {u.busiest.map((b) => (
              <li key={b.access}>
                <button type="button" className="dk-row" onClick={() => onOpen({ kind: 'access', id: b.access })}>
                  <span className="who"><b><bdi>{b.name || t('log.noName')}</bdi></b>
                    <small>{t('use.busyLine', { calls: num(b.calls, lang), articles: num(b.articles, lang) })}</small></span>
                </button>
              </li>
            ))}
          </ul>
        </Block>
      ) : null}
      <Block title={t('use.limited')}>
        {limited.length ? (
          <ul className="dk-rows">
            {limited.map((l) => (
              <li key={l.access}>
                <button type="button" className="dk-row" onClick={() => onOpen({ kind: 'access', id: l.access })}>
                  <span className="who"><b><bdi>{l.name || t('log.noName')}</bdi></b>
                    <small>{Object.entries(l.limits).filter(([, n]) => n).map(([k, n]) => t(`use.limits.${k}`, { n: num(n ?? 0, lang) })).join(' · ')}</small></span>
                </button>
              </li>
            ))}
          </ul>
        ) : <p className="dk-none">{t('use.limitedNone')}</p>}
      </Block>
    </div>
  );
}

/** «النسخ»: each edition with its date, counts, size and hash; whether it is still on the server; how many times each
 *  file left and to whom; the day the next is built. */
export function EditionsPart({ onOpen }: Opens) {
  const { t, i18n } = useD();
  const lang = i18n.language;
  const q = useEditions();
  if (q.isPending) return <LinesSkeleton lines={6} />;
  if (q.isError) return <Failed error={q.error} retry={() => void q.refetch()} />;
  const e = q.data;
  return (
    <div className="dk-parts">
      <Block title={t('editions.title')} lead={t('editions.next', { date: dateOf(e.next_on, lang) })}>
        {e.editions.length ? null : <p className="dk-none">{t('editions.none')}</p>}
      </Block>
      {e.editions.map((ed) => (
        <Block key={`${ed.date}-${ed.sha256}`} title={t('editions.edition', { date: dateOf(ed.date, lang) })}
               more={<span className={`dk-tag ${ed.on_disk ? 'ok' : ''}`}>{t(ed.on_disk ? 'editions.onDisk' : 'editions.gone')}</span>}>
          <dl className="dk-figures">
            {(['texts', 'articles', 'versions'] as const).map((k) => (
              <div key={k}><dt>{t(`editions.${k}`)}</dt><dd>{ed[k] === null ? '—' : num(ed[k] ?? 0, lang)}</dd></div>
            ))}
            {ed.bytes !== null ? <div><dt>{t('editions.size')}</dt><dd>{bytes(ed.bytes)}</dd></div> : null}
          </dl>
          <div className="dk-hash">
            <span>{t('editions.hash')}</span>
            <code dir="ltr">{ed.sha256}</code>
            <Copy text={ed.sha256} />
          </div>
          {ed.files.length ? (
            <table className="dk-table">
              <caption>{t('editions.files')}</caption>
              <thead><tr><th scope="col">{t('editions.file')}</th><th scope="col">{t('editions.size')}</th><th scope="col">{t('editions.taken')}</th></tr></thead>
              <tbody>
                {ed.files.map((f) => (
                  <tr key={f.name}><th scope="row"><code dir="ltr">{f.name}</code></th><td>{bytes(f.bytes)}</td><td>{num(f.taken, lang)}</td></tr>
                ))}
              </tbody>
            </table>
          ) : null}
          <h3 className="dk-sub">{t('editions.downloads')}</h3>
          {ed.downloads.length ? (
            <ul className="dk-rows">
              {ed.downloads.map((d, i) => (
                <li key={`${d.at}-${i}`}>
                  <button type="button" className="dk-row" onClick={() => onOpen({ kind: 'access', id: d.access })}>
                    <span className="who"><b><bdi>{d.name || t('log.noName')}</bdi></b>
                      <small><code dir="ltr">{d.file}</code> · {momentOf(d.at, lang)} · {t(d.by === 'key' ? 'editions.byKey' : 'editions.byAccount')}</small></span>
                  </button>
                </li>
              ))}
            </ul>
          ) : <p className="dk-small">{t('editions.noDownloads')}</p>}
        </Block>
      ))}
    </div>
  );
}

/** The acts that concern an access more than its request open the access; the others, the request. */
const ON_ACCESS = new Set<DeskEvent['act']>(['changed', 'renewed', 'ended', 'key_made', 'key_ended']);

/** «السجل»: every act, the newest first, a sentence each, a page at a time. */
export function LogPart({ onOpen }: Opens) {
  const { t, i18n } = useD();
  const lang = i18n.language;
  const q = useLog();
  const rows = q.data?.pages.flatMap((p) => p.results) ?? [];
  return (
    <Block title={t('log.title')} lead={t('log.lead')}>
      {q.isPending ? <LinesSkeleton lines={6} /> : null}
      {q.isError ? <Failed error={q.error} retry={() => void q.refetch()} /> : null}
      {q.isSuccess && !rows.length ? <p className="dk-none">{t('log.none')}</p> : null}
      {rows.length ? (
        <ol className="dk-rows dk-log">
          {rows.map((e, i) => {
            const target: Open | null = e.access && (ON_ACCESS.has(e.act) || !e.request) ? { kind: 'access', id: e.access }
              : e.request ? { kind: 'request', id: e.request } : null;
            const inner = (
              <span className="who">
                <span>{eventLine(t, e, lang)}</span>
                <small><time dateTime={e.at}>{momentOf(e.at, lang)}</time>{e.by ? <> · <bdi dir="ltr">@{e.by}</bdi></> : null}</small>
              </span>
            );
            return (
              <li key={`${e.at}-${i}`}>
                {target ? <button type="button" className="dk-row" onClick={() => onOpen(target)}>{inner}</button> : <div className="dk-row">{inner}</div>}
              </li>
            );
          })}
        </ol>
      ) : null}
      <More has={Boolean(q.hasNextPage)} busy={q.isFetchingNextPage} onMore={() => void q.fetchNextPage()} />
    </Block>
  );
}
