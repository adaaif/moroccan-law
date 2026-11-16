import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { topicColour } from '@/features/topics/colour';
import { TopicIcon } from '@/features/topics/TopicIcon';
import { api } from '@/shared/services/api';
import { todayIso } from '@/shared/services/today';
import '@/shared/locales/pages';
import './home.css';

type Both = { ar: string; fr: string };
type Change = { date: string; label: Both; topic: { slug: string; name: Both }; change: string; path: string; text: string | null;
                stage: string; line?: Both | null };
type Calendar = { today: string; ahead: Change[]; behind: Change[] };
/** A new text an editor told under a plain headline (R13 of the for-everyone review). */
type Told = { path: string; headline: string; summary: string; registers?: Record<string, { headline: string; summary: string }>;
              text: { title: string; date: string | null; path: string } };

type Row = { key: string; date: string | null; title: string; line?: string; to: string; topic?: Change['topic']; told?: boolean;
             side: 'ahead' | 'behind' | 'bill'; lang: 'ar' | 'fr' };

const DAY = 86_400_000;

/**
 * «شنو تبدّل، وشنو جاي» (30 Oct 2026, the home drawn again): the law's calendar around today
 * on one spine. Today first, then what changes next, the soonest first (C3 of the where-it-trips review: the furthest came
 * first and the next change last), each with its date and how far it is, a finance bill on top in a bill's dashes, never
 * as law. Under a line that says so, what changed lately: the new texts an editor told under a plain headline and the
 * dated changes of the topics, newest first. Each in its topic's colour, each opening its page.
 */
export default function HomeCalendar() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const locale = lang === 'fr' ? 'fr-MA' : 'ar-MA';
  const cal = useQuery({ queryKey: ['topics', 'calendar'], queryFn: () => api<Calendar>('/topics/calendar/'), staleTime: 600_000 });
  const told = useQuery({ queryKey: ['explain', 'new'], queryFn: () => api<{ items: Told[] }>('/explain/new/'), staleTime: 300_000, retry: false });
  const laws = useQuery({ queryKey: ['budget', 'laws'], queryFn: () => api<{ year: number; kind: string }[]>('/budget/laws/'), staleTime: 600_000 });
  if (!cal.data) return null;
  const today = todayIso();
  const pick = (b: Both | null | undefined) => (b ? b[lang] || b.ar : '');
  const ahead: Row[] = cal.data.ahead.slice(0, 3).map((e) => (
    { key: `${e.topic.slug}-${e.change}`, date: e.date, title: pick(e.label), line: pick(e.line), to: e.path, topic: e.topic, side: 'ahead', lang }));
  const byText = new Map(cal.data.behind.filter((e) => e.text).map((e) => [e.text, e]));
  const fromTold: Row[] = (told.data?.items ?? []).slice(0, 4).map((x) => {
    const fr = lang === 'fr' ? x.registers?.fr : undefined;
    return { key: x.path, date: x.text.date, title: (fr ?? x).headline, to: x.text.path, topic: byText.get(x.text.path)?.topic, told: true, side: 'behind',
             lang: fr ? 'fr' : 'ar' };
  });
  const toldTexts = new Set(fromTold.map((r) => r.to));
  const behind: Row[] = [...fromTold, ...cal.data.behind.filter((e) => !e.text || !toldTexts.has(e.text)).map((e): Row => (
    { key: `${e.topic.slug}-${e.change}`, date: e.date, title: pick(e.label), to: e.path, topic: e.topic, side: 'behind', lang }))]
    .sort((a, b) => (b.date ?? '').localeCompare(a.date ?? '')).slice(0, 4);
  const pending = (laws.data ?? []).find((l) => l.kind === 'bill' && !(laws.data ?? []).some((o) => o.kind === 'law' && o.year === l.year));
  const bill: Row[] = pending ? [{ key: 'bill', date: null, title: t('pages:explain.bill', { year: pending.year }), line: t('pages:explain.billLine'),
                                   to: '/topics/tax/pages/bill-2027', side: 'bill', lang }] : [];
  const leaf = (iso: string) => {
    const d = new Date(`${iso}T00:00:00Z`);
    return {
      day: d.getUTCDate(),
      month: new Intl.DateTimeFormat(locale, { month: 'short', timeZone: 'UTC' }).format(d),
      year: iso.slice(0, 4) !== today.slice(0, 4) ? iso.slice(0, 4) : '',
    };
  };
  const far = (iso: string) => {
    const n = Math.round((Date.parse(`${iso}T00:00:00Z`) - Date.parse(`${today}T00:00:00Z`)) / DAY);
    return n === 0 ? t('pages:home2.today') : n > 0 ? t('pages:home2.in', { count: n }) : t('pages:home2.ago', { count: -n });
  };
  const todayLong = new Intl.DateTimeFormat(locale, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' })
    .format(new Date(`${today}T00:00:00Z`));

  const row = (r: Row) => {
    const d = r.date ? leaf(r.date) : null;
    return (
      <li key={r.key} className={`hm-ev ${r.side}`} style={r.topic ? topicColour(r.topic.slug) : undefined}>
        {d ? (
          <time className="hm-d" dateTime={r.date!}><b>{d.day}</b><span>{d.month}</span>{d.year ? <small>{d.year}</small> : null}</time>
        ) : <span className="hm-d"><span>{t('pages:home2.bill')}</span></span>}
        <span className="hm-node" aria-hidden="true" />
        <Link to={r.to} className="hm-body">
          <span className="hm-meta">
            {r.topic ? <span className="tag"><TopicIcon slug={r.topic.slug} size={15} />{pick(r.topic.name)}</span> : null}
            {r.told ? <span className="new">{t('pages:home2.newText')}</span> : null}
            {r.date ? <span className={r.side === 'ahead' ? 'soon' : undefined}>{far(r.date)}</span> : null}
          </span>
          <span className="hm-t" lang={r.lang} dir="auto">{r.title}</span>
          {r.line ? <span className="hm-l" lang={lang}>{r.line}</span> : null}
        </Link>
      </li>
    );
  };

  return (
    <section className="hm-cal" aria-labelledby="hm-cal">
      <div className="hm-head">
        <h2 id="hm-cal">{t('pages:home2.title')}</h2>
        <p>{t('pages:home2.lead')}</p>
      </div>
      <ol className="hm-line">
        <li className="hm-today" aria-current="date">
          <b>{t('pages:home2.today')}</b>
          <span className="now" aria-hidden="true" />
          <span>{todayLong}</span>
        </li>
        {[...bill, ...ahead].map(row)}
        {behind.length ? (
          <li className="hm-today">
            <b>{t('pages:home2.lately')}</b>
            <span aria-hidden="true" />
            <span />
          </li>
        ) : null}
        {behind.map(row)}
      </ol>
    </section>
  );
}
