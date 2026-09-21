import { Router } from "express";

import {
  handleQuery,
  handleQueryStream,
} from "../controllers/query.controller.js";

const router = Router();

router.post(
  "/",
  handleQuery
);

router.post(
  "/stream",
  handleQueryStream
);

export default router;