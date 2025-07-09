#!/bin/bash

set -e

# Load biến môi trường
if [ -f .env ]; then
  export $(cat .env | xargs)
else
  echo ".env file not found"
  exit 1
fi

echo "== PREFECT UI/ API =="
echo "PREFECT_API_URL=$PREFECT_API_URL"
echo "PREFECT_UI_URL=$PREFECT_UI_URL"

# Ép Prefect biết đúng URL public
export PREFECT_API_URL=$PREFECT_API_URL
export PREFECT_UI_URL=$PREFECT_UI_URL

echo "== STARTING PREFECT SERVER =="
prefect server start --host 0.0.0.0 --port 4200 &

SERVER_PID=$!
sleep 40

echo "== CREATE WORK POOL (if not exists) =="
prefect work-pool create -t process local-process-pool || true

echo "== STARTING PREFECT WORKER =="
prefect worker start --pool local-process-pool --type process &

WORKER_PID=$!
sleep 10

echo "== SERVING FLOW =="
python my_flows.py

# Wait cho các tiến trình chạy nền
wait $SERVER_PID
wait $WORKER_PID
