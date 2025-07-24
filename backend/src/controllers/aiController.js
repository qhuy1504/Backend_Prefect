// controllers/aiController.js
import OpenAI from 'openai';
import {askLlamaViaMCP } from '../services/aiOllamaService.js';

const openai = new OpenAI({
    baseURL: "https://openrouter.ai/api/v1",
    apiKey: process.env.OPENROUTER_API_KEY, // đặt key trong .env
    defaultHeaders: {
        // Không bắt buộc nếu bạn không có site
        // "HTTP-Referer": "https://your-site.com",
        // "X-Title": "Your Site Name"
    },
});

export const askAI = async (req, res) => {
    try {
        const { messages } = req.body;

        if (!messages || messages.length === 0) {
            return res.status(400).json({ error: "Messages không được để trống." });
        }

        const completion = await openai.chat.completions.create({
            model: "google/gemini-2.0-flash-exp:free",
            messages,
        });

        const reply = completion.choices?.[0]?.message?.content || "Không có phản hồi từ AI.";
        console.log("AI Reply:", reply);
        res.json({ text: reply });

    } catch (err) {
        console.error("Lỗi gọi OpenRouter:", err);
        res.status(500).json({ error: "Lỗi gọi OpenRouter." });
    }
};



export const askAIWithOllama = async (req, res) => {
    const { prompt } = req.body;
    console.log("Received prompt:", prompt);
    try {
        const response = await askLlamaViaMCP(prompt);
        console.log("Ollama response:", response);
        res.json({ text: response });
    } catch (error) {
        res.status(500).json({ error: 'AI error', detail: error.message });
    }
};

