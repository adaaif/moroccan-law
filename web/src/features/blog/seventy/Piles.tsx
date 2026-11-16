import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';
import { longDate } from '@/features/corpus/format';
import type { SeventyPost } from '../blog.api';
import { columnAt, decadeTicks, n, spaced, stepFor, useTheme, useWidth } from '../viz';
import { yearRows } from './rows';

type Pick = { i: number; j: number | null } | null;
type Note = { i: number; text: string };

const FONT = '500 14px "Readex Pro", sans-serif';

/**
 * The post's one picture: a pile of paper a year from No. 1 (1913), each issue a sheet as thick as its pages, laid from
 * January at the bottom to December at the top; the «bis» issues in the Bulletin's violet. The piles rise year by year
 * once, as the page opens (still, with reduced motion). A tap names the sheet under the finger, the arrows walk the
 * years and the issues, Enter opens the issue. Canvas for the 5,470 sheets; the notes and the years drawn over it.
 */
export default function Piles({ post }: { post: SeventyPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  // The years run left to right on an Arabic page too (the chart rule of 1 Nov 2026); the notes read in the page's language.
  const rtl = false;
  const textRtl = lang !== 'fr';
  const navigate = useNavigate();
  const theme = useTheme();
  const [ref, width] = useWidth<HTMLDivElement>(900);
  const canvas = useRef<HTMLCanvasElement>(null);
  const progress = useRef(0);
  const [pick, setPick] = useState<Pick>(null);

  const f = post.figures;
  const [first, last] = f.span;
  const years = useMemo(() => yearRows(f), [f]);
  const issues = useMemo(() => years.map((y) => f.issues[String(y.year)] ?? []), [f, years]);
  const count = years.length;
  const phone = width < 640;
  const band = phone ? 66 : 70;
  const plot = phone ? 280 : 420;
  const base = band + plot;
  const height = base + 28;
  const max = Math.max(...years.map((y) => y.pages));
  const k = plot / max;
  const step = width / count;
  const bw = Math.max(2, step * (phone ? 0.8 : 0.7));
  const left = useCallback((i: number) => (rtl ? width - (i + 1) * step : i * step) + (step - bw) / 2, [rtl, width, step, bw]);

  const draw = useCallback(() => {
    const c = canvas.current;
    if (!c) return;
    const dpr = window.devicePixelRatio || 1;
    if (c.width !== Math.round(width * dpr)) { c.width = Math.round(width * dpr); c.height = Math.round(height * dpr); }
    const ctx = c.getContext('2d');
    if (!ctx) return;
    const css = getComputedStyle(c);
    const tone = (name: string) => css.getPropertyValue(name).trim();
    const paper = [tone('--bp-sheet-a'), tone('--bp-sheet-b')];
    const bis = [tone('--bp-bis-a'), tone('--bp-bis-b')];
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);
    const p = progress.current;
    years.forEach((y, i) => {
      // Each year starts after the one before it, so the piles rise in reading order.
      const g = Math.max(0, Math.min(1, (p - (i / count) * 0.65) / 0.35));
      const top = y.pages * k * (1 - (1 - g) ** 3);
      let cum = 0;
      issues[i].forEach((s, j) => {
        if (cum >= top) return;
        const h = Math.min(s[3] * k, top - cum);
        ctx.fillStyle = (s[1] ? bis : paper)[j % 2];
        ctx.fillRect(left(i), base - cum - h, bw, h);
        cum += s[3] * k;
      });
    });
    ctx.fillStyle = tone('--color-ink');
    ctx.fillRect(0, base, width, 1);
    if (pick && p >= 1) {
      const x = left(pick.i);
      ctx.strokeStyle = tone('--color-ink');
      ctx.lineWidth = 2;
      if (pick.j === null) {
        ctx.strokeRect(x - 1.5, base - years[pick.i].pages * k - 1.5, bw + 3, years[pick.i].pages * k + 1.5);
      } else {
        const below = issues[pick.i].slice(0, pick.j).reduce((a, s) => a + s[3], 0) * k;
        const h = Math.max(2, issues[pick.i][pick.j][3] * k);
        ctx.strokeRect(x - 1.5, base - below - h - 1, bw + 3, h + 1);
      }
    }
  }, [width, height, years, issues, count, k, base, bw, left, pick]);

  // The one moment of motion: the piles rise as the page opens, once.
  useEffect(() => {
    if (progress.current >= 1 || !width) { draw(); return; }
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) { progress.current = 1; draw(); return; }
    let frame = 0;
    const start = performance.now();
    const tick = (now: number) => {
      progress.current = Math.min(1, (now - start) / 1800);
      draw();
      if (progress.current < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [draw, width, theme]);

  // The notes: the first year, the thinnest, the year it came out twice a week, the thickest with its thickest issue.
  const notes = useMemo<Note[]>(() => {
    const at = (year: number) => years.findIndex((y) => y.year === year);
    // The thinnest year since independence: the first years of 1913 count their months from February.
    const since = years.filter((y) => y.year >= 1956);
    const least = since.reduce((a, y) => (y.pages < a.pages ? y : a));
    const y56 = years.find((y) => y.year === 1956);
    const most = years.reduce((a, y) => (y.pages > a.pages ? y : a));
    const one = Math.max(...issues[at(most.year)].map((s) => s[3]));
    const twice = Number(post.weekdays[post.weekdays.length - 1].from.slice(0, 4));
    const out: Note[] = [
      { i: 0, text: t('seventy.piles.notes.first', { year: first, pages: n(years[0].pages, lang) }) },
      { i: at(least.year), text: t(phone ? 'seventy.piles.notes.leastShort' : 'seventy.piles.notes.least', { year: least.year, pages: n(least.pages, lang) }) },
      { i: at(most.year), text: t(phone ? 'seventy.piles.notes.mostShort' : 'seventy.piles.notes.most', { year: most.year, pages: n(most.pages, lang), one: n(one, lang) }) },
    ];
    if (!phone) out.splice(2, 0, { i: at(twice), text: t('seventy.piles.notes.twice', { year: twice }) });
    if (!phone && y56) out.splice(1, 0, { i: at(1956), text: t('seventy.piles.notes.y56', { year: 1956, pages: n(y56.pages, lang) }) });
    return out;
  }, [years, issues, post.weekdays, first, lang, phone, t]);

  const placed = useMemo(() => {
    // On the server (the landing pages drawn at each deploy) no canvas: the notes are placed by an estimate.
    const ctx = typeof document === 'undefined' ? null : document.createElement('canvas').getContext('2d');
    if (ctx) ctx.font = FONT;
    const rows: [number, number][][] = [[], [], []];
    return notes.map((note) => {
      const w = (ctx ? ctx.measureText(note.text).width : note.text.length * 7.5) + 2;
      const x = left(note.i) + bw / 2;
      // A note reads away from its pile in the page's direction, and turns back at the edge.
      let a = rtl ? x + 6 - w : x - 6;
      if (a < 0) a = x - 6;
      if (a + w > width) a = x + 6 - w;
      const row = Math.max(0, rows.findIndex((r) => r.every(([p, q]) => a + w + 8 < p || a > q + 8)));
      rows[row].push([a, a + w]);
      return { ...note, x, a, w, y: 16 + row * 20 };
    });
  }, [notes, left, bw, rtl, width]);

  const at = (e: PointerEvent<HTMLDivElement>): Pick => {
    const box = e.currentTarget.getBoundingClientRect();
    const i = columnAt(e.clientX - box.left, box.width, count, rtl);
    const v = (base - (e.clientY - box.top)) / k;
    if (v < 0) return null;
    let cum = 0;
    const j = issues[i].findIndex((s) => (cum += s[3]) >= v);
    return { i, j: j < 0 ? null : j };
  };
  const key = (e: KeyboardEvent<HTMLDivElement>) => {
    const d = stepFor(e, rtl);
    const cur = pick ?? { i: d < 0 ? count : -1, j: null };
    if (d) {
      e.preventDefault();
      setPick({ i: Math.max(0, Math.min(count - 1, cur.i + d)), j: null });
    } else if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
      e.preventDefault();
      const i = Math.max(0, cur.i);
      const top = issues[i].length - 1;
      const j = cur.j === null ? (e.key === 'ArrowUp' ? 0 : top) : cur.j + (e.key === 'ArrowUp' ? 1 : -1);
      setPick({ i, j: Math.max(0, Math.min(top, j)) });
    } else if (e.key === 'Enter' && pick?.j != null) {
      navigate(issuePath(issues[pick.i][pick.j]));
    }
  };

  const sentence = (() => {
    if (!pick) return t('seventy.piles.hint');
    const y = years[pick.i];
    if (pick.j === null) {
      return t('seventy.piles.year', { year: y.year, issues: n(y.issues, lang), pages: n(y.pages, lang), texts: n(y.texts, lang) });
    }
    const s = issues[pick.i][pick.j];
    const md = String(s[2]).padStart(4, '0');
    const what = post.issues[issueKey(s)]?.[lang === 'fr' ? 'fr' : 'ar'];
    return (
      <>
        {t('seventy.piles.issue', { number: issueLabel(s, lang), date: longDate(`${y.year}-${md.slice(0, 2)}-${md.slice(2)}`, lang),
                                    pages: n(s[3], lang), texts: n(s[4], lang) })}
        {what ? ` ${what}.` : ''}{' '}
        <Link to={issuePath(s)}>{t('fig.open')}</Link>
      </>
    );
  })();

  const ticks = decadeTicks(first, last);
  return (
    <div className="bp-piles">
      <div ref={ref} className="bp-piles-plot" tabIndex={0} role="img"
           aria-label={t('seventy.piles.aria', { from: first, to: last, count: years.length })}
           onPointerMove={(e) => e.pointerType === 'mouse' && setPick(at(e))} onPointerDown={(e) => setPick(at(e))}
           onKeyDown={key} style={{ height }}>
        <canvas ref={canvas} style={{ width, height }} aria-hidden="true" />
        <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
          {placed.map((p) => (
            <g key={p.i}>
              <line className="bp-leader" x1={p.x} x2={p.x} y1={p.y + 5} y2={base - years[p.i].pages * k - 5} />
              <text x={textRtl ? p.a + p.w : p.a} y={p.y} direction={textRtl ? 'rtl' : 'ltr'} textAnchor="start">{p.text}</text>
            </g>
          ))}
          {/* The decades that keep their distance (52 px), the first and last years kept first: 113 years on a phone. */}
          {spaced(ticks, (i) => left(i) + bw / 2).map(([i, year]) => {
            const x = left(+i) + bw / 2;
            return <text key={i} x={Math.min(Math.max(x, 18), width - 18)} y={height - 6} textAnchor="middle" className="is-soft">{year}</text>;
          })}
        </svg>
      </div>
      <p className="bp-pick" aria-live="polite">{sentence}</p>
    </div>
  );
}

const issueKey = (s: number[]) => (s[1] ? `${s[0]}-bis` : String(s[0]));
const issuePath = (s: number[]) => `/bo/general_ar/${issueKey(s)}`;
const issueLabel = (s: number[], lang: string) => `${s[0]}${s[1] ? (lang === 'fr' ? ' bis' : ' مكرر') : ''}`;
