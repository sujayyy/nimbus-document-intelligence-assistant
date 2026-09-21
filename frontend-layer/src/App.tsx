import { useEffect, useRef, useState } from "react";
import "./App.css";


type Source = {
  source_file?: string;
  chunk_id?: string;
  page?: number | null;
  page_number?: number | null;
  score?: number;
  text?: string;
};


type UploadedDocument = {
  id: string;
  name: string;
  pages: number;
  chunks: number;
};


type Message = {
  id: number;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  sources?: Source[];
  documentUpload?: UploadedDocument;
};


const API_BASE_URL =
  "http://localhost:5001/api";


function formatTime(date: Date) {
  return date.toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  });
}


function getSourcePage(source: Source) {
  return source.page_number ?? source.page ?? null;
}


/* =====================================================
   NIMBUS LOGO
===================================================== */

function NimbusLogo() {
  return (
    <div
      className="nimbus-logo"
      aria-hidden="true"
    >
      <span />
      <span />
      <span />
    </div>
  );
}


/* =====================================================
   PDF ICON
===================================================== */

function PdfIcon() {
  return (
    <svg
      width="22"
      height="22"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <path d="M8 13h2" />
      <path d="M8 17h8" />
      <path d="M13 13h3" />
    </svg>
  );
}


/* =====================================================
   INLINE MARKDOWN
===================================================== */

function renderInline(text: string) {

  const parts =
    text.split(
      /(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)/g
    );


  return parts.map(
    (part, index) => {

      if (
        part.startsWith("`") &&
        part.endsWith("`")
      ) {
        return (
          <code
            key={index}
            className="inline-code"
          >
            {part.slice(1, -1)}
          </code>
        );
      }


      if (
        part.startsWith("**") &&
        part.endsWith("**")
      ) {
        return (
          <strong key={index}>
            {part.slice(2, -2)}
          </strong>
        );
      }


      if (
        part.startsWith("*") &&
        part.endsWith("*")
      ) {
        return (
          <em key={index}>
            {part.slice(1, -1)}
          </em>
        );
      }


      return (
        <span key={index}>
          {part}
        </span>
      );
    }
  );
}


/* =====================================================
   MARKDOWN MESSAGE
===================================================== */

function MarkdownMessage({
  content,
}: {
  content: string;
}) {

  const lines =
    content.split("\n");

  const elements:
    React.ReactNode[] = [];

  let bulletItems:
    string[] = [];

  let numberedItems:
    string[] = [];

  let codeLines:
    string[] = [];

  let insideCode =
    false;


  const flushLists = () => {

    if (
      bulletItems.length > 0
    ) {

      elements.push(
        <ul
          key={`ul-${elements.length}`}
        >
          {bulletItems.map(
            (item, index) => (
              <li key={index}>
                {renderInline(item)}
              </li>
            )
          )}
        </ul>
      );

      bulletItems = [];
    }


    if (
      numberedItems.length > 0
    ) {

      elements.push(
        <ol
          key={`ol-${elements.length}`}
        >
          {numberedItems.map(
            (item, index) => (
              <li key={index}>
                {renderInline(item)}
              </li>
            )
          )}
        </ol>
      );

      numberedItems = [];
    }
  };


  const flushCode = () => {

    if (
      codeLines.length > 0
    ) {

      elements.push(
        <pre
          key={`code-${elements.length}`}
        >
          <code>
            {codeLines.join("\n")}
          </code>
        </pre>
      );

      codeLines = [];
    }
  };


  lines.forEach(
    (line, index) => {

      const trimmed =
        line.trim();


      if (
        trimmed.startsWith("```")
      ) {

        if (insideCode) {

          flushCode();

          insideCode =
            false;

        } else {

          flushLists();

          insideCode =
            true;
        }

        return;
      }


      if (insideCode) {

        codeLines.push(line);

        return;
      }


      if (!trimmed) {

        flushLists();

        return;
      }


      if (
        trimmed.startsWith("# ")
      ) {

        flushLists();

        elements.push(
          <h2 key={index}>
            {renderInline(
              trimmed.slice(2)
            )}
          </h2>
        );

        return;
      }


      if (
        trimmed.startsWith("## ")
      ) {

        flushLists();

        elements.push(
          <h3 key={index}>
            {renderInline(
              trimmed.slice(3)
            )}
          </h3>
        );

        return;
      }


      if (
        trimmed.startsWith("### ")
      ) {

        flushLists();

        elements.push(
          <h4 key={index}>
            {renderInline(
              trimmed.slice(4)
            )}
          </h4>
        );

        return;
      }


      if (
        /^[-*•]\s+/.test(
          trimmed
        )
      ) {

        numberedItems = [];

        bulletItems.push(
          trimmed.replace(
            /^[-*•]\s+/,
            ""
          )
        );

        return;
      }


      if (
        /^\d+\.\s+/.test(
          trimmed
        )
      ) {

        bulletItems = [];

        numberedItems.push(
          trimmed.replace(
            /^\d+\.\s+/,
            ""
          )
        );

        return;
      }


      if (
        /^---+$/.test(
          trimmed
        )
      ) {

        flushLists();

        elements.push(
          <hr key={index} />
        );

        return;
      }


      flushLists();

      elements.push(
        <p key={index}>
          {renderInline(trimmed)}
        </p>
      );
    }
  );


  flushLists();

  flushCode();


  return (
    <div className="markdown">
      {elements}
    </div>
  );
}


