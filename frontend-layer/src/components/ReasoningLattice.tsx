import { AnimatePresence, motion } from "motion/react";

/* =====================================================
   REASONING LATTICE

   The pre-token state. Two rows of nodes fire in a
   travelling wave with a couple of warm nodes standing
   in for the chunks currently under consideration.

   The caption rotates through what the pipeline is
   genuinely doing at this point - reading retrieved
   pages and composing - rather than inventing a
   progress percentage nobody reports.
===================================================== */

const NODES = 18;

type Props = {
  caption?: string;
};

export function ReasoningLattice({ caption = "Reading" }: Props) {
  return (
    <div className="lattice" role="status" aria-live="polite">
      <div className="lattice-grid" aria-hidden="true">
        {Array.from({ length: NODES }).map((_, i) => (
          <span
            key={i}
            className={`lattice-node ${
              i % 7 === 3 ? "is-hot" : ""
            }`}
            style={{
              animationDelay: `${((i % 6) * 0.09 + Math.floor(i / 6) * 0.05).toFixed(2)}s`,
            }}
          />
        ))}
      </div>

      <AnimatePresence mode="wait">
        <motion.span
          key={caption}
          className="lattice-label"
          initial={{ opacity: 0, y: 3 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -3 }}
          transition={{ duration: 0.18 }}
        >
          {caption}
        </motion.span>
      </AnimatePresence>
    </div>
  );
}
