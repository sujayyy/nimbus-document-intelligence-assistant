import { useEffect, useRef } from "react";
import {
  motion,
  useMotionValue,
  useReducedMotion,
  useSpring,
  useTransform,
} from "motion/react";

/* =====================================================
   3D DOCUMENT OBJECT

   Layered sheets on separate Z planes inside one
   perspective, rotated as a single body by a spring
   that trails the cursor. CSS 3D rather than WebGL:
   nothing to download, nothing to compose on the GPU
   beyond transforms, and it degrades to a still stack
   when the viewer prefers reduced motion.

   The orbit ring shares the document's 3D space, so
   paper and intelligence read as one object instead of
   a badge pasted over a picture of a page.
===================================================== */

const NODE_COUNT = 4;
const ORBIT_RADIUS = 150;

type Props = {
  /** Lights the ring while the pipeline is working. */
  active?: boolean;
};

export function DocumentObject({ active = false }: Props) {
  const reduced = useReducedMotion();
  const hostRef = useRef<HTMLDivElement>(null);

  /* Pointer position, normalised to -0.5..0.5 */
  const px = useMotionValue(0);
  const py = useMotionValue(0);

  const sx = useSpring(px, {
    stiffness: 110,
    damping: 18,
    mass: 0.6,
  });

  const sy = useSpring(py, {
    stiffness: 110,
    damping: 18,
    mass: 0.6,
  });

  /* Resting tilt keeps the object reading as 3D even
     before the cursor has moved. */
  const rotateY = useTransform(sx, [-0.5, 0.5], [-26, 26]);
  const rotateX = useTransform(sy, [-0.5, 0.5], [18, -18]);

  useEffect(() => {
    if (reduced) {
      return;
    }

    const onMove = (event: PointerEvent) => {
      const host = hostRef.current;

      if (!host) {
        return;
      }

      const rect = host.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;

      /* Divided by viewport rather than element size so
         the object keeps responding when the cursor is
         nowhere near it. */
      px.set(
        Math.max(
          -0.5,
          Math.min(0.5, (event.clientX - cx) / window.innerWidth),
        ),
      );

      py.set(
        Math.max(
          -0.5,
          Math.min(0.5, (event.clientY - cy) / window.innerHeight),
        ),
      );
    };

    window.addEventListener("pointermove", onMove, { passive: true });

    return () => {
      window.removeEventListener("pointermove", onMove);
    };
  }, [px, py, reduced]);

  return (
    <div className="doc3d" ref={hostRef} aria-hidden="true">
      <motion.div
        className="doc3d-body"
        style={
          reduced
            ? undefined
            : {
                rotateX,
                rotateY,
                transformPerspective: 1100,
              }
        }
      >
        <div className="doc3d-sheet s1" />
        <div className="doc3d-sheet s2" />

        <div className="doc3d-sheet s3">
          <div className="doc3d-corner" />
          <div className="doc3d-band" />

          <div className="doc3d-rule" style={{ width: "88%" }} />
          <div className="doc3d-rule is-hit" style={{ width: "72%" }} />
          <div className="doc3d-rule" style={{ width: "94%" }} />
          <div className="doc3d-rule" style={{ width: "62%" }} />
          <div className="doc3d-rule is-hit" style={{ width: "80%" }} />
          <div className="doc3d-rule" style={{ width: "48%" }} />

          <div className="doc3d-tag">PDF</div>
        </div>

        {/* The index plane. Sharing the document's
            perspective and rotation states the whole
            product at rest: a sheet above, the lattice
            it becomes below. */}
        <div className="doc3d-plane" aria-hidden="true">
          {Array.from({ length: 60 }).map((_, i) => (
            <span
              key={i}
              className={`doc3d-cell ${
                [7, 19, 33, 46].includes(i) ? "is-hit" : ""
              }`}
            />
          ))}
        </div>

        <motion.div
          className="doc3d-orbit"
          animate={reduced ? undefined : { rotateZ: 360 }}
          transition={
            reduced
              ? undefined
              : {
                  duration: active ? 9 : 34,
                  ease: "linear",
                  repeat: Infinity,
                }
          }
        >
          <div className="doc3d-ring" />

          {Array.from({ length: NODE_COUNT }).map((_, index) => {
            const angle = (index / NODE_COUNT) * Math.PI * 2;

            return (
              <div
                key={index}
                className="doc3d-node"
                style={{
                  transform: `translate3d(${
                    Math.cos(angle) * ORBIT_RADIUS
                  }px, ${Math.sin(angle) * ORBIT_RADIUS}px, 0)`,
                  opacity: active ? 1 : 0.55,
                }}
              />
            );
          })}
        </motion.div>
      </motion.div>
    </div>
  );
}
