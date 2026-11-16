import { useMemo, useState } from 'react';
import { Button, Note, PageSkeleton } from '@/shared/components/ui';
import { pick, useKitItem, type Named } from '../kit/api';
import { KitPage } from '../kit/parts';
import { transition } from '../kit/motion';
import { Chips, SourceFold } from '../kit/tool/parts';
import { useToolState } from '../kit/tool/state';
import { SCENES, SIGN_CARDS } from './scenes/data';
import { SCENE_COLOURS, SIGNS } from './scenes/signs';
import { answer, learned, order, readBoxes, shuffled } from './practice';
import { articleLabel, useRoadT } from './strings';

type Card = { key: string; kind: 'scene' | 'sign' | 'figure'; scene?: string; sign?: string; question: Named; choices: Named[]; quote: Named;
  cites: { path: string }[] };
type Batch = { title: Named; cards: Card[] };

/** The sign game (Q3, call K2): a sign, and what each of three signs requires, in the words already written
 *  and checked for each sign; nothing new is written. The right one is the sign's own. */
function signCards(): Card[] {
  return SIGN_CARDS.map((s, i) => {
    const others = SIGN_CARDS.filter((x) => x.key !== s.key);
    const two = [others[(i + 1) % others.length], others[(i + 4) % others.length]];
    return {
      key: `sign-${s.key}`, kind: 'sign', sign: s.key,
      question: { ar: 'ماذا تفرض هذه العلامة؟', fr: 'Qu’impose ce panneau ?' },
      choices: [s.says, ...two.map((x) => x.says)], quote: s.name, cites: s.cites.map((path) => ({ path })),
    } satisfies Card;
  });
}

/** «تمرن» (R10 of the road plan; Q2, Q3 of the road tools review): one card at a time, big answers, the sign or the
 *  scene's still live, the article's words on the reveal, a progress ring, missed cards back first on this phone.
 *  Two decks: the signs (from their checked words) and the cards a person writes from one article each, approved
 *  by batches (Q3 of the road plan). Never the official exam nor a copy of it. */
export default function PracticePage({ slug }: { slug: string }) {
  const { t, i18n } = useRoadT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const [s, set] = useToolState({ d: 'signs' });
  const q = useKitItem<Batch>(slug, 'cards', 'batch-1');
  const deck = s.d === 'cards' ? 'cards' : 'signs';
  const all = useMemo(() => (deck === 'signs' ? signCards() : q.data?.cards ?? []), [deck, q.data]);
  const [turn, setTurn] = useState(0);
  const [boxes, setBoxes] = useState(() => readBoxes(deck));
  const [chosen, setChosen] = useState<number | null>(null);
  const cards = useMemo(() => order(all, boxes, turn), [all, boxes, turn]);
  const card = cards[0];
  const choices = card ? shuffled(card.choices.map((c, i) => ({ c, i })), card.key + turn) : [];
  const done = learned(boxes);
  const pickDeck = (d: string) => { set({ d }); setBoxes(readBoxes(d)); setChosen(null); };
  const reply = (i: number) => { setChosen(i); setBoxes(answer(deck, card.key, i === 0, turn)); };
  const next = () => transition(() => { setChosen(null); setTurn(turn + 1); });
  if (deck === 'cards' && q.isLoading) return <KitPage slug={slug} title={t('practice.title')} lead={t('practice.lead')}><PageSkeleton /></KitPage>;
  return (
    <KitPage slug={slug} title={t('practice.title')} lead={t('practice.lead')}>
      <Note tone="law" quiet><p className="m-0 text-meta">{t('practice.notExam')}</p></Note>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Chips value={deck} onChange={pickDeck} options={[{ key: 'signs', label: t('practice.decks.signs') }, { key: 'cards', label: t('practice.decks.cards') }]} />
        {all.length ? <Ring done={done} total={all.length} label={t('practice.learned', { done, total: all.length })} /> : null}
      </div>
      {!card ? (
        <section className="flex flex-col gap-2 rounded-card bg-sheet px-5 py-6"><p className="m-0 text-body">{t('practice.none')}</p></section>
      ) : (
        <section key={card.key + turn} className="flex flex-col gap-4 rounded-card bg-sheet px-5 py-5 motion-safe:animate-[rise_220ms_ease-out_both] sm:px-7" aria-live="polite" style={SCENE_COLOURS}>
          {card.sign ? (
            <svg viewBox="0 0 100 100" width="140" height="140" role="img" aria-label={t('practice.signAlt')} className="self-center" dangerouslySetInnerHTML={{ __html: SIGNS[card.sign]() }} />
          ) : card.scene ? <p className="m-0 text-meta text-ink-soft">{pick(SCENES.find((x) => x.key === card.scene)?.title, lang)}</p> : null}
          <h2 className="m-0 text-h3 font-semibold">{pick(card.question, lang)}</h2>
          <ul className="m-0 flex list-none flex-col gap-2 p-0">
            {choices.map(({ c, i }) => (
              <li key={i}>
                <button type="button" disabled={chosen !== null} onClick={() => reply(i)}
                        className={`min-h-14 w-full rounded-control border px-4 py-2 text-start text-lead transition-[background-color,border-color] duration-200 motion-reduce:transition-none ${
                          chosen === null ? 'border-field bg-sheet hover:border-[var(--t)]' : i === 0 ? 'border-2 border-in-force bg-[color-mix(in_srgb,var(--color-in-force)_10%,var(--color-sheet))]' : i === chosen ? 'border-2 border-amended bg-amended-wash' : 'border-rule opacity-60'}`}>
                  {pick(c, lang)}
                </button>
              </li>
            ))}
          </ul>
          {chosen !== null ? (
            <>
              <p className={`m-0 text-lead font-semibold ${chosen === 0 ? 'text-in-force' : 'text-amended'}`}>{t(chosen === 0 ? 'practice.right' : 'practice.wrong')}</p>
              {card.kind !== 'sign' ? <blockquote lang="ar" dir="rtl" className="m-0 border-s-4 border-stamp ps-3 font-law text-law">{pick(card.quote, lang)}</blockquote>
                : <p className="m-0 text-body">{t('practice.thisIs', { name: pick(card.quote, lang) })}</p>}
              <SourceFold paths={card.cites.map((c) => c.path)} label={articleLabel} />
              <Button variant="primary" className="self-start" onClick={next}>{t('practice.next')}</Button>
            </>
          ) : null}
        </section>
      )}
    </KitPage>
  );
}

/** How far the deck is learned (cards past the second box), as a ring. */
function Ring({ done, total, label }: { done: number; total: number; label: string }) {
  const r = 18, c = 2 * Math.PI * r;
  return (
    <span className="inline-flex items-center gap-2 text-meta text-ink-soft">
      <svg width="44" height="44" viewBox="0 0 44 44" aria-hidden="true" className="-rotate-90">
        <circle cx="22" cy="22" r={r} fill="none" stroke="var(--color-rule)" strokeWidth="5" />
        <circle cx="22" cy="22" r={r} fill="none" stroke="var(--t)" strokeWidth="5" strokeLinecap="round"
                strokeDasharray={c} strokeDashoffset={c * (1 - done / Math.max(1, total))} className="motion-safe:transition-[stroke-dashoffset] motion-safe:duration-500" />
      </svg>
      {label}
    </span>
  );
}
