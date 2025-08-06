import os
import random
import string
from datetime import datetime
import random
import re

def say_hello(name: str) -> str:
    """Xin chào một người nào đó."""
    return f"Hello, {name}! đẹp trai nhất Tây Ninh!"

def get_temperature_by_city(province: str) -> str:
    """Lấy thông tin nhiệt độ của tỉnh, thành phố Tây Ninh."""
    return f"Nhiệt độ hiện tại ở {province} là khoảng 25 độ C."

def calculate(prompt: str) -> str:
    """
    Phân tích cú pháp promt như '2 cộng 3' và trả về kết quả.
    Các phép toán được hỗ trợ: add, subtract, multiply, divide
    """
    try:
        # Loại bỏ dấu nháy đơn hoặc kép và strip khoảng trắng
        cleaned = prompt.strip().replace('"', '').replace("'", "")
        parts = cleaned.lower().split()

        print("Cleaned parts:", parts)

        if len(parts) != 3:
            return "Error: Prompt format must be 'number operation number'. E.g., '2 add 3'"
        
        a = float(parts[0])
        operation = parts[1]
        b = float(parts[2])

        # Map toán tử ký hiệu sang từ
        op_map = {
            "+": "add",
            "-": "subtract",
            "*": "multiply",
            "x": "multiply",
            "/": "divide",
        }
        operation = op_map.get(operation, operation)

        if operation == "add":
            result = a + b
        elif operation == "subtract":
            result = a - b
        elif operation == "multiply":
            result = a * b
        elif operation == "divide":
            if b == 0:
                return "Error: Cannot divide by zero!"
            result = a / b
        else:
            return "Error: Unknown operation. Use 'add', 'subtract', 'multiply', or 'divide'"

        return f"The result of {a} {operation} {b} is {result}"
    except Exception as e:
        return f"Error: {str(e)}"



def check_file(file_path: str) -> str:
    """Kiểm tra xem một tệp có tồn tại trên hệ thống hay không."""
    if os.path.exists(file_path):
        return f"Đúng, file '{file_path}' tồn tại trên máy tính của bạn."
    else:
        return f"Không, file '{file_path}' không được tìm thấy."


def random_number(input) -> str:
    print("Input for random_number:", input)
    """
    Tạo một số ngẫu nhiên giữa min_val và max_val (bao gồm cả hai giá trị).
    Chấp nhận đầu vào từ điển hoặc dấu nhắc chuỗi.
    """
    # Nếu input là chuỗi
    if isinstance(input, str):
        # Tìm tất cả các số trong chuỗi
        numbers = list(map(int, re.findall(r'\d+', input)))
        if len(numbers) == 1:
            min_val = 1
            max_val = numbers[0]
        elif len(numbers) >= 2:
            min_val, max_val = numbers[0], numbers[1]
        else:
            min_val, max_val = 1, 100
    elif isinstance(input, dict):
        if "value" in input:
            return int(input["value"])
        min_val = input.get("min_val", 1)
        max_val = input.get("max_val", 100)
    else:
        return "Invalid input format"

    result = random.randint(min_val, max_val)
    return f"Random number between {min_val} and {max_val}: {result}"


def text_transform_logic(text: str, operation: str) -> str:
    if operation == "upper":
        return f"Uppercase: {text.upper()}"
    elif operation == "lower":
        return f"Lowercase: {text.lower()}"
    elif operation == "title":
        return f"Title case: {text.title()}"
    elif operation == "reverse":
        return f"Reversed: {text[::-1]}"
    elif operation == "length":
        return f"Length: {len(text)} characters"
    else:
        return "Error: Unsupported operation"




