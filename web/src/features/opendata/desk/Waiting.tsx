import { useState } from 'react';
import { chipClass } from '@/shared/components/buttons';
import { num, REQUEST_FILTERS, type Overview, type RequestFilter } from '../desk';
import { useRequests } from '../desk.api';
import { useD } from '../desk.strings';
import { Block, Failed, More } from './bits';
import { useSearch } from './hooks';
import { Search } from './Search';
import { AccessLine, RequestLine } from './rows';
import type { Open } from './types';

/**
 * «ينتظرك»: the requests that wait for an answer, the longest-waiting first, each with the day its answer is due; then,
 * quieter, those waiting for their account's answer; then the accesses that end within 30 days, each with «تجديد». When
 * nothing waits it says so, and the month's figures come first; otherwise they sit under the lists. Every request, in
 * any state, is a fold away.
 */
export function Waiting({ data, open, onOpen }: { data: Overview; open: Open | null; onOpen: (o: Open) => void }) {
  const { t } = useD();
  const is = (kind: Open['kind'], id: number) => open?.kind === kind && open.id === id;
  const none = !data.waiting.length;
  const figures = <Figures data={data} />;
  return (
    <div className="dk-parts">
      <Block title={<>{t('waiting.title')}{data.figures.waiting ? <span className="dk-count">{data.figures.waiting}</span> : null}</>}
             lead={none ? undefined : t('waiting.lead', { days: data.state.answer_days })}>
        {none ? <p className="dk-none">{t('waiting.none')}</p> : (
          <ul className="dk-rows">
            {data.waiting.map((r) => <RequestLine key={r.id} r={r} open={is('request', r.id)} onOpen={() => onOpen({ kind: 'request', id: r.id })} />)}
          </ul>
        )}
        {data.figures.waiting > data.waiting.length ? <p className="dk-small">{t('waiting.shown')}</p> : null}
      </Block>
      {none ? figures : null}
      {data.asked.length ? (
        <Block quiet title={<>{t('waiting.asked')}<span className="dk-count quiet">{data.asked.length}</span></>} lead={t('waiting.askedLead')}>
          <ul className="dk-rows">
            {data.asked.map((r) => <RequestLine key={r.id} quiet r={r} open={is('request', r.id)} onOpen={() => onOpen({ kind: 'request', id: r.id })} />)}
          </ul>
        </Block>
      ) : null}
      {data.ending.length ? (
        <Block title={<>{t('waiting.ending')}<span className="dk-count quiet">{data.figures.ending}</span></>}>
          <ul className="dk-rows">
            {data.ending.map((a) => (
              <AccessLine key={a.id} a={a} open={is('access', a.id)} onOpen={() => onOpen({ kind: 'access', id: a.id })}
                          renew={() => onOpen({ kind: 'access', id: a.id, act: 'renew' })} />
            ))}
          </ul>
        </Block>
      ) : null}
      {none ? null : figures}
      <AllRequests open={open} onOpen={onOpen} />
    </div>
  );
}

/** The month's figures as a ledger: what arrived, what was decided and how fast, what waits, what is held. */
function Figures({ data }: { data: Overview }) {
  const { t, i18n } = useD();
  const lang = i18n.language;
  const f = data.figures;
  const n = (v: number | null) => (v === null ? t('figures.none') : num(v, lang));
  const rows: [string, string][] = [
    ['received', n(f.received)], ['accepted', n(f.accepted)], ['declined', n(f.declined)], ['median', n(f.median_days)],
    ['waiting', n(f.waiting)], ['oldest', n(f.oldest_days)], ['live', n(f.live)], ['keys', n(f.keys)], ['ending', n(f.ending)],
  ];
  return (
    <Block title={t('waiting.figures')}>
      <dl className="dk-figures">
        {rows.map(([k, v]) => <div key={k}><dt>{t(`figures.${k}`)}</dt><dd>{v}</dd></div>)}
      </dl>
    </Block>
  );
}

/** Every request, by state, with a search; a page at a time. Asked for only once it is opened. */
function AllRequests({ open, onOpen }: { open: Open | null; onOpen: (o: Open) => void }) {
  const { t, i18n } = useD();
  const [shown, setShown] = useState(false);
  const [state, setState] = useState<RequestFilter>('all');
  const search = useSearch();
  const q = useRequests(state, search.q, shown);
  const counts = q.data?.pages[0]?.counts;
  const rows = q.data?.pages.flatMap((p) => p.results) ?? [];
  const total = counts ? Object.values(counts).reduce((a, b) => a + b, 0) : null;
  return (
    <details className="dk-fold" onToggle={(e) => setShown((e.target as HTMLDetailsElement).open)}>
      <summary>{t('waiting.all')}</summary>
      <div className="dk-fold-body">
        <p className="dk-lead">{t('waiting.allLead')}</p>
        <div className="dk-filters" role="group" aria-label={t('filters.label')}>
          {REQUEST_FILTERS.map((k) => (
            <button key={k} type="button" aria-pressed={state === k} className={chipClass(state === k)} onClick={() => setState(k)}>
              {t(`filters.requests.${k}`)}
              {counts ? <span className="n">{num(k === 'all' ? total ?? 0 : counts[k], i18n.language)}</span> : null}
            </button>
          ))}
        </div>
        <Search search={search} />
        {q.isError ? <Failed error={q.error} retry={() => void q.refetch()} /> : null}
        {q.isSuccess && !rows.length ? <p className="dk-none">{search.q ? t('filters.nothingFound', { q: search.q }) : t('filters.nothing')}</p> : null}
        {rows.length ? (
          <ul className="dk-rows">
            {rows.map((r) => <RequestLine key={r.id} r={r} open={open?.kind === 'request' && open.id === r.id} onOpen={() => onOpen({ kind: 'request', id: r.id })} />)}
          </ul>
        ) : null}
        <More has={Boolean(q.hasNextPage)} busy={q.isFetchingNextPage} onMore={() => void q.fetchNextPage()} />
      </div>
    </details>
  );
}
