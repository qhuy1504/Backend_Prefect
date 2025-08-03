# Use official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements.txt into the container
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy all backend source code into the container
COPY . .

# Expose the port your app runs on (thay đổi nếu khác)
EXPOSE 3001

# Command to run the application
CMD ["python", "main.py"]
