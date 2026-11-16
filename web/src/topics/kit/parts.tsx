import { useEffect, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { AR, longDate } from '@/features/corpus/format';
import { Button, Note, Page } from '@/shared/components/ui';
import { api } from '@/shared/services/api';
import { usePageTitle } from '@/shared/services/title';
import { useTopic } from '@/features/topics/topics.api';
import { topicColour } from '@/features/topics/colour';
import { pick, refPath, useKitT, type Base, type Cite, type Delay, type Named } from './api';
import { useProfile } from './profile';
import { noteUse } from './use';

/** The articles a sentence rests on, as chips that open them: «المادة 65 · مدونة الأسرة». The law's names stay Arabic. */
export function Cites({ cites, className = '' }: { cites?: Cite[]; className?: string }) {
  const { i18n } = useKitT();
  if (!cites?.length) return null;
  const many = new Set(cites.map((c) => c.text.ar)).size > 1;
  return (
    <ul className={`m-0 flex list-none flex-wrap gap-1.5 p-0 ${className}`}>
      {cites.map((c) => (
        <li key={c.path}>
          <Link to={c.path} className="inline-flex min-h-11 max-w-full flex-wrap items-center gap-1.5 rounded-full bg-wash px-3 text-meta text-stamp no-underline hover:bg-stamp hover:text-on-stamp">
            <bdi {...AR} className="font-semibold">{c.label}</bdi>
            {many ? <span lang={i18n.language} className="text-ink-soft">{pick(c.text, i18n.language)}</span> : null}
          </Link>
        </li>
      ))}
    </ul>
  );
}

/** Who checked it and when (F15), or that an article it rests on changed since («يحتاج مراجعة», in amber: A13 of
 *  the road-signposted review). A draft says nothing: what no specialist has reviewed yet is said once, on «عن «قانون»» (#ab-tools)
 *  and in the footer (an editorial call of 15 Nov 2026). */
export function CheckedLine({ item }: { item: Pick<Base, 'state' | 'checked'> }) {
  const { t, i18n } = useKitT();
  if (item.state === 'checked' && item.checked)
    return <span>{t('checked', { by: item.checked.by, date: longDate(item.checked.on, i18n.language) })}</span>;
  return item.state === 'stale' ? <span className="text-amended">{t('stale')}</span> : null;
}

/** Whether `CheckedLine` has something to say. */
const says = (item?: Pick<Base, 'state' | 'checked'>) => Boolean(item && (item.state === 'stale' || (item.state === 'checked' && item.checked)));

const MARK = { display: 'inline-block', verticalAlign: '-1px', marginInlineEnd: 8 } as const;

/** A time limit the law sets: «الأجل: 30 يوما، من اليوم الموالي للولادة». */
export function DelayLine({ delay }: { delay: Delay }) {
  const { t, i18n } = useKitT();
  // Hours first (PX6 of the where-it-trips review): the custody's 48 hours read «الأجل: ، من ساعة الإيقاف», the hours lost.
  const span = delay.hours ? t('hours', { count: delay.hours })
    : [delay.months ? t('months', { count: delay.months }) : '', delay.days || !delay.months ? t('days', { count: delay.days ?? 0 }) : '']
      .filter(Boolean).join(t('and'));
  return (
    <p className="m-0 inline-flex items-center gap-2 self-start rounded-full bg-amended-wash px-3 py-1 text-meta text-amended">
      <Clock />{t('within', { span, from: pick(delay.from, i18n.language) })}
    </p>
  );
}

/** A topic's page: the way back to the topic in its colour, the title and lead, who checked it, then the page, then
 *  «هل ساعدك هذا؟» (the reminder that this is general information is the footer's). `discreet` pages carry the quick exit (F14).
 *  A tool ends on «كيفاش حسبنا؟», the way to how the tools count and who reviewed them (15 Nov 2026). */
export function KitPage({ slug, item, title, lead, discreet, wide, aside, story, children }: {
  slug: string;
  item?: Pick<Base, 'state' | 'checked' | 'for'>;
  title: string;
  lead?: string;
  discreet?: boolean;
  wide?: boolean;
  /** A desk's side column (G11 of the family-papers review): a journey's day and paper held beside its steps. */
  aside?: ReactNode;
  /** A data story's headline (the bill-story review, C1): set in Markazi, the weight of a front page. */
  story?: boolean;
  children: ReactNode;
}) {
  const { t, i18n } = useKitT();
  const topic = useTopic(slug);
  // A tool's page counts its openings (M1); nothing about the reader goes with it.
  useEffect(() => { if (window.location.pathname.includes('/tools/')) noteUse('open'); }, []);
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  usePageTitle(discreet ? [t('neutralTitle')] : [title, topic.data?.name[lang]]);
  const path = typeof window === 'undefined' ? '' : window.location.pathname;
  // A tool on a desk (U18 of the Moroccan-design review): what one tells it on one side, its answer held in view on
  // the other, as a fare search does; the page's other half was empty paper. A phone keeps one column.
  const tool = path.includes('/tools/');
  const checked = says(item);
  const forWho = item?.for?.length && topic.data?.module?.profile ? item.for : null;
  return (
    <Page width={wide || tool ? 'wide' : 'reading'} className="gap-5"
          aside={aside ? <div style={topicColour(slug)} className="hidden lg:sticky lg:top-6 lg:flex lg:flex-col lg:gap-4">{aside}</div> : undefined}>
      <div style={topicColour(slug)} className="flex flex-col gap-5">
        {discreet ? <SafeExit /> : null}
        <Link to={`/topics/${slug}`} className="inline-flex min-h-11 items-center gap-2 self-start text-body text-ink-soft no-underline hover:text-stamp">
          <span aria-hidden="true" className="size-2.5 rounded-full bg-[var(--t)]" />{topic.data?.name[lang] ?? ''}
        </Link>
        <header className="flex flex-col gap-2">
          <h1 lang={lang} className="m-0 text-h1 font-bold leading-tight" style={story ? { fontFamily: 'var(--font-law)', fontSize: 'clamp(2.25rem, 1.7rem + 2vw, 3.25rem)', lineHeight: 1.15 } : undefined}>{title}</h1>
          {lead ? <p lang={lang} className="m-0 max-w-[62ch] text-lead text-ink-soft">{lead}</p> : null}
          {/* One quiet line (T7): who checked it, or that an article changed since; and whom it speaks to. Nothing for a
              draft (15 Nov 2026): the line is not drawn empty, nor its dashed mark alone. */}
          {checked || forWho ? (
            // One flow of words with its mark at their start (PX24 of the where-it-trips review): as wrapping boxes, the mark
            // stood alone on a line of a phone and «هذه الصفحة تخص» began the next with a stray «·».
            <p className="m-0 text-meta text-ink-soft">
              {item?.state === 'stale' ? <span aria-hidden="true" className="size-2 rounded-full bg-amended" style={MARK} /> : null}
              {checked && item ? <CheckedLine item={item} /> : null}
              {forWho ? <>{checked ? ' ' : null}<ForNames slug={slug} who={forWho} first={!checked} /></> : null}
            </p>
          ) : null}
          {item?.for ? <NotYou slug={slug} who={item.for} /> : null}
        </header>
        {tool ? (
          <div className="flex flex-col gap-5 [&:not(:has(>[data-answer]))]:max-w-[45rem] lg:[&:has(>[data-answer])]:grid lg:[&:has(>[data-answer])]:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:[&:has(>[data-answer])]:items-start lg:[&:has(>[data-answer])]:gap-x-10 lg:[&>*]:col-start-1 lg:[&>[data-answer]]:col-start-2 lg:[&>[data-answer]]:[grid-row:1/span_30]">
            {children}
            {/* One small way to how the tools count and who reviewed them, at the end of the tool (of its first column on a
                desk), never printed. */}
            <p className="m-0 text-meta" data-noprint>
              <Link to="/about#ab-tools" className="inline-flex min-h-11 items-center">{t('howCounted')}</Link>
            </p>
          </div>
        ) : children}
        {path ? <Helped path={path} /> : null}
        {/* The reminder that this is general information is the footer's, under every page (HM44: it was said twice). */}
      </div>
    </Page>
  );
}

/** Whom a page speaks to, by the topic's «where do you work?» answers (T5 of the work plan), inside the page's one line;
 *  `first` when nothing comes before it on that line (no «·» to lead it). */
function ForNames({ slug, who, first = false }: { slug: string; who: string[]; first?: boolean }) {
  const { t, i18n } = useKitT();
  const profile = useTopic(slug).data?.module?.profile;
  if (!profile) return null;
  const names = who.map((k) => pick(profile.options.find((o) => o.key === k)?.label, i18n.language)).filter(Boolean).join('، ');
  return <span lang={i18n.language}>{first ? '' : '· '}{t('profile.for', { who: names })}</span>;
}

/** When the reader answered otherwise, what law is theirs instead: the one note that stays a note. */
function NotYou({ slug, who }: { slug: string; who: string[] }) {
  const { t, i18n } = useKitT();
  const lang = i18n.language;
  const profile = useTopic(slug).data?.module?.profile;
  const [mine] = useProfile(slug);
  const other = profile && mine && !who.includes(mine) ? profile.options.find((o) => o.key === mine) : undefined;
  if (!other) return null;
  return (
    <Note tone="warn" quiet>
      <p lang={lang} className="m-0 text-meta">
        {t('profile.notYou', { you: pick(other.label, lang), law: pick(other.law, lang) })}
        {other.to ? <> · <Link to={refPath(slug, other.to)}>{t('more')}</Link></> : null}
      </p>
    </Note>
  );
}

/** «هل ساعدك هذا؟» (F15): a yes, or a no and why. Counted in the weekly reader report; nothing about the reader is
 *  kept. The device remembers it answered, so the question does not come back. */
export function Helped({ path }: { path: string }) {
  const { t } = useKitT();
  const key = `law.helped.${path}`;
  const [state, setState] = useState<'ask' | 'why' | 'done'>(() => {
    try { return localStorage.getItem(key) ? 'done' : 'ask'; } catch { return 'ask'; }
  });
  const send = (helped: boolean, reason = '') => {
    setState('done');
    try { localStorage.setItem(key, '1'); } catch { /* private mode: asked again next time */ }
    void api('/topics/helped/', { method: 'POST', json: { path, helped, reason } }).catch(() => undefined);
  };
  if (state === 'done') return <p className="m-0 text-meta text-ink-soft" aria-live="polite">{t('helped.thanks')}</p>;
  return (
    <section className="flex flex-wrap items-center gap-2 rounded-card bg-sheet px-5 py-4" aria-live="polite">
      <h2 className="m-0 me-2 text-body font-semibold">{state === 'ask' ? t('helped.q') : t('helped.why')}</h2>
      {state === 'ask' ? (
        <>
          <Button onClick={() => send(true)}>{t('helped.yes')}</Button>
          <Button onClick={() => setState('why')}>{t('helped.no')}</Button>
        </>
      ) : (['unclear', 'not_mine', 'wrong'] as const).map((r) => <Button key={r} onClick={() => send(false, r)}>{t(`helped.${r}`)}</Button>)}
    </section>
  );
}

/** «اخرج بسرعة» (F14): one tap leaves for a neutral page and takes this one out of the history, so «back» does not
 *  return to it. Escape does the same. Held at the top while the page scrolls. */
export function SafeExit() {
  const { t } = useKitT();
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && leave();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);
  return (
    <div className="sticky top-2 z-30 flex justify-end">
      <button type="button" onClick={leave} title={t('exitHint')}
              className="inline-flex h-11 items-center gap-2 rounded-full bg-ink px-5 text-body font-semibold text-sheet shadow-lg hover:bg-stamp">
        <span aria-hidden="true">✕</span>{t('exit')}
      </button>
    </div>
  );
}

