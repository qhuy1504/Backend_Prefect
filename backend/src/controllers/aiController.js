import fetch from "node-fetch";

const GEMINI_API_KEY = process.env.GEMINI_API_KEY;
console.log("Gemini API Key:", GEMINI_API_KEY);

export const askGemini = async (req, res) => {
    try {
        const { prompt } = req.body;
        console.log("Received prompt:", prompt);

        const geminiRes = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro-latest:generateContent?key=${GEMINI_API_KEY}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                contents: [{ parts: [{ text: prompt }] }]
            })
        });

        const result = await geminiRes.json();
        console.log("Gemini response:", result);

        if (!geminiRes.ok) {
            return res.status(400).json({ error: result.error || "Gemini API error" });
        }

        const text = result.candidates?.[0]?.content?.parts?.[0]?.text || "Không có phản hồi";
        res.json({ text });
    } catch (err) {
        console.error("Gemini error:", err);
        res.status(500).json({ error: "Lỗi server Gemini" });
    }
};
