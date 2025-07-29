import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

// Lấy __dirname trong ES Module
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Đường dẫn file JSON
const envConfigPath = path.join("/app/env-config.json");

// Regex để kiểm tra các giá trị
const regexValidators = {
    REACT_APP_API_URL: /^https?:\/\/.+/,
    PREFECT_API_URL: /^https?:\/\/.+/,
    PREFECT_UI_URL: /^https?:\/\/.+/,
    JWT_SECRET: /^[a-f0-9]{40,}$/,
    CLOUDINARY_CLOUD_NAME: /^[a-z0-9-_]+$/,
    CLOUDINARY_API_KEY: /^[0-9]{15,}$/,
    CLOUDINARY_API_SECRET: /^[\w-]+$/,
    EMAIL_FROM: /^[\w.+-]+@[a-z0-9.-]+\.[a-z]{2,}$/i,
    EMAIL_PASSWORD: /^[\w\s]{10,}$/, // Không quá chặt để tránh lỗi
    OPENROUTER_API_KEY: /^sk-or-v1-[a-f0-9]{64}$/i,
    DATABASE_URL: /^postgres:\/\/\w+:\w+@[\w.-]+:\d+\/\w+$/,
    OPENWEATHER_API_KEY: /^[a-f0-9]{32}$/i,
};

// Hàm kiểm tra từng field
const validateField = (key, value) => {
    const regex = regexValidators[key];
    return regex ? regex.test(value) : true; // Nếu không có validator, mặc định hợp lệ
};

export const saveEnvConfig = (req, res) => {
    const data = req.body;

    if (!data || typeof data !== "object") {
        return res.status(400).json({ message: "Invalid data format." });
    }

    try {
        // Lặp qua từng nhóm
        for (const groupKey of Object.keys(data)) {
            const group = data[groupKey];
            for (const key in group) {
                const value = group[key];
                if (!validateField(key, value)) {
                    return res.status(400).json({
                        message: `Invalid value for '${key}': '${value}'`,
                    });
                }
            }
        }

        // Nếu hợp lệ, lưu file
        fs.writeFileSync(envConfigPath, JSON.stringify(data, null, 2), "utf-8");
        res.status(200).json({ message: "env-config.json saved successfully." });
    } catch (error) {
        console.error("Save error:", error);
        res.status(500).json({ message: "Failed to save env-config.json." });
    }
};

// Controller: Lấy file JSON
export const getEnvConfig = (req, res) => {
    try {
        const json = fs.readFileSync(envConfigPath, "utf-8");
        res.status(200).json(JSON.parse(json));
    } catch (error) {
        console.error("Read error:", error);
        res.status(500).json({ message: "Failed to read env-config.json." });
    }
};
