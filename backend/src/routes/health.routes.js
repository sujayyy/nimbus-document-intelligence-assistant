import { Router } from "express";

import {
  handleHealth,
} from "../controllers/health.controller.js";

const router = Router();

router.get(
  "/",
  handleHealth
);

export default router;