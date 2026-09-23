import { motion } from "motion/react";
import type { RefObject } from "react";
import { MicIcon, PlusIcon, SendIcon } from "./icons";

/* =====================================================
   COMMAND BAR

   The control surface. Focus lifts it and rings it in
   the accent; the send button is the only filled
   control on the screen, so it always reads as the
   primary action.
===================================================== */

type Props = {
  value: string;
  placeholder: string;
  hint: string;
  canSend: boolean;
  isLoading: boolean;
  isUploading: boolean;
  isListening: boolean;
  textareaRef: RefObject<HTMLTextAreaElement | null>;
  onChange: (event: React.ChangeEvent<HTMLTextAreaElement>) => void;
  onKeyDown: (event: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  onSubmit: (event: React.FormEvent) => void;
  onUploadClick: () => void;
  onMicClick: () => void;
};

export function CommandBar({
  value,
  placeholder,
  hint,
  canSend,
  isLoading,
  isUploading,
  isListening,
  textareaRef,
  onChange,
  onKeyDown,
  onSubmit,
  onUploadClick,
  onMicClick,
}: Props) {
  const busy = isLoading || isUploading;

  return (
    <div className="cmd-wrap">
      <div className="cmd-inner">
        <form className="cmd" onSubmit={onSubmit}>
          <motion.button
            type="button"
            className="btn-icon"
            onClick={onUploadClick}
            disabled={busy}
            aria-label="Upload a PDF"
            title="Upload a PDF"
            whileTap={{ scale: 0.9 }}
            transition={{ type: "spring", stiffness: 500, damping: 24 }}
          >
            <PlusIcon size={18} />
          </motion.button>

          <textarea
            ref={textareaRef}
            value={value}
            disabled={busy}
            onChange={onChange}
            onKeyDown={onKeyDown}
            placeholder={placeholder}
            rows={1}
            aria-label="Ask a question about your document"
          />

          <div className="cmd-actions">
            <motion.button
              type="button"
              className={`btn-icon mic ${isListening ? "is-live" : ""}`}
              onClick={onMicClick}
              disabled={busy}
              aria-label={
                isListening ? "Listening" : "Dictate a question"
              }
              whileTap={{ scale: 0.9 }}
              transition={{ type: "spring", stiffness: 500, damping: 24 }}
            >
              <MicIcon size={18} />
            </motion.button>

            <motion.button
              type="submit"
              className="send"
              disabled={!canSend}
              aria-label="Send"
              whileHover={canSend ? { y: -1 } : undefined}
              whileTap={canSend ? { scale: 0.92 } : undefined}
              transition={{ type: "spring", stiffness: 500, damping: 24 }}
            >
              {isLoading ? (
                <motion.span
                  className="send-spin"
                  animate={{ rotate: 360 }}
                  transition={{
                    duration: 0.8,
                    ease: "linear",
                    repeat: Infinity,
                  }}
                />
              ) : (
                <SendIcon size={17} />
              )}
            </motion.button>
          </div>
        </form>

        <div className="cmd-foot">
          <span className={`cmd-doc ${hint.includes("No document") ? "is-empty" : ""}`}>
            <span className="cmd-doc-dot" aria-hidden="true" />
            {hint}
          </span>
          <span className="cmd-hint">Shift + Enter for a new line</span>
        </div>
      </div>
    </div>
  );
}