function leave() {
  try { sessionStorage.clear(); } catch { /* nothing kept to clear */ }
  window.location.replace('https://www.google.com/');
}

/** Where a page leads next, as rows: the journeys, papers, pages and tools it names. */
export function NextLinks({ slug, refs, titles }: { slug: string; refs?: string[]; titles: Record<string, Named | undefined> }) {
  const { t, i18n } = useKitT();
  const shown = (refs ?? []).filter((r) => titles[r]);
  if (!shown.length) return null;
  return (
    <section className="flex flex-col gap-2">
      <h2 className="m-0 text-lead font-semibold">{t('after')}</h2>
      <ul className="m-0 grid list-none gap-2 p-0 sm:grid-cols-2">
        {shown.map((r) => (
          <li key={r}>
            <Link to={refPath(slug, r)} className="flex min-h-14 items-center rounded-card bg-sheet px-4 py-3 text-body font-medium text-ink no-underline hover:text-stamp">
              {pick(titles[r], i18n.language)}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

const Clock = () => (
  <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" />
  </svg>
);

/** Stops on a line, in the reading direction, those reached filled. */
export function Stops({ stages, reached }: { stages: string[]; reached: number }) {
  return (
    <ol className="relative m-0 grid list-none p-0" style={{ gridTemplateColumns: `repeat(${stages.length}, minmax(0, 1fr))` }}>
      <span aria-hidden="true" className="absolute top-[7px] h-0.5 bg-rule" style={{ insetInline: `${50 / stages.length}%` }} />
      {stages.map((label, i) => (
        <li key={label} aria-current={i === reached ? 'step' : undefined}
            className={`relative flex flex-col items-center gap-1 text-center text-meta leading-snug ${i === reached ? 'font-semibold text-amended' : 'text-ink-soft'}`}>
          <span aria-hidden="true" className={`size-4 rounded-full border-2 ${i <= reached ? 'border-amended bg-amended' : 'border-rule bg-sheet'}`} />
          {label}
        </li>
      ))}
    </ol>
  );
}
