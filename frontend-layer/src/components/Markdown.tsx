import { memo } from "react";
import type React from "react";

/* =====================================================
   MARKDOWN

   The block and inline grammar is carried over from the
   original renderer unchanged - same fences, headings,
   bullets, ordered lists and rules - so answers that
   rendered correctly before still do.

   Two things are new, both of them document-specific:
   pipe tables, which financial documents produce
   constantly, and [Page N] citations, which become real
   controls that drive the evidence panel.
===================================================== */

/* No /g flag: RegExp.test is stateful when global, which
   makes repeated calls alternate true/false and silently
   drops every other citation. */
const CITE_NUM_RE = /^\[Page\s+(\d+)\]$/;

type InlineProps = {
  text: string;
  onCite?: (page: number) => void;
  activePage?: number | null;
};

function renderInline({
  text,
  onCite,
  activePage,
}: InlineProps): React.ReactNode[] {
  const parts = text.split(
    /(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*|\[Page\s+\d+\])/g,
  );

  return parts.map((part, index) => {
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code key={index} className="md-code">
          {part.slice(1, -1)}
        </code>
      );
    }

    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }

    /* Checked before single-asterisk italics so that a
       bold run is never mistaken for one. */
    const citeMatch = part.match(CITE_NUM_RE);

    if (citeMatch) {
      const page = Number(citeMatch[1]);

      if (Number.isFinite(page)) {
        return (
          <button
            key={index}
            type="button"
            className={`cite ${activePage === page ? "is-on" : ""}`}
            onClick={() => onCite?.(page)}
            title={`Show the evidence from page ${page}`}
          >
            p.{page}
          </button>
        );
      }
    }

    if (part.startsWith("*") && part.endsWith("*")) {
      return <em key={index}>{part.slice(1, -1)}</em>;
    }

    return <span key={index}>{part}</span>;
  });
}

function splitRow(line: string): string[] {
  return line
    .trim()
    .replace(/^\||\|$/g, "")
    .split("|")
    .map((cell) => cell.trim());
}

function isDivider(line: string): boolean {
  return /^\s*\|?[\s:-]*-[\s:|-]*\|?\s*$/.test(line) && line.includes("-");
}

type Props = {
  content: string;
  onCite?: (page: number) => void;
  activePage?: number | null;
};

function MarkdownBase({ content, onCite, activePage }: Props) {
  const lines = content.split("\n");
  const elements: React.ReactNode[] = [];

  let bulletItems: string[] = [];
  let numberedItems: string[] = [];
  let codeLines: string[] = [];
  let insideCode = false;

  const inline = (text: string) =>
    renderInline({ text, onCite, activePage });

  const flushLists = () => {
    if (bulletItems.length > 0) {
      elements.push(
        <ul key={`ul-${elements.length}`}>
          {bulletItems.map((item, index) => (
            <li key={index}>{inline(item)}</li>
          ))}
        </ul>,
      );

      bulletItems = [];
    }

    if (numberedItems.length > 0) {
      elements.push(
        <ol key={`ol-${elements.length}`}>
          {numberedItems.map((item, index) => (
            <li key={index}>{inline(item)}</li>
          ))}
        </ol>,
      );

      numberedItems = [];
    }
  };

  const flushCode = () => {
    if (codeLines.length > 0) {
      elements.push(
        <pre key={`code-${elements.length}`}>
          <code>{codeLines.join("\n")}</code>
        </pre>,
      );

      codeLines = [];
    }
  };

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    const trimmed = line.trim();

    if (trimmed.startsWith("```")) {
      if (insideCode) {
        flushCode();
        insideCode = false;
      } else {
        flushLists();
        insideCode = true;
      }

      continue;
    }

    if (insideCode) {
      codeLines.push(line);
      continue;
    }

    if (!trimmed) {
      flushLists();
      continue;
    }

    /* --- Table ------------------------------------- */

    if (
      trimmed.startsWith("|") &&
      index + 1 < lines.length &&
      isDivider(lines[index + 1])
    ) {
      flushLists();

      const header = splitRow(trimmed);
      const rows: string[][] = [];

      let cursor = index + 2;

      while (
        cursor < lines.length &&
        lines[cursor].trim().startsWith("|")
      ) {
        rows.push(splitRow(lines[cursor]));
        cursor += 1;
      }

      elements.push(
        <div className="md-table-wrap" key={`tbl-${index}`}>
          <table>
            <thead>
              <tr>
                {header.map((cell, cellIndex) => (
                  <th key={cellIndex}>{inline(cell)}</th>
                ))}
              </tr>
            </thead>

            <tbody>
              {rows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {row.map((cell, cellIndex) => (
                    <td key={cellIndex}>{inline(cell)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );

      index = cursor - 1;
      continue;
    }

    /* --- Headings ---------------------------------- */

    if (trimmed.startsWith("# ")) {
      flushLists();
      elements.push(<h2 key={index}>{inline(trimmed.slice(2))}</h2>);
      continue;
    }

    if (trimmed.startsWith("## ")) {
      flushLists();
      elements.push(<h3 key={index}>{inline(trimmed.slice(3))}</h3>);
      continue;
    }

    if (trimmed.startsWith("### ")) {
      flushLists();
      elements.push(<h4 key={index}>{inline(trimmed.slice(4))}</h4>);
      continue;
    }

    /* --- Lists ------------------------------------- */

    if (/^[-*•]\s+/.test(trimmed)) {
      numberedItems = [];
      bulletItems.push(trimmed.replace(/^[-*•]\s+/, ""));
      continue;
    }

    if (/^\d+\.\s+/.test(trimmed)) {
      bulletItems = [];
      numberedItems.push(trimmed.replace(/^\d+\.\s+/, ""));
      continue;
    }

    /* --- Rule -------------------------------------- */

    if (/^---+$/.test(trimmed)) {
      flushLists();
      elements.push(<hr key={index} />);
      continue;
    }

    /* --- Paragraph ---------------------------------

       Consecutive plain lines are one paragraph, as in
       real Markdown. Rendering each source line as its
       own <p> turned every soft wrap in a model answer
       into a visible paragraph break. */

    flushLists();

    const paragraph: string[] = [trimmed];

    while (index + 1 < lines.length) {
      const next = lines[index + 1].trim();

      if (
        !next ||
        next.startsWith("```") ||
        next.startsWith("|") ||
        next.startsWith("# ") ||
        next.startsWith("## ") ||
        next.startsWith("### ") ||
        /^[-*\u2022]\s+/.test(next) ||
        /^\d+\.\s+/.test(next) ||
        /^---+$/.test(next)
      ) {
        break;
      }

      paragraph.push(next);
      index += 1;
    }

    elements.push(<p key={index}>{inline(paragraph.join(" "))}</p>);
  }

  flushLists();
  flushCode();

  return <div className="md">{elements}</div>;
}

/* Every keystroke of the stream re-renders the whole
   transcript. Without this, each completed answer
   re-parses its entire Markdown on every token of the
   answer being written - quadratic in a long session. */
export const Markdown = memo(MarkdownBase);
