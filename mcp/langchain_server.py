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

class ListDirectoryInput(BaseModel):
    directory_path: str = "."  # optional

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
    args_schema=GetTemperatureInput
),

    Tool.from_function(
        func=tools.say_hello,
        name="say_hello",
        description="Dùng để chào một người nào đó theo tên",
        args_schema=SayHelloInput
    ),
    Tool.from_function(
        func=tools.calculate,
        name="calculate",
        description="Phân tích toán học từ một chuỗi như '2 cộng 3'.",
        args_schema=CalculateInput
    ),
    Tool.from_function(
        func=tools.check_file,
        name="check_file",
        description="Kiểm tra xem file có tồn tại.",
        args_schema=CheckFileInput
    ),
    Tool.from_function(
        func=tools.random_number,
        name="random_number",
        description="Sinh số ngẫu nhiên giữa min và max.",
        args_schema=RandomNumberInput
    ),
    Tool.from_function(
        func=tools.text_transform,
        name="text_transform",
        description="Dùng để chuyển đổi văn bản theo yêu cầu. Hỗ trợ viết hoa, viết thường, đảo ngược, đếm số ký tự, v.v. Nhận đầu vào là prompt có định dạng rõ như 'Viết hoa chuỗi: hello'.",
        args_schema=TextTransformInput
    ),
    Tool.from_function(
        func=tools.convert_temperature,
        name="convert_temperature",
        description="Chuyển đổi nhiệt độ giữa Celsius, Fahrenheit, Kelvin.",
        args_schema=ConvertTemperatureInput
    ),
    Tool.from_function(
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
        args_schema=TextStatsInput
    ),
    Tool.from_function(
        func=tools.list_directory,
        name="list_directory",
        description="Chỉ sử dụng khi người dùng yêu cầu liệt kê nội dung trong một thư mục cụ thể trên hệ thống, ví dụ: 'Hiển thị thư mục /home/user'. Không sử dụng cho các câu hỏi không liên quan đến thư mục.",
        args_schema=ListDirectoryInput
    )

]

# Tạo memory
chat_history = MessagesPlaceholder(variable_name="chat_history")
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
print("Memory initialized with key:", memory)

# B3: Tạo agent executor

agent_executor = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.OPENAI_FUNCTIONS ,
    verbose=True,
    memory=memory,
    agent_kwargs={
        "input_variables": ["input", "agent_scratchpad", "chat_history"],
        "system_message": (
        "Bạn là một trợ lý AI thông minh. Khi người dùng hỏi một câu liên quan đến các chức năng kỹ thuật như: "
        "chuyển đổi nhiệt độ, tạo mật khẩu, liệt kê thư mục, hãy sử dụng các công cụ có sẵn để trả lời. "
        "Nếu câu hỏi không thuộc các chủ đề đó, hãy trả lời như một trợ lý trò chuyện thông minh."
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
        

        result = agent_executor.invoke({
        "input": chat_prompt.prompt,
        "chat_history": memory.buffer  # hoặc []
                    })
        # Kiểm tra và chỉ trả về giá trị 'output'
        if isinstance(result, dict) and "output" in result:
            print(f"Agent response: {result['output']}")
            return {"response": result["output"]}
        else:
            return {"response": result}  # fallback nếu không có key 'output'
    except Exception as e:
        traceback.print_exc()
  
        return {"response": f"Error: {e}"}


@app.get("/")
def read_root():
    return {"message": "Agent backend is running!"}

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000)
