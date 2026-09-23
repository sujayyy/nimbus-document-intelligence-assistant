import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";

import "./App.css";

import { CommandBar } from "./components/CommandBar";
import { DocumentRail } from "./components/DocumentRail";
import { EmptyState } from "./components/EmptyState";
import { EvidencePanel } from "./components/EvidencePanel";
import { IngestCinematic } from "./components/IngestCinematic";
import { ReasoningLattice } from "./components/ReasoningLattice";
import { CountUp } from "./components/CountUp";
import { Markdown } from "./components/Markdown";
import { ParticleField } from "./components/ParticleField";
import {
  CheckIcon,
  CopyIcon,
  MenuIcon,
  NewChatIcon,
  PanelIcon,
  PdfIcon,
} from "./components/icons";
import {
  formatTime,
  getSourcePage,
  type Message,
  type Source,
  type UploadedDocument,
} from "./types";

/* =====================================================
   NIMBUS

   The transport layer below is unchanged from the
   original client: the same endpoints, the same
   multipart upload, the same SSE frame parsing, the
   same citation-filtering rules and the same message
   identity scheme. Everything added here is presentation
   fed by state that already existed, plus three fields
   that record what the stream reported so the retrieval
   trace can show it.
===================================================== */

const API_BASE_URL = "http://localhost:5001/api";

