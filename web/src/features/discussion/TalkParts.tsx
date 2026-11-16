import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ARCH, ArchDoor } from '@/features/topics/Arch';
import { topicColour } from '@/features/topics/colour';
import { TopicIcon } from '@/features/topics/TopicIcon';
import { searchApi } from '@/features/search/search.api';
import { Button } from '@/shared/components/ui';
import { useSession } from '@/shared/stores/session';
import { useRegistrationOpen } from '@/features/accounts/registration';
import { discussionApi, PERIODS, SORTS, type Contribution, type Labelled, type Period, type PlaceSummary, type Similar,
         type Sort } from './discussion.api';
import { ago, placeName, slugOf, useT } from './strings';
import './talk.css';

/* The conversation's own parts (30 Oct 2026): the question box, a real exchange, the doors, a topic's tag, a person's
   initial and a post's answers as a bubble. talk.css draws them. */

/** A topic named by its line icon and its door's name, in its colour. */
export function TopicTag({ place, name }: { place: string; name: { ar: string; fr: string | null } | null | undefined }) {
  const { i18n } = useT();
  const slug = slugOf(place);
  return (
    <span className="tk-tag" style={topicColour(slug)}>
      {slug === 'general' ? <ChatIcon size={16} /> : <TopicIcon slug={slug} size={16} />}
      {placeName(name, i18n.language)}
    </span>
  );
}

/** A person by the first letter of their name (people are named, never drawn); someone without a name by a dot. */
export function Initial({ name }: { name?: string | null }) {
  return <span className="tk-initial" aria-hidden="true">{name ? [...name.trim()][0] : '•'}</span>;
}

export function ChatIcon({ size = 20 }: { size?: number }) {
  return (
    <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
         strokeLinejoin="round" strokeLinecap="round" className="shrink-0">
      <path d="M4 5h16v11H9l-5 4zM8 9.5h8M8 12.5h5" />
    </svg>
  );
}

/** The general place's door: the arch in the conversation's colour, a message in it. */
export function TalkArch({ className = '' }: { className?: string }) {
  return (
    <svg aria-hidden="true" viewBox="-2 -2 124 136" className={`tk-arch ${className}`}>
      <path d={ARCH} />
      <svg x="42" y="58" width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"
           strokeLinejoin="round" strokeLinecap="round"><path d="M4 5h16v11H9l-5 4zM8 9.5h8M8 12.5h5" /></svg>
    </svg>
  );
}

/** A topic's door, as on the home, with how many of its questions wait for an answer. */
export function RoomDoor({ p }: { p: PlaceSummary }) {
  const { t, i18n } = useT();
  return (
    <Link to={p.path} className="tk-door" style={topicColour(p.slug)}>
      <span className="tk-door-arch">
        <ArchDoor slug={p.slug} />
        {p.open_questions ? <span className="tk-wait" aria-hidden="true">{p.open_questions}</span> : null}
      </span>
      <span className="tk-door-name">{placeName(p.short ?? p.name, i18n.language)}</span>
      <span className="tk-door-count">{t('talk2.posts', { count: p.count })}</span>
      {p.open_questions ? <span className="tk-sr">{t('open', { count: p.open_questions })}</span> : null}
    </Link>
  );
}

/** The place for a law no topic holds: a row under the doors. */
export function GeneralDoor({ p }: { p: PlaceSummary }) {
  const { t, i18n } = useT();
  return (
    <Link to={p.path} className="tk-general">
      <span className="tk-general-icon"><ChatIcon /></span>
      <span>
        <b>{placeName(p.name, i18n.language)}</b>
        <small>{t('talk3.generalLead')}</small>
      </span>
      <span className="tk-general-n">{t('talk2.posts', { count: p.count })}</span>
    </Link>
  );
}

/** A question someone answered, as the exchange it was: the asker from the start side, the answer from the end side. */
export function Exchange({ q }: { q: Labelled & { answer: Contribution | null } }) {
  const { t, i18n } = useT();
  const a = q.answer!;
  const asker = q.anonymous || !q.author || 'deleted' in q.author ? null : q.author.name;
  const answerer = a.anonymous || !a.author || 'deleted' in a.author ? null : a.author.name;
  return (
    <figure className="tk-exchange" style={topicColour(slugOf(q.label.place ?? ''))}>
      <figcaption className="tk-exchange-cap">
        <span>{t('talk3.exchangeCap')}</span>
        {q.label.place ? <TopicTag place={q.label.place} name={q.label.name} /> : null}
      </figcaption>
      <div className="tk-say tk-say-q">
        <span className="tk-say-who"><Initial name={asker} /><b dir="auto">{asker ?? t('anonymous')}</b></span>
        <p className="tk-bubble" dir="auto">{q.title || q.body}</p>
      </div>
      <div className="tk-say tk-say-a">
        <span className="tk-say-who"><b dir="auto">{answerer ?? t('anonymous')}</b><Initial name={answerer} /></span>
        <p className="tk-bubble" dir="auto">{a.body}</p>
        <span className="tk-say-meta">
          {a.accepted ? <span className="yes">✓ {t('accepted')}</span> : null}
          {a.useful ? <span>{t('usefulCount', { count: a.useful })}</span> : null}
          <time dateTime={a.created_at}>{ago(a.created_at, i18n.language)}</time>
        </span>
      </div>
      <Link to={q.path} className="tk-exchange-more">{t('talk3.exchangeMore')}</Link>
    </figure>
  );
}

