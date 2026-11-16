import { sharePicture } from '@/topics/kit/tool/picture';
import { n, named } from './format';
import type { PlaceProfile } from './places.api';

/** A place as a picture to forward (PL23): its name, its texts, its first year, where to find them. */
export function sharePlace(p: PlaceProfile, lang: string, t: (k: string, o?: Record<string, unknown>) => string) {
  const first = p.place.first ? Number(p.place.first.date.slice(0, 4)) : null;
  const peak = [...p.years].sort((a, b) => b.texts - a.texts)[0];
  return sharePicture({
    dir: lang === 'fr' ? 'ltr' : 'rtl',
    colour: getComputedStyle(document.documentElement).getPropertyValue('--color-stamp').trim() || '#5b3a9e',
    over: t('pages:places.share.over', { name: named(p.place, lang) }),
    value: n(p.place.texts, lang),
    lines: [t('pages:places.share.texts', { count: p.place.texts }), first ? t('pages:places.share.first', { year: first }) : '',
            peak && peak.texts ? t('pages:places.share.peak', { year: peak.year, count: peak.texts }) : ''].filter(Boolean),
    source: t('pages:places.share.source'),
    site: t('pages:places.share.site', { slug: p.place.slug }),
  }, p.place.slug);
}
