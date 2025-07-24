FROM python:3.11-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt || true

RUN chmod +x ./start.sh

EXPOSE 4200
CMD ["/bin/bash", "./start.sh"]