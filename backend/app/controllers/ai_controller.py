# controllers/ai_controller.py
from flask import request, jsonify
from services.ai_ollama_service import ask_llama_via_mcp

def ask_ai_with_ollama(request):
    data = request.get_json()
    prompt = data.get("prompt")

    print("Received prompt:", prompt)

    try:
        response = ask_llama_via_mcp(prompt)
        print("Ollama response:", response)
        return jsonify({ "text": response })
    except Exception as e:
        return jsonify({ "error": "AI error", "detail": str(e) }), 500
