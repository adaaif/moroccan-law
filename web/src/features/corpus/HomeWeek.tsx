import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { firstRegister, useWeek, type WeekText } from '@/features/explain/explain.api';
import { topicColour } from '@/features/topics/colour';
import { TopicIcon } from '@/features/topics/TopicIcon';
import '@/shared/locales/pages';
import { todayIso } from '@/shared/services/today';
import { shortName } from './article/message';
import { AR, issueNo, longDate } from './format';
import { units, type Unit } from './newWeek';
import './week.css';

/**
 * The week's Bulletin on the home (30 Oct 2026: the «what's new» column was a plain list, hard to read): the week drawn as the Bulletin draws its own front page. Its name over a double rule, a dateline of the issue's
 * number and its two dates; then what an editor told in plain words, «يهم الناس», with its topic; then the week's other
 * texts as printed, each with its kind, its topic, its page and what it changes; the rest counted. The week's other
 * issues lie under it as sheets. Beside the question on a desk, in the flow on a phone.
 */
export default function HomeWeek() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const week = useWeek('');
  const w = week.data;
  if (!w?.issues.length) return null;
  const issues = [...w.issues].sort((a, b) => b.date.localeCompare(a.date));
  // The front page is the newest issue that holds the texts listed under it (W9 of the library-search review): the block named
  // «7556 مكرر», a report of 226 pages with no text, above decrees printed in 7555. An issue with no text stays among the
  // week's other issues, at the foot.
  const of = (key: string) => (x: WeekText) => x.issue.key === key;
  const front = issues.find((i) => w.people.some(of(i.key)) || w.rest.some(of(i.key))) ?? issues[0];
  const people = w.people.filter(of(front.key)), rest = w.rest.filter(of(front.key));
  // Its Hijri date from the week's own answer (HM2 of the hard-moment review: the home fetched the list of every
  // issue for this one line).
  const hijri = front.hijri;
  const told = people.filter((x) => firstRegister(x.told ?? {}, i18n.language)).slice(0, 2);
  // A series of texts of one form (twenty decrees «يتعلق باختصاصات وزير …») is one line, as on /new (1 Nov 2026).
  const listed = units(rest, w.series ?? {}).slice(0, told.length ? 3 : 4);
  const shown = listed.reduce((n, u) => n + (u.kind === 'text' ? 1 : u.texts.length), 0);
  const more = rest.length - shown + front.special;
  const span = new Intl.DateTimeFormat(lang === 'fr' ? 'fr-MA' : 'ar-MA', { day: 'numeric', month: 'long', timeZone: 'UTC' })
    .formatRange(new Date(`${w.from}T00:00:00Z`), new Date(`${w.to}T00:00:00Z`));
  const open = `/bo/${front.edition}/${front.key}`;

  return (
    <section className="wk" aria-labelledby="wk-title" data-stack={issues.length > 1 ? '' : undefined}>
      <div className="wk-paper">
        <header className="wk-head">
          <h2 id="wk-title">
            {/* «This week» only while it is: on 9 November the week of 26 October stood under it, the newest the SGG
                had published (RD23 of the readers review). */}
            <span className="wk-kicker">{t(todayIso() > w.to ? 'pages:homeWeek.kickerLast' : 'pages:homeWeek.kicker')}</span>
            <span className="wk-name">{t('pages:homeWeek.name')}</span>
          </h2>
          <p className="wk-span"><span>{span}</span><span>{t('pages:week.issues', { count: issues.length })}</span></p>
          <hr className="wk-rule" />
        </header>
        <div className="wk-dateline">
          <Link to={open} className="wk-no" aria-label={t('stamp.issue', { number: issueNo(front, t) })}>
            <span>{t('pages:homeWeek.issue')}</span>
            <b>{issueNo(front, t)}</b>
          </Link>
          <p className="wk-dates m-0">
            {hijri ? <span><bdi lang="ar">{hijri}</bdi></span> : null}
            <span>{longDate(front.date, lang)}</span>
          </p>
        </div>

        {told.length ? (
          <div className="wk-told">
            <p className="wk-label">{t('pages:week.people')}</p>
            {told.map((x) => <Story key={x.path} x={x} />)}
          </div>
        ) : null}

        {listed.length ? (
          <ul className="wk-texts">{listed.map((u) => <Row key={u.kind === 'text' ? u.text.path : u.id} u={u} lang={lang} />)}</ul>
        ) : null}

        <footer className="wk-foot">
          {more > 0 ? <Link to={open}>{t('pages:homeWeek.more', { count: more })}</Link> : <Link to={open}>{t('corpus.openIssue')}</Link>}
          {issues.filter((i) => i !== front).map((i) => (
            <Link key={i.key} to={`/bo/${i.edition}/${i.key}`}>{t('pages:homeWeek.also', { issue: issueNo(i, t) })}</Link>
          ))}
          <Link to="/new" className="wk-all">{t('pages:new.all')}</Link>
        </footer>
      </div>
    </section>
  );
}

