#!/bin/bash

set -e

if [ -f .env ]; then
  export $(cat .env | sed 's/\r//' | xargs)
else
  echo ".env file not found"
  exit 1
fi

echo "== PREFECT UI/ API =="
echo "PREFECT_API_URL=$PREFECT_API_URL"
echo "PREFECT_UI_URL=$PREFECT_UI_URL"


export PREFECT_API_URL=$PREFECT_API_URL
export PREFECT_UI_URL=$PREFECT_UI_URL

echo "== STARTING PREFECT SERVER =="
prefect server start --host 0.0.0.0 --port 4200 &

SERVER_PID=$!
sleep 60

echo "== CREATE WORK POOL (if not exists) =="
prefect work-pool create -t process local-process-pool || true

echo "== STARTING PREFECT WORKER =="
prefect worker start --pool local-process-pool --type process &

WORKER_PID=$!
sleep 20

echo "== SERVING FLOW =="
python my_flows.py


wait $SERVER_PID
wait $WORKER_PID
