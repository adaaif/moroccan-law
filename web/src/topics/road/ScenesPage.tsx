import { useEffect, useRef, useState } from 'react';
import { Button } from '@/shared/components/ui';
import { KitPage } from '../kit/parts';
import { reducedMotion, transition } from '../kit/motion';
import { SourceFold } from '../kit/tool/parts';
import { toolLink, useToolState } from '../kit/tool/state';
import { noteUse } from '../kit/use';
import { mount, type Controller, type SceneDef } from './scenes/engine';
import { SCENES, type Scene } from './scenes/data';
import { SCENE_COLOURS } from './scenes/signs';
import { OFFENCES } from './rules/fines';
import { useFines } from './rules/rates';
import { articleLabel, useRoadT } from './strings';
import { todayIso } from '@/shared/services/today';

type Phase = 'ask' | 'wrong' | 'play';
const today = () => todayIso();

/** The scene as it would go after a wrong answer (S1): the actors on their other paths, a red ring where they meet,
 *  the question then what is said there. */
function wrongDef(scene: Scene): SceneDef {
  const w = scene.ask!.wrong!;
  return {
    ...scene, dur: w.dur, still: 0, loop: false, guidesTill: 0, guides: [],
    actors: scene.actors.map((a, i) => (w.actors[i] ? { ...a, d: w.actors[i].d ?? a.d, keys: w.actors[i].keys, glow: undefined, signal: undefined } : a)),
    flags: [...(w.flags ?? []), {
      at: [w.at, w.dur], draw: (g, el) => {
        el('circle', { cx: w.clash[0], cy: w.clash[1], r: 30, fill: 'none', stroke: 'var(--g-red)', 'stroke-width': 4 }, g);
        el('circle', { cx: w.clash[0], cy: w.clash[1], r: 30, fill: 'var(--g-red)', opacity: 0.15 }, g);
      },
    }],
    steps: [{ t: 0, ...scene.ask!.q }, { t: w.at, ...w.says }],
  };
}

/** What a breach costs, worked out from the fine tool's rules and rates (S4): never a second copy of the numbers. */
function useCost(scene: Scene): string | null {
  const { t, i18n } = useRoadT();
  const rates = useFines('road', today()).values;
  const nf = new Intl.NumberFormat(i18n.language === 'fr' ? 'fr-MA' : 'ar-MA');
  const dh = (n: number) => t('dh', { amount: nf.format(n) });
  const o = OFFENCES.find((x) => x.key === scene.offence);
  if (!o) return scene.costNote ? (i18n.language === 'fr' ? scene.costNote.fr : scene.costNote.ar) : null;
  if (o.klass === 'walk') return t('scenes.costWalk', { offence: t(`offences.${o.key}`), amount: dh(rates.walk_30) });
  const k = `c${o.klass}`;
  return t('scenes.cost', { offence: t(`offences.${o.key}`), klass: t(`classesShort.${o.klass}`), full: dh(rates[`${k}_30`]),
    day: dh(rates[`${k}_day`]), points: o.points ? t('points_n', { count: o.points }) : t('scenes.noPoints') });
}

/** One scene (S1–S6 of the road tools review): it asks first on its still frame — a choice, or a tap on a car —;
 *  a wrong answer plays what would happen and its cost, then the right way; a scrubber walks the scene, a tap on
 *  the drawing pauses it, «ببطء» plays it at half speed. Under reduced motion the steps and the scrubber are the
 *  only ways through. The drawing never mirrors: traffic keeps to the right in both languages. */
