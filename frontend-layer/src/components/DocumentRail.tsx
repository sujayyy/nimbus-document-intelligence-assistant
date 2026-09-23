import { AnimatePresence, motion } from "motion/react";
import type { UploadedDocument } from "../types";
import { CountUp } from "./CountUp";
import {
  CheckIcon,
  CloseIcon,
  LayersIcon,
  PlusIcon,
} from "./icons";

/* =====================================================
   DOCUMENT RAIL

   The library. Each entry is a real paper stack in 3D -
   hover fans the sheets apart, the active document
   grows a coloured spine like a tab on a physical file.
===================================================== */

type Props = {
  documents: UploadedDocument[];
  activeId: string | null;
  isBusy: boolean;
  uploadingName: string | null;
  onSelect: (document: UploadedDocument) => void;
  onRemove: (id: string) => void;
  onUploadClick: () => void;
};

export function DocumentRail({
  documents,
  activeId,
  isBusy,
  uploadingName,
  onSelect,
  onRemove,
  onUploadClick,
}: Props) {
  return (
    <>
      <div className="rail-head">
        <span className="label">Documents</span>

        <span className="label tnum">
          {documents.length > 0 ? String(documents.length).padStart(2, "0") : "--"}
        </span>
      </div>

      <div className="rail-body scroll">
        <AnimatePresence initial={false}>
          {uploadingName && (
            <motion.div
              className="ingest"
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.98 }}
              transition={{ duration: 0.24, ease: "easeOut" }}
            >
              <div className="ingest-head">
                <span className="ingest-name">{uploadingName}</span>
              </div>

              <div className="ingest-bar">
                <span className="ingest-fill" />
              </div>

              <div className="ingest-stages">
                <span className="ingest-stage is-on">Uploading</span>
                <span className="ingest-stage is-on">Processing</span>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <AnimatePresence initial={false}>
          {documents.map((document) => {
            const isActive = document.id === activeId;

            return (
              <motion.div
                key={document.id}
                layout
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, x: -12 }}
                transition={{
                  type: "spring",
                  stiffness: 380,
                  damping: 30,
                }}
              >
                <div className={`doc-card ${isActive ? "is-active" : ""}`}>
                  <motion.div
                    className="doc-card-body"
                    whileHover={{ y: -2, rotateX: 5, rotateY: -4 }}
                    whileTap={{ scale: 0.985 }}
                    transition={{
                      type: "spring",
                      stiffness: 420,
                      damping: 26,
                    }}
                  >
                    <button
                      type="button"
                      className="doc-card-hit"
                      onClick={() => onSelect(document)}
                      disabled={isBusy}
                      aria-pressed={isActive}
                      aria-label={`Use ${document.name}`}
                    />

                    <span className="stack" aria-hidden="true">
                      <span className="stack-sheet" />
                      <span className="stack-sheet" />
                      <span className="stack-sheet">
                        <span className="stack-tick" />
                      </span>
                    </span>

                    <span className="doc-card-info">
                      <span className="doc-card-name">{document.name}</span>

                      <span className="doc-card-meta">
                        <span className="meta-pages">
                          <CountUp value={document.pages} /> pages
                        </span>

                        <span className="meta-sep" aria-hidden="true" />

                        {/* Chunk count is machine-derived, so it
                            takes the steel register. */}
                        <span className="meta-chunks">
                          <CountUp value={document.chunks} /> chunks
                        </span>
                      </span>
                    </span>

                    {isActive && (
                      <span
                        className="doc-card-live"
                        title="Indexed and active"
                      >
                        <CheckIcon size={12} />
                      </span>
                    )}

                    <button
                      type="button"
                      className="doc-card-remove"
                      onClick={(event) => {
                        event.stopPropagation();
                        onRemove(document.id);
                      }}
                      disabled={isBusy}
                      aria-label={`Remove ${document.name}`}
                    >
                      <CloseIcon size={13} />
                    </button>
                  </motion.div>
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>

        {documents.length === 0 && !uploadingName && (
          <div className="rail-empty">
            <LayersIcon size={20} />
            <p>No documents yet.</p>
            <p className="rail-empty-sub">
              Add a PDF to start asking questions.
            </p>
          </div>
        )}
      </div>

      <div className="rail-foot">
        <motion.button
          type="button"
          className="rail-add"
          onClick={onUploadClick}
          disabled={isBusy}
          whileHover={{ y: -1 }}
          whileTap={{ scale: 0.98 }}
          transition={{ type: "spring", stiffness: 420, damping: 26 }}
        >
          <PlusIcon size={16} />
          Add PDF
        </motion.button>
      </div>
    </>
  );
}
