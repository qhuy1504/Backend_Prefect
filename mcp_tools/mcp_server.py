from flask import Flask, request, jsonify
from mcp_tools import search_vector_store

app = Flask(__name__)

@app.route("/")
def home():
    return "MCP Vector Search API is running."

@app.route("/search", methods=["POST"])
def search():
    data = request.get_json()
    prompt = data.get("prompt")
    if not data or "prompt" not in data:
        return jsonify({"error": "Missing 'prompt' field in JSON"}), 400

    print(f"[INFO] Received prompt: {prompt}")

    try:
        response = search_vector_store(prompt)
        print(f"[INFO] Search results: {response}")
        return jsonify({"response": response}), 200
    except Exception as e:
        print(f"[ERROR] {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
    # app.run(host="localhost", port=5001, debug=True)

