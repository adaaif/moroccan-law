import { Link } from 'react-router-dom';
import { longDate } from '@/features/corpus/format';
import { pick, refPath, useKitT, type Reform, type Vote } from '../api';
import { hemicycle } from './hemicycle';
import './words';

/** A count as dots, one a voice (or an amendment): those for in the topic's colour, those against in ink, the
 *  abstentions hollow. The same mark at every size: the Chamber's 395 seats, a committee's 40 voices. A chart, so
 *  left to right on an Arabic page too. */
export function Dots({ parts, label }: { parts: [number, number, number]; label?: string }) {
  const kinds = ['f', 'a', 'b'] as const;
  return (
    <span className="dv" dir="ltr" role={label ? 'img' : undefined} aria-label={label} aria-hidden={label ? undefined : true}>
      {parts.flatMap((n, k) => Array.from({ length: n }, (_, i) => <i key={`${k}-${i}`} className={kinds[k]} />))}
    </span>
  );
}

/** A chamber's vote (the Chamber-vote update, 15 Nov 2026; redrawn as a door on 15 Nov): the bill passed through
 *  the Chamber, so its 395 seats are the stones of a horseshoe arch, the site's own shape for a way in. Those who voted
 *  for fill it from the left foot in the topic's colour, those against in ink after them, the seats that did not vote
 *  stay empty; the count stands in the doorway as a score, the way a result is read in Morocco. The dots follow the
 *  count, never the benches: who sat where is not in the record. They fill once, in a sweep, unless motion is reduced. */
export function Chamber({ slug, reform }: { slug: string; reform: Reform }) {
  const { t, i18n } = useKitT();
  const lang = i18n.language;
  const vote = reform.votes?.find((v) => v.seats);
  if (!vote?.seats) return null;
  const before = reform.votes?.find((v) => v !== vote && v.date <= vote.date);
  const { seats, r, height, cx, cy } = hemicycle(vote.seats, 360, 0.5, 0.56);
  const silent = vote.seats - vote.for - vote.against - vote.abstain;
  const kind = (i: number) => (i < vote.for ? 'f' : i < vote.for + vote.against ? 'a' : i < vote.for + vote.against + vote.abstain ? 'b' : 'n');
  const none = t('vote.nobody');
  // The doorway says who voted for and against; under it, the two counts the arch leaves to its empty seats.
  const rows: { key: string; label: string; n: number }[] = [
    { key: 'b', label: t('vote.abstain'), n: vote.abstain },
    { key: 'n', label: t('vote.silent'), n: silent },
  ];
  const am = reform.amendments;
  const sep = lang === 'fr' ? ', ' : '، ';
  return (
    <section className="vt" aria-labelledby="vt-h">
      <div className="vt-words">
        <p className="vt-day"><time dateTime={vote.date}>{longDate(vote.date, lang)}</time>{sep}{pick(vote.body, lang)}</p>
        <h2 id="vt-h" className="vt-h">{pick(vote.headline, lang)}</h2>
      </div>
      {/* A chart reads left to right on an Arabic page too. */}
      <svg className="vt-room" viewBox={`0 0 360 ${height.toFixed(0)}`} role="img"
           aria-label={t('vote.picture', { for: vote.for, against: vote.against, silent, seats: vote.seats })}>
        {seats.map((s, i) => (
          <circle key={i} className={`vt-seat ${kind(i)}`} cx={s.x.toFixed(1)} cy={s.y.toFixed(1)} r={r.toFixed(1)}
                  style={{ '--i': i } as React.CSSProperties} />
        ))}
        {/* The score in the doorway: for on the side its seats fill from. */}
        <text className="vt-n f" x={cx - 43} y={cy + 4} textAnchor="middle">{vote.for}</text>
        <text className="vt-n" x={cx + 43} y={cy + 4} textAnchor="middle">{vote.against}</text>
        <line className="vt-dash" x1={cx - 5} x2={cx + 5} y1={cy - 11} y2={cy - 11} />
        <text className="vt-l" x={cx - 43} y={cy + 25} textAnchor="middle">{t('vote.for')}</text>
        <text className="vt-l" x={cx + 43} y={cy + 25} textAnchor="middle">{t('vote.against')}</text>
        <text className="vt-mid" x={cx} y={cy + 58} textAnchor="middle">{t('vote.voted', { count: vote.for + vote.against + vote.abstain })}</text>
        <text className="vt-l" x={cx} y={cy + 77} textAnchor="middle">{t('vote.ofSeats', { count: vote.seats })}</text>
      </svg>
      <div className="vt-count">
        <ol className="vt-tally">
          {rows.map((row) => (
            <li key={row.key} className={row.key}>
              <span className="vt-key" aria-hidden="true" />
              <span>{row.label}</span>
              {row.n ? <b>{row.n}</b> : <em>{none}</em>}
            </li>
          ))}
        </ol>
        <p className="vt-how">{t('vote.how')}{vote.cites?.length ? <> {vote.cites.map((c) => <Link key={c.path} to={c.path}>{t('vote.cite', { article: c.label, law: pick(c.text, lang) })}</Link>)}</> : null}</p>
      </div>
      <div className="vt-after">
        {vote.note ? <p className="vt-next">{pick(vote.note, lang)}</p> : null}
        {before ? (
          <p className="vt-before">
            <span>{t('vote.before', { date: longDate(before.date, lang), body: pick(before.body, lang), for: before.for, against: before.against })}{before.note ? <> {pick(before.note, lang)}</> : null}</span>
            <Dots parts={[before.for, before.against, before.abstain]} />
          </p>
        ) : null}
        {am ? (
          <p className="vt-am">
            <b>{t('vote.accepted', { count: am.accepted })}</b> {t('vote.ofFiled', { count: am.filed })}{lang === 'fr' ? ' : ' : ': '}
            {(['government', 'majority', 'opposition'] as const).map((side) => t(`vote.side.${side}`, { count: am.groups.filter((g) => g.side === side).reduce((n, g) => n + g.accepted, 0) })).join(sep)}.
            {am.page && am.link ? <> <Link to={refPath(slug, am.page)}>{pick(am.link, lang)}</Link></> : null}
          </p>
        ) : null}
        <p className="vt-src">
          {[vote, before].filter((v): v is Vote => Boolean(v?.source)).map((v) => (
            <a key={v.key} href={v.source!.url} target="_blank" rel="noreferrer">{pick(v.source!.name, lang)}</a>
          ))}
          <span>{t('changes.updated', { date: longDate(reform.checked_on, lang) })}</span>
        </p>
      </div>
    </section>
  );
}

