import fs from "fs";

import {
  ingestDocument,
} from "../services/ai.service.js";

export async function handleDocumentUpload(
  req,
  res,
  next
) {
  let filePath;

  try {
    if (!req.file) {
      return res.status(400).json({
        error: "PDF file is required",
      });
    }

    filePath = req.file.path;

    const result = await ingestDocument(
      filePath,
      req.file.originalname
    );

    return res.status(200).json(result);
  } catch (error) {
    next(error);
  } finally {
    if (filePath) {
      fs.unlink(
        filePath,
        (unlinkError) => {
          if (unlinkError) {
            console.error(
              "Failed to remove temporary upload:",
              unlinkError.message
            );
          }
        }
      );
    }
  }
}