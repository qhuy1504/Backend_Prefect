FROM python:3.11-slim

WORKDIR /app

# Copy toàn bộ mã nguồn (bao gồm .env, my_flows.py)
COPY . .

# Cài thư viện
RUN pip install --no-cache-dir -r requirements.txt || true

# Cho phép chạy script
RUN chmod +x ./start.sh

EXPOSE 4200

CMD ["./start.sh"]
