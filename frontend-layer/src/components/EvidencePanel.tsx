import { AnimatePresence, motion } from "motion/react";
import { getSourcePage, type Source } from "../types";
import { CloseIcon, LayersIcon } from "./icons";

/* =====================================================
   EVIDENCE PANEL

   Only cited sources appear here. That is deliberate:
   the pipeline validates citations and drops any page
   the answer did not actually lean on, so showing the
   raw retrieved set would overstate the evidence.

   Selecting a card highlights the matching [p.N] marker
   inside the answer, and vice versa.
===================================================== */

type Props = {
  sources: Source[];
  documentName: string | null;
  activePage: number | null;
  onSelect: (page: number | null) => void;
  onClose?: () => void;
};

export function EvidencePanel({
  sources,
  documentName,
  activePage,
  onSelect,
  onClose,
}: Props) {
  return (
    <>
      <div className="evidence-head">
        <span className="label">Evidence</span>

        <div className="topbar-right">
          <span className="label tnum">
            {sources.length > 0
              ? String(sources.length).padStart(2, "0")
              : "--"}
          </span>

          {onClose && (
            <button
              type="button"
              className="btn-icon only-narrow"
              onClick={onClose}
              aria-label="Close the evidence panel"
            >
              <CloseIcon size={15} />
            </button>
          )}
        </div>
      </div>

      <div className="evidence-body scroll">
        {sources.length === 0 ? (
          <div className="ev-empty">
            <LayersIcon size={20} />
            <p style={{ marginTop: "var(--s-3)" }}>
              Evidence appears here once Nimbus answers.
            </p>
            <p
              style={{
                marginTop: "var(--s-2)",
                fontSize: "var(--t-xs)",
              }}
            >
              Every figure is traced back to the page it came from.
            </p>
          </div>
        ) : (
          <AnimatePresence initial={false}>
            {sources.map((source, index) => {
              const page = getSourcePage(source);

              if (page == null) {
                return null;
              }

              const isOn = activePage === page;

              return (
                <motion.button
                  key={`${page}-${index}`}
                  type="button"
                  className={`ev-card ${isOn ? "is-on" : ""}`}
                  onClick={() => onSelect(isOn ? null : page)}
                  aria-pressed={isOn}
                  layout
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{
                    type: "spring",
                    stiffness: 400,
                    damping: 30,
                    delay: index * 0.04,
                  }}
                  whileHover={{ y: -2 }}
                >
                  <span className="ev-card-head">
                    <span className="ev-index tnum">{index + 1}</span>

                    <span style={{ minWidth: 0 }}>
                      <span className="ev-page">Page {page}</span>

                      <span className="ev-doc">
                        {source.source_file || documentName || "Document"}
                      </span>
                    </span>
                  </span>

                  <AnimatePresence initial={false}>
                    {isOn && source.text && (
                      <motion.span
                        className="ev-excerpt"
                        style={{ display: "block" }}
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        exit={{ opacity: 0, height: 0 }}
                        transition={{ duration: 0.24, ease: "easeOut" }}
                      >
                        {source.text.slice(0, 460)}
                        {source.text.length > 460 ? "…" : ""}
                      </motion.span>
                    )}
                  </AnimatePresence>
                </motion.button>
              );
            })}
          </AnimatePresence>
        )}
      </div>
    </>
  );
}
