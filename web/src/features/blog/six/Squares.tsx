import { useMemo, useState, type KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';
import type { SixPost } from '../blog.api';
import { n, stepFor, useWidth } from '../viz';

type Pick = { c: number; k: number } | null;
type Cell = { c: number; k: number; x: number; y: number; state: number };

/**
 * The post's one picture: the six constitutions side by side, each a column with a square for each article, title by
 * title from the top, coloured by what became of it since the constitution before (the corpus's lineage): ink kept
 * word for word, grey rewritten, violet new, pale unsure. The first and last constitutions' titles are named beside
 * them where the screen is wide enough; a tap names any square and opens its article.
 */
export default function Squares({ post }: { post: SixPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const rtl = lang !== 'fr';
  const navigate = useNavigate();
  const [ref, width] = useWidth<HTMLDivElement>(900);
  const [pick, setPick] = useState<Pick>(null);
  const six = post.figures.constitutions;
  const names = useMemo(() => Object.fromEntries(post.themes.map((th) => [th.key, lang === 'fr' ? th.fr : th.ar])), [post.themes, lang]);

  const phone = width < 600;
  const labels = width >= 900 ? 2 : width >= 600 ? 1 : 0;
  const per = phone ? 4 : 6;
  const s = phone ? 7 : 11;
  const gap = 2;
  const group = phone ? 4 : 6;
  const head = 44;
  const cw = per * (s + gap) - gap;
  // The titles beside the outer columns take the room their longest name needs, measured in the chart's type.
  const room = useMemo(() => {
    const ctx = typeof document === 'undefined' ? null : document.createElement('canvas').getContext('2d');
    if (ctx) ctx.font = '14px "Readex Pro", sans-serif';
    const widest = (c: number) => Math.max(0, ...six[c].titles.map((ti) => {
      const text = names[ti.theme] || ti.name;
      return ctx ? ctx.measureText(text).width : text.length * 7.5;
    }));
    return { first: Math.min(230, widest(0) + 26), last: Math.min(230, widest(six.length - 1) + 26) };
  }, [six, names]);
  const side = (end: boolean) => (labels === 2 || (labels === 1 && end) ? (end ? room.last : room.first) : 0);
  const startSpace = side(false), endSpace = side(true);
  const colGap = Math.max(10, (width - startSpace - endSpace - six.length * cw) / (six.length - 1));
  const colX = (i: number) => (rtl ? width - startSpace - (i + 1) * cw - i * colGap : startSpace + i * (cw + colGap));

  const layout = useMemo(() => {
    const cells: Cell[] = [];
    const groups: { c: number; title: number; y: number }[] = [];
    let height = 0;
    six.forEach((con, c) => {
      let y = head, col = 0, title = -1;
      con.squares.forEach(([, ti, state], k) => {
        if (ti !== title) {
          if (title >= 0) y += (col ? s + gap : 0) + group;
          col = 0; title = ti;
          groups.push({ c, title: ti, y });
        }
        const dx = rtl ? cw - (col + 1) * (s + gap) + gap : col * (s + gap);
        cells.push({ c, k, x: colX(c) + dx, y, state });
        col += 1;
        if (col === per) { col = 0; y += s + gap; }
      });
      height = Math.max(height, y + s + 8);
    });
    return { cells, groups, height };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [six, width, rtl]);

  // The titles beside the first and last constitutions, pushed apart so none covers another.
  const notes = useMemo(() => {
    const out: { c: number; title: number; y: number; at: number; text: string }[] = [];
    const sides = labels === 2 ? [0, six.length - 1] : labels === 1 ? [six.length - 1] : [];
    for (const c of sides) {
      let last = -Infinity;
      for (const g of layout.groups.filter((x) => x.c === c)) {
        const title = six[c].titles[g.title];
        const at = Math.max(g.y + s / 2, last + 18);
        last = at;
        out.push({ c, title: g.title, y: g.y + s / 2, at, text: names[title.theme] || title.name });
      }
    }
    return out;
  }, [layout, labels, six, s, names]);
  const height = Math.max(layout.height, ...notes.map((x) => x.at + 12));

  const sentence = (() => {
    if (!pick) return t('six.hero.hint');
    const con = six[pick.c];
    const [number, ti, state] = con.squares[pick.k];
    const title = con.titles[ti];
    const states = t('six.hero.states', { returnObjects: true, prev: six[pick.c - 1]?.year }) as string[];
    return (
      <>
        {t('six.hero.pick', { year: con.year, n: number, title: names[title.theme] || title.name, state: states[state] })}{' '}
        <Link to={`${con.path}/art_${number}`}>{t('six.hero.read')}</Link>
      </>
    );
  })();

  const key = (e: KeyboardEvent<SVGSVGElement>) => {
    const d = stepFor(e, rtl);
    const cur = pick ?? { c: 0, k: 0 };
    if (d) {
      e.preventDefault();
      const c = Math.max(0, Math.min(six.length - 1, cur.c + d));
      setPick({ c, k: Math.min(cur.k, six[c].squares.length - 1) });
    } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      setPick({ c: cur.c, k: Math.max(0, Math.min(six[cur.c].squares.length - 1, cur.k + (e.key === 'ArrowDown' ? 1 : -1))) });
    } else if (e.key === 'Enter' && pick) {
      navigate(`${six[pick.c].path}/art_${six[pick.c].squares[pick.k][0]}`);
    }
  };
  const chosen = pick ? layout.cells.find((x) => x.c === pick.c && x.k === pick.k) : null;

  return (
    <div className="bp-squares">
      <div ref={ref} className="bp-plot">
        <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" tabIndex={0} onKeyDown={key}
             aria-label={t('six.hero.aria', { first: six[0].year, last: six[six.length - 1].year })}>
          {six.map((con, c) => (
            <g key={con.year}>
              <text x={colX(c) + cw / 2} y={16} textAnchor="middle" className="is-strong">{con.year}</text>
              <text x={colX(c) + cw / 2} y={34} textAnchor="middle" direction={rtl ? 'rtl' : 'ltr'} className="is-soft">
                {phone ? n(con.articles, lang) : t('six.hero.count', { n: n(con.articles, lang) })}
              </text>
            </g>
          ))}
          {layout.cells.map((cell) => (
            <rect key={`${cell.c}-${cell.k}`} x={cell.x} y={cell.y} width={s} height={s} rx={1.5} className={`sq s${cell.state}`}
                  onPointerDown={() => setPick({ c: cell.c, k: cell.k })}
                  onPointerEnter={(e) => e.pointerType === 'mouse' && setPick({ c: cell.c, k: cell.k })} />
          ))}
          {chosen ? <rect x={chosen.x - 2} y={chosen.y - 2} width={s + 4} height={s + 4} rx={2.5} className="sq-pick" /> : null}
          {notes.map((note) => {
            const x0 = note.c === 0 ? colX(0) + (rtl ? cw : 0) : colX(note.c) + (rtl ? 0 : cw);
            const outward = (note.c === 0) === rtl ? 1 : -1;
            const xt = x0 + outward * 14;
            return (
              <g key={`${note.c}-${note.title}`} className="sq-note">
                <path d={`M${x0 + outward * 2},${note.y} L${xt - outward * 4},${note.at}`} />
                <text x={xt} y={note.at + 5} direction={rtl ? 'rtl' : 'ltr'} textAnchor={(outward === 1) === rtl ? 'end' : 'start'}>{note.text}</text>
              </g>
            );
          })}
        </svg>
      </div>
      <p className="bp-pick" aria-live="polite">{sentence}</p>
    </div>
  );
}
