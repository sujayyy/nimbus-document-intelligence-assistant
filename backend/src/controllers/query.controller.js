import {
  queryAI,
  streamQueryAI,
} from "../services/ai.service.js";

function validateQueryInput(req, res) {
  const { document_id, question } = req.body;

  if (
    typeof document_id !== "string" ||
    !document_id.trim()
  ) {
    res.status(400).json({
      error: "document_id is required",
    });

    return null;
  }

  if (
    typeof question !== "string" ||
    !question.trim()
  ) {
    res.status(400).json({
      error: "question is required",
    });

    return null;
  }

  return {
    documentId: document_id.trim(),
    question: question.trim(),
  };
}

export async function handleQuery(req, res, next) {
  try {
    const input = validateQueryInput(req, res);

    if (!input) {
      return;
    }

    const result = await queryAI(
      input.documentId,
      input.question
    );

    return res.status(200).json(result);
  } catch (error) {
    next(error);
  }
}

export async function handleQueryStream(
  req,
  res,
  next
) {
  try {
    const input = validateQueryInput(req, res);

    if (!input) {
      return;
    }

    const aiResponse = await streamQueryAI(
      input.documentId,
      input.question
    );

    res.status(200);

    res.setHeader(
      "Content-Type",
      "text/event-stream; charset=utf-8"
    );

    res.setHeader(
      "Cache-Control",
      "no-cache, no-transform"
    );

    res.setHeader(
      "Connection",
      "keep-alive"
    );

    res.setHeader(
      "X-Accel-Buffering",
      "no"
    );

    if (typeof res.flushHeaders === "function") {
      res.flushHeaders();
    }

    const aiStream = aiResponse.data;

    const cleanup = () => {
      if (!aiStream.destroyed) {
        aiStream.destroy();
      }
    };

    req.on("close", cleanup);
    req.on("aborted", cleanup);

    aiStream.on("error", (error) => {
      console.error(
        "AI streaming error:",
        error.message
      );

      cleanup();

      if (!res.headersSent) {
        next(error);
      } else {
        res.end();
      }
    });

    aiStream.on("end", () => {
      if (!res.writableEnded) {
        res.end();
      }
    });

    aiStream.pipe(res);
  } catch (error) {
    next(error);
  }
}