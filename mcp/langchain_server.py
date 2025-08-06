from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import os

from langchain.agents import initialize_agent, AgentType
from langchain_community.llms import Ollama
from langchain.tools import Tool
import traceback

import tools as tools
from langchain.memory import ConversationBufferMemory
from langchain.prompts import MessagesPlaceholder
from langchain.tools import Tool, StructuredTool

# B1: Tạo LLM local
llm = Ollama(model="llama3.2:latest")

# Định nghĩa schema

class SayHelloInput(BaseModel):
    name: str

class CalculateInput(BaseModel):
    prompt: str

class CheckFileInput(BaseModel):
    file_path: str

class RandomNumberInput(BaseModel):
    input: str  # hoặc có thể là dict, nếu cần thêm kiểm tra

class TextTransformInput(BaseModel):
    prompt: str

class ConvertTemperatureInput(BaseModel):
    temperature: float
    from_unit: str
    to_unit: str

class GeneratePasswordInput(BaseModel):
    length: int = 12
    include_symbols: bool = True

class TextStatsInput(BaseModel):
    text: str

class GetTemperatureInput(BaseModel):
    province: str



# B2: Convert tools thành LangChain-compatible tools
tools = [
    Tool.from_function(
    func=tools.get_temperature_by_city,
    name="get_temperature_by_city",
    description=(
        "Trả về nhiệt độ hiện tại của một tỉnh hoặc thành phố ở Việt Nam. "
        "Chỉ sử dụng khi người dùng hỏi về nhiệt độ, ví dụ như 'Nhiệt độ ở Tây Ninh là bao nhiêu?'. "
        "Tham số: province (str) – tên tỉnh/thành phố, ví dụ: 'Tây Ninh'."
    ),
    args_schema=GetTemperatureInput,
    return_direct=True  # Trả về trực tiếp kết quả mà không cần định dạng lại
),

    Tool.from_function(
        func=tools.say_hello,
        name="say_hello",
        description="Dùng để chào một người nào đó theo tên",
        args_schema=SayHelloInput,
        return_direct=True
    ),
    Tool.from_function(
        func=tools.calculate,
        name="calculate",
        description="Phân tích toán học từ một chuỗi như '2 cộng 3'.",
        args_schema=CalculateInput,
        return_direct=True
    ),
    Tool.from_function(
        func=tools.check_file,
        name="check_file",
        description="Kiểm tra xem file có tồn tại.",
        args_schema=CheckFileInput,
        return_direct=True
    ),
    Tool.from_function(
        func=tools.random_number,
        name="random_number",
        description="Sinh số ngẫu nhiên giữa min và max.",
        args_schema=RandomNumberInput,
        return_direct=True
    ),
    Tool.from_function(
        func=tools.text_transform,
        name="text_transform",
        description="Dùng để chuyển đổi văn bản theo yêu cầu. Hỗ trợ viết hoa, viết thường, đảo ngược, đếm số ký tự, v.v. Nhận đầu vào là prompt có định dạng rõ như 'Viết hoa chuỗi: hello'.",
        args_schema=TextTransformInput,
        return_direct=True
    ),
    StructuredTool.from_function(
        func=tools.convert_temperature,
        name="convert_temperature",
        description="Chuyển đổi nhiệt độ giữa Celsius, Fahrenheit, Kelvin.",
        args_schema=ConvertTemperatureInput,
        return_direct=True
    ),
    StructuredTool.from_function(
        func=tools.generate_password,
        name="generate_password",
        description="Tạo một mật khẩu an toàn.",
        args_schema=GeneratePasswordInput,
        return_direct=True
    ),
    Tool.from_function(
        func=tools.text_stats,
        name="text_stats",
        description="Phân tích văn bản để đếm ký tự/từ, v.v.",
        args_schema=TextStatsInput,
        return_direct=True
    )

]

# Tạo memory
chat_history = MessagesPlaceholder(variable_name="chat_history")
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
print("Memory initialized with key:", memory)

# B3: Tạo agent executor

