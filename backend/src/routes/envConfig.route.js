import express from "express";
import { saveEnvConfig, getEnvConfig } from "../controllers/envConfig.controller.js";

const router = express.Router();

// Route để lấy dữ liệu hiện tại
router.get("/", getEnvConfig);

// Route để lưu file env-config.json
router.post("/", saveEnvConfig);

export default router;