/* =====================================================
   PDF UPLOAD CARD
===================================================== */

function UploadCard({
  document,
}: {
  document: UploadedDocument;
}) {

  return (
    <div className="upload-card">

      <div className="upload-card-icon">
        <PdfIcon />
      </div>


      <div className="upload-card-info">

        <div className="upload-card-name">
          {document.name}
        </div>


        <div className="upload-card-meta">

          PDF ·{" "}
          {document.pages}{" "}
          {document.pages === 1
            ? "page"
            : "pages"}{" "}
          ·{" "}
          {document.chunks}{" "}
          {document.chunks === 1
            ? "chunk"
            : "chunks"}

        </div>

      </div>


      <div
        className="upload-card-check"
        aria-label="Upload complete"
      >

        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M20 6L9 17l-5-5" />
        </svg>

      </div>

    </div>
  );
}


/* =====================================================
   APP
===================================================== */

function App() {

  const [input, setInput] =
    useState("");

  const [isLoading, setIsLoading] =
    useState(false);

  const [isListening, setIsListening] =
    useState(false);

  const [isUploading, setIsUploading] =
    useState(false);

  const [documents, setDocuments] = useState<UploadedDocument[]>([]);

  const [documentId, setDocumentId] =
    useState<string | null>(null);

  const [documentName, setDocumentName] =
    useState<string | null>(null);


  const fileInputRef =
    useRef<HTMLInputElement>(null);

  const textareaRef =
    useRef<HTMLTextAreaElement>(null);

  const messagesEndRef =
    useRef<HTMLDivElement>(null);


  /*
   * Citation pages and raw sources
   * are stored per assistant message.
   *
   * This prevents unrelated retrieved
   * pages from being shown as sources.
   */

  const citedPagesRef =
    useRef<Record<number, number[]>>(
      {}
    );

  const pendingSourcesRef =
    useRef<Record<number, Source[]>>(
      {}
    );


  const [messages, setMessages] =
    useState<Message[]>([
      {
        id: 1,

        role: "assistant",

        content:
          "Hello, I'm Nimbus. Upload a PDF using the **+** button, then ask me anything about it.",

        timestamp:
          new Date(),
      },
    ]);


  /* ===================================================
     AUTO SCROLL
  =================================================== */

  useEffect(() => {

    requestAnimationFrame(
      () => {

        messagesEndRef.current?.scrollIntoView(
          {
            behavior: "auto",
            block: "end",
          }
        );

      }
    );

  }, [messages]);


  /* ===================================================
     TEXTAREA RESIZE
  =================================================== */

  const resizeTextarea =
    () => {

      const textarea =
        textareaRef.current;

      if (!textarea) {
        return;
      }

      textarea.style.height =
        "auto";

      const newHeight =
        Math.min(
          textarea.scrollHeight,
          150
        );

      textarea.style.height =
        `${newHeight}px`;
    };


  const handleInputChange = (
    e: React.ChangeEvent<HTMLTextAreaElement>
  ) => {

    setInput(
      e.target.value
    );

    resizeTextarea();
  };


  /* ===================================================
     NEW CHAT
  =================================================== */

  const startNewChat =
    () => {

      if (
        isLoading ||
        isUploading
      ) {
        return;
      }


      setInput("");

      setDocuments([]);

      setDocumentId(null);

      setDocumentName(null);


      if (
        textareaRef.current
      ) {

        textareaRef.current.style.height =
          "auto";
      }


      setMessages([
        {
          id: Date.now(),

          role: "assistant",

          content:
            "Hello, I'm Nimbus. Upload a PDF using the **+** button, then ask me anything about it.",

          timestamp:
            new Date(),
        },
      ]);
    };


  /* ===================================================
     SPEECH TO TEXT
  =================================================== */

  const startSpeechRecognition =
    () => {

      const SpeechRecognition =
        (window as any).SpeechRecognition ||
        (window as any)
          .webkitSpeechRecognition;


      if (
        !SpeechRecognition
      ) {

        alert(
          "Speech recognition is not supported in this browser."
        );

        return;
      }


      const recognition =
        new SpeechRecognition();


      recognition.lang =
        "en-US";

      recognition.continuous =
        false;

      recognition.interimResults =
        false;


      recognition.onstart =
        () => {

          setIsListening(
            true
          );
        };


      recognition.onresult =
        (
          event: any
        ) => {

          const transcript =
            event.results[0][0]
              .transcript;


          setInput(
            (previous) =>
              previous.trim()
                ? `${previous} ${transcript}`
                : transcript
          );


          setTimeout(
            resizeTextarea,
            0
          );
        };


      recognition.onerror =
        (
          event: any
        ) => {

          console.error(
            "Speech recognition error:",
            event.error
          );

          setIsListening(
            false
          );
        };


      recognition.onend =
        () => {

          setIsListening(
            false
          );
        };


      recognition.start();
    };


  /* ===================================================
     PDF UPLOAD
  =================================================== */

  const uploadPdf =
    async (
      file: File
    ) => {

      if (
        isLoading ||
        isUploading
      ) {
        return;
      }


      const isPdf =
        file.type ===
          "application/pdf" ||
        file.name
          .toLowerCase()
          .endsWith(".pdf");


      if (!isPdf) {

        alert(
          "Only PDF files are supported."
        );

        return;
      }


      const formData =
        new FormData();


      formData.append(
        "file",
        file
      );


      setIsUploading(
        true
      );


      try {

        const response =
          await fetch(
            `${API_BASE_URL}/documents`,
            {
              method:
                "POST",

              body:
                formData,
            }
          );


        let data:
          any = null;


        try {

          data =
            await response.json();

        } catch {

          // Keep generic error.
        }


        if (
          !response.ok
        ) {

          const errorMessage =
            data?.details?.detail ||
            data?.details?.error ||
            data?.detail ||
            data?.error ||
            "PDF upload failed.";


          throw new Error(
            errorMessage
          );
        }


        if (
          !data?.document_id
        ) {

          throw new Error(
            "The backend did not return a document_id."
          );
        }


        const uploadedDocument:
          UploadedDocument =
          {
            id:
              data.document_id,

            name:
              data.filename ||
              file.name,

            pages:
              Number(
                data.pages || 0
              ),

            chunks:
              Number(
                data.chunks || 0
              ),
          };

        setDocuments((previous) => [
  ...previous,
  uploadedDocument,
]);

        /*
         * Keep document information
         * internally.
         *
         * Do NOT render a separate
         * document library.
         */

        setDocumentId(
          uploadedDocument.id
        );

        setDocumentName(
          uploadedDocument.name
        );


        /*
         * Show the uploaded PDF
         * directly on the USER side.
         */

        const uploadMessageId =
          Date.now();

        const successMessageId =
          uploadMessageId + 1;


        setMessages(
          (previous) => [

            ...previous,

            {
              id:
                uploadMessageId,

              role:
                "user",

              content:
                "",

              timestamp:
                new Date(),

              documentUpload:
                uploadedDocument,
            },


            {
              id:
                successMessageId,

              role:
                "assistant",

              content:
                `PDF uploaded successfully.\n\n**${uploadedDocument.name}** is ready for questions.\n\n**${uploadedDocument.pages} ${uploadedDocument.pages === 1 ? "page" : "pages"} · ${uploadedDocument.chunks} ${uploadedDocument.chunks === 1 ? "chunk" : "chunks"}**`,

              timestamp:
                new Date(),
            },

          ]
        );

      } catch (
        error
      ) {

        console.error(
          "Nimbus upload error:",
          error
        );


        const errorText =
          error instanceof Error
            ? error.message
            : "Unknown upload error.";


        setMessages(
          (previous) => [

            ...previous,

            {
              id:
                Date.now(),

              role:
                "assistant",

              content:
                `I couldn't upload the PDF.\n\n${errorText}`,

              timestamp:
                new Date(),
            },

          ]
        );

      } finally {

        setIsUploading(
          false
        );


        if (
          fileInputRef.current
        ) {

          fileInputRef.current.value =
            "";
        }
      }
    };


  const handleFileChange =
    (
      e: React.ChangeEvent<HTMLInputElement>
    ) => {

      const file =
        e.target.files?.[0];


      if (file) {

        uploadPdf(
          file
        );
      }
    };

const selectDocument = (document: UploadedDocument) => {
  if (isLoading || isUploading) return;

  setDocumentId(document.id);
  setDocumentName(document.name);
};

  /* ===================================================
     COPY
  =================================================== */

  const copyMessage =
    async (
      content: string
    ) => {

      try {

        await navigator.clipboard.writeText(
          content
        );

      } catch (
        error
      ) {

        console.error(
          "Copy failed:",
          error
        );
      }
    };


  /* ===================================================
     FILTER SOURCES
  =================================================== */

  const filterSourcesByCitedPages =
    (
      sources: Source[],
      citedPages: number[]
    ) => {

      if (
        citedPages.length ===
        0
      ) {

        return [];
      }


      const citedSet =
        new Set(
          citedPages
        );


      const seenPages =
        new Set<number>();


      return sources.filter(
        (source) => {

          const page =
            getSourcePage(
              source
            );


          if (
            page == null ||
            !citedSet.has(page) ||
            seenPages.has(page)
          ) {

            return false;
          }


          seenPages.add(
            page
          );

          return true;
        }
      );
    };


  /* ===================================================
     UPDATE SOURCES
  =================================================== */

  const updateAssistantSources =
    (
      assistantId: number,
      sources: Source[]
    ) => {

      pendingSourcesRef.current[
        assistantId
      ] =
        sources;


      const citedPages =
        citedPagesRef.current[
          assistantId
        ] || [];


      const filteredSources =
        filterSourcesByCitedPages(
          sources,
          citedPages
        );


      setMessages(
        (previous) =>
          previous.map(
            (message) =>
              message.id ===
              assistantId

                ? {
                    ...message,

                    sources:
                      filteredSources,
                  }

                : message
          )
      );
    };


  /* ===================================================
     UPDATE CITATIONS
  =================================================== */

  const updateAssistantCitations =
    (
      assistantId: number,
      pages: unknown
    ) => {

      const normalizedPages =
        Array.from(
          new Set(
            Array.isArray(pages)
              ? pages
                  .map(Number)
                  .filter(
                    (page) =>
                      Number.isFinite(
                        page
                      )
                  )
              : []
          )
        ).sort(
          (a, b) =>
            a - b
        );


      citedPagesRef.current[
        assistantId
      ] =
        normalizedPages;


      const rawSources =
        pendingSourcesRef.current[
          assistantId
        ] || [];


      const filteredSources =
        filterSourcesByCitedPages(
          rawSources,
          normalizedPages
        );


      setMessages(
        (previous) =>
          previous.map(
            (message) =>
              message.id ===
              assistantId

                ? {
                    ...message,

                    sources:
                      filteredSources,
                  }

                : message
          )
      );
    };


  /* ===================================================
     APPEND STREAM TOKEN
  =================================================== */

  const appendAssistantText =
    (
      assistantId: number,
      text: string
    ) => {

      if (!text) {
        return;
      }


      setMessages(
        (previous) =>
          previous.map(
            (message) =>
              message.id ===
              assistantId

                ? {
                    ...message,

                    content:
                      message.content +
                      text,
                  }

                : message
          )
      );
    };


  /* ===================================================
     PROCESS SSE EVENT
  =================================================== */

  const processSSEEvent =
    (
      event: string,
      assistantId: number
    ) => {

      const lines =
        event.split(
          /\r?\n/
        );


      const eventName =
        lines
          .find(
            (line) =>
              line.startsWith(
                "event:"
              )
          )
          ?.slice(6)
          .trim() ||
        "message";


      const dataLine =
        lines.find(
          (line) =>
            line.startsWith(
              "data:"
            )
        );


      if (!dataLine) {
        return;
      }


      const dataText =
        dataLine
          .slice(5)
          .trim();


      if (
        !dataText ||
        dataText ===
          "[DONE]"
      ) {

        return;
      }


      let data:
        any;


      try {

        data =
          JSON.parse(
            dataText
          );

      } catch {

        console.warn(
          "Could not parse SSE data:",
          dataText
        );

        return;
      }


      /* TOKEN */

      if (
        eventName ===
        "token"
      ) {

        const token =
          typeof data ===
          "string"

            ? data

            : data?.text ||
              "";


        appendAssistantText(
          assistantId,
          token
        );

        return;
      }


      /* CITATION VALIDATION */

      if (
        eventName ===
        "citation_validation"
      ) {

        updateAssistantCitations(
          assistantId,
          data?.cited_pages
        );

        return;
      }


      /* SOURCES */

      if (
        eventName ===
        "sources"
      ) {

        const sources =
          Array.isArray(data)
            ? data
            : data?.sources ||
              [];


        updateAssistantSources(
          assistantId,
          sources
        );

        return;
      }


      /* ERROR */

      if (
        eventName ===
        "error"
      ) {

        throw new Error(
          data?.error ||
            data?.detail ||
            "Nimbus streaming failed."
        );
      }
    };


  /* ===================================================
     SEND MESSAGE
  =================================================== */

  const sendMessage =
    async () => {

      const trimmedInput =
        input.trim();


      if (
        !trimmedInput ||
        isLoading ||
        isUploading
      ) {

        return;
      }


      if (
        !documentId
      ) {

        setMessages(
          (previous) => [

            ...previous,

            {
              id:
                Date.now(),

              role:
                "assistant",

              content:
                "Please upload a PDF using the **+** button before asking a question.",

              timestamp:
                new Date(),
            },

          ]
        );

        return;
      }


      const userMessage:
        Message =
        {
          id:
            Date.now(),

          role:
            "user",

          content:
            trimmedInput,

          timestamp:
            new Date(),
        };


      const assistantId =
        Date.now() + 1;


      citedPagesRef.current[
        assistantId
      ] = [];


      pendingSourcesRef.current[
        assistantId
      ] = [];


      setMessages(
        (previous) => [

          ...previous,

          userMessage,

          {
            id:
              assistantId,

            role:
              "assistant",

            content:
              "",

            timestamp:
              new Date(),

            sources:
              [],
          },

        ]
      );


      setInput("");


      if (
        textareaRef.current
      ) {

        textareaRef.current.style.height =
          "auto";
      }


      setIsLoading(
        true
      );


      try {

        const response =
          await fetch(
            `${API_BASE_URL}/query/stream`,
            {
              method:
                "POST",

              headers: {
                "Content-Type":
                  "application/json",
              },

              body:
                JSON.stringify({
                  document_id:
                    documentId,

                  question:
                    trimmedInput,
                }),
            }
          );


        if (
          !response.ok
        ) {

          let errorMessage =
            "Something went wrong while contacting Nimbus.";


          try {

            const errorData =
              await response.json();


            errorMessage =
              errorData?.details?.detail ||
              errorData?.details?.error ||
              errorData?.detail ||
              errorData?.error ||
              errorMessage;

          } catch {
            // Keep generic error.
          }


          throw new Error(
            errorMessage
          );
        }


        if (
          !response.body
        ) {

          throw new Error(
            "Streaming is not supported by this response."
          );
        }


        const reader =
          response.body.getReader();


        const decoder =
          new TextDecoder();


        let buffer =
          "";


        while (
          true
        ) {

          const {
            value,
            done,
          } =
            await reader.read();


          if (
            done
          ) {

            break;
          }


          buffer +=
            decoder.decode(
              value,
              {
                stream:
                  true,
              }
            );


          const events =
            buffer.split(
              /\r?\n\r?\n/
            );


          buffer =
            events.pop() ||
            "";


          for (
            const event of events
          ) {

            if (
              event.trim()
            ) {

              processSSEEvent(
                event,
                assistantId
              );
            }
          }
        }


        if (
          buffer.trim()
        ) {

          processSSEEvent(
            buffer,
            assistantId
          );
        }

      } catch (
        error
      ) {

        console.error(
          "Nimbus API error:",
          error
        );


        const errorText =
          error instanceof Error
            ? error.message
            : "Unknown connection error.";


        setMessages(
          (previous) =>
            previous.map(
              (message) =>
                message.id ===
                assistantId

                  ? {
                      ...message,

                      content:
                        `I couldn't connect to Nimbus.\n\n${errorText}`,

                      sources:
                        [],
                    }

                  : message
            )
        );

      } finally {

        setIsLoading(
          false
        );
      }
    };


  /* ===================================================
     FORM SUBMIT
  =================================================== */

  const handleSubmit =
    (
      e: React.FormEvent
    ) => {

      e.preventDefault();

      sendMessage();
    };


  /* ===================================================
     RENDER
  =================================================== */

  return (
    <main className="app">

      <div className="background-grid" />

      <div className="background-orb" />


      {/* =================================================
          NAVBAR
      ================================================= */}

      <header className="navbar">

        <button
          className="brand"
          onClick={
            startNewChat
          }
          aria-label="Start a new chat"
        >

          <NimbusLogo />

          <div className="brand-text">

            <div className="brand-name">
              Nimbus
            </div>

            <div className="brand-caption">
              AI ASSISTANT
            </div>

          </div>

        </button>


        <div className="nav-status">

          <span className="status-dot" />

          <span>

            {documentId
              ? "Document connected"
              : "Waiting for PDF"}

          </span>

        </div>

      </header>


      {/* =================================================
          CHAT AREA
      ================================================= */}

      <section className="chat-shell">

        <div className="messages">

          {messages.map(
            (message) => (

              <div
                key={
                  message.id
                }
                className={`message-row ${message.role}`}
              >

                {/* ======================================
                    USER MESSAGE
                ====================================== */}

                {message.role ===
                  "user" && (

                  <div className="user-message-content">

                    <div className="message-time user-time">

                      {formatTime(
                        message.timestamp
                      )}

                    </div>


                    {message.documentUpload ? (

                      <UploadCard
                        document={
                          message.documentUpload
                        }
                      />

                    ) : (

                      <div className="user-bubble">

                        {message.content}

                      </div>

                    )}

                  </div>
                )}


                {/* ======================================
                    ASSISTANT MESSAGE
                ====================================== */}

                {message.role ===
                  "assistant" && (

                  <div className="assistant-message-content">

                    <div className="assistant-header">

                      <NimbusLogo />

                      <div className="assistant-meta">

                        <span className="assistant-name">
                          Nimbus
                        </span>

                        <span className="message-time">

                          {formatTime(
                            message.timestamp
                          )}

                        </span>

                      </div>

                    </div>


                    <div className="assistant-bubble">

                      {message.content ? (

                        <MarkdownMessage
                          content={
                            message.content
                          }
                        />

                      ) : isLoading ? (

                        <div className="thinking-bubble">

                          <span />
                          <span />
                          <span />

                        </div>

                      ) : null}

                    </div>


                    {/* =================================
                        SOURCES
                    ================================= */}

                    {message.sources &&
                      message.sources.length >
                        0 && (

                      <div className="sources">

                        <div className="sources-title">
                          SOURCES
                        </div>


                        <div className="source-list">

                          {message.sources.map(
                            (
                              source,
                              index
                            ) => {

                              const page =
                                getSourcePage(
                                  source
                                );


                              if (
                                page ==
                                null
                              ) {

                                return null;
                              }


                              return (
                                <span
                                  className="source-chip"
                                  key={`${page}-${index}`}
                                >

                                  {
                                    source.source_file ||
                                    documentName ||
                                    "Document"
                                  }

                                  {" · Page "}

                                  {page}

                                </span>
                              );
                            }
                          )}

                        </div>

                      </div>
                    )}


                    {/* =================================
                        ACTIONS
                    ================================= */}

                    {message.id !==
                      1 &&
                      !message.content.startsWith(
                        "I couldn't connect"
                      ) &&
                      message.content.trim() !==
                        "" && (

                      <div className="message-actions">

                        <button
                          type="button"
                          onClick={() =>
                            copyMessage(
                              message.content
                            )
                          }
                        >

                          <svg
                            width="14"
                            height="14"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="1.8"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            aria-hidden="true"
                          >

                            <rect
                              x="9"
                              y="9"
                              width="11"
                              height="11"
                              rx="2"
                            />

                            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />

                          </svg>

                          Copy

                        </button>


                        <button
                          type="button"
                          aria-label="Helpful"
                        >

                          <svg
                            width="14"
                            height="14"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="1.8"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            aria-hidden="true"
                          >

                            <path d="M7 10v12" />

                            <path d="M15 5.88L14 10h5.83a2 2 0 0 1 1.95 2.45l-2.25 9A2 2 0 0 1 17.58 23H4a2 2 0 0 1-2-2v-9a2 2 0 0 1 2-2h3l4.5-7.5A2 2 0 0 1 15 5.88Z" />

                          </svg>

                          Helpful

                        </button>


                        <button
                          type="button"
                          aria-label="Not helpful"
                        >

                          <svg
                            width="14"
                            height="14"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="1.8"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            aria-hidden="true"
                          >

                            <path d="M17 14V2" />

                            <path d="M9 18.12L10 14H4.17a2 2 0 0 1-1.95-2.45l2.25-9A2 2 0 0 1 6.42 1H20a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-3l-4.5 7.5A2 2 0 0 1 9 18.12Z" />

                          </svg>

                        </button>

                      </div>
                    )}

                  </div>
                )}

              </div>
            )
          )}


          <div
            ref={
              messagesEndRef
            }
          />

        </div>

      </section>


      {/* =================================================
          COMPOSER
      ================================================= */}

      {documents.length > 0 && (
  <div className="documents-shelf">

    <div className="documents-list">
      {documents.map((document) => {
        const isActive = document.id === documentId;

        return (
          <button
            key={document.id}
            type="button"
            className={`document-chip ${
              isActive ? "active" : ""
            }`}
            onClick={() => selectDocument(document)}
            disabled={isLoading || isUploading}
            title={document.name}
          >
            <span className="document-chip-icon">
              <PdfIcon />
            </span>

            <span className="document-chip-name">
              {document.name}
            </span>

            {isActive && (
              <span className="document-chip-dot" />
            )}
          </button>
        );
      })}
    </div>
  </div>
)}


      <div className="composer-wrapper">

        <form
          className="composer"
          onSubmit={
            handleSubmit
          }
        >

          {/* PDF INPUT */}

          <input
            ref={
              fileInputRef
            }
            type="file"
            accept="application/pdf,.pdf"
            onChange={
              handleFileChange
            }
            hidden
          />


          {/* PLUS */}

          <button
            type="button"
            className="composer-icon-button upload-button"
            onClick={() =>
              fileInputRef.current?.click()
            }
            disabled={
              isLoading ||
              isUploading
            }
            aria-label="Upload PDF"
            title="Upload PDF"
          >

            {isUploading ? (

              <div className="upload-loader" />

            ) : (

              <svg
                width="21"
                height="21"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >

                <path d="M12 5v14" />

                <path d="M5 12h14" />

              </svg>

            )}

          </button>


          {/* TEXTAREA */}

          <textarea
            ref={
              textareaRef
            }
            value={
              input
            }
            disabled={
              isLoading ||
              isUploading
            }
            onChange={
              handleInputChange
            }
            onKeyDown={
              (e) => {

                if (
                  e.key ===
                    "Enter" &&
                  !e.shiftKey
                ) {

                  e.preventDefault();

                  sendMessage();
                }

              }
            }
            placeholder={
              isUploading
                ? "Uploading PDF..."
                : isLoading
                  ? "Nimbus is thinking..."
                  : documentId
                    ? "Ask Nimbus anything..."
                    : "Upload a PDF to begin..."
            }
            rows={1}
          />


          {/* RIGHT ACTIONS */}

          <div className="composer-actions">

            {/* MICROPHONE */}

            <button
              type="button"
              className={`mic-button ${
                isListening
                  ? "listening"
                  : ""
              }`}
              onClick={
                startSpeechRecognition
              }
              disabled={
                isLoading ||
                isUploading
              }
              aria-label="Voice input"
            >

              <svg
                className="mic-icon"
                width="25"
                height="25"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >

                <rect
                  x="9"
                  y="2"
                  width="6"
                  height="12"
                  rx="3"
                />

                <path d="M5 10v2a7 7 0 0 0 14 0v-2" />

                <path d="M12 19v3" />

                <path d="M8 22h8" />

              </svg>

            </button>


            {/* SEND */}

            <button
              type="submit"
              className="send-button"
              disabled={
                isLoading ||
                isUploading ||
                !input.trim() ||
                !documentId
              }
              aria-label="Send message"
            >

              {isLoading ? (

                <div className="button-loader" />

              ) : (

                <svg
                  width="19"
                  height="19"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >

                  <path d="M22 2L11 13" />

                  <path d="M22 2L15 22L11 13L2 9L22 2Z" />

                </svg>

              )}

            </button>

          </div>

        </form>


        {/* FOOTER */}

        <div className="composer-footer">

          <span>

            {documentName
              ? `${documentName} · ACTIVE DOCUMENT`
              : "UPLOAD A PDF TO START"}

          </span>


          <span>
            SHIFT + ENTER FOR NEW LINE
          </span>


          <span>
            NIMBUS · RAG ASSISTANT
          </span>

        </div>

      </div>

    </main>
  );
}


export default App;