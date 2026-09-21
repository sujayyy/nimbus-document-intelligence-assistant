import {
  checkAIHealth,
} from "../services/ai.service.js";

export async function handleHealth(req, res) {
  try {
    const aiHealth = await checkAIHealth();

    return res.status(200).json({
      status: "healthy",
      service:
        "Document Intelligence Assistant Backend",
      ai_layer: {
        status: "healthy",
        ...aiHealth,
      },
    });
  } catch (error) {
    console.error(
      "AI health check failed:",
      error.message
    );

    return res.status(503).json({
      status: "degraded",
      service:
        "Document Intelligence Assistant Backend",
      ai_layer: {
        status: "unavailable",
      },
    });
  }
}