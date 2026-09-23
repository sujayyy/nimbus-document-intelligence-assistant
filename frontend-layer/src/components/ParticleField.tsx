import { useEffect, useRef } from "react";
import { useReducedMotion } from "motion/react";

/* =====================================================
   PARTICLE FIELD

   Ambient drift behind the workspace: nodes that wander,
   link to their neighbours, and reach for the cursor.

   Built natively rather than in a sandboxed iframe, which
   matters for three reasons. It reads our design tokens
   from computed style, so it can never drift out of sync
   with the palette. It shares the page's pointer, so the
   cursor actually drives it. And it costs one canvas
   instead of a second document plus four CDN fetches.

   Register discipline holds here too: most nodes are
   steel - this is the machine idling - with a handful of
   warm ones standing in for pages. `intensity` is driven
   by real pipeline state, so the field quickens while
   Nimbus is working and settles when it is not.
===================================================== */

const NODE_COUNT = 58;
const LINK_DIST = 108;
const CURSOR_DIST = 170;
const WARM_EVERY = 9;

type Node = {
  x: number;
  y: number;
  vx: number;
  vy: number;
  warm: boolean;
  /* Tiny glyph widths - the field reads as drifting text
     fragments rather than generic sci-fi dust. */
  w: number;
};

type Props = {
  /** 0 = idle, 1 = pipeline working. */
  intensity?: number;
};

export function ParticleField({ intensity = 0 }: Props) {
  const reduced = useReducedMotion();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const intensityRef = useRef(intensity);

  useEffect(() => {
    intensityRef.current = intensity;
  }, [intensity]);

  useEffect(() => {
    if (reduced) {
      return;
    }

    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");

    if (!canvas || !ctx) {
      return;
    }

    /* Palette comes from the tokens, never duplicated as
       literals in here. */
    const read = (name: string) =>
      getComputedStyle(document.documentElement)
        .getPropertyValue(name)
        .trim();

    const steel = read("--steel") || "#0025ff";

    /* Not --accent: saturated yellow is invisible on a
       white ground. The document register is carried by
       ink here instead, and the field stays legible. */
    const accent = read("--ink") || "#000000";

    const hexToRgb = (hex: string) => {
      const h = hex.replace("#", "");
      const full =
        h.length === 3
          ? h
              .split("")
              .map((c) => c + c)
              .join("")
          : h;

      return [
        parseInt(full.slice(0, 2), 16),
        parseInt(full.slice(2, 4), 16),
        parseInt(full.slice(4, 6), 16),
      ];
    };

    const [sr, sg, sb] = hexToRgb(steel);
    const [ar, ag, ab] = hexToRgb(accent);

    let width = 0;
    let height = 0;
    let raf = 0;
    let running = true;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const nodes: Node[] = [];
    const pointer = { x: -9999, y: -9999 };

    const seed = () => {
      nodes.length = 0;

      for (let i = 0; i < NODE_COUNT; i += 1) {
        nodes.push({
          x: Math.random() * width,
          y: Math.random() * height,
          vx: (Math.random() - 0.5) * 0.12,
          vy: -(Math.random() * 0.14 + 0.03),
          warm: i % WARM_EVERY === 4,
          w: 2 + Math.round(Math.random() * 5),
        });
      }
    };

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      width = rect.width;
      height = rect.height;
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      if (nodes.length === 0) {
        seed();
      }
    };

    const onPointer = (e: PointerEvent) => {
      const rect = canvas.getBoundingClientRect();
      pointer.x = e.clientX - rect.left;
      pointer.y = e.clientY - rect.top;
    };

    const onLeave = () => {
      pointer.x = -9999;
      pointer.y = -9999;
    };

    const frame = () => {
      if (!running) {
        return;
      }

      const k = intensityRef.current;
      const speed = 1 + k * 1.6;

      ctx.clearRect(0, 0, width, height);

      /* Links first so nodes sit on top of their own web. */
      ctx.lineWidth = 0.7;

      for (let i = 0; i < nodes.length; i += 1) {
        const a = nodes[i];

        for (let j = i + 1; j < nodes.length; j += 1) {
          const b = nodes[j];
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const d2 = dx * dx + dy * dy;

          if (d2 > LINK_DIST * LINK_DIST) {
            continue;
          }

          const fade = 1 - Math.sqrt(d2) / LINK_DIST;

          ctx.strokeStyle = `rgba(${sr},${sg},${sb},${(
            0.1 * fade +
            k * 0.12 * fade
          ).toFixed(3)})`;

          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        }
      }

      for (const n of nodes) {
        n.x += n.vx * speed;
        n.y += n.vy * speed;

        if (n.y < -12) {
          n.y = height + 12;
          n.x = Math.random() * width;
        }

        if (n.x < -12) {
          n.x = width + 12;
        } else if (n.x > width + 12) {
          n.x = -12;
        }

        const dx = pointer.x - n.x;
        const dy = pointer.y - n.y;
        const dist = Math.hypot(dx, dy);
        const near = dist < CURSOR_DIST;

        if (near) {
          const fade = 1 - dist / CURSOR_DIST;

          ctx.strokeStyle = `rgba(${sr},${sg},${sb},${(
            0.24 * fade
          ).toFixed(3)})`;
          ctx.lineWidth = 0.7;

          ctx.beginPath();
          ctx.moveTo(n.x, n.y);
          ctx.lineTo(pointer.x, pointer.y);
          ctx.stroke();
        }

        const base = n.warm ? 0.3 : 0.2;
        const lift = near ? 0.26 : 0;

        ctx.fillStyle = n.warm
          ? `rgba(${ar},${ag},${ab},${(base + lift + k * 0.2).toFixed(3)})`
          : `rgba(${sr},${sg},${sb},${(base + lift + k * 0.2).toFixed(3)})`;

        ctx.fillRect(n.x, n.y, n.w, 1.6);
      }

      raf = requestAnimationFrame(frame);
    };

    const onVisibility = () => {
      if (document.hidden) {
        running = false;
        cancelAnimationFrame(raf);
      } else if (!running) {
        running = true;
        raf = requestAnimationFrame(frame);
      }
    };

    resize();

    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    window.addEventListener("pointermove", onPointer, { passive: true });
    window.addEventListener("pointerleave", onLeave);
    document.addEventListener("visibilitychange", onVisibility);

    raf = requestAnimationFrame(frame);

    return () => {
      running = false;
      cancelAnimationFrame(raf);
      ro.disconnect();
      window.removeEventListener("pointermove", onPointer);
      window.removeEventListener("pointerleave", onLeave);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [reduced]);

  if (reduced) {
    return null;
  }

  return <canvas ref={canvasRef} className="field" aria-hidden="true" />;
}
