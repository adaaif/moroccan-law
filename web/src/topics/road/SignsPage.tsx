import { useEffect, useState } from 'react';
import { Button } from '@/shared/components/ui';
import { Sheet } from '@/shared/components/Sheet';
import { KitPage } from '../kit/parts';
import { reducedMotion, transition } from '../kit/motion';
import { SourceFold } from '../kit/tool/parts';
import { toolLink } from '../kit/tool/state';
import { SIGN_CARDS, SIGN_FAMILY, FAMILIES, type SignCard } from './scenes/data';
import { SCENE_COLOURS, SIGNS } from './scenes/signs';
import { articleLabel, useRoadT } from './strings';

const SEEN = 'law.road.signs.sorted';

/** «العلامات» (R9 of the road plan; G1–G3 of the road tools review): the signs drawn from joint order 2805.14's
 *  words. The first visit shows them mixed, then they sort themselves into their families — the shape says what a
 *  sign does before its picture does —; a tap opens a sign big, with what it requires, its scene and its cost. The
 *  order's whole catalogue comes family by family once the order is on the site (G3). */
export default function SignsPage({ slug }: { slug: string }) {
  const { t, i18n } = useRoadT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const [sorted, setSorted] = useState(() => { try { return reducedMotion() || localStorage.getItem(SEEN) === '1'; } catch { return true; } });
  const [open, setOpen] = useState<SignCard | null>(null);
  useEffect(() => {
    if (sorted) return;
    const id = setTimeout(() => { transition(() => setSorted(true)); try { localStorage.setItem(SEEN, '1'); } catch { /* private window */ } }, 900);
    return () => clearTimeout(id);
  }, [sorted]);
  const tile = (s: SignCard) => (
    <li key={s.key} style={{ viewTransitionName: `sign-${s.key}` }}>
      <button type="button" onClick={() => setOpen(s)}
              className="flex h-full w-full flex-col items-center gap-2 rounded-card bg-sheet px-3 py-3 text-center hover:ring-2 hover:ring-[var(--t)]">
        <svg viewBox="0 0 100 100" width="64" height="64" role="img" aria-label={s.name[lang]} dangerouslySetInnerHTML={{ __html: SIGNS[s.key]() }} />
        <span className="text-body font-semibold leading-snug">{s.name[lang]}</span>
      </button>
    </li>
  );
  return (
    <KitPage slug={slug} title={t('signs.title')} lead={t('signs.lead')}>
      <div style={SCENE_COLOURS} className="flex flex-col gap-4">
        {!sorted ? (
          <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5">
            <p className="m-0 text-lead font-medium">{t('signs.mixed')}</p>
            <ul className="m-0 grid list-none grid-cols-3 gap-2 p-0 sm:grid-cols-4">{SIGN_CARDS.map(tile)}</ul>
          </section>
        ) : FAMILIES.map((f) => {
          const here = SIGN_CARDS.filter((s) => SIGN_FAMILY[s.key] === f.key);
          if (!here.length) return null;
          return (
            <section key={f.key} className="flex flex-col gap-3 rounded-card bg-paper">
              <div className="flex items-center gap-3">
                <svg viewBox="0 0 100 100" width="36" height="36" aria-hidden="true" dangerouslySetInnerHTML={{ __html: f.shape }} />
                <div className="flex flex-col">
                  <h2 className="m-0 text-lead font-semibold">{f.name[lang]}</h2>
                  <p className="m-0 text-meta text-ink-soft">{f.says[lang]}</p>
                </div>
              </div>
              <ul className="m-0 grid list-none grid-cols-2 gap-2 p-0 sm:grid-cols-4">{here.map(tile)}</ul>
            </section>
          );
        })}
        <p className="m-0 text-meta text-ink-soft">{t('signs.source')}</p>
        <p className="m-0 text-meta text-ink-soft">{t('signs.more')}</p>
      </div>
      {open ? <SignSheet sign={open} slug={slug} onClose={() => setOpen(null)} /> : null}
    </KitPage>
  );
}

/** A sign opened big (G2): what it requires, its code, the articles, its scene and the fine for ignoring it. */
function SignSheet({ sign, slug, onClose }: { sign: SignCard; slug: string; onClose: () => void }) {
  const { t, i18n } = useRoadT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  return (
    <Sheet centered label={sign.name[lang]} onClose={onClose}>
      <div className="flex flex-col items-center gap-3 text-center" style={SCENE_COLOURS}>
        <svg viewBox="0 0 100 100" width="160" height="160" role="img" aria-label={sign.name[lang]}
             className="motion-safe:animate-[rise_220ms_ease-out_both]" dangerouslySetInnerHTML={{ __html: SIGNS[sign.key]() }} />
        <h2 className="m-0 text-h3 font-bold">{sign.name[lang]}</h2>
        <p className="m-0 text-lead">{sign.says[lang]}</p>
        <p className="m-0 text-meta text-ink-soft">{t('signs.code', { code: sign.code })}</p>
        <SourceFold paths={sign.cites} label={articleLabel} />
        <div className="flex flex-wrap justify-center gap-2">
          {sign.scene ? <Button variant="primary" to={toolLink(`/topics/${slug}/tools/scenes`, { s: sign.scene })}>{t('signs.seeScene')}</Button> : null}
          {sign.offence ? <Button to={toolLink(`/topics/${slug}/tools/${sign.offence === 'speed' ? 'speed' : 'fine'}`, sign.offence === 'speed' ? {} : { o: sign.offence })}>{t('signs.cost')}</Button> : null}
          <Button onClick={onClose}>{t('signs.close')}</Button>
        </div>
      </div>
    </Sheet>
  );
}
