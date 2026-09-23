import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";

/* =====================================================
   INGEST CINEMATIC

   The sequence that plays while a PDF is being ingested.
   It is not decoration: each phase names a real stage of
   the backend pipeline, in order.

       PARSE   PyMuPDF walks the pages
       CHUNK   pages are cut into page-aware token chunks
       EMBED   chunks become vectors
       INDEX   vectors are added to the FAISS index

   Honesty rule: the timeline runs once through those four
   phases and then HOLDS. It only resolves when the real
   upload request settles. If the request is slower than
   the animation, the lattice keeps breathing; if it is
   faster, the sequence fast-forwards. The animation can
   never report a finished index before the server has
   actually returned one.

   Canvas rather than DOM because the slice and disperse
   phases move ~60 elements per frame, which is cheap on
   a bitmap and expensive as layers.
===================================================== */

type Stage = {
  key: string;
  label: string;
  dur: number;
};

const STAGES: Stage[] = [
  { key: "materialise", label: "READ", dur: 620 },
  { key: "scan", label: "PARSE", dur: 940 },
  { key: "slice", label: "CHUNK", dur: 860 },
  { key: "disperse", label: "EMBED", dur: 1000 },
  { key: "index", label: "INDEX", dur: 780 },
];

const RESOLVE_MS = 620;
const LINES = 15;
const BANDS = 6;
const GRID_COLS = 12;
const GRID_ROWS = 6;

const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);
const easeInOut = (t: number) =>
  t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
const clamp01 = (t: number) => Math.max(0, Math.min(1, t));
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

type Props = {
  /** Filename being ingested. */
  name: string;
  /** Flips true when the real upload request settles. */
  settled: boolean;
  /** True when that request failed. */
  failed?: boolean;
  /** Real counts from the API - only known once settled. */
  pages?: number;
  chunks?: number;
  onDone: () => void;
};