def text_transform(prompt: str) -> str:
    """
    Phân tích prompt để xác định thao tác cần thực hiện với văn bản.
    Hỗ trợ: 'upper', 'lower', 'title', 'reverse', 'length'.
    Ví dụ: 'Viết hoa chuỗi: hello world'
    """
    original_prompt = prompt  # giữ lại để dùng trong phản hồi
    prompt = prompt.strip().lower()

    if "upper" in prompt or "viết hoa" in prompt:
        operation = "upper"
    elif "lower" in prompt or "viết thường" in prompt:
        operation = "lower"
    elif "title" in prompt or "chữ hoa đầu từ" in prompt:
        operation = "title"
    elif "reverse" in prompt or "đảo ngược" in prompt:
        operation = "reverse"
    elif "length" in prompt or "bao nhiêu ký tự" in prompt:
        operation = "length"
    else:
        return "Tôi không thể xác định yêu cầu chuyển đổi văn bản từ câu lệnh của bạn."

    match = re.search(r":\s*(.+)", prompt)
    if match:
        text = match.group(1)
    else:
        return "Tôi không tìm thấy đoạn văn bản cần xử lý trong yêu cầu."

    # Gọi xử lý
    result = text_transform_logic(text, operation)

    # Trả về kết quả như hội thoại
    return f"Kết quả chuyển đổi theo yêu cầu của bạn ({operation}) là: {result}"



def convert_temperature(temperature: float, from_unit: str, to_unit: str) -> str:
    """Chuyển đổi nhiệt độ giữa Celsius, Fahrenheit, và Kelvin."""
    from_unit = from_unit.lower()
    to_unit = to_unit.lower()
    
    if from_unit in ("fahrenheit", "f"):
        celsius = (temperature - 32) * 5/9
    elif from_unit in ("kelvin", "k"):
        celsius = temperature - 273.15
    elif from_unit in ("celsius", "c"):
        celsius = temperature
    else:
        return "Error: from_unit must be 'celsius', 'fahrenheit', or 'kelvin'"
    
    if to_unit in ("fahrenheit", "f"):
        result = celsius * 9/5 + 32
        unit_symbol = "°F"
    elif to_unit in ("kelvin", "k"):
        result = celsius + 273.15
        unit_symbol = "K"
    elif to_unit in ("celsius", "c"):
        result = celsius
        unit_symbol = "°C"
    else:
        return "Error: to_unit must be 'celsius', 'fahrenheit', or 'kelvin'"
    
    return f"{temperature}° {from_unit.title()} = {result:.2f}{unit_symbol}"

def generate_password(length: int = 12, include_symbols: bool = True) -> str:
    """Tạo một mật khẩu an toàn."""
    if length < 4:
        return "Error: Password length must be at least 4 characters."
    
    lowercase = string.ascii_lowercase
    uppercase = string.ascii_uppercase
    digits = string.digits
    symbols = "!@#$%^&*()_+-=[]{}|;:,.<>?" if include_symbols else ""
    
    password = [
        random.choice(lowercase),
        random.choice(uppercase),
        random.choice(digits)
    ]
    if include_symbols:
        password.append(random.choice(symbols))
    
    all_chars = lowercase + uppercase + digits + symbols
    for _ in range(length - len(password)):
        password.append(random.choice(all_chars))
    
    random.shuffle(password)
    
    return f"Generated password ({length} chars): {''.join(password)}"

def text_stats(text: str) -> str:
    """Lấy thống kê về một văn bản: số lượng từ, số lượng ký tự, v.v."""
    if not text.strip():
        return "Error: Please provide some text to analyze."
    
    words = text.split()
    characters = len(text)
    characters_no_spaces = len(text.replace(" ", ""))
    sentences = len([s for s in text.split('.') if s.strip()])
    paragraphs = len([p for p in text.split('\n') if p.strip()])
    
    return f"""Text Statistics:
- Characters: {characters} (including spaces)
- Characters: {characters_no_spaces} (excluding spaces)
- Words: {len(words)}
- Sentences: {sentences}
- Paragraphs: {paragraphs}
- Average word length: {sum(len(word) for word in words) / len(words):.1f} characters"""


