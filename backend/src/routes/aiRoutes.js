// routes/aiRoutes.js
import express from "express";
import { askGemini } from "../controllers/aiController.js";

const router = express.Router();

router.post("/ask", askGemini);

export default router;
