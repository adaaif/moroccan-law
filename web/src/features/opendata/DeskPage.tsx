import { Link, useSearchParams } from 'react-router-dom';
import { useState } from 'react';
import { useMe } from '@/features/accounts/accounts.service';
import NotFound from '@/features/corpus/NotFound';
import { useNoIndex } from '@/features/discussion/noindex';
import { Page, PageSkeleton } from '@/shared/components/ui';
import { usePageTitle } from '@/shared/services/title';
import { dateOf, iso, partOf, PARTS, type Overview, type Part } from './desk';
import { useOverview } from './desk.api';
import { useD } from './desk.strings';
import { AccessSheetView } from './desk/AccessSheet';
import { Failed, Holder } from './desk/bits';
import { useWide } from './desk/hooks';
import { Accesses, EditionsPart, LogPart, UsePart } from './desk/Parts';
import { RequestSheetView } from './desk/RequestSheet';
import type { Open } from './desk/types';
import { Waiting } from './desk/Waiting';
import '@/features/corpus/library.css';
import './desk.css';

/**
 * «إدارة الوصول» (/data/desk), for an account the server lets in (`me.desk`): one line on how the programme stands, then
 * five parts that are addresses (`?part=`): what waits, the accesses, their use, the editions, the log. A request or an
 * access opens as a sheet: beside the list on a desk, from the bottom on a phone; the back button closes it. Anyone
 * else is shown the page an unknown address shows, and the server refuses them anyway.
 */
export default function DeskPage() {
  const me = useMe();
  if (!me.data) return <Page width="wide"><PageSkeleton /></Page>;
  if (!me.data.desk) return <NotFound />;
  return <Desk />;
}

function Desk() {
  const { t } = useD();
  usePageTitle([t('title')]);
  useNoIndex();
  const [params] = useSearchParams();
  const part = partOf(params.get('part'));
  const overview = useOverview();
  const wide = useWide();
  // What is open belongs to the part it was opened from: another part (a tab, or the back button) closes it.
  const [opened, setOpened] = useState<(Open & { part: Part }) | null>(null);
  if (opened && opened.part !== part) setOpened(null);
  const open = opened && opened.part === part ? opened : null;
  const onOpen = (o: Open) => setOpened({ ...o, part });
  const close = () => setOpened(null);
  const programme = overview.data?.state;
  const sheet = open ? (open.kind === 'request'
    ? <RequestSheetView id={open.id} programme={programme} onClose={close} onAccess={(id) => onOpen({ kind: 'access', id })} />
    : <AccessSheetView id={open.id} start={open.act} programme={programme} onClose={close} />) : null;
  return (
    <Page width="wide" className="lb dk">
      <header className="lb-head dk-head">
        <div>
          <h1>{t('title')}</h1>
          {overview.data ? <Strip data={overview.data} /> : <p className="dk-strip" aria-hidden="true">&nbsp;</p>}
        </div>
      </header>
      <nav className="dk-tabs" aria-label={t('parts.label')}>
        {PARTS.map((p) => (
          <Link key={p} to={{ pathname: '/data/desk', search: p === 'waiting' ? '' : `?part=${p}` }} aria-current={p === part ? 'page' : undefined}
                onClick={() => setOpened(null)}>
            {t(`parts.${p}`)}
            {p === 'waiting' && overview.data?.figures.waiting ? <span className="n">{overview.data.figures.waiting}</span> : null}
          </Link>
        ))}
      </nav>
      <div className={`dk-room ${open && wide ? 'open' : ''}`}>
        <div className="dk-list">
          {part === 'waiting' ? (
            overview.isPending ? <PageSkeleton /> : overview.isError ? <Failed error={overview.error} retry={() => void overview.refetch()} />
              : <Waiting data={overview.data} open={open} onOpen={onOpen} />
          ) : part === 'accesses' ? <Accesses open={open} onOpen={onOpen} />
            : part === 'use' ? <UsePart open={open} onOpen={onOpen} />
              : part === 'editions' ? <EditionsPart open={open} onOpen={onOpen} />
                : <LogPart open={open} onOpen={onOpen} />}
        </div>
        {sheet ? (
          <Holder wide={wide} label={t(open?.kind === 'request' ? 'sheet.requestLabel' : 'sheet.accessLabel')} onClose={close}>
            {sheet}
          </Holder>
        ) : null}
      </div>
    </Page>
  );
}

/** How the programme stands, in one line: whether requests are open, where the staff's letters go, the terms' date, the
 *  newest edition and the day of the next. It only says; nothing is changed here. */
function Strip({ data }: { data: Overview }) {
  const { t, i18n } = useD();
  const lang = i18n.language;
  const s = data.state;
  return (
    <p className="dk-strip dk-dots" aria-label={t('strip.label')}>
      <span>
        <span className={s.position === 'request' ? 'on' : 'warn'}>{t(`strip.position.${s.position}`)}</span>
        <span className={s.letter_to.length ? '' : 'warn'}>
          {s.letter_to.length ? t('strip.letterTo', { to: s.letter_to.map(iso).join(lang === 'fr' ? ', ' : '، ') }) : t('strip.noLetter')}
        </span>
        <span>{t('strip.terms', { date: dateOf(s.terms, lang) })}</span>
        <span>{s.edition ? t('strip.edition', { date: dateOf(s.edition.date, lang) }) : t('strip.noEdition')}</span>
        <span>{t('strip.next', { date: dateOf(s.next_edition_on, lang) })}</span>
      </span>
    </p>
  );
}
