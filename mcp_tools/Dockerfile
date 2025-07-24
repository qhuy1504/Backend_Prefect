FROM python:3.11-slim

# Tạo thư mục làm việc
WORKDIR /app

# Copy toàn bộ mã nguồn vào container
COPY . .

# Cài đặt các thư viện cần thiết
RUN pip install --no-cache-dir -r requirements.txt || true

# Mở port Flask
EXPOSE 5001

# Khởi động Flask app
CMD ["python", "mcp_server.py"]
