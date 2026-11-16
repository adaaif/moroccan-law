import { Link } from 'react-router-dom';
import { pageImageUrl } from '@/features/corpus/corpus.api';
import type { DrCrop } from './blog.api';
import './print.css';

/**
 * An article as the Bulletin printed it: the page's own image, framed on the article (the crop is the meta's, read on the
 * image, as shares of it). The frame keeps the clipping's shape at any width: the image is drawn wider than the frame and
 * moved by margins, whose percentages are the frame's width. A tap opens the whole page.
 */
export function Print({ viewer, crop, alt }: { viewer: string; crop: DrCrop; alt: string }) {
  const [, doc, index] = viewer.match(/\/pages\/(\d+)\/(\d+)/) ?? [];
  const w = crop.right - crop.left, h = (crop.bottom - crop.top) * crop.ratio;
  return (
    <Link to={viewer} className="bp-print" style={{ aspectRatio: `${w} / ${h}` }} dir="ltr">
      {/* The page at a phone's width (900) or a desk's (1600): the image is drawn 1/w times the frame's width. */}
      <img src={`${pageImageUrl(doc, index)}?w=1600`} srcSet={`${pageImageUrl(doc, index)}?w=900 900w, ${pageImageUrl(doc, index)}?w=1600 1600w`}
           sizes={`calc((min(100vw, 680px) - 40px) * ${(1 / w).toFixed(2)})`} alt={alt} loading="lazy" decoding="async"
           style={{ width: `${100 / w}%`, marginLeft: `${(-crop.left / w) * 100}%`, marginTop: `${((-crop.top * crop.ratio) / w) * 100}%` }} />
    </Link>
  );
}
