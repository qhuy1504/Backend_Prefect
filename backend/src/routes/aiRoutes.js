// routes/aiRoutes.js
import express from "express";
import { askAI, askAIWithOllama } from "../controllers/aiController.js";

const router = express.Router();

router.post("/ask-ai", askAI);
router.post("/ask-ollama", askAIWithOllama);

export default router;