const TITLE_MAX = 140;

/** A question asked in the box: its first sentence as the title, all of it as the words when it is longer. */
function asPost(words: string): { title: string; body: string } {
  if (words.length <= TITLE_MAX && !/[؟?.!]\s+\S/.test(words)) return { title: words, body: '' };
  const first = words.split(/(?<=[؟?.!])\s+/)[0];
  const title = first.length <= TITLE_MAX ? first : `${first.slice(0, TITLE_MAX - 1).replace(/\s+\S*$/, '')}…`;
  return { title, body: words };
}

/**
 * «شنو السؤال ديالك؟» on the hub: the reader writes, the words name their topic (search's suggestions know Darija), the
 * questions already asked there that share the words show before a new one is asked, and the question goes on to its
 * topic's form, kept as that form's draft.
 */
export function AskBox({ places, autoFocus = false }: { places: PlaceSummary[]; autoFocus?: boolean }) {
  const { t, i18n } = useT();
  const navigate = useNavigate();
  const [text, setText] = useState('');
  const [chosen, setChosen] = useState('');
  const [choosing, setChoosing] = useState(false);
  const [guess, setGuess] = useState('');
  const [similar, setSimilar] = useState<{ for: string; questions: Similar[] }>({ for: '', questions: [] });
  const words = text.trim();
  // While sign-up is closed a visitor without an account cannot post (C1 of the where-it-trips review: they typed a whole
  // question, then met «ادخل إلى حسابك» with no way to make one). The box says so before typing, and the question goes to
  // the law's answer.
  const signedIn = useSession((x) => Boolean(x.tokens));
  const registrationOpen = useRegistrationOpen();
  const searchOnly = !signedIn && !registrationOpen;
  const guessed = words.length >= 8 && places.some((p) => p.slug === guess) ? guess : '';
  const slug = chosen || guessed;
  const place = places.find((p) => p.slug === slug);

  useEffect(() => {
    if (words.length < 8) return;
    let live = true;
    const id = window.setTimeout(() => {
      searchApi.suggest(words).then((r) => { if (live) setGuess(r.topics[0]?.slug ?? ''); }).catch(() => undefined);
    }, 350);
    return () => { live = false; window.clearTimeout(id); };
  }, [words]);

  useEffect(() => {
    if (!slug || words.length < 12) return;
    let live = true;
    const id = window.setTimeout(() => {
      discussionApi.similar(`/talk/${slug}`, words)
        .then((r) => { if (live) setSimilar({ for: `${slug}:${words}`, questions: r.questions.slice(0, 3) }); })
        .catch(() => undefined);
    }, 450);
    return () => { live = false; window.clearTimeout(id); };
  }, [slug, words]);

  const shown = slug && words.length >= 12 && similar.for.startsWith(`${slug}:`) ? similar.questions : [];
  const go = () => {
    if (searchOnly) {
      if (words.length >= 2) navigate(`/search?q=${encodeURIComponent(words)}`);
      return;
    }
    if (!place || words.length < 5) return;
    try {
      // The topic's form opens on it as on a draft the reader left there (Composer's own key).
      localStorage.setItem(`law.draft:${place.path}:top:`, JSON.stringify({ kind: 'question', ...asPost(words), anonymous: false }));
    } catch {
      // Private mode: the form opens empty.
    }
    navigate(place.path);
  };

  return (
    <form className="tk-ask" onSubmit={(e) => { e.preventDefault(); go(); }}>
      <label className="tk-ask-label" htmlFor="tk-ask">{t('talk3.askLabel')}</label>
      {searchOnly ? <p className="m-0 text-meta text-ink-soft">{t('talk3.askClosed')}</p> : null}
      <div className="tk-ask-field">
        <textarea id="tk-ask" dir="auto" rows={2} maxLength={2000} value={text} placeholder={t('talk3.askPlaceholder')} autoFocus={autoFocus}
                  onChange={(e) => setText(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) go(); }} />
      </div>
      {searchOnly ? null : place && !choosing ? (
        <div className="tk-ask-row">
          <span className="tk-ask-where">{t('talk2.where')}</span>
          <span className="tk-chip" aria-pressed="true" style={topicColour(place.slug)}>
            {place.slug === 'general' ? <ChatIcon size={18} /> : <TopicIcon slug={place.slug} size={18} />}
            {placeName(place.short ?? place.name, i18n.language)}
          </span>
          <button type="button" className="tk-ask-change" onClick={() => setChoosing(true)}>{t('talk3.askChange')}</button>
        </div>
      ) : words.length >= 5 || choosing ? (
        <div className="flex flex-col gap-2">
          <span className="tk-ask-where">{t('talk3.askPick')}</span>
          <ul className="tk-chips">
            {places.map((p) => (
              <li key={p.slug}>
                <button type="button" className="tk-chip" aria-pressed={p.slug === slug} style={topicColour(p.slug)}
                        onClick={() => { setChosen(p.slug); setChoosing(false); }}>
                  {p.slug === 'general' ? <ChatIcon size={18} /> : <TopicIcon slug={p.slug} size={18} />}
                  {placeName(p.short ?? p.name, i18n.language)}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {shown.length ? (
        <ul className="tk-similar">
          <li className="tk-similar-head">{t('talk3.similarHead')}</li>
          {shown.map((q) => (
            <li key={q.id}>
              <Link to={q.path}>
                <span className="tk-similar-q" dir="auto">{q.title || q.body}</span>
                <span className="tk-similar-n">{q.accepted ? '✓ ' : ''}{t('composer2.similarAnswers', { count: q.answers })}</span>
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
      <div className="tk-ask-row">
        <Button variant="primary" type="submit" className="tk-ask-go" disabled={searchOnly ? words.length < 2 : !place || words.length < 5}>
          {t(searchOnly ? 'talk3.askSearch' : 'talk3.askGo')}
        </Button>
      </div>
    </form>
  );
}

/** A post's answers as a bubble at its end: dots while nobody answered, the count once someone did, green once the
 *  asker marked one; a post (not a question) counts its comments quietly. */
export function Answers({ c }: { c: Contribution }) {
  const { t } = useT();
  const n = c.reply_count;
  const state = c.kind !== 'question' ? 'post' : c.solved ? 'solved' : n ? 'answered' : 'waiting';
  const label = state === 'waiting' ? t('talk3.waitingLabel') : state === 'solved' ? t('talk3.solvedLabel')
    : state === 'post' ? t('talk3.commentsNoun', { count: n }) : t('talk3.answersNoun', { count: n });
  return (
    <div className="tk-count" data-state={state}>
      <span className="tk-count-b" aria-hidden="true">
        {state === 'waiting' ? <span className="tk-dots"><i /><i /><i /></span> : n}
      </span>
      <span className="tk-count-l" aria-hidden="true">{label}</span>
      <span className="tk-sr">{state === 'waiting' ? label : `${n} ${state === 'solved' ? t('talk3.answersNoun', { count: n }) : label}`}
        {state === 'solved' ? ` (${label})` : ''}</span>
    </div>
  );
}

/** A feed's four orders, and under «الأنفع» its period: the last week, month (its first), year, or since the start
 *  (31 Oct 2026). `waiting`: how many questions «بلا جواب» holds, said on it. */
export function FeedSorts({ sort, period, onSort, onPeriod, waiting = 0 }: {
  sort: Sort; period: Period; onSort: (s: Sort) => void; onPeriod: (p: Period) => void; waiting?: number;
}) {
  const { t } = useT();
  return (
    <div className="tk-sorts">
      <div role="tablist" aria-label={t('talk2.sortLabel')} className="tk-tabs">
        {SORTS.map((s) => (
          <button key={s} type="button" role="tab" aria-selected={sort === s} onClick={() => onSort(s)}
                  className={`h-10 rounded-full border px-4 text-meta ${sort === s ? 'border-stamp bg-stamp text-on-stamp' : 'border-rule bg-sheet text-ink hover:border-stamp'}`}>
            {t(`talk2.sorts.${s}`)}{s === 'open' && waiting ? ` (${waiting})` : ''}
          </button>
        ))}
      </div>
      {sort === 'top' ? (
        <div role="tablist" aria-label={t('talk2.periodLabel')} className="tk-seg tk-period">
          {PERIODS.map((x) => (
            <button key={x} type="button" role="tab" aria-selected={period === x} onClick={() => onPeriod(x)}>
              {t(`talk2.periods.${x}`)}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
