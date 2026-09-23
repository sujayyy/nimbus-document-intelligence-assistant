# Nimbus — presenter guide

Use Case 03 · Retrieval & RAG · Team No. 5 — Sujay, Mahesh, Yamini, Siva Prasad

Per-slide scripts live in the **speaker notes of `Nimbus-Document-Intelligence.pptx`**
(View → Notes, or the presenter view in Keynote / PowerPoint / Google Slides).

---

## 1. How to present without losing the animations

**Present from `nimbus-deck.html` in a browser.** That is the real deck — wipes between
slides, staggered reveals, counting numbers, the travelling pulse. The `.pptx` is a set of
flat images and keeps none of it.

Setup, in order:

1. Open `nimbus-deck.html` in Chrome or Safari.
2. Press **F** (Chrome) or **⌃⌘F** (Safari) for full screen. The deck auto-scales to any
   display and letterboxes — it never reflows, so a projector at 4:3 still shows it correctly.
3. Navigate with **→ / ←**, space, or swipe. Scroll also works.
4. Press **Home** to jump back to slide 1 before you start.

If you need to fix a typo two minutes before presenting: hover the top-left corner or press
**E**, click the text, edit it, press **E** again. **⌘S** downloads the edited file.

**When to fall back to the .pptx:** if the venue makes you upload to their machine, if you
need it on a shared drive, or if someone wants to annotate it. Upload the `.pptx` — the
speaker notes travel with it.

**Do not** open the HTML from a USB stick on an unfamiliar machine without testing it first;
the Google Fonts request needs network. If there is no network, the deck still works, it just
falls back to a system font.

---

## 2. Live demo — what to ask

Have the PDF already uploaded and indexed **before** you start presenting. Ingestion takes a
few seconds and dead air is expensive.

### Safe openers — these score 1.00 and cite cleanly

| Ask this | Why it's safe |
|---|---|
| *What was total revenue in fiscal year 2025?* | Single clean figure, cites the income statement page. Best first question. |
| *How many employees does the company have?* | Exact number, one page, fast. |
| *What was net income in fiscal year 2025?* | Same shape as the first, good if you want a second factual one. |

### The one that shows retrieval working

| Ask this | Why |
|---|---|
| *What are the company's business segments?* | The answer is spread across pages. Watch it pull several and cite them all — this is the slide-4 story happening live. |
| *What does the document say about its datacenters and operations?* | Broad question, no single sentence answers it. Shows synthesis across chunks rather than lookup. |

### The money shot — refusal

Do this last. It is the thing people remember.

| Ask this | What happens |
|---|---|
| *What was revenue in fiscal year 2035?* | Refuses, and explains *why*: the document only covers 2023–2025. Not a generic "I don't know". |
| *Who will win the FIFA World Cup in 2030?* | Obviously out of scope. Usually gets a laugh, and makes the point instantly. |
| *What is the revenue guidance for fiscal year 2026?* | The best one for a technical audience — it's exactly the kind of thing an annual report *might* contain, but this one doesn't. Refusing a plausible question is much harder than refusing a silly one. |

### Avoid these on stage

- *How did revenue change?* — the answer gives both years' figures but doesn't state the
  percentage change. Correct, but it looks incomplete if someone is reading closely.
- Anything about **cybersecurity** or **competition** — these need evidence from two or three
  specific pages and the answer comes back thinner than you'd like.
- Anything you haven't tried on that exact PDF. The model is not deterministic.

---

## 3. Chunking strategy — the full explanation

**Why chunk at all.** You cannot embed an eighty-page PDF as one vector; the meaning averages
out into nothing. And you cannot send the whole document to the model on every question — it
is too long and it buries the relevant part. So the document is cut into pieces, each piece is
embedded separately, and only the pieces that match the question get sent on.

**What we do.** Fixed-size chunks of **512 tokens with 50 tokens of overlap**, cut page by
page so every chunk knows which page it came from. That page number is what becomes the
citation later — chunking and citation are the same mechanism.

**What the overlap is for.** The last 50 tokens of one chunk are repeated as the first 50 of
the next. Without it, a sentence that straddles a boundary is destroyed — half its meaning in
one chunk, half in another, and neither piece matches the question. With it, that sentence
survives intact in at least one chunk.

**Why 512, measured.** Five configurations, same document, same questions, each given the
same total amount of retrieved text so none of them wins just by being handed more. The figure
is how often the page holding the answer came back, through the full pipeline:

| Config | Right page retrieved |
|---|---|
| 256 tokens / 25 overlap | 87% |
| **512 tokens / 50 overlap** | **87%** |
| 1024 tokens / 100 overlap | 69% |
| 512 tokens, no overlap | 87% |
| 512 tokens, 20% overlap | 80% |

**256 and 512 tied.** Once the reranker and the fusion run, chunk size below 1024 stops
mattering. So the choice was made on cost: 512 reaches the same number with **127 chunks
instead of 230**, and sends the model **five chunks instead of nine** — half the index to
build and search, and a shorter prompt with less distracting text around the answer.

**Why 1024 loses.** The chunk holds one useful sentence plus a page of unrelated text. When all
of that is averaged into a single vector, the unrelated text dominates and drags the chunk away
from the question. A top-3 result also covers less of the document.

**Why more overlap is not better.** 20% scored 80%, worse than both 10% and none. Overlap
exists to stop a sentence being destroyed at a chunk boundary; past that it just duplicates
text, and duplicated chunks crowd out distinct pages in a fixed retrieval budget.

**The sharpest thing to say if pushed:** chunk size matters enormously for raw vector search —
256 gets 87% there and 512 only 73%. The ranking stack absorbs the difference. A weaker
retrieval pipeline would need the smaller chunks.

