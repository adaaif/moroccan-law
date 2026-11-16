import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { reducedMotion } from '../../kit/motion';
import { num } from '../../kit/viz/viz';
import { useBillYears } from '../billYears';
import { useTaxT } from '../strings';
import { GainCurve } from './GainCurve';
import './story.css';

const GUESS_AT = 15000;
const SEEN = 'law.topic.tax.bill-guess';

/** The bill's story at the top of its page (the bill-story review, Y1, Y2; C2 «guess»): first the reader guesses
 *  what someone on 15,000 gross gains in 2027, then the curve answers for every salary; on a desk the curve stays while
 *  four short steps scroll beside it, each lighting its stretch; on a phone the steps are a row of four to tap. */
export function BillStory({ slug }: { slug: string }) {
  const { t, i18n } = useTaxT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const [shown, setShown] = useState(() => { try { return localStorage.getItem(SEEN) === '1'; } catch { return false; } });
  const [guess, setGuess] = useState(1500);
  const [guessed, setGuessed] = useState<number | null>(null);
  const truth = useBillYears(slug, GUESS_AT, 0)?.years[0].gain ?? null;
  // A salary already in the address (a person picked lower on the page, a shared link) goes straight to the curve.
  const [params] = useSearchParams();
  const reveal = (g: number | null) => {
    setGuessed(g);
    setShown(true);
    try { localStorage.setItem(SEEN, '1'); } catch { /* private window */ }
  };
  if (!shown && !params.has('g')) {
    return (
      <section className="st-guess" aria-labelledby="st-guess">
        <h2 id="st-guess" className="st-q">{t('story.guessQ', { g: num(GUESS_AT, lang) })}</h2>
        <p className="st-guess-v">{t('story.guessV', { v: num(guess, lang) })}</p>
        <input type="range" min={0} max={3000} step={50} value={guess} onChange={(e) => setGuess(Number(e.target.value))}
               aria-label={t('story.guessAria')} className="st-range" />
        <p className="st-guess-ends"><span>0</span><span>{num(3000, lang)}</span></p>
        <div className="st-guess-acts">
          <button type="button" className="st-go" onClick={() => reveal(guess)}>{t('story.show')}</button>
          <button type="button" className="st-skip" onClick={() => reveal(null)}>{t('story.skip')}</button>
        </div>
      </section>
    );
  }
  return (
    <section className="st-story" aria-labelledby="st-title">
      <h2 id="st-title" className="st-q">{t('story.title')}</h2>
      {guessed !== null && truth !== null ? (
        <p className="st-guessed">{t('story.guessed', { mine: num(guessed, lang), truth: num(truth, lang), g: num(GUESS_AT, lang) })}</p>
      ) : null}
      <Steps slug={slug} />
      <p className="st-source">{t('story.source')}</p>
    </section>
  );
}

const STEPS: [string, [number, number] | null][] = [['s1', [3000, 8374]], ['s2', [8374, 11800]], ['s3', [11800, 30000]], ['s4', null]];

/** Four steps beside the curve (Y2): on a desk each step scrolling into the middle of the screen lights its stretch; on a
 *  phone, a row of four to tap, the curve above them. */
function Steps({ slug }: { slug: string }) {
  const { t } = useTaxT();
  const [at, setAt] = useState(0);
  const refs = useRef<(HTMLLIElement | null)[]>([]);
  const [desk, setDesk] = useState(() => typeof window !== 'undefined' && window.matchMedia('(min-width: 1024px)').matches);
  useEffect(() => {
    const mq = window.matchMedia('(min-width: 1024px)');
    const hear = () => setDesk(mq.matches);
    mq.addEventListener('change', hear);
    return () => mq.removeEventListener('change', hear);
  }, []);
  useEffect(() => {
    if (!desk) return;
    const io = new IntersectionObserver((es) => es.forEach((e) => {
      if (e.isIntersecting) setAt(refs.current.indexOf(e.target as HTMLLIElement));
    }), { rootMargin: '-45% 0px -45% 0px' });
    refs.current.forEach((el) => el && io.observe(el));
    return () => io.disconnect();
  }, [desk]);
  const range = STEPS[at]?.[1] ?? null;
  if (!desk) {
    return (
      <div className="st-phone">
        <GainCurve slug={slug} range={range} />
        <div className="st-tabs" role="tablist" aria-label={t('story.stepsAria')}>
          {STEPS.map(([k], i) => (
            <button key={k} type="button" role="tab" aria-selected={i === at} onClick={() => setAt(i)}>{i + 1}</button>
          ))}
        </div>
        <p className="st-step-text" role="tabpanel">{t(`story.${STEPS[at][0]}`)}</p>
      </div>
    );
  }
  return (
    <div className="st-scrolly">
      <ol className="st-steps">
        {STEPS.map(([k], i) => (
          <li key={k} ref={(el) => { refs.current[i] = el; }} className={i === at ? 'on' : ''}
              onClick={() => { setAt(i); refs.current[i]?.scrollIntoView({ block: 'center', behavior: reducedMotion() ? 'auto' : 'smooth' }); }}>
            {t(`story.${k}`)}
          </li>
        ))}
      </ol>
      <div className="st-sticky"><GainCurve slug={slug} range={range} /></div>
    </div>
  );
}