/** A text an editor told: its topic, their headline, the start of their plain words. */
function Story({ x }: { x: WeekText }) {
  const { i18n } = useTranslation();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const register = firstRegister(x.told ?? {}, i18n.language)!;
  const e = x.told![register]!;
  return (
    <article className="wk-story" style={x.topic ? topicColour(x.topic.slug) : undefined}>
      {x.topic ? <Link to={`/topics/${x.topic.slug}`} className="wk-topic" lang={lang}><TopicIcon slug={x.topic.slug} size={15} />{x.topic.name[lang]}</Link> : null}
      <Link to={x.path} className="h" dir="auto">{e.headline}</Link>
      <p dir={register === 'fr' ? 'ltr' : 'rtl'}>{e.body}</p>
    </article>
  );
}

function Row({ u, lang }: { u: Unit; lang: 'ar' | 'fr' }) {
  return u.kind === 'text' ? <Text x={u.text} lang={lang} /> : <Series u={u} />;
}

/** A series as one line: its kind and how many, its shared words, the first members by what differs; /new lists all. */
function Series({ u }: { u: Extract<Unit, { kind: 'series' }> }) {
  const { t } = useTranslation();
  const x = u.texts[0];
  const parts = [...new Set(u.texts.map((m) => m.part).filter(Boolean))];
  return (
    <li>
      <span className="wk-meta">
        <span className="wk-type">{t(`corpus.types.${x.type}`, { defaultValue: t('corpus.types.other') })}</span>
        <span className="wk-page">{u.texts.length} {t('pages:new3.texts', { count: u.texts.length })}</span>
      </span>
      <Link {...AR} to="/new" className="wk-title">{u.series.head} …</Link>
      {parts.length > 1 ? <span {...AR} className="wk-changes">{shortName(parts.slice(0, 3).join(t('corpus.listSep')), 110)}{parts.length > 3 ? ' …' : ''}</span> : null}
    </li>
  );
}

/** A text as printed: its kind and topic, its page in the issue, its title, the law it changes. */
function Text({ x, lang }: { x: WeekText; lang: 'ar' | 'fr' }) {
  const { t } = useTranslation();
  return (
    <li style={x.topic ? topicColour(x.topic.slug) : undefined}>
      <span className="wk-meta">
        <span className="wk-type">{t(`corpus.types.${x.type}`, { defaultValue: t('corpus.types.other') })}</span>
        {x.topic ? <Link to={`/topics/${x.topic.slug}`} className="wk-topic" lang={lang}><TopicIcon slug={x.topic.slug} size={14} />{x.topic.name[lang]}</Link> : null}
        {x.page ? <span className="wk-page">{t('stamp.page', { page: x.page })}</span> : null}
      </span>
      <Link {...AR} to={x.path} className="wk-title">{shortName(x.title, 140)}</Link>
      {x.changes.length ? (
        <span className="wk-changes">
          {t('pages:week.changes')} <Link to={x.changes[0].path} lang={lang}>{shortName(x.changes[0].name[lang], 70)}</Link>
          {x.changes.length > 1 ? ` ${t('pages:homeWeek.andMore', { count: x.changes.length - 1 })}` : ''}
        </span>
      ) : null}
    </li>
  );
}
