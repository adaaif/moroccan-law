import { useEffect, useRef, useState } from 'react';
import { usePreview } from '@/features/corpus/corpus.api';
import { Button } from '@/shared/components/ui';
import { mount } from './scenes/engine';
import { SCENES, SIGN_CARDS } from './scenes/data';
import { SCENE_COLOURS, SIGNS } from './scenes/signs';
import { useRoadT } from './strings';

type Kind = 'scene' | 'sign' | 'figure';
const q = (s: string) => `'${s.replace(/'/g, "''")}'`;

/** The practice cards' workshop on the reviewer's desk (Q1 of the road tools review): a person picks a scene and its
 *  moment, or a sign, writes the question, the choices (the first is right) and the article's own words, sees the card
 *  as readers will, checks that the cited article is on the site, and copies the card's YAML into cards.yaml. Nothing is
 *  written by a model (docs/rules.md, «No chat about the law»); a batch reaches readers once another person approves
 *  it. */
export default function CardWorkshop() {
  const { t } = useRoadT();
  const [kind, setKind] = useState<Kind>('scene');
  const [scene, setScene] = useState(SCENES[0].key);
  const [sign, setSign] = useState(SIGN_CARDS[0].key);
  const [at, setAt] = useState(SCENES[0].still ?? 0);
  const [key, setKey] = useState('');
  const [question, setQuestion] = useState({ ar: '', fr: '' });
  const [choices, setChoices] = useState([{ ar: '', fr: '' }, { ar: '', fr: '' }, { ar: '', fr: '' }]);
  const [quote, setQuote] = useState({ ar: '', fr: '' });
  const [cite, setCite] = useState('/ma/decret/2-10-420/art_36');
  const [copied, setCopied] = useState(false);
  const svg = useRef<SVGSVGElement>(null);
  const def = SCENES.find((s) => s.key === scene)!;
  const preview = usePreview(cite.startsWith('/ma/') ? cite : null);
  useEffect(() => {
    if (kind !== 'scene' || !svg.current) return;
    const c = mount(svg.current, def, 'ar', () => undefined, () => undefined);
    c.show(at);
    return () => c.halt();
  }, [kind, def, at]);
  const yaml = [
    `      - key: ${key || 'new-card'}`,
    `        kind: ${kind}`,
    ...(kind === 'scene' ? [`        scene: ${scene}`, `        at: ${at}`] : kind === 'sign' ? [`        sign: ${sign}`] : []),
    `        question: {ar: ${q(question.ar)}, fr: ${q(question.fr)}}`,
    `        choices:`,
    ...choices.map((c) => `          - {ar: ${q(c.ar)}, fr: ${q(c.fr)}}`),
    `        quote: {ar: ${q(quote.ar)}, fr: ${q(quote.fr)}}`,
    `        cites: [${cite}]`,
  ].join('\n');
  const field = 'h-11 w-full rounded-control border border-field bg-sheet px-3 text-body';
  const pair = (v: { ar: string; fr: string }, set: (x: { ar: string; fr: string }) => void, label: string) => (
    <div className="grid gap-2 sm:grid-cols-2">
      <input aria-label={`${label} (ar)`} placeholder={`${label} — ar`} value={v.ar} dir="rtl" onChange={(e) => set({ ...v, ar: e.target.value })} className={field} />
      <input aria-label={`${label} (fr)`} placeholder={`${label} — fr`} value={v.fr} dir="ltr" onChange={(e) => set({ ...v, fr: e.target.value })} className={field} />
    </div>
  );
  return (
    <section className="flex flex-col gap-4 rounded-card bg-sheet px-5 py-5" style={SCENE_COLOURS}>
      <h2 className="m-0 text-h3 font-bold">{t('workshop.title')}</h2>
      <p className="m-0 text-body text-ink-soft">{t('workshop.lead')}</p>
      <div className="flex flex-wrap gap-2">
        {(['scene', 'sign', 'figure'] as Kind[]).map((k) => (
          <button key={k} type="button" aria-pressed={kind === k} onClick={() => setKind(k)}
                  className={`min-h-11 rounded-full border px-4 text-body ${kind === k ? 'border-ink bg-ink text-sheet' : 'border-rule'}`}>{t(`workshop.kinds.${k}`)}</button>
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="flex flex-col gap-3">
          <input aria-label={t('workshop.key')} placeholder={t('workshop.key')} value={key} dir="ltr" onChange={(e) => setKey(e.target.value.replace(/[^a-z0-9-]/g, ''))} className={field} />
          {kind === 'scene' ? (
            <>
              <select value={scene} onChange={(e) => { setScene(e.target.value); setAt(SCENES.find((s) => s.key === e.target.value)?.still ?? 0); }} className={field}>
                {SCENES.map((s) => <option key={s.key} value={s.key}>{s.title.ar}</option>)}
              </select>
              <label className="flex flex-col gap-1 text-meta text-ink-soft">{t('workshop.at', { ms: at })}
                <input type="range" min={0} max={def.dur} step={50} value={at} onChange={(e) => setAt(Number(e.target.value))} dir="ltr" />
              </label>
            </>
          ) : kind === 'sign' ? (
            <select value={sign} onChange={(e) => setSign(e.target.value)} className={field}>
              {SIGN_CARDS.map((s) => <option key={s.key} value={s.key}>{s.name.ar}</option>)}
            </select>
          ) : null}
          {pair(question, setQuestion, t('workshop.question'))}
          {choices.map((c, i) => <div key={i}>{pair(c, (x) => setChoices(choices.map((y, j) => (j === i ? x : y))), i === 0 ? t('workshop.right') : t('workshop.choice', { n: i + 1 }))}</div>)}
          {pair(quote, setQuote, t('workshop.quote'))}
          <input aria-label={t('workshop.cite')} value={cite} dir="ltr" onChange={(e) => setCite(e.target.value.trim())} className={field} />
          <p className={`m-0 text-meta ${preview.data ? 'text-in-force' : 'text-amended'}`}>
            {preview.isLoading ? '…' : preview.data ? `${t('workshop.found')}: ${preview.data.label ?? ''}` : t('workshop.missing')}
          </p>
        </div>
        <div className="flex flex-col gap-3">
          <span className="text-meta font-semibold text-ink-soft">{t('workshop.preview')}</span>
          <div className="flex flex-col gap-3 rounded-card border border-rule px-4 py-4">
            {kind === 'scene' ? <svg ref={svg} viewBox={`0 0 360 ${def.height ?? 240}`} style={{ direction: 'ltr' }} className="w-full rounded-control" /> : null}
            {kind === 'sign' ? <svg viewBox="0 0 100 100" width="120" height="120" className="self-center" dangerouslySetInnerHTML={{ __html: SIGNS[sign]() }} /> : null}
            <p className="m-0 text-lead font-semibold">{question.ar || '…'}</p>
            {choices.map((c, i) => <p key={i} className={`m-0 rounded-control border px-3 py-2 text-body ${i === 0 ? 'border-in-force' : 'border-rule'}`}>{c.ar || '…'}</p>)}
            {quote.ar ? <blockquote lang="ar" dir="rtl" className="m-0 border-s-4 border-stamp ps-3 font-law text-body">{quote.ar}</blockquote> : null}
          </div>
          <pre dir="ltr" className="m-0 max-h-72 overflow-auto rounded-control bg-paper p-3 text-meta">{yaml}</pre>
          <Button onClick={() => { void navigator.clipboard?.writeText(yaml).then(() => setCopied(true)).catch(() => setCopied(false)); }}>
            {copied ? t('workshop.copied') : t('workshop.copy')}
          </Button>
        </div>
      </div>
    </section>
  );
}