agent_executor_primary = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True,
    memory=memory,
    agent_kwargs={
        "input_variables": ["input", "agent_scratchpad", "chat_history"],
        "system_message": (
            "Bạn là một trợ lý AI thông minh và đa năng. Nhiệm vụ chính của bạn là trả lời các câu hỏi của người dùng. "
            "**Nếu câu hỏi có thể được giải quyết bằng một trong các công cụ bạn có (ví dụ: chuyển đổi nhiệt độ, tạo mật khẩu, liệt kê thư mục, hoặc lấy thông tin nhiệt độ theo tỉnh), hãy sử dụng công cụ đó để cung cấp câu trả lời chính xác.** "
            "Đối với tất cả các câu hỏi khác không liên quan đến công cụ, hãy trả lời một cách tự nhiên, thông minh và hữu ích như một trợ lý trò chuyện thông thường. "
            "Hãy luôn ưu tiên hiểu ý định của người dùng để đưa ra phản hồi phù hợp nhất."
        )
    },
    handle_parsing_errors=True,
    max_iterations=10,
)

# B4: Tạo agent executor dự phòng (OPENAI_FUNCTIONS)
# Sử dụng cùng LLM và tools, nhưng với AgentType khác
agent_executor_fallback = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.OPENAI_FUNCTIONS, 
    verbose=True, 
    memory=memory, 
    agent_kwargs={
        "input_variables": ["input", "agent_scratchpad", "chat_history"],
        "system_message": (
            "Bạn là một trợ lý AI hữu ích và có khả năng sử dụng các công cụ. "
            "Nếu người dùng hỏi một câu hỏi liên quan đến các chức năng kỹ thuật, hãy sử dụng các công cụ có sẵn để trả lời. "
            "Nếu câu hỏi không thuộc các chủ đề đó, hãy trả lời như một trợ lý trò chuyện thông minh và trực tiếp."
        )
    },
    handle_parsing_errors=True,
    max_iterations=10,
)

# FastAPI setup
app = FastAPI()

origins = [
    "http://localhost:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatPrompt(BaseModel):
    prompt: str

@app.post("/chat")
async def chat_with_agent(chat_prompt: ChatPrompt):
    try:
        # 1. Thử gọi agent chính (STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION)
        main_agent_result = await agent_executor_primary.ainvoke({
            "input": chat_prompt.prompt,
            "chat_history": memory.buffer
        })

        # Lấy output từ agent chính
        main_output = main_agent_result.get("output", str(main_agent_result))

        # 2. Kiểm tra các trường hợp lỗi hoặc hành vi không mong muốn từ agent chính
        if "Error:" in main_output or "Tôi không thể xác định yêu cầu chuyển đổi văn bản từ câu lệnh của bạn." in main_output or \
           main_output.strip().startswith("Action:"):
            print(f"Agent chính gặp lỗi hoặc cố gắng gọi công cụ sai: {main_output}. Đang chuyển sang chế độ dự phòng (OPENAI_FUNCTIONS).")
            # 3. Chuyển sang chế độ dự phòng: gọi agent dự phòng (OPENAI_FUNCTIONS)
            fallback_agent_result = await agent_executor_fallback.ainvoke({
                "input": chat_prompt.prompt,
                "chat_history": memory.buffer
            })
            fallback_output = fallback_agent_result.get("output", str(fallback_agent_result))
            return {"response": fallback_output}
        else:
            # 4. Nếu không có lỗi, trả về kết quả từ agent chính
            print(f"Agent chính phản hồi: {main_output}")
            return {"response": main_output}

    except Exception as e:
        traceback.print_exc()
        print(f"Có lỗi không mong muốn xảy ra với agent chính: {e}. Đang chuyển sang chế độ dự phòng (OPENAI_FUNCTIONS).")
        # Nếu có bất kỳ Exception nào khác xảy ra, cũng chuyển sang chế độ dự phòng
        try:
            fallback_agent_result = await agent_executor_fallback.ainvoke({
                "input": chat_prompt.prompt,
                "chat_history": memory.buffer
            })
            fallback_output = fallback_agent_result.get("output", str(fallback_agent_result))
            return {"response": fallback_output}
        except Exception as fallback_e:
            traceback.print_exc()
            return {"response": f"Lỗi trong chế độ dự phòng: {fallback_e}"}


@app.get("/")
def read_root():
    return {"message": "Agent backend is running!"}

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000)
