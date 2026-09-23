import { useEffect, useRef, useState } from "react";
import { useReducedMotion } from "motion/react";

/* =====================================================
   COUNT UP

   Page and chunk counts roll up rather than appearing.
   The figure is real from the first frame in the
   accessibility tree - only the visual tween animates -
   so a screen reader never reads a number the API did
   not return.
===================================================== */

const DURATION = 620;

const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);

type Props = {
  value: number;
  /** Skip the tween below this, where it just looks like a glitch. */
  threshold?: number;
};

export function CountUp({ value, threshold = 8 }: Props) {
  const reduced = useReducedMotion();

  /* Derived during render rather than written from the
     effect, so the non-animating case never schedules a
     second render just to land on the value it already
     knew. */
  const animates = !reduced && value >= threshold;

  const [tweened, setTweened] = useState(0);
  const raf = useRef(0);

  useEffect(() => {
    if (!animates) {
      return;
    }

    const start = performance.now();

    const step = (now: number) => {
      const t = Math.min(1, (now - start) / DURATION);

      setTweened(Math.round(easeOut(t) * value));

      if (t < 1) {
        raf.current = requestAnimationFrame(step);
      }
    };

    raf.current = requestAnimationFrame(step);

    return () => cancelAnimationFrame(raf.current);
  }, [value, animates]);

  const shown = animates ? tweened : value;

  return (
    <span className="tnum">
      <span aria-hidden="true">{shown.toLocaleString()}</span>
      <span className="sr-only">{value.toLocaleString()}</span>
    </span>
  );
}
