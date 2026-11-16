import { Link } from 'react-router-dom';
import { pick, refPath, useKitT, type Named, type Series } from './api';
import { useTween } from './motion';

export type Story = {
  year: number; value: number; change?: number; from: string; page?: number; words: Named;
  who?: { key: string; share: number; label: Named; rule?: Named; to?: string }[];
  who_from?: { from: string; page?: number }; goal?: Named;
};

/** A series' year told first (N1, N2 of the road tools review): the newest figure, large, with its change; who it
 *  was, as one bar of shares, each part leading to the rule that is theirs; the goal the authorities set, said and
 *  never drawn. Every figure names its report and page, as the chart under it does. */
export default function SeriesStory({ s, slug }: { s: Series & { story?: Story }; slug: string }) {
  const { t, i18n } = useKitT();
  const lang = i18n.language;
  const st = s.story;
  const n = useTween(st?.value ?? 0, 900);
  if (!st) return null;
  const nf = new Intl.NumberFormat(lang === 'fr' ? 'fr-MA' : 'ar-MA', { maximumFractionDigits: 2 });
  const source = (from: string, page?: number) => `${s.files[from]?.title ?? from}${page ? ` · ${t('page', { page })}` : ''}`;
  const tones = ['var(--t)', 'var(--color-chart-1)', 'var(--color-chart-2)', 'var(--color-ink-soft)'];
  return (
    <section className="flex flex-col gap-4 rounded-card bg-sheet px-5 py-5 sm:px-7">
      <div className="flex flex-col gap-1">
        <p className="m-0 text-display font-bold leading-none tabular-nums text-[color:var(--t)]">{nf.format(n)}</p>
        <p lang={lang} className="m-0 text-lead font-medium">{pick(st.words, lang)}</p>
        {st.change ? <p className="m-0 text-body text-repealed"><bdi dir="ltr">+{nf.format(st.change)}%</bdi> {t('story.change', { year: st.year - 1 })}</p> : null}
        <p className="m-0 text-meta text-ink-soft">{source(st.from, st.page)}</p>
      </div>
      {st.who?.length ? (
        <div className="flex flex-col gap-3">
          <h3 className="m-0 text-lead font-semibold">{t('story.who', { year: st.year })}</h3>
          <div aria-hidden="true" className="flex h-5 overflow-hidden rounded-full bg-rule">
            {st.who.map((w, i) => (
              <span key={w.key} style={{ width: `${w.share}%`, background: tones[i % tones.length], animationDelay: `${i * 80}ms` }}
                    className="block h-full motion-safe:animate-[rise_480ms_ease-out_both]" />
            ))}
          </div>
          <ul className="m-0 flex list-none flex-col gap-2 p-0">
            {st.who.map((w, i) => (
              <li key={w.key} className="flex items-start gap-3">
                <span aria-hidden="true" className="mt-1.5 size-3 shrink-0 rounded-full" style={{ background: tones[i % tones.length] }} />
                <span className="flex min-w-0 flex-col">
                  <span lang={lang} className="text-body"><b className="tabular-nums">{nf.format(w.share)}%</b> {pick(w.label, lang)}</span>
                  {w.rule ? (
                    w.to ? <Link to={refPath(slug, w.to)} lang={lang} className="text-meta font-medium">{pick(w.rule, lang)} ›</Link>
                      : <span lang={lang} className="text-meta text-ink-soft">{pick(w.rule, lang)}</span>
                  ) : null}
                </span>
              </li>
            ))}
          </ul>
          {st.who_from ? <p className="m-0 text-meta text-ink-soft">{source(st.who_from.from, st.who_from.page)}</p> : null}
        </div>
      ) : null}
      {st.goal ? <p lang={lang} className="m-0 text-body text-ink-soft">{pick(st.goal, lang)}</p> : null}
    </section>
  );
}
