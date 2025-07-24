from langchain_ollama import OllamaEmbeddings 
from langchain_community.vectorstores import FAISS
from duckduckgo_search import DDGS
from langchain.llms import Ollama

from langchain.schema import Document
import hashlib
import os
import pickle
import json
import re

embedding = OllamaEmbeddings(model="llama3", base_url="http://host.docker.internal:11434")
llm = Ollama(model="llama3", base_url="http://host.docker.internal:11434")


def build_all_tools():
    tools = [
        ("./data/stock_data.json", "./data/pkl/stock", "./data/hash/hash_stock.json"),
        ("./data/nation_data.json", "./data/pkl/nation", "./data/hash/hash_nation.json"),
        ("./data/history_data.json", "./data/pkl/history", "./data/hash/hash_history.json")
    ]
    for json_path, faiss_path, hash_path in tools:
        build_vectorstore(json_path, faiss_path, hash_path)


def append_data_and_rebuild(question: str, answer: str, tool_key: str):
    data_file_map = {
        "stock": "./data/stock_data.json",
        "nation": "./data/nation_data.json",
        "history": "./data/history_data.json"
    }

    json_path = data_file_map.get(tool_key)
    if not json_path:
        print(f"[WARN] Tool key {tool_key} không hợp lệ.")
        return

    # Tải dữ liệu hiện tại (nếu có)
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except Exception:
                data = []
    else:
        data = []

    # Kiểm tra xem câu hỏi đã có chưa
    if any(item["question"] == question for item in data):
        print("[INFO] Câu hỏi đã tồn tại, không thêm lại.")
    else:
        data.append({"question": question, "answer": answer})
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[INFO] Đã lưu câu hỏi mới vào {json_path}")

        # Lấy path FAISS và hash tương ứng để cập nhật
        faiss_path = f"./data/pkl/{tool_key}"
        hash_path = f"./data/hash/hash_{tool_key}.json"
        build_vectorstore(json_path, faiss_path, hash_path)
        print(f"[INFO] Đã cập nhật vectorstore cho {tool_key}")




def normalize_text(text):
    text = text.lower()
    text = re.sub(r'_', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def build_vectorstore(json_path: str, faiss_path: str, hash_path: str):
    if not os.path.exists(json_path):
        return
    os.makedirs(faiss_path, exist_ok=True)

    with open(json_path, "r", encoding="utf-8") as f:
        json_data = json.load(f)

    if os.path.exists(hash_path):
        with open(hash_path, "r") as f:
            old_hashes = json.load(f)
    else:
        old_hashes = {}

    new_documents = []
    new_hashes = {}

    for item in json_data:
        q_text = item["question"]
        q_hash = hashlib.sha256(q_text.encode("utf-8")).hexdigest()
        new_hashes[q_text] = q_hash

        if q_text not in old_hashes or old_hashes[q_text] != q_hash:
            new_documents.append(Document(page_content=q_text, metadata={"answer": item["answer"]}))

    if new_documents:
        index_file = os.path.join(faiss_path, "index.faiss")
        pkl_file = os.path.join(faiss_path, "index.pkl")
        
        if os.path.exists(index_file) and os.path.exists(pkl_file):
            vectorstore = FAISS.load_local(faiss_path, embedding, allow_dangerous_deserialization=True)
            vectorstore.add_documents(new_documents)
        else:
            vectorstore = FAISS.from_documents(new_documents, embedding)

        vectorstore.save_local(faiss_path)

        with open(hash_path, "w") as f:
            json.dump(new_hashes, f)

        print(f"FAISS index updated: {faiss_path}")
    else:
        print(f"No update needed for: {faiss_path}")
        
def search_duckduckgo(query):
    with DDGS() as ddgs:
        results = ddgs.text(query, max_results=3)
        print(f"[INFO] DuckDuckGo search query: {query}")
        print(f"[INFO] DuckDuckGo search results: {results}")
        return [r['body'] for r in results]

def search_vector(json_query: str, faiss_path: str, top_k: int = 3):
    if not os.path.exists(faiss_path):
        print(f"[ERROR] FAISS path does not exist: {faiss_path}")
        return []

    try:
        vectorstore = FAISS.load_local(faiss_path, embedding, allow_dangerous_deserialization=True)
        print(f"[INFO] Loaded FAISS vectorstore from: {faiss_path}")
    except Exception as e:
        print(f"[ERROR] Lỗi khi load FAISS vectorstore: {e}")
        return []

    query_text = normalize_text(json_query)
    print(f"[DEBUG] Normalized query text: {query_text}")
    query_embedding = embedding.embed_query(query_text)

    results = vectorstore.similarity_search_with_score_by_vector(query_embedding, k=top_k)
    for doc, score in results:
        print(f"[DEBUG] content: {doc.page_content} | score: {score} | metadata: {doc.metadata.get('answer', 'Không có')}")
    filtered = [(doc, score) for doc, score in results if score < 0.6]
    
    if not filtered:
        print("[INFO] Không có kết quả phù hợp. Thực hiện tìm kiếm bằng LLM.")
        llm_answer = llm.invoke(query_text)
        

        return [{
            "matched_question": None,
            "score": None,
            "answer": "Trả lời hoàn toàn bằng Tiếng Việt: ",
            "suggestions": llm_answer
        }]

       # Lấy ra kết quả có score thấp nhất
    lowest_score_result = min(filtered, key=lambda x: x[1])

    return [
        {
            "matched_question": doc.page_content,
            "score": float(score),
            "answer": doc.metadata.get("answer", "Không có")
        }
        for doc, score in [lowest_score_result]
    ]
if __name__ == "__main__":
    print("Đang tiến hành build vectorstore cho tất cả tool...")
    build_all_tools()
    print("Hoàn tất.")
