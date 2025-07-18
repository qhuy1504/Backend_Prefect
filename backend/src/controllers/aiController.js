// controllers/aiController.js
import OpenAI from 'openai';

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
            model: "openai/gpt-3.5-turbo",
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