function SceneView({ scene, slug }: { scene: Scene; slug: string }) {
  const { t, i18n } = useRoadT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const svg = useRef<SVGSVGElement>(null);
  const ctl = useRef<Controller | null>(null);
  const [phase, setPhase] = useState<Phase>(scene.ask ? 'ask' : 'play');
  const [answer, setAnswer] = useState<{ right: boolean } | null>(null);
  const [step, setStep] = useState(0);
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [slow, setSlow] = useState(false);
  const cost = useCost(scene);
  const def = phase === 'wrong' && scene.ask?.wrong ? wrongDef(scene) : scene;
  useEffect(() => {
    if (!svg.current) return;
    ctl.current = mount(svg.current, def, lang, setStep, () => setPlaying(false), setTime);
    if (phase === 'wrong' || (phase === 'play' && answer)) {
      if (reducedMotion()) ctl.current.show(phase === 'wrong' ? scene.ask!.wrong!.at : def.steps[def.steps.length - 1].t + 1);
      else { ctl.current.play(slow ? 0.5 : 1); setPlaying(true); }
    }
    return () => ctl.current?.halt();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scene, lang, phase]);
  const choose = (i: number) => {
    const c = scene.ask!.choices[i];
    if (!answer) noteUse(c.right ? 'right' : 'wrong');
    transition(() => {
      setAnswer({ right: Boolean(c.right) });
      setPhase(c.right || !scene.ask!.wrong ? 'play' : 'wrong');
    });
  };
  const tapDrawing = (e: React.MouseEvent<SVGSVGElement>) => {
    if (phase === 'ask' && scene.ask) {
      const r = svg.current!.getBoundingClientRect(), vb = svg.current!.viewBox.baseVal;
      const x = vb.x + ((e.clientX - r.left) / r.width) * vb.width, y = vb.y + ((e.clientY - r.top) / r.height) * vb.height;
      const near = scene.ask.choices.map((c, i) => ({ i, p: c.actor !== undefined ? ctl.current?.where(c.actor) : null }))
        .filter((c) => c.p).map((c) => ({ ...c, d: Math.hypot(c.p!.x - x, c.p!.y - y) })).sort((a, b) => a.d - b.d)[0];
      if (near && near.d < 40) choose(near.i);
      return;
    }
    toggle();
  };
  const toggle = () => {
    if (reducedMotion() || !ctl.current) return;
    if (playing) { ctl.current.halt(); setPlaying(false); } else { ctl.current.play(slow ? 0.5 : 1); setPlaying(true); }
  };
  const caption = phase === 'ask' && scene.ask ? scene.ask.q[lang] : def.steps[step]?.[lang];
  return (
    <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7" style={SCENE_COLOURS}>
      <h2 className="m-0 text-lead font-semibold">{scene.title[lang]}</h2>
      <div className="relative [@media(orientation:landscape)_and_(max-height:520px)]:-mx-5">
        <svg ref={svg} viewBox={`0 0 360 ${scene.height ?? 240}`} style={{ direction: 'ltr' }} role="img" aria-label={scene.title[lang]}
             onClick={tapDrawing}
             className="block h-auto w-full cursor-pointer overflow-hidden rounded-control [@media(orientation:landscape)_and_(max-height:520px)]:max-h-[78vh]" />
      </div>
      <p className="m-0 min-h-[3.2em] text-lead font-medium leading-snug" aria-live="polite">{caption}</p>

      {phase === 'ask' && scene.ask ? (
        <div className="flex flex-col gap-2">
          <div className="grid gap-2 sm:grid-cols-2">
            {scene.ask.choices.map((c, i) => (
              <button key={i} type="button" onClick={() => choose(i)}
                      className="min-h-12 rounded-control border border-field bg-sheet px-4 py-2 text-start text-body font-medium transition-transform duration-150 active:scale-[.98] motion-reduce:transition-none hover:border-[var(--t)]">
                {c.label[lang]}
              </button>
            ))}
          </div>
          <button type="button" onClick={() => { setAnswer(null); setPhase('play'); }} className="min-h-11 self-start text-body text-ink-soft">{t('scenes.skip')}</button>
        </div>
      ) : (
        <>
          {answer ? (
            <p className={`m-0 rounded-control px-3 py-2 text-body font-semibold ${answer.right ? 'bg-[color-mix(in_srgb,var(--color-in-force)_12%,var(--color-sheet))] text-in-force' : 'bg-amended-wash text-amended'}`}>
              {answer.right ? t('scenes.right') : scene.ask?.because ? scene.ask.because[lang] : t('scenes.wrong')}
            </p>
          ) : null}
          <div className="flex items-center gap-3" dir="ltr">
            <button type="button" onClick={toggle} disabled={reducedMotion()} aria-label={t(playing ? 'scenes.pause' : 'scenes.play')}
                    className="grid size-11 shrink-0 place-items-center rounded-full bg-[var(--t)] text-on-stamp disabled:opacity-40">
              <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                {playing ? <path d="M7 5h4v14H7zM13 5h4v14h-4z" /> : <path d="M8 5v14l11-7z" />}
              </svg>
            </button>
            <div className="relative flex-1">
              <input type="range" min={0} max={def.dur} step={20} value={Math.min(time, def.dur)} aria-label={t('scenes.scrub')}
                     onChange={(e) => { ctl.current?.show(Number(e.target.value)); setPlaying(false); }}
                     className="w-full accent-[var(--t)]" />
              <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 -bottom-1 h-2">
                {def.steps.map((s, i) => <span key={i} className={`absolute top-0 h-2 w-0.5 ${i <= step ? 'bg-[var(--t)]' : 'bg-field'}`} style={{ left: `${(s.t / def.dur) * 100}%` }} />)}
              </div>
            </div>
            <button type="button" aria-pressed={slow} onClick={() => setSlow(!slow)} disabled={reducedMotion()}
                    className={`min-h-11 shrink-0 rounded-full border px-3 text-meta ${slow ? 'border-[var(--t)] bg-wash' : 'border-field'}`}>{t('scenes.slow')}</button>
          </div>
          {phase === 'wrong' ? (
            <Button variant="primary" className="self-start" onClick={() => transition(() => { setAnswer(null); setPhase('play'); })}>{t('scenes.showRight')}</Button>
          ) : scene.ask && answer ? (
            <button type="button" onClick={() => { setAnswer(null); setPhase('ask'); }} className="min-h-11 self-start text-body font-medium text-stamp">{t('scenes.again')}</button>
          ) : null}
        </>
      )}

      <div className="flex flex-col gap-2 border-t border-rule pt-3">
        <p className="m-0 text-body">{scene.rule[lang]}</p>
        {cost ? <p className="m-0 text-body font-medium">{cost}</p> : null}
        <SourceFold paths={scene.cites} label={articleLabel} />
        {scene.offence ? <Button className="self-start" to={toolLink(`/topics/${slug}/tools/fine`, { o: scene.offence })}>{t('scenes.toFine')}</Button> : null}
      </div>
    </section>
  );
}

/** «مشاهد الطريق» (R8 of the road plan): each rule as a scene drawn in code from its article, shown before a
 *  specialist's review (Q2), which the page says. The scene in the address (`?s=`), so a link opens it. */
export default function ScenesPage({ slug }: { slug: string }) {
  const { t, i18n } = useRoadT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const [s, set] = useToolState({ s: SCENES[0].key });
  const scene = SCENES.find((x) => x.key === s.s) ?? SCENES[0];
  return (
    <KitPage slug={slug} title={t('scenes.title')} lead={t('scenes.lead')}>
      <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1" role="group" aria-label={t('scenes.title')}>
        {SCENES.map((x) => (
          <button key={x.key} type="button" aria-pressed={x.key === scene.key} onClick={() => transition(() => set({ s: x.key }))}
                  className={`h-11 shrink-0 rounded-full border px-4 text-body ${x.key === scene.key ? 'border-ink bg-ink text-sheet' : 'border-rule bg-sheet'}`}>
            {x.title[lang]}
          </button>
        ))}
      </div>
      <SceneView key={scene.key} scene={scene} slug={slug} />
    </KitPage>
  );
}
