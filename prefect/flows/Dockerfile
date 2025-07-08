# Bắt đầu từ image nền của Prefect
FROM prefecthq/prefect:3-python3.13

# Đặt thư mục làm việc
WORKDIR /opt/prefect/flows

# Copy file requirements trước để tận dụng cache
COPY requirements.txt .

# Cài đặt các thư viện
RUN pip install -r requirements.txt

# Copy toàn bộ code còn lại
COPY . .