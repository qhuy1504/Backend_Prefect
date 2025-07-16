import express from "express";
import { forgotPassword, verifyOtp, resetPassword, changePassword } from "../controllers/authController.js";
import { authMiddleware } from "../middlewares/authenticate.js";

const router = express.Router();

router.post("/forgot-password", forgotPassword);
router.post("/verify-otp", verifyOtp);
router.post("/reset-password", resetPassword);
router.post("/change-password", authMiddleware, changePassword);


export default router;