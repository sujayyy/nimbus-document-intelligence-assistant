import express from "express";
import cors from "cors";

import env from "./config/env.js";

import healthRoutes from "./routes/health.routes.js";
import documentRoutes from "./routes/document.routes.js";
import queryRoutes from "./routes/query.routes.js";

import {
  errorMiddleware,
} from "./middleware/error.middleware.js";

const app = express();

// --------------------------------------------------
// Middleware
// --------------------------------------------------

app.use(
  cors({
    origin: env.corsOrigin,
  })
);

app.use(
  express.json({
    limit: "1mb",
  })
);

// --------------------------------------------------
// Root
// --------------------------------------------------

app.get("/", (req, res) => {
  res.status(200).json({
    service:
      "Document Intelligence Assistant Backend",
    status: "running",
  });
});

// --------------------------------------------------
// API routes
// --------------------------------------------------

app.use(
  "/api/health",
  healthRoutes
);

app.use(
  "/api/documents",
  documentRoutes
);

app.use(
  "/api/query",
  queryRoutes
);

// --------------------------------------------------
// 404
// --------------------------------------------------

app.use((req, res) => {
  res.status(404).json({
    error: "Route not found",
    path: req.originalUrl,
  });
});

// --------------------------------------------------
// Error handler
// --------------------------------------------------

app.use(errorMiddleware);

// --------------------------------------------------
// Start
// --------------------------------------------------

app.listen(
  env.port,
  () => {
    console.log(
      `Backend server running on http://localhost:${env.port}`
    );

    console.log(
      `AI Layer configured at ${env.aiLayerUrl}`
    );
  }
);