/** The committee's amendments, one dot each (the Chamber-vote update): every amendment filed is a dot beside the
 *  group that filed it — taken into the bill in the topic's colour, rejected in ink, taken back by its authors
 *  hollow — so 59 of 287 is seen before it is read. A chart, so left to right. */
export function Amendments({ reform }: { reform: Reform }) {
  const { t, i18n } = useKitT();
  const lang = i18n.language;
  const am = reform.amendments;
  if (!am?.groups?.length) return null;
  const words = lang === 'fr' ? 'ltr' : 'rtl';
  return (
    <section className="am" aria-labelledby="am-h">
      <h2 id="am-h" className="am-h"><b>{am.accepted}</b> <span>{t('vote.took', { count: am.filed })}</span></h2>
      <ul className="am-groups" dir="ltr">
        {am.groups.map((g) => (
          <li key={g.key}>
            <span className="am-who" dir={words}>{pick(g.label, lang)}</span>
            <span className="am-n" dir={words}><b>{g.accepted}</b> {t('vote.of', { count: g.filed })}</span>
            <Dots parts={[g.accepted, g.rejected, g.withdrawn]} />
          </li>
        ))}
      </ul>
      <p className="am-key" dir="ltr">
        <span dir={words}><i className="am-sw f" aria-hidden="true" />{t('vote.keyTaken')}</span>
        <span dir={words}><i className="am-sw a" aria-hidden="true" />{t('vote.keyRejected')}</span>
        <span dir={words}><i className="am-sw b" aria-hidden="true" />{t('vote.keyWithdrawn')}</span>
      </p>
      {am.note ? <p className="vt-how">{pick(am.note, lang)}</p> : null}
      <p className="vt-src">
        {am.source ? <a href={am.source.url} target="_blank" rel="noreferrer">{pick(am.source.name, lang)}</a> : null}
        <span>{t('changes.updated', { date: longDate(reform.checked_on, lang) })}</span>
      </p>
    </section>
  );
}
