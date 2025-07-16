import express from "express";
import { upload } from "../middlewares/upload.js";
import { handleImportFile } from "../controllers/importController.js";

const router = express.Router();

// Route xử lý upload và đọc file
router.post("/upload", upload.single("file"), handleImportFile);

export default router;
