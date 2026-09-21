export function errorMiddleware(
  err,
  req,
  res,
  next
) {
  console.error(
    `${req.method} ${req.originalUrl}`,
    err
  );

  // Multer errors
  if (
    err.name === "MulterError"
  ) {
    if (err.code === "LIMIT_FILE_SIZE") {
      return res.status(413).json({
        error:
          "Uploaded file exceeds the maximum allowed size",
      });
    }

    return res.status(400).json({
      error: err.message,
    });
  }

  // PDF validation errors
  if (
    err.message ===
    "Only PDF files are supported"
  ) {
    return res.status(400).json({
      error: err.message,
    });
  }

  // AI Layer returned an HTTP error
  if (err.response) {
    return res.status(
      err.response.status || 502
    ).json({
      error: "AI layer request failed",
      details: err.response.data,
    });
  }

  // AI Layer could not be reached
  if (err.request) {
    return res.status(503).json({
      error: "AI layer is unavailable",
    });
  }

  return res.status(500).json({
    error: "Internal server error",
  });
}