import { motion } from "motion/react";
import { DocumentObject } from "./DocumentObject";
import {
  FinanceIcon,
  FindingsIcon,
  RiskIcon,
  SummaryIcon,
} from "./icons";

/* =====================================================
   EMPTY STATE

   The 3D document carries the hero. Suggestions below
   are framed by the kind of question they are, not as
   generic buttons - the label teaches what the product
   can be asked while it offers the shortcut.
===================================================== */

const SUGGESTIONS = [
  {
    text: "Summarise this document",
    kind: "Overview",
    Icon: SummaryIcon,
  },
  {
    text: "What are the key findings?",
    kind: "Analysis",
    Icon: FindingsIcon,
  },
  {
    text: "Find the financial highlights",
    kind: "Figures",
    Icon: FinanceIcon,
  },
  {
    text: "What risks are mentioned?",
    kind: "Risk",
    Icon: RiskIcon,
  },
];

type Props = {
  hasDocument: boolean;
  isBusy: boolean;
  onAsk: (question: string) => void;
};

export function EmptyState({ hasDocument, isBusy, onAsk }: Props) {
  return (
    <motion.div
      className="hero"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
    >
      <motion.div
        initial={{ opacity: 0, y: 14, scale: 0.96 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{
          type: "spring",
          stiffness: 200,
          damping: 24,
          delay: 0.05,
        }}
      >
        <DocumentObject active={isBusy} />
      </motion.div>

      <motion.h1
        className="hero-title"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: "easeOut", delay: 0.14 }}
      >
        Ask your documents anything.
      </motion.h1>

      <motion.p
        className="hero-sub"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: "easeOut", delay: 0.2 }}
      >
        {hasDocument
          ? "Every answer is grounded in the pages it came from, with the evidence shown beside it."
          : "Upload a PDF and explore its contents with grounded answers, cited page by page."}
      </motion.p>

      <motion.div
        className="suggest"
        initial="hidden"
        animate="visible"
        variants={{
          hidden: {},
          visible: {
            transition: { staggerChildren: 0.06, delayChildren: 0.26 },
          },
        }}
      >
        {SUGGESTIONS.map(({ text, kind, Icon }) => (
          <motion.button
            key={text}
            type="button"
            className="suggest-card"
            onClick={() => onAsk(text)}
            disabled={!hasDocument || isBusy}
            title={
              hasDocument
                ? text
                : "Upload a PDF first"
            }
            variants={{
              hidden: { opacity: 0, y: 10 },
              visible: {
                opacity: 1,
                y: 0,
                transition: { duration: 0.3, ease: "easeOut" },
              },
            }}
            whileHover={hasDocument && !isBusy ? { y: -2 } : undefined}
            whileTap={hasDocument && !isBusy ? { scale: 0.985 } : undefined}
          >
            <span className="suggest-icon">
              <Icon size={15} />
            </span>

            <span className="suggest-text">
              {text}
              <span className="suggest-kind">{kind}</span>
            </span>
          </motion.button>
        ))}
      </motion.div>
    </motion.div>
  );
}
