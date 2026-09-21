import dotenv from "dotenv";

dotenv.config();

const env = {
  nodeEnv: process.env.NODE_ENV || "development",

  port: Number(process.env.PORT) || 5001,

  aiLayerUrl:
    process.env.AI_LAYER_URL || "http://127.0.0.1:3000",

  aiRequestTimeout:
    Number(process.env.AI_REQUEST_TIMEOUT_MS) || 120000,

  maxUploadSizeMb:
    Number(process.env.MAX_UPLOAD_SIZE_MB) || 50,

  corsOrigin:
    process.env.CORS_ORIGIN || "*",
};

export default env;