import axios from "axios";
import FormData from "form-data";
import fs from "fs";

import env from "../config/env.js";

const aiClient = axios.create({
  baseURL: env.aiLayerUrl,
  timeout: env.aiRequestTimeout,
});

/**
 * Send a normal query to the AI Layer.
 *
 * AI contract:
 * POST /query?document_id=...&question=...
 */
export async function queryAI(documentId, question) {
  const response = await aiClient.post(
    "/query",
    null,
    {
      params: {
        document_id: documentId,
        question,
      },
    }
  );

  return response.data;
}

/**
 * Upload a PDF to the AI Layer.
 *
 * AI contract:
 * POST /documents/upload
 * multipart/form-data
 * field: file
 */
export async function ingestDocument(filePath, originalFilename) {
  const form = new FormData();

  form.append(
    "file",
    fs.createReadStream(filePath),
    {
      filename: originalFilename,
      contentType: "application/pdf",
    }
  );

  const response = await aiClient.post(
    "/documents/upload",
    form,
    {
      headers: form.getHeaders(),
      maxContentLength: Infinity,
      maxBodyLength: Infinity,
    }
  );

  return response.data;
}

/**
 * Check whether the AI Layer is healthy.
 */
export async function checkAIHealth() {
  const response = await aiClient.get("/health");

  return response.data;
}

/**
 * Create a streaming connection to the AI Layer.
 *
 * The AI Layer already generates SSE.
 * Backend simply proxies that stream to the client.
 */
export async function streamQueryAI(
  documentId,
  question
) {
  return aiClient.post(
    "/query/stream",
    null,
    {
      params: {
        document_id: documentId,
        question,
      },
      responseType: "stream",
      timeout: 0,
    }
  );
}