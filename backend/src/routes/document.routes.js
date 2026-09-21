import { Router } from "express";
import multer from "multer";

import env from "../config/env.js";

import {
  handleDocumentUpload,
} from "../controllers/document.controller.js";

const router = Router();

const upload = multer({
  dest: "uploads/",

  limits: {
    fileSize:
      env.maxUploadSizeMb * 1024 * 1024,
  },

  fileFilter: (req, file, callback) => {
    const isPdf =
      file.mimetype === "application/pdf" ||
      file.originalname
        .toLowerCase()
        .endsWith(".pdf");

    if (!isPdf) {
      return callback(
        new Error(
          "Only PDF files are supported"
        )
      );
    }

    callback(null, true);
  },
});

router.post(
  "/",
  upload.single("file"),
  handleDocumentUpload
);

export default router;