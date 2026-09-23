/* =====================================================
   SHARED TYPES

   Source and UploadedDocument match the API payloads
   exactly as the original client read them - page and
   page_number are both tolerated because the backend
   has used both.
===================================================== */

export type Source = {
  source_file?: string;
  chunk_id?: string;
  page?: number | null;
  page_number?: number | null;
  score?: number;
  text?: string;
};

export type UploadedDocument = {
  id: string;
  name: string;
  pages: number;
  chunks: number;
};

export type Message = {
  id: number;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;

  /** Cited, de-duplicated sources - what the answer stands on. */
  sources?: Source[];

  /** Everything retrieval returned, before citation filtering.
      Used only to visualise the funnel; never shown as evidence. */
  retrieved?: Source[];

  /** Present once citation validation has reported. */
  citedPages?: number[];

  /** True while the SSE stream for this message is open. */
  streaming?: boolean;

  /** Set when the request failed, so the turn renders as an error. */
  isError?: boolean;

  documentUpload?: UploadedDocument;
};

export function getSourcePage(source: Source): number | null {
  return source.page_number ?? source.page ?? null;
}

export function formatTime(date: Date): string {
  return date.toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  });
}
