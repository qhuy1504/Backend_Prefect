from vector_tool import search_vector
from vector_tool import append_data_and_rebuild , search_duckduckgo, get_weather_open_meteo,search_weather_tool, search_bank_stock_tool
import difflib


VECTOR_TOOLS = {
    "stock": {
        "desc": ["cổ phiếu", "chứng khoán", "HOSE", "giá trần", "giá sàn", 
                 "VNINDEX", "volume", "tài chính", "thông tin", "giao dịch", 
                 "dữ liệu" , "sàn","hôm nay", "thế nào", "ngân hàng", "lãi suất", 
                 "lợi nhuận", "công ty", "doanh nghiệp", "tỷ giá", "tiền tệ"
                 ], 
        "search_fn": lambda query: search_bank_stock_tool(query)
    },
    "nation": {
        "desc": ["biển số", "tỉnh", "thành phố", "đăng ký xe", "địa lý",
                 "dân số", "hành chính", "đất nước", "khu vực", "thủ đô",
                 "thời tiết", "hôm nay", "Hà Nội", "Việt Nam", "TP.HCM",
                 "ngọn núi", "cao nhất", "tốt nghiệp", "địa danh", "tết",
                 
                 ],
        "faiss": "./data/pkl/nation",
        "search_fn": lambda query: search_vector(query, "./data/pkl/nation")
    },
    "history": {
        "desc": ["lịch sử", "chiến tranh", "sự kiện", "năm", "cách mạng", "thế kỷ", "kiến thức", "tìm kiếm web"],
        "faiss": "./data/pkl/history",
        "search_fn": lambda query: search_vector(query, "./data/pkl/history")
    },
    "weather": {
        "desc": ["thời tiết", "trời", "nhiệt độ", "mưa'", "gió", "ẩm", "nắng",
                 "bao nhiêu độ", "thời tiết hôm nay", "hôm nay trời thế nào",
                 "dự báo thời tiết", "thời tiết ở", "thành phố", "nhiệt độ hiện tại",],
        "search_fn": lambda query: search_weather_tool(query)
    }
}

def select_vector_tool(prompt: str) -> str:
    prompt = prompt.lower()
    for key, tool in VECTOR_TOOLS.items():
        for keyword in tool["desc"]:
            if keyword in prompt:
                print(f"[DEBUG] Matched keyword '{keyword}' in tool '{key}'")
                return key
    return None
def search_vector_store(query: str) -> str:
    selected_tool = select_vector_tool(query)
    print(f"[INFO] Selected tool: {selected_tool}")
    print(f"[INFO] Query: {query}")
    
    if selected_tool:
        results = VECTOR_TOOLS[selected_tool]["search_fn"](query)
        print(f"[INFO] Search results from {selected_tool}: {results}")
        
        if results:
            output = []
            for r in results:
                answer_text = str(r.get("answer", "Không có"))
                if r.get("suggestions"):
                    suggestions_text = r['suggestions']
                    print(f"[INFO] Suggestions: {suggestions_text}")
                    full_text = f"{r['answer']}{suggestions_text}"
                else:
                    full_text = r["answer"]

                # Lưu dữ liệu vector sau mỗi lần tìm thấy
                append_data_and_rebuild(query, full_text, selected_tool)

                output.append(full_text)

            return "\n\n".join(output)
    
    # Nếu không có công cụ phù hợp hoặc kết quả trống => dùng fallback DuckDuckGo
    print("[INFO] Using fallback search_vector (e.g. DuckDuckGo)")
    fallback_results = search_duckduckgo(query)
    if fallback_results:
        return "\n\n".join(fallback_results)
    
    return "Không tìm thấy kết quả."