**If asked "did you try anything else":** yes — 192/20, and a scheme that embeds small
sub-chunks but returns the parent chunk. Both were worse. A structure-aware splitter was also
tried in an earlier round, but that code is no longer in the repository, so we do not claim it.

---

## 4. Architecture — how to walk it, with the retrieval part stressed

Walk slide 4 left to right. Three lanes, one direction, no jumping around.

### Lane 1 — Ingest. Happens once, when the PDF is uploaded.

PyMuPDF pulls the text out **page by page**, so every piece of text stays attached to its page
number. That text is cut into 512-token chunks. Each chunk goes through MiniLM, which turns it
into a list of 384 numbers — a vector. All those vectors go into a FAISS index.

> One line worth saying: *"the page number rides along the whole way — that's what makes the
> citation at the end possible."*

### Lane 2 — Retrieve. Happens every time someone asks. **This is the heart of it.**

This is the part to slow down on. Four steps:

1. **The question becomes a vector too**, using the *same* model. That matters: the question
   and the chunks have to live in the same space for the comparison to mean anything.

2. **FAISS finds the nearest chunks by meaning.** Not keyword matching — this is why *"how
   much did we earn"* can find a paragraph that never uses the word "earn". FAISS compares the
   question's vector against all 127 chunk vectors and returns the closest ones.

3. **A second model re-reads them.** Vector search is fast but rough — it compares two
   summaries of meaning without ever looking at the question and the chunk *together*. So a
   reranker (a cross-encoder) takes the top candidates and reads each one against the actual
   question, scoring how well it really answers it. This is much slower, which is exactly why
   it runs on a shortlist and not the whole document.

4. **We combine both opinions instead of trusting either.** The vector search and the reranker
   each produce a ranking, and we fuse them. This is the single most important design decision
   in the project, and it's measured: the combination scores **87%**, while vector search alone
   gets **73%** and the reranker alone gets **68%**. The fusion beats both of its own inputs —
   that's the signature of a real ensemble, not stacked complexity.

   > If one sentence survives from this slide, make it that one.

Five chunks come out. That is the only evidence that goes any further.

### Lane 3 — Ground. Turning evidence into a trustworthy answer.

Claude receives those five chunks and nothing else — no training-data recall, no internet. It
is instructed to answer from the supplied text and mark each fact with the page it came from.

Then the part people don't expect: **we verify the citations.** Every `[Page N]` the model
writes is checked against the pages actually supplied. If even one doesn't match, the answer is
thrown away and a refusal is returned instead. The user never sees the unverified answer.

> *"We don't ask the model to be honest. We check."*

---

## 5. Key changes from the previous deck

| # | Change | Why |
|---|---|---|
| 1 | **Numbers updated across the board.** The old deck reported page recall 94.1%, citation recall 88.2%. | Those were measured against the first version of our test set, which we later found had mislabelled questions. Current figures come from a re-run you can reproduce with one command. |
| 2 | **Dropped the "71.6% → 94.1%" improvement story.** | Same reason — it compared numbers from a test set we no longer trust. The honest version is on the challenges slide instead. |
| 3 | **"20-question gold set" → 24 questions.** | 18 the document can answer, 6 it cannot. You cannot measure refusal without questions that have no answer. |
| 4 | **Removed the citation-precision metric entirely.** | It was always 100% — but only because the pipeline *rejects* any answer with a failing citation. Reporting a guarantee as a score is misleading. It's now described as an enforced rule, not a result. |
| 5 | **Merged the two pipeline slides.** | The old slides 3 and 6 were both numbered 01–06 strips saying nearly the same thing. |
| 6 | **New architecture diagram.** | The old one was a static image and didn't show the retrieval path in any detail. |
| 7 | **Chunking lab promoted to its own slide.** | The brief names it in the definition of done. It was previously one line. |
| 8 | **New "definition of done" slide.** | Answers the brief's four completion criteria directly, point by point. |
| 9 | **Retrospective results now carry measured numbers.** | The old table said "Higher recall" and "Better ordering". It now says 73% → 87%. |
| 10 | **Corrected the future-work list.** | The old deck listed structure-aware chunking as unexplored. We had tested it and it lost — claiming otherwise would have been wrong. |
| 11 | **Runtime screenshot reshot.** | The old one showed a UI that no longer exists. |
| 12 | **Complete visual redesign.** | The deck now matches the product's own interface — same colours, same typography, same rules about what yellow and blue mean. |

---

## 6. Questions you should expect, and short answers

**"Why not just use a bigger model / ChatGPT?"**
A bigger model still doesn't have your document. The whole point is that the answer comes from
the PDF you uploaded thirty seconds ago and is traceable to a page.

**"What stops it hallucinating?"**
Three things, in order: it only sees the retrieved chunks; it must cite a page for each fact;
and we verify those citations and refuse if they fail. We measured zero fabricated figures
across all 18 answerable questions.

**"Why is accuracy only 83%?"**
Our scorer compares wording. A correct answer phrased differently gets marked down. Three of
the losses are questions where we answered exactly what was asked and were penalised for not
volunteering extra figures nobody requested. It's a floor.

**"Does it work on other documents?"**
Everything we measured is on one report. That is the honest limit, and it's the first item on
our future-work list.

**"Why didn't you use LangChain or LlamaIndex?"**
For a pipeline this size a framework adds indirection without removing work, and it makes it
harder to say exactly what happens between question and answer. Ours is a handful of explicit
Python modules we can test one at a time.

**"Why FAISS and not a vector database?"**
For one document with 127 chunks, an in-process exact index is faster and simpler than a
network service, and it gives exact results rather than approximate ones.