export function IngestCinematic({
  name,
  settled,
  failed = false,
  pages,
  chunks,
  onDone,
}: Props) {
  const reduced = useReducedMotion();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const settledRef = useRef(settled);
  const doneRef = useRef(onDone);

  const [stageLabel, setStageLabel] = useState(STAGES[0].label);
  const [stageIndex, setStageIndex] = useState(0);
  const [holding, setHolding] = useState(false);

  /* Mirrored into refs in an effect, not during render, so
     the rAF loop can read the latest values without the
     loop itself being a render dependency. */
  useLayoutEffect(() => {
    settledRef.current = settled;
    doneRef.current = onDone;
  }, [settled, onDone]);

  useEffect(() => {
    /* Reduced motion: no canvas loop at all. The overlay
       still appears so the state is legible, but nothing
       animates beyond the indeterminate bar in the DOM. */
    if (reduced) {
      if (settled) {
        const t = setTimeout(() => doneRef.current(), 240);
        return () => clearTimeout(t);
      }

      return;
    }

    const canvas = canvasRef.current;

    if (!canvas) {
      return;
    }

    const ctx = canvas.getContext("2d");

    if (!ctx) {
      return;
    }

    /* Palette is read from the tokens, never written as
       literals here - the previous version hardcoded its
       hexes and silently kept the old identity when the
       palette changed. */
    const token = (name: string, fallback: string) =>
      getComputedStyle(document.documentElement)
        .getPropertyValue(name)
        .trim() || fallback;

    const C = {
      sheet: token("--sheet", "#f6e6ea"),
      sheetLine: token("--sheet-line", "#c49aa9"),
      sheet2: token("--sheet-2", "#e4cbd3"),
      accent: token("--accent", "#ffc247"),
      machine2: token("--machine-2", "#1f0b12"),
      steel: token("--steel", "#ff2d78"),
      steelBright: token("--steel-bright", "#ff9ec1"),
    };

    const rgba = (hex: string, a: number) => {
      const h = hex.replace("#", "");
      const f =
        h.length === 3
          ? h.split("").map((c) => c + c).join("")
          : h;
      const r = parseInt(f.slice(0, 2), 16);
      const g = parseInt(f.slice(2, 4), 16);
      const b = parseInt(f.slice(4, 6), 16);
      return `rgba(${r},${g},${b},${a})`;
    };

    let raf = 0;
    let width = 0;
    let height = 0;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      width = rect.width;
      height = rect.height;
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    resize();
    window.addEventListener("resize", resize);

    const total = STAGES.reduce((sum, s) => sum + s.dur, 0);
    const start = performance.now();

    /* Deterministic scatter so the lattice looks designed
       rather than random on every mount. */
    const jitter = (i: number, salt: number) =>
      (Math.sin(i * 12.9898 + salt * 78.233) * 43758.5453) % 1;

    let resolveStart = 0;

    /* Virtual clock. Once the upload actually returns, the
       remaining phases run at CATCH_UP speed instead of
       waiting out the full timeline - the sequence is still
       shown end to end, it just stops being the bottleneck.
       Previously a one-second upload still cost the user
       the whole 4.2s. */
    const CATCH_UP = 4.5;

    let vTime = 0;
    let lastTick = start;

    const frame = (now: number) => {
      const rate = settledRef.current ? CATCH_UP : 1;

      vTime += (now - lastTick) * rate;
      lastTick = now;

      const elapsed = vTime;

      /* --- Resolve ------------------------------------ */

      if (resolveStart) {
        const rp = clamp01((now - resolveStart) / RESOLVE_MS);

        draw(1, "index", 1, easeOut(rp));

        if (rp >= 1) {
          doneRef.current();
          return;
        }

        raf = requestAnimationFrame(frame);
        return;
      }

      /* --- Timeline ----------------------------------- */

      let acc = 0;
      let active = STAGES.length - 1;
      let localT = 1;

      for (let i = 0; i < STAGES.length; i += 1) {
        if (elapsed < acc + STAGES[i].dur) {
          active = i;
          localT = (elapsed - acc) / STAGES[i].dur;
          break;
        }

        acc += STAGES[i].dur;
      }

      const finishedTimeline = elapsed >= total;

      if (finishedTimeline) {
        active = STAGES.length - 1;
        localT = 1;
      }

      setStageIndex(active);
      setStageLabel(STAGES[active].label);
      setHolding(finishedTimeline && !settledRef.current);

      /* The hold: the index breathes until the server
         actually answers. */
      const holdPulse = finishedTimeline
        ? 0.5 + 0.5 * Math.sin((elapsed - total) / 420)
        : 0;

      draw(
        clamp01(elapsed / total),
        STAGES[active].key,
        localT,
        0,
        holdPulse,
      );

      if (finishedTimeline && settledRef.current) {
        resolveStart = now;
      }

      raf = requestAnimationFrame(frame);
    };

    /* --------------------------------------------------
       DRAW
    -------------------------------------------------- */

    function draw(
      _global: number,
      stage: string,
      t: number,
      resolveT: number,
      pulse = 0,
    ) {
      ctx!.clearRect(0, 0, width, height);

      const cx = width / 2;
      const cy = height / 2;

      /* Page geometry, shrinking away on resolve */
      const scale = 1 - resolveT * 0.55;
      const pw = Math.min(232, width * 0.46) * scale;
      const ph = pw * 1.31;
      const px = cx - pw / 2;
      const py = cy - ph / 2 - 10 + resolveT * 60;

      const alpha = 1 - resolveT;

      const stageAt = STAGES.findIndex((s) => s.key === stage);

      const past = (key: string) =>
        stageAt > STAGES.findIndex((s) => s.key === key);

      /* --- Phase progress ---------------------------- */

      const pMat = stage === "materialise" ? easeOut(t) : 1;
      const pScan = stage === "scan" ? t : past("scan") ? 1 : 0;
      const pSlice = stage === "slice" ? easeInOut(t) : past("slice") ? 1 : 0;
      const pDisp =
        stage === "disperse" ? easeInOut(t) : past("disperse") ? 1 : 0;
      const pIdx = stage === "index" ? easeOut(t) : past("index") ? 1 : 0;

      ctx!.globalAlpha = alpha;

      /* --- Page sheet -------------------------------- */

      if (pDisp < 1) {
        const sheetA = pMat * (1 - pDisp);

        ctx!.globalAlpha = alpha * sheetA;
        ctx!.fillStyle = C.sheet;
        ctx!.strokeStyle = rgba(C.sheetLine, 0.95);
        ctx!.lineWidth = 1;

        const grow = lerp(0.86, 1, pMat);
        const gw = pw * grow;
        const gh = ph * grow;
        const gx = cx - gw / 2;
        const gy = cy - gh / 2 - 10 + resolveT * 60;

        ctx!.beginPath();
        ctx!.rect(gx, gy, gw, gh);
        ctx!.fill();
        ctx!.stroke();

        /* Text lines, revealed by the scan */
        for (let i = 0; i < LINES; i += 1) {
          const ly = gy + 26 + i * ((gh - 44) / LINES);
          const reveal = clamp01(pScan * LINES - i);

          if (reveal <= 0) {
            continue;
          }

          const lw =
            (gw - 44) * (0.55 + 0.45 * Math.abs(jitter(i, 3)));

          ctx!.globalAlpha = alpha * sheetA * reveal * 0.85 * (1 - pSlice);
          ctx!.fillStyle = i % 5 === 2 ? C.accent : C.sheet2;
          ctx!.fillRect(gx + 22, ly, lw * reveal, 3);
        }

        /* Scan beam */
        if (stage === "scan") {
          const by = gy + 14 + (gh - 28) * pScan;

          const grad = ctx!.createLinearGradient(gx, by - 22, gx, by + 6);
          grad.addColorStop(0, rgba(C.steelBright, 0));
          grad.addColorStop(1, rgba(C.steelBright, 0.36));

          ctx!.globalAlpha = alpha;
          ctx!.fillStyle = grad;
          ctx!.fillRect(gx, by - 22, gw, 28);

          ctx!.fillStyle = C.steelBright;
          ctx!.fillRect(gx, by, gw, 1.4);
        }
      }

      /* --- Chunk bands -> lattice -------------------- */

      if (pSlice > 0) {
        for (let b = 0; b < BANDS; b += 1) {
          const bandH = (ph - 40) / BANDS;
          const homeX = px + 18;
          const homeY = py + 22 + b * bandH;
          const homeW = pw - 36;
          const homeH = bandH - 6;

          /* Slice: bands separate vertically */
          const sliceGap = pSlice * 7 * (b - (BANDS - 1) / 2);

          /* Disperse: each band becomes a lattice cell */
          const gridW = Math.min(width * 0.64, 460) * scale;
          const gridH = gridW * 0.5;
          const col = b % GRID_COLS;

          /* A deliberate shallow arc, not random scatter -
             ragged offsets read as misalignment, an arc
             reads as composition. */
          const arc = Math.sin((b / (BANDS - 1)) * Math.PI);

          const targetX =
            cx - gridW / 2 + (gridW / BANDS) * b + gridW / (BANDS * 2) - 26;
          const targetY = cy - gridH / 2 - 26 - arc * 16;

          const bx = lerp(homeX, targetX, pDisp);
          const by = lerp(homeY + sliceGap, targetY, pDisp);
          const bw = lerp(homeW, 52 * scale, pDisp);
          const bh = lerp(homeH, 34 * scale, pDisp);

          /* Chunks hand off to the lattice rather than
             sitting on top of it. */
          const handoff = 1 - pIdx;

          ctx!.globalAlpha = alpha * (0.35 + 0.65 * pSlice) * handoff;

          if (handoff <= 0.02) {
            continue;
          }
          ctx!.fillStyle = pDisp > 0.4 ? C.machine2 : C.sheet;
          ctx!.strokeStyle =
            pDisp > 0.4 ? rgba(C.steel, 0.85) : rgba(C.accent, 0.9);
          ctx!.lineWidth = 1;

          ctx!.beginPath();
          ctx!.rect(bx, by, bw, bh);
          ctx!.fill();
          ctx!.stroke();

          /* Chunk id, only legible once dispersed */
          if (pDisp > 0.55) {
            ctx!.globalAlpha = alpha * (pDisp - 0.55) * 2.2 * handoff;
            ctx!.fillStyle = C.steelBright;
            ctx!.font =
              '500 9px "DM Mono", ui-monospace, monospace';
            ctx!.fillText(
              `c${String(b).padStart(2, "0")}`,
              bx + 6,
              by + bh / 2 + 3,
            );
          }

          void col;
        }
      }

      /* --- Index lattice ----------------------------- */

      if (pIdx > 0) {
        const gridW = Math.min(width * 0.64, 460) * scale;
        const gridH = gridW * 0.5;
        const ox = cx - gridW / 2;
        const oy = cy - gridH / 2 - 34;

        for (let r = 0; r < GRID_ROWS; r += 1) {
          for (let c = 0; c < GRID_COLS; c += 1) {
            const i = r * GRID_COLS + c;
            /* +GRID_COLS of headroom so the final row
               actually completes - scaling by <1 left the
               tail of the grid permanently invisible. */
            const appear = clamp01(
              pIdx * (GRID_ROWS * GRID_COLS + GRID_COLS) - i,
            );

            if (appear <= 0) {
              continue;
            }

            const nx = ox + (gridW / (GRID_COLS - 1)) * c;
            const ny = oy + (gridH / (GRID_ROWS - 1)) * r;

            const warm = Math.abs(jitter(i, 11)) > 0.86;
            const breathe = 1 + pulse * 0.32 * Math.abs(jitter(i, 5));

            ctx!.globalAlpha = alpha * appear * (warm ? 1 : 0.72);
            ctx!.fillStyle = warm ? C.accent : C.steel;

            ctx!.beginPath();
            ctx!.arc(nx, ny, 2.1 * breathe * scale, 0, Math.PI * 2);
            ctx!.fill();

            /* Hairline connections along the row */
            if (c > 0 && appear > 0.6) {
              ctx!.globalAlpha = alpha * appear * 0.26;
              ctx!.strokeStyle = C.steel;
              ctx!.lineWidth = 0.6;
              ctx!.beginPath();
              ctx!.moveTo(nx - gridW / (GRID_COLS - 1), ny);
              ctx!.lineTo(nx, ny);
              ctx!.stroke();
            }
          }
        }
      }

      ctx!.globalAlpha = 1;
    }

    raf = requestAnimationFrame(frame);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, [reduced, settled]);

  return (
    <motion.div
      className="cine"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      role="status"
      aria-live="polite"
    >
      <canvas ref={canvasRef} className="cine-canvas" aria-hidden="true" />

      <div className="cine-hud">
        <div className="cine-file">{name}</div>

        <div className="cine-stages">
          {STAGES.slice(1).map((stage, i) => {
            const idx = i + 1;

            return (
              <span
                key={stage.key}
                className={`cine-stage ${
                  stageIndex > idx ? "is-done" : ""
                } ${stageIndex === idx ? "is-on" : ""}`}
              >
                {stage.label}
              </span>
            );
          })}
        </div>

        <AnimatePresence initial={false}>
          <motion.div
            key={holding ? "hold" : stageLabel}
            className="cine-read"
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -5 }}
            transition={{ duration: 0.16, ease: "easeOut" }}
          >
            {failed
              ? "Upload failed"
              : holding
                ? "Waiting for the index to return"
                : stageLabel}
          </motion.div>
        </AnimatePresence>

        {settled && !failed && (
          <motion.div
            className="cine-counts tnum"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
          >
            {pages} pages · {chunks} chunks
          </motion.div>
        )}

        <div className="cine-bar">
          <span className={`cine-fill ${holding ? "is-hold" : ""}`} />
        </div>
      </div>
    </motion.div>
  );
}