function App() {
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadingName, setUploadingName] = useState<string | null>(null);

  /* Drives the ingest cinematic. `settled` flips only when
     the real request returns, so the sequence can hold. */
  const [ingest, setIngest] = useState<{
    name: string;
    settled: boolean;
    failed: boolean;
    pages?: number;
    chunks?: number;
  } | null>(null);

  const [documents, setDocuments] = useState<UploadedDocument[]>([]);
  const [documentId, setDocumentId] = useState<string | null>(null);
  const [documentName, setDocumentName] = useState<string | null>(null);

  const [messages, setMessages] = useState<Message[]>([]);

  /* --- View state (presentation only) --------------- */

  const [activePage, setActivePage] = useState<number | null>(null);
  const [railOpen, setRailOpen] = useState(false);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [copiedId, setCopiedId] = useState<number | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const dragDepth = useRef(0);

  /* The uploaded document waits here until the cinematic
     resolves, so it lands in the rail on the beat rather
     than popping in mid-sequence. */
  const pendingDoc = useRef<UploadedDocument | null>(null);

  /*
   * Citation pages and raw sources are stored per
   * assistant message. This prevents unrelated retrieved
   * pages from being shown as sources.
   */

  const citedPagesRef = useRef<Record<number, number[]>>({});
  const pendingSourcesRef = useRef<Record<number, Source[]>>({});

  /* Tokens arrive far faster than the screen refreshes.
     Buffering them and flushing once per frame keeps the
     transcript identical while cutting renders from one
     per token to at most one per frame. */
  const tokenBuffer = useRef<Record<number, string>>({});
  const flushHandle = useRef(0);

  /* ===================================================
     AUTO SCROLL
  =================================================== */

  useEffect(() => {
    requestAnimationFrame(() => {
      messagesEndRef.current?.scrollIntoView({
        behavior: "auto",
        block: "end",
      });
    });
  }, [messages]);

  useEffect(
    () => () => {
      if (flushHandle.current) {
        cancelAnimationFrame(flushHandle.current);
      }
    },
    [],
  );

  /* ===================================================
     TEXTAREA RESIZE
  =================================================== */

  const resizeTextarea = () => {
    const textarea = textareaRef.current;

    if (!textarea) {
      return;
    }

    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 168)}px`;
  };

  const handleInputChange = (
    e: React.ChangeEvent<HTMLTextAreaElement>,
  ) => {
    setInput(e.target.value);
    resizeTextarea();
  };

  /* ===================================================
     NEW CHAT
  =================================================== */

  const startNewChat = () => {
    if (isLoading || isUploading) {
      return;
    }

    setInput("");
    setDocuments([]);
    setDocumentId(null);
    setDocumentName(null);
    setActivePage(null);

    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }

    setMessages([]);
  };

  /* ===================================================
     SPEECH TO TEXT
  =================================================== */

  const startSpeechRecognition = () => {
    const SpeechRecognition =
      (window as any).SpeechRecognition ||
      (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      alert("Speech recognition is not supported in this browser.");
      return;
    }

    const recognition = new SpeechRecognition();

    recognition.lang = "en-US";
    recognition.continuous = false;
    recognition.interimResults = false;

    recognition.onstart = () => {
      setIsListening(true);
    };

    recognition.onresult = (event: any) => {
      const transcript = event.results[0][0].transcript;

      setInput((previous) =>
        previous.trim() ? `${previous} ${transcript}` : transcript,
      );

      setTimeout(resizeTextarea, 0);
    };

    recognition.onerror = (event: any) => {
      console.error("Speech recognition error:", event.error);
      setIsListening(false);
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    recognition.start();
  };

  /* ===================================================
     PDF UPLOAD
  =================================================== */

  const uploadPdf = async (file: File) => {
    if (isLoading || isUploading) {
      return;
    }

    const isPdf =
      file.type === "application/pdf" ||
      file.name.toLowerCase().endsWith(".pdf");

    if (!isPdf) {
      alert("Only PDF files are supported.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    setIsUploading(true);
    setUploadingName(file.name);
    setIngest({ name: file.name, settled: false, failed: false });

    try {
      const response = await fetch(`${API_BASE_URL}/documents`, {
        method: "POST",
        body: formData,
      });

      let data: any = null;

      try {
        data = await response.json();
      } catch {
        // Keep generic error.
      }

      if (!response.ok) {
        const errorMessage =
          data?.details?.detail ||
          data?.details?.error ||
          data?.detail ||
          data?.error ||
          "PDF upload failed.";

        throw new Error(errorMessage);
      }

      if (!data?.document_id) {
        throw new Error(
          "The backend did not return a document_id.",
        );
      }

      const uploadedDocument: UploadedDocument = {
        id: data.document_id,
        name: data.filename || file.name,
        pages: Number(data.pages || 0),
        chunks: Number(data.chunks || 0),
      };

      /* Held until the cinematic resolves - commitIngest
         below does the actual insertion. */
      pendingDoc.current = uploadedDocument;

      setIngest((previous) =>
        previous
          ? {
              ...previous,
              settled: true,
              pages: uploadedDocument.pages,
              chunks: uploadedDocument.chunks,
            }
          : previous,
      );
    } catch (error) {
      console.error("Nimbus upload error:", error);

      const errorText =
        error instanceof Error
          ? error.message
          : "Unknown upload error.";

      pendingDoc.current = null;

      setIngest((previous) =>
        previous
          ? { ...previous, settled: true, failed: true }
          : previous,
      );

      setMessages((previous) => [
        ...previous,
        {
          id: Date.now(),
          role: "assistant",
          content: `I couldn't upload the PDF.\n\n${errorText}`,
          timestamp: new Date(),
          isError: true,
        },
      ]);
    } finally {
      setIsUploading(false);
      setUploadingName(null);

      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  /* Called when the cinematic finishes its resolve. */
  const commitIngest = () => {
    const uploadedDocument = pendingDoc.current;

    setIngest(null);

    if (!uploadedDocument) {
      return;
    }

    pendingDoc.current = null;

    setDocuments((previous) => [...previous, uploadedDocument]);
    setDocumentId(uploadedDocument.id);
    setDocumentName(uploadedDocument.name);

    setMessages((previous) => [
      ...previous,
      {
        id: Date.now(),
        role: "user",
        content: "",
        timestamp: new Date(),
        documentUpload: uploadedDocument,
      },
    ]);
  };

  const handleFileChange = (
    e: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const file = e.target.files?.[0];

    if (file) {
      uploadPdf(file);
    }
  };

  const selectDocument = (document: UploadedDocument) => {
    if (isLoading || isUploading) {
      return;
    }

    setDocumentId(document.id);
    setDocumentName(document.name);
    setRailOpen(false);
  };

  /* Removes the document from this session's picker only.
     There is no DELETE endpoint, so nothing is destroyed
     server-side and the index stays available. */

  const removeDocument = (id: string) => {
    if (isLoading || isUploading) {
      return;
    }

    setDocuments((previous) => {
      const next = previous.filter((item) => item.id !== id);

      if (id === documentId) {
        const fallback = next[next.length - 1] ?? null;
        setDocumentId(fallback?.id ?? null);
        setDocumentName(fallback?.name ?? null);
      }

      return next;
    });
  };

  /* ===================================================
     DRAG AND DROP
  =================================================== */

  const handleDragEnter = (e: React.DragEvent) => {
    if (!Array.from(e.dataTransfer.types).includes("Files")) {
      return;
    }

    dragDepth.current += 1;
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    dragDepth.current = Math.max(0, dragDepth.current - 1);

    if (dragDepth.current === 0) {
      setIsDragging(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    dragDepth.current = 0;
    setIsDragging(false);

    const file = e.dataTransfer.files?.[0];

    if (file) {
      uploadPdf(file);
    }
  };

  /* ===================================================
     COPY
  =================================================== */

  const copyMessage = async (id: number, content: string) => {
    try {
      await navigator.clipboard.writeText(content);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 1600);
    } catch (error) {
      console.error("Copy failed:", error);
    }
  };

  /* ===================================================
     FILTER SOURCES
  =================================================== */

  const filterSourcesByCitedPages = (
    sources: Source[],
    citedPages: number[],
  ) => {
    if (citedPages.length === 0) {
      return [];
    }

    const citedSet = new Set(citedPages);
    const seenPages = new Set<number>();

    return sources.filter((source) => {
      const page = getSourcePage(source);

      if (
        page == null ||
        !citedSet.has(page) ||
        seenPages.has(page)
      ) {
        return false;
      }

      seenPages.add(page);
      return true;
    });
  };

  /* ===================================================
     UPDATE SOURCES
  =================================================== */

  const updateAssistantSources = (
    assistantId: number,
    sources: Source[],
  ) => {
    pendingSourcesRef.current[assistantId] = sources;

    const citedPages = citedPagesRef.current[assistantId] || [];

    const filteredSources = filterSourcesByCitedPages(
      sources,
      citedPages,
    );

    setMessages((previous) =>
      previous.map((message) =>
        message.id === assistantId
          ? {
              ...message,
              sources: filteredSources,
              retrieved: sources,
            }
          : message,
      ),
    );
  };

  /* ===================================================
     UPDATE CITATIONS
  =================================================== */

  const updateAssistantCitations = (
    assistantId: number,
    pages: unknown,
  ) => {
    const normalizedPages = Array.from(
      new Set(
        Array.isArray(pages)
          ? pages
              .map(Number)
              .filter((page) => Number.isFinite(page))
          : [],
      ),
    ).sort((a, b) => a - b);

    citedPagesRef.current[assistantId] = normalizedPages;

    const rawSources = pendingSourcesRef.current[assistantId] || [];

    const filteredSources = filterSourcesByCitedPages(
      rawSources,
      normalizedPages,
    );

    setMessages((previous) =>
      previous.map((message) =>
        message.id === assistantId
          ? {
              ...message,
              sources: filteredSources,
              citedPages: normalizedPages,
            }
          : message,
      ),
    );
  };

  /* ===================================================
     APPEND STREAM TOKEN
  =================================================== */

  const flushTokens = () => {
    flushHandle.current = 0;

    const buffered = tokenBuffer.current;
    tokenBuffer.current = {};

    const ids = Object.keys(buffered);

    if (ids.length === 0) {
      return;
    }

    setMessages((previous) =>
      previous.map((message) => {
        const chunk = buffered[message.id];

        return chunk
          ? { ...message, content: message.content + chunk }
          : message;
      }),
    );
  };

  const appendAssistantText = (
    assistantId: number,
    text: string,
  ) => {
    if (!text) {
      return;
    }

    tokenBuffer.current[assistantId] =
      (tokenBuffer.current[assistantId] ?? "") + text;

    if (flushHandle.current) {
      return;
    }

    flushHandle.current = requestAnimationFrame(flushTokens);
  };

  /* ===================================================
     PROCESS SSE EVENT
  =================================================== */

  const processSSEEvent = (event: string, assistantId: number) => {
    const lines = event.split(/\r?\n/);

    const eventName =
      lines
        .find((line) => line.startsWith("event:"))
        ?.slice(6)
        .trim() || "message";

    const dataLine = lines.find((line) => line.startsWith("data:"));

    if (!dataLine) {
      return;
    }

    const dataText = dataLine.slice(5).trim();

    if (!dataText || dataText === "[DONE]") {
      return;
    }

    let data: any;

    try {
      data = JSON.parse(dataText);
    } catch {
      console.warn("Could not parse SSE data:", dataText);
      return;
    }

    /* TOKEN */

    if (eventName === "token") {
      const token =
        typeof data === "string" ? data : data?.text || "";

      appendAssistantText(assistantId, token);
      return;
    }

    /* CITATION VALIDATION */

    if (eventName === "citation_validation") {
      updateAssistantCitations(assistantId, data?.cited_pages);
      return;
    }

    /* SOURCES */

    if (eventName === "sources") {
      const sources = Array.isArray(data)
        ? data
        : data?.sources || [];

      updateAssistantSources(assistantId, sources);
      return;
    }

    /* ERROR */

    if (eventName === "error") {
      throw new Error(
        data?.error || data?.detail || "Nimbus streaming failed.",
      );
    }
  };

  /* ===================================================
     SEND MESSAGE
  =================================================== */

  const sendMessage = async (override?: string) => {
    const trimmedInput = (override ?? input).trim();

    if (!trimmedInput || isLoading || isUploading) {
      return;
    }

    if (!documentId) {
      setMessages((previous) => [
        ...previous,
        {
          id: Date.now(),
          role: "assistant",
          content:
            "Please upload a PDF before asking a question.",
          timestamp: new Date(),
        },
      ]);

      return;
    }

    const userMessage: Message = {
      id: Date.now(),
      role: "user",
      content: trimmedInput,
      timestamp: new Date(),
    };

    const assistantId = Date.now() + 1;

    citedPagesRef.current[assistantId] = [];
    pendingSourcesRef.current[assistantId] = [];

    setMessages((previous) => [
      ...previous,
      userMessage,
      {
        id: assistantId,
        role: "assistant",
        content: "",
        timestamp: new Date(),
        sources: [],
        streaming: true,
      },
    ]);

    setInput("");
    setActivePage(null);

    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }

    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/query/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          document_id: documentId,
          question: trimmedInput,
        }),
      });

      if (!response.ok) {
        let errorMessage =
          "Something went wrong while contacting Nimbus.";

        try {
          const errorData = await response.json();

          errorMessage =
            errorData?.details?.detail ||
            errorData?.details?.error ||
            errorData?.detail ||
            errorData?.error ||
            errorMessage;
        } catch {
          // Keep generic error.
        }

        throw new Error(errorMessage);
      }

      if (!response.body) {
        throw new Error(
          "Streaming is not supported by this response.",
        );
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();

        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });

        const events = buffer.split(/\r?\n\r?\n/);

        buffer = events.pop() || "";

        for (const event of events) {
          if (event.trim()) {
            processSSEEvent(event, assistantId);
          }
        }
      }

      if (buffer.trim()) {
        processSSEEvent(buffer, assistantId);
      }
    } catch (error) {
      console.error("Nimbus API error:", error);

      const errorText =
        error instanceof Error
          ? error.message
          : "Unknown connection error.";

      setMessages((previous) =>
        previous.map((message) =>
          message.id === assistantId
            ? {
                ...message,
                content: `I couldn't reach Nimbus.\n\n${errorText}`,
                sources: [],
                isError: true,
              }
            : message,
        ),
      );
    } finally {
      /* Land the tail of the buffer before the message is
         marked complete, or the last frame's tokens are
         dropped. */
      if (flushHandle.current) {
        cancelAnimationFrame(flushHandle.current);
      }

      flushTokens();

      setIsLoading(false);

      setMessages((previous) =>
        previous.map((message) =>
          message.id === assistantId
            ? { ...message, streaming: false }
            : message,
        ),
      );
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendMessage();
  };

  const handleKeyDown = (
    e: React.KeyboardEvent<HTMLTextAreaElement>,
  ) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  /* ===================================================
     DERIVED
  =================================================== */

  /* Evidence mirrors the most recent answer that has any. */
  const evidenceSources = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      const message = messages[i];

      if (
        message.role === "assistant" &&
        message.sources &&
        message.sources.length > 0
      ) {
        return message.sources;
      }
    }

    return [] as Source[];
  }, [messages]);

  /* The pipeline reports its stage once, in the status
     pill, instead of repeating a stepper inside every
     answer. Derived from the same stream flags the
     stepper used. */
  const phase = useMemo(() => {
    const last = messages[messages.length - 1];

    if (!last || last.role !== "assistant" || !last.streaming) {
      return null;
    }

    if (!last.retrieved) {
      return "Retrieving";
    }

    if (!last.citedPages) {
      return "Reading";
    }

    return "Composing";
  }, [messages]);

  const isBusy = isLoading || isUploading;
  const hasConversation = messages.length > 0;

  const placeholder = isUploading
    ? "Processing your PDF…"
    : isLoading
      ? "Nimbus is reading…"
      : documentId
        ? "Ask anything about this document…"
        : "Upload a PDF to begin…";

  const hint = documentName
    ? `${documentName} · active`
    : "No document selected";

  return (
    <main
      className="shell"
      onDragEnter={handleDragEnter}
      onDragOver={(e) => e.preventDefault()}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      <div className="desk" />
      <div className="desk-bloom" />

      <input
        ref={fileInputRef}
        type="file"
        accept="application/pdf,.pdf"
        onChange={handleFileChange}
        hidden
      />

      {/* ============================================
          TOPBAR
      ============================================ */}

      <header className="topbar">
        <div className="topbar-left">
          <button
            type="button"
            className="btn-icon only-narrow"
            onClick={() => setRailOpen(true)}
            aria-label="Open the document library"
          >
            <MenuIcon size={18} />
          </button>

          <button
            type="button"
            className="brand"
            onClick={startNewChat}
            aria-label="Nimbus - start a new session"
          >
            <span className="mark" aria-hidden="true">
              <span className="mark-sheet" />
              <span className="mark-sheet" />
              <span className="mark-sheet" />
            </span>

            <span className="brand-text">
              <span className="brand-name">Nimbus</span>
              <span className="brand-sub">Document Intelligence</span>
            </span>
          </button>
        </div>

        <div className="topbar-right">
          <span
            className={`status ${
              isBusy ? "is-busy" : documentId ? "is-live" : ""
            }`}
          >
            <span className="status-dot" />
            {isUploading
              ? "Processing"
              : isLoading
                ? (phase ?? "Retrieving")
                : documentId
                  ? "Grounded"
                  : "Awaiting PDF"}
          </span>

          <button
            type="button"
            className="btn-icon"
            onClick={startNewChat}
            disabled={isBusy}
            aria-label="Start a new session"
            title="New session"
          >
            <NewChatIcon size={17} />
          </button>

          <button
            type="button"
            className="btn-icon only-narrow"
            onClick={() => setEvidenceOpen(true)}
            aria-label="Open the evidence panel"
          >
            <PanelIcon size={17} />
          </button>
        </div>
      </header>

      {/* ============================================
          RAIL
      ============================================ */}

      <aside
        className={`rail ${railOpen ? "is-open" : ""}`}
        aria-label="Document library"
      >
        <DocumentRail
          documents={documents}
          activeId={documentId}
          isBusy={isBusy}
          uploadingName={uploadingName}
          onSelect={selectDocument}
          onRemove={removeDocument}
          onUploadClick={() => fileInputRef.current?.click()}
        />
      </aside>

      {/* ============================================
          STAGE
      ============================================ */}

      <section className="stage">
        {/* Quickens while the pipeline is working, settles
            when it is idle - ambient motion tied to real
            state rather than running for its own sake. */}
        <ParticleField intensity={isLoading ? 1 : 0} />

        <div className="stage-scroll scroll">
          <div className="stage-inner">
            {!hasConversation ? (
              <EmptyState
                hasDocument={Boolean(documentId)}
                isBusy={isBusy}
                onAsk={(question) => sendMessage(question)}
              />
            ) : (
              messages.map((message) => {
                /* --- Upload event row --------------- */

                if (message.documentUpload) {
                  return (
                    <motion.div
                      key={message.id}
                      className="event"
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{
                        type: "spring",
                        stiffness: 380,
                        damping: 28,
                      }}
                    >
                      <span className="event-icon">
                        <PdfIcon size={14} />
                      </span>

                      <span className="event-text">
                        <strong>{message.documentUpload.name}</strong> is
                        ready
                      </span>

                      <span className="event-meta">
                        <CountUp value={message.documentUpload.pages} />{" "}
                        pages
                        <span className="meta-sep" aria-hidden="true" />
                        <span className="meta-chunks">
                          <CountUp value={message.documentUpload.chunks} />{" "}
                          chunks
                        </span>
                      </span>
                    </motion.div>
                  );
                }

                /* --- Question ----------------------- */

                if (message.role === "user") {
                  return (
                    <motion.div
                      key={message.id}
                      className="turn is-question"
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.3, ease: "easeOut" }}
                    >
                      <div className="turn-margin">
                        <span className="turn-badge">Q</span>
                      </div>

                      <div className="question">
                        <div className="label question-label">
                          {formatTime(message.timestamp)}
                        </div>

                        <p className="question-text">
                          {message.content}
                        </p>
                      </div>
                    </motion.div>
                  );
                }

                /* --- Answer ------------------------- */

                const isError = Boolean(message.isError);

                const canAct =
                  !message.streaming &&
                  !isError &&
                  message.content.trim() !== "";

                return (
                  <motion.div
                    key={message.id}
                    className="turn is-answer"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3, ease: "easeOut" }}
                  >
                    <div className="turn-margin">
                      <span className="turn-badge" aria-hidden="true">
                        <span className="mark-dot" />
                      </span>
                    </div>

                    <div
                      className={`answer ${isError ? "is-error" : ""}`}
                    >
                      <div className="answer-head">
                        <span className="answer-name">Nimbus</span>
                        <span className="answer-time">
                          {formatTime(message.timestamp)}
                        </span>
                      </div>

                      <div className="answer-body">
                        {message.content ? (
                          <Markdown
                            content={message.content}
                            activePage={activePage}
                            onCite={(page) => {
                              setActivePage(
                                activePage === page ? null : page,
                              );
                              setEvidenceOpen(true);
                            }}
                          />
                        ) : message.streaming ? (
                          <ReasoningLattice
                            caption={
                              !message.retrieved
                                ? "Retrieving"
                                : !message.citedPages
                                  ? "Reading pages"
                                  : "Composing"
                            }
                          />
                        ) : null}
                      </div>

                      {canAct && (
                        <div className="acts">
                          <button
                            type="button"
                            className={`act ${
                              copiedId === message.id ? "is-done" : ""
                            }`}
                            onClick={() =>
                              copyMessage(message.id, message.content)
                            }
                          >
                            {copiedId === message.id ? (
                              <CheckIcon size={13} />
                            ) : (
                              <CopyIcon size={13} />
                            )}
                            {copiedId === message.id
                              ? "Copied"
                              : "Copy"}
                          </button>

                          {(message.citedPages?.length ?? 0) > 0 && (
                            <span className="cited">
                              <span className="cited-label">
                                Grounded in
                              </span>

                              {message.citedPages?.map((page) => (
                                <button
                                  key={page}
                                  type="button"
                                  className={`cited-chip ${
                                    activePage === page ? "is-on" : ""
                                  }`}
                                  onClick={() => {
                                    setActivePage(
                                      activePage === page ? null : page,
                                    );
                                    setEvidenceOpen(true);
                                  }}
                                  title={`Show page ${page}`}
                                >
                                  p.{page}
                                </button>
                              ))}
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </motion.div>
                );
              })
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        <CommandBar
          value={input}
          placeholder={placeholder}
          hint={hint}
          canSend={Boolean(input.trim()) && !isBusy && Boolean(documentId)}
          isLoading={isLoading}
          isUploading={isUploading}
          isListening={isListening}
          textareaRef={textareaRef}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          onSubmit={handleSubmit}
          onUploadClick={() => fileInputRef.current?.click()}
          onMicClick={startSpeechRecognition}
        />
      </section>

      {/* ============================================
          EVIDENCE
      ============================================ */}

      <aside
        className={`evidence ${evidenceOpen ? "is-open" : ""}`}
        aria-label="Evidence"
      >
        <EvidencePanel
          sources={evidenceSources}
          documentName={documentName}
          activePage={activePage}
          onSelect={setActivePage}
          onClose={() => setEvidenceOpen(false)}
        />
      </aside>

      {/* ============================================
          OVERLAYS
      ============================================ */}

      <AnimatePresence>
        {(railOpen || evidenceOpen) && (
          <motion.button
            type="button"
            className="scrim"
            aria-label="Close panel"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            onClick={() => {
              setRailOpen(false);
              setEvidenceOpen(false);
            }}
          />
        )}
      </AnimatePresence>

      <AnimatePresence>
        {ingest && (
          <IngestCinematic
            name={ingest.name}
            settled={ingest.settled}
            failed={ingest.failed}
            pages={ingest.pages}
            chunks={ingest.chunks}
            onDone={commitIngest}
          />
        )}
      </AnimatePresence>

      <AnimatePresence>
        {isDragging && (
          <motion.div
            className="drop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.16 }}
          >
            <motion.div
              className="drop-frame"
              initial={{ scale: 0.94, y: 10 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.97 }}
              transition={{
                type: "spring",
                stiffness: 340,
                damping: 26,
              }}
            >
              <PdfIcon size={34} />
              <span className="drop-title">Drop to add</span>
              <span className="drop-sub">PDF only</span>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </main>
  );
}

export default App;
