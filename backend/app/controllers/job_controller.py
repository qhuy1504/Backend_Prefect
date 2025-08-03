from unittest import result
from flask import Blueprint, request, jsonify, Response, stream_with_context
from prefect import flow
from db import get_connection, release_connection
import time
from services.prefect_service import upsert_concurrency_limit_for_tag, get_flow_run_logs, get_flow_run_state, upsert_variable, trigger_prefect_flow
import re
import json
import requests
from datetime import datetime, timedelta
import os
from psycopg2.extras import RealDictCursor
import asyncio
import concurrent.futures
import hashlib
import traceback
import threading



PREFECT_API_URL = os.getenv("PREFECT_API_URL")

seen_ids = set()
seen_ids_lock = threading.Lock()

def create_job_with_tasks():
    data = request.get_json()
    
    name = data.get('name')
    concurrent = data.get('concurrent')
    tasks = data.get('tasks', [])
    schedule = data.get('schedule') or {}

    schedule_type = schedule.get('type')
    schedule_value = str(schedule.get('value')) if schedule.get('value') else None
    schedule_unit = schedule.get('unit')

    if not name:
        return jsonify({"error": 'Invalid input: "name" is a required field.'}), 400

    conn = get_connection()
    cur = conn.cursor()

    try:
        # Check if job already exists
        cur.execute('SELECT id FROM jobs WHERE name = %s', (name,))
        existing = cur.fetchone()
        if existing:
            return jsonify({
                "message": f'Job with name "{name}" already exists.',
                "existing_job_id": existing[0],
                "error_code": "JOB_NAME_EXISTS"
            }), 409


        cur.execute('''
            INSERT INTO jobs (name, concurrent, schedule_type, schedule_value, schedule_unit)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        ''', (name, concurrent, schedule_type, schedule_value, schedule_unit))

        job_id = cur.fetchone()[0]

        for i, task in enumerate(tasks):
            task_name = task.get('name')
            script_type = task.get('script_type')
            script_content = task.get('script_content')
            parameters = json.dumps(task.get('parameters')) if task.get('parameters') else None

            # Try insert new task
            cur.execute('''
                INSERT INTO tasks (name, script_type, script_content)
                VALUES (%s, %s, %s)
                ON CONFLICT (name) DO NOTHING
                RETURNING id
            ''', (task_name, script_type, script_content))

            task_row = cur.fetchone()
            if not task_row:
                cur.execute('SELECT id FROM tasks WHERE name = %s', (task_name,))
                task_row = cur.fetchone()

            task_id = task_row[0]

            cur.execute('''
                INSERT INTO job_task (job_id, task_id, execution_order, parameters)
                VALUES (%s, %s, %s, %s)
            ''', (job_id, task_id, i, parameters))

        # Tag chuẩn hoá
        prefect_tag = f"job-{re.sub(r'[^a-z0-9-]', '', name.lower().replace(' ', '-').replace('_', '-'))}"

        # Upsert Prefect concurrency limit
        upsert_concurrency_limit_for_tag(prefect_tag, concurrent)

        conn.commit()

        return jsonify({
            "message": "Job and its tasks created successfully!",
            "jobId": job_id,
            "jobName": name,
            "tasksLinked": len(tasks),
            "prefect": {
                "tag": prefect_tag,
                "concurrencyLimit": concurrent
            }
        }), 201

    except Exception as e:
        conn.rollback()
        print("Error in create_job_with_tasks:", str(e))
        return jsonify({"error": "Failed to create job and tasks"}), 500

    finally:
        cur.close()
        release_connection(conn)

def get_jobs_with_tasks():
    try:
        conn = get_connection()
        cur = conn.cursor()

        query = """
        SELECT
            j.id,
            j.name,
            j.status,
            j.concurrent,
            j.flow_run_id,
            j.created_at,
            j.updated_at,
            j.schedule_type,
            j.schedule_value,
            j.schedule_unit,
            COALESCE(
                json_agg(
                    json_build_object(
                        'job_task_id', jt.id,
                        'task_id', t.id,
                        'task_name', t.name,
                        'status', jt.status,
                        'execution_order', jt.execution_order,
                        'script_type', t.script_type
                    )
                    ORDER BY jt.execution_order ASC
                ) FILTER (WHERE t.id IS NOT NULL),
                '[]'::json
            ) AS tasks
        FROM
            jobs j
        LEFT JOIN
            job_task jt ON j.id = jt.job_id
        LEFT JOIN
            tasks t ON jt.task_id = t.id
        GROUP BY
            j.id
        ORDER BY
            j.id DESC;
        """

        cur.execute(query)
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        result = [dict(zip(columns, row)) for row in rows]


        cur.close()
        release_connection(conn)

        return jsonify(result), 200

    except Exception as e:
        print("Error fetching jobs with tasks:", e)
        return jsonify({"error": "Failed to fetch jobs"}), 500

def get_logs(job_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM logs WHERE job_id = %s ORDER BY log_time DESC",
            (job_id,)
        )
        rows = cursor.fetchall()

        # Lấy tên các cột để chuyển đổi sang dict
        colnames = [desc[0] for desc in cursor.description]
        logs = [dict(zip(colnames, row)) for row in rows]

        cursor.close()
        release_connection(conn)

        return jsonify(logs), 200

    except Exception as e:
        print("Error fetching logs:", e)
        return jsonify({'error': 'Failed to fetch logs'}), 500
    
def update_job(job_id):
    try:
        data = request.get_json()
        name = data.get("name")
        concurrent = data.get("concurrent")
        schedule_type = data.get("schedule_type")
        schedule_value = data.get("schedule_value")
        schedule_unit = data.get("schedule_unit")

        # Nếu là cron thì không có schedule_unit
        if schedule_type == "cron":
            schedule_unit = None

        conn = get_connection()
        cur = conn.cursor()

        query = """
            UPDATE jobs SET 
                name = %s,
                concurrent = %s,
                schedule_type = %s,
                schedule_value = %s,
                schedule_unit = %s
            WHERE id = %s
            RETURNING *;
        """
        cur.execute(query, (name, concurrent, schedule_type, schedule_value, schedule_unit, job_id))
        updated_row = cur.fetchone()

        if updated_row is None:
            return jsonify({"error": "Job not found"}), 404

        columns = [desc[0] for desc in cur.description]
        result = dict(zip(columns, updated_row))

        conn.commit()
        cur.close()
        release_connection(conn)

        return jsonify(result), 200
    except Exception as e:
        print(f"Error updating job: {e}")
        return jsonify({"error": "Failed to update job"}), 500
    
def delete_job(job_id):
    conn = get_connection()
    cur = conn.cursor()

    try:
        # Bắt đầu transaction
        conn.autocommit = False

        # BƯỚC KIỂM TRA
        check_query = """
        SELECT j.name, COUNT(jt.id) as task_count
        FROM jobs j
        LEFT JOIN job_task jt ON j.id = jt.job_id
        WHERE j.id = %s
        GROUP BY j.name;
        """
        cur.execute(check_query, (job_id,))
        result = cur.fetchone()

        if not result:
            conn.rollback()
            return jsonify({"error": "Job not found"}), 404

        job_name, task_count = result

        # BƯỚC XÓA
        delete_query = "DELETE FROM jobs WHERE id = %s"
        cur.execute(delete_query, (job_id,))

        if cur.rowcount == 0:
            raise Exception("Deletion failed unexpectedly.")

        # Commit nếu không lỗi
        conn.commit()
        return "", 204  # 204 No Content

    except Exception as e:
        conn.rollback()
        print(f"Error deleting job {job_id}:", e)
        return jsonify({"error": "Failed to delete job"}), 500

    finally:
        cur.close()
        release_connection(conn)
def stream_job_logs(job_id):
    def event_stream():
        conn = get_connection()
        cur = conn.cursor()

        MAX_RETRIES = 5
        RETRY_DELAY = 1  # seconds
        flow_run_id = None

        for _ in range(MAX_RETRIES):
            cur.execute("SELECT flow_run_id FROM job WHERE id = %s", (job_id,))
            row = cur.fetchone()
            if row and row[0]:
                flow_run_id = row[0]
                break
            time.sleep(RETRY_DELAY)

        if not flow_run_id:
            yield sse_format({"message": "Could not find a running flow for this job after multiple attempts.", "type": "error"})
            return

        yield sse_format({"message": f"Connected to log stream for flow run: {flow_run_id}", "type": "info"})

        last_timestamp = '1970-01-01T00:00:00.000000+00:00'
        is_running = True

        while is_running:
            try:
                logs = get_flow_run_logs(flow_run_id)
                new_logs = [log for log in logs if log["timestamp"] > last_timestamp]

                if new_logs:
                    new_logs.sort(key=lambda l: l["timestamp"])
                    for log in new_logs:
                        yield sse_format({"message": log["message"], "type": "log"})
                    last_timestamp = new_logs[-1]["timestamp"]

                flow_state = get_flow_run_state(flow_run_id)
                if flow_state["state_type"] in ['COMPLETED', 'FAILED', 'CANCELLED', 'CRASHED']:
                    yield sse_format({"message": f"Flow finished with state: {flow_state['state_type']}", "type": "info"})
                    is_running = False

                time.sleep(3)

            except Exception as e:
                yield sse_format({"message": f"Polling error: {str(e)}", "type": "error"})
                is_running = False

        cur.close()
        release_connection(conn)

    return Response(stream_with_context(event_stream()), mimetype="text/event-stream")
def sse_format(data):
    return f"data: {json.dumps(data)}\n\n"
def get_tasks_by_job_id(job_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()

        query = """
        SELECT
            t.id AS task_template_id,
            t.name,
            t.description,
            t.script_type,
            t.script_content,
            jt.id AS job_task_id,
            jt.execution_order,
            jt.status AS task_status,
            jt.parameters
        FROM
            job_task jt
        JOIN
            tasks t ON jt.task_id = t.id
        WHERE
            jt.job_id = %s
        ORDER BY
            jt.execution_order ASC
        """

        cursor.execute(query, (job_id,))
        column_names = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        

        # Nếu không có task nào, kiểm tra job có tồn tại không
        if not rows:
            cursor.execute("SELECT id FROM jobs WHERE id = %s", (job_id,))
            job_exists = cursor.fetchone()
            if not job_exists:
                return jsonify({"error": "Job not found"}), 404

        # Lấy tên cột để tạo dict
       
        results = [dict(zip(column_names, row)) for row in rows]
        

        return jsonify(results), 200

    except Exception as e:
        print(f"Error fetching tasks for job {job_id}:", e)
        return jsonify({"error": "Failed to fetch tasks for the job"}), 500

    finally:
        cursor.close()
        release_connection(conn)
def add_task_to_job(job_id):
    data = request.get_json()
    name = data.get('name')
    script_type = data.get('script_type')
    script_content = data.get('script_content')

    conn = get_connection()
    cur = conn.cursor()

    try:
        conn.autocommit = False

        # 1. UPSERT task
        task_upsert = """
        INSERT INTO tasks (name, script_type, script_content)
        VALUES (%s, %s, %s)
        ON CONFLICT (name) DO UPDATE SET
            script_type = EXCLUDED.script_type,
            script_content = EXCLUDED.script_content;
        """
        cur.execute(task_upsert, (name, script_type, script_content))

        # 2. Lấy task_id
        cur.execute("SELECT id FROM tasks WHERE name = %s", (name,))
        task_row = cur.fetchone()
        if not task_row:
            raise Exception("Task not found after insert.")
        task_id = task_row[0]

        # 3. Lấy execution_order lớn nhất
        cur.execute("SELECT MAX(execution_order) FROM job_task WHERE job_id = %s", (job_id,))
        max_order = cur.fetchone()[0]
        new_order = (max_order if max_order is not None else -1) + 1

        # 4. Insert job_task
        insert_job_task = """
        INSERT INTO job_task (job_id, task_id, execution_order)
        VALUES (%s, %s, %s)
        RETURNING *;
        """
        cur.execute(insert_job_task, (job_id, task_id, new_order))
        new_task = cur.fetchone()

        conn.commit()
        return jsonify({
            "job_id": new_task[0],
            "task_id": new_task[1],
            "execution_order": new_task[2]
        }), 201

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500

    finally:
        cur.close()
        release_connection(conn)
def update_job_task(job_task_id):
    data = request.get_json()
    name = data.get("name")
    script_type = data.get("script_type")
    script_content = data.get("script_content")
    description = data.get("description")

    conn = get_connection()
    cur = conn.cursor()

    try:
        # Lấy task_id từ bảng job_task
        cur.execute('SELECT task_id FROM job_task WHERE id = %s', (job_task_id,))
        result = cur.fetchone()
        if not result:
            return jsonify({'error': 'Job-Task link not found.'}), 404

        task_id = result[0]

        # Cập nhật bảng tasks
        cur.execute('''
            UPDATE tasks
            SET name = %s, script_type = %s, script_content = %s, description = %s
            WHERE id = %s
            RETURNING *
        ''', (name, script_type, script_content, description, task_id))
        updated_task = cur.fetchone()

        conn.commit()
        return jsonify({
            'id': updated_task[0],
            'name': updated_task[1],
            'script_type': updated_task[2],
            'script_content': updated_task[3],
            'description': updated_task[4]
        }), 200

    except Exception as e:
        conn.rollback()
        print("Error updating job task:", e)
        return jsonify({'error': 'Failed to update task'}), 500
    finally:
        cur.close()
        release_connection(conn)


def delete_job_task(job_task_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute('DELETE FROM job_task WHERE id = %s', (job_task_id,))
        conn.commit()
        return '', 204
    except Exception as e:
        conn.rollback()
        print("Error deleting job task:", e)
        return jsonify({'error': 'Failed to remove task'}), 500
    finally:
        cur.close()
        release_connection(conn)
def create_prefect_deployment_controller(data):
    prefect_api_url = os.getenv("PREFECT_API_URL")

    flow_id = data.get("flow_id")
    name = data.get("name")
    tags = data.get("tags", [])
    parameters = data.get("parameters", {})
    schedules = data.get("schedules", [])

    if not flow_id or not name:
        return jsonify({"error": "flow_id và name là bắt buộc"}), 400

    parameter_schema = {
        "title": "Parameters",
        "type": "object",
        "properties": {
            "jobId": { "type": "integer" },
            "tasks": {
                "type": "array",
                "items": { "$ref": "#/components/schemas/TaskDict" }
            },
            "concurrent": { "type": "integer" },
            "db_url": {
                "type": "string",
                "default": "postgresql://postgres:123456@localhost:5432/appjob"
            }
        },
        "required": ["jobId", "tasks", "concurrent"],
        "components": {
            "schemas": {
                "TaskDict": {
                    "type": "object",
                    "properties": {
                        "name": { "type": "string" },
                        "script_type": { "type": "string" },
                        "script_content": { "type": "string" }
                    },
                    "required": ["name", "script_type", "script_content"]
                }
            }
        }
    }

    body = {
        "name": name,
        "flow_id": flow_id,
        "work_pool_name": "local-process-pool",
        "entrypoint": "my_flows.py:multi_task_job_flow",
        "path": "/app",
        # "path": "F:/THUC_TAP2/APP_JOB/prefect/flows",
        "tags": tags,
        "parameter_openapi_schema": parameter_schema,
        "enforce_parameter_schema": False,
        "schedules": schedules,
        "parameters": parameters
    }

    try:
        response = requests.post(f"{prefect_api_url}/deployments/", json=body, headers={"Content-Type": "application/json"})
        response.raise_for_status()
        return response.json(), 201 
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}, 500 
    
def fetch_flow_id_by_name(flow_name):


    try:
        response = requests.post(
            f"{PREFECT_API_URL}/flows/filter",
            json={
                "flows": {"name": {"any_": [flow_name]}},
                "limit": 1
            }
        )
        response.raise_for_status()
        data = response.json()
        return data[0]["id"] if data else None
    except Exception as e:
        print(f"Error fetching flow ID: {e}")
        return None


# Hàm buildPrefectSchedule tương đương
def build_prefect_schedule(job):
    if not job.get("schedule_type") or not job.get("schedule_value"):
        return []

    tz = "Asia/Ho_Chi_Minh"
    now = datetime.utcnow().isoformat() + "Z"

    if job["schedule_type"] == "cron":
        return [
            {
                "schedule": {
                    "cron": job["schedule_value"],
                    "timezone": tz
                },
                "active": True
            }
        ]

    if job["schedule_type"] == "interval":
        unit = job.get("schedule_unit", "").lower()
        try:
            n = int(job["schedule_value"])
        except ValueError:
            return []

        seconds = {
            "seconds": n,
            "minutes": n * 60,
            "hours": n * 3600,
            "days": n * 86400
        }.get(unit, 0)

        if seconds <= 0:
            return []

        return [
            {
                "schedule": {
                    "interval": seconds,
                    "anchor_date": now,
                    "timezone": tz
                },
                "active": True
            }
        ]

    return []
def trigger_job_flow_prefect(job_id):
    conn = get_connection()
    cur = conn.cursor()

    try:
        # --- BƯỚC 1: LẤY JOB VÀ TASKS ---
        cur.execute("SELECT * FROM jobs WHERE id = %s", (job_id,))
        job = cur.fetchone()

        if not job:
            return jsonify({"error": "Job not found"}), 404

        job_columns = [desc[0] for desc in cur.description]
        job_dict = dict(zip(job_columns, job))

        cur.execute("""
            SELECT t.name, t.script_type, t.script_content
            FROM job_task jt
            JOIN tasks t ON jt.task_id = t.id
            WHERE jt.job_id = %s
            ORDER BY jt.execution_order ASC
        """, (job_id,))
        task_rows = cur.fetchall()
        task_columns = [desc[0] for desc in cur.description]
        tasks = [dict(zip(task_columns, row)) for row in task_rows]

        # --- BƯỚC 2: LẤY FLOW_ID ---
        flow_name = "entrypoint_dynamic_job"
        flow_id = fetch_flow_id_by_name(flow_name)
        if not flow_id:
            raise Exception(f"Không tìm thấy flow với tên '{flow_name}' trong Prefect.")

        # Lưu biến (giả định upsert_variable là lưu vào Redis, DB hoặc Prefect Variable)
        upsert_variable(f"job_{job_id}_tasks", tasks)
        upsert_variable(f"job_{job_id}_concurrent", job_dict["concurrent"])

        # --- BƯỚC 3: TẠO DEPLOYMENT ---
        deployment_name = f"job_{job_id}_deployment"
        schedule_obj = build_prefect_schedule(job_dict)

        deployment, _ = create_prefect_deployment_controller({
            "flow_id": flow_id,
            "name": deployment_name,
            "parameters": {
                "jobId": int(job_id)
            },
            "tags": ["auto-deploy", f"job-{job_id}"],
            "schedules": schedule_obj
        })
        print(f"Deployment response: {deployment}")

        deployment_id = deployment.get("id")
        if not deployment_id:
            raise Exception("Failed to create Prefect deployment.")

        time.sleep(5)  # đợi Prefect khởi tạo deployment

        # --- BƯỚC 4: TRIGGER FLOW ---
        flow_response = trigger_prefect_flow(deployment_id, {
            "jobId": int(job_id)
        })

        flow_run_id = flow_response.get("id")
        if not flow_run_id:
            raise Exception("Failed to trigger flow run from deployment.")

        # --- BƯỚC 5: UPDATE DB ---
        cur.execute("""
            UPDATE jobs
            SET status = 'running',
                flow_run_id = %s,
                deployment_id = %s,
                updated_at = NOW()
            WHERE id = %s
        """, (flow_run_id, deployment_id, job_id))

        conn.commit()

        return jsonify({
            "message": f"Job {job_id} triggered successfully.",
            "deployment_id": deployment_id,
            "flow_run_id": flow_run_id
        }), 200

    except Exception as e:
        conn.rollback()
        print(f"Error triggering job {job_id}: {e}")
        return jsonify({"error": "Failed to trigger job flow"}), 500

    finally:
        cur.close()
        release_connection(conn)

def get_flow_run_status(flow_run_id):

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        response = requests.get(f"{PREFECT_API_URL}/flow_runs/{flow_run_id}")
        response.raise_for_status()

        data = response.json()
        state = data.get("state", {})
        status = state.get("type")

        # Cập nhật DB
        cursor.execute(
            """
            UPDATE jobs
            SET status = %s,
                updated_at = NOW()
            WHERE flow_run_id = %s
            """,
            (status, flow_run_id)
        )
        conn.commit()

        return jsonify({
            "id": data.get("id"),
            "name": data.get("name"),
            "status": status,
            "timestamp": state.get("timestamp")
        }), 200

    except requests.RequestException as e:
        print("Lỗi khi gọi API Prefect:", str(e))
        return jsonify({"error": "Không thể lấy trạng thái flow run"}), 500

    except Exception as db_err:
        print("Lỗi khi cập nhật DB:", str(db_err))
        return jsonify({"error": "Lỗi hệ thống"}), 500

    finally:
        cursor.close()
        release_connection(conn)
        
        
# Kiểm tra và lấy JSON từ URL an toàn     
def safe_get_json(url):
    try:
        res = requests.get(url)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        print(f"[safe_get_json] Failed to fetch from {url}: {str(e)}")
        return {"error": f"Failed to fetch data from {url}"}
    
def safe_post_json(url, json_body):
    try:
        res = requests.post(url, json=json_body)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        print(f"[safe_post_json] Failed to POST to {url}: {str(e)}")
        return {"error": f"Failed to post data to {url}"}
    
#Lấy thông tin flow_run_id, deployment_id, flow_id, work_pool_name.
def get_job_info(job_id):
    
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("SELECT flow_run_id FROM jobs WHERE id = %s", (job_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": "Job not found"}), 404

        initial_flow_run_id = row["flow_run_id"]
        print("DEBUG initial_flow_run_id:", initial_flow_run_id)
           # Nếu flow_run_id là None thì bỏ qua
        # if initial_flow_run_id is None:
        #     return jsonify({
        #         "flow_run_id": None,
        #         "deployment_id": None,
        #         "flow_id": None,
        #         "flow_name": None,
        #         "work_pool_name": None,
        #         "deployment_name": None
        #     })
        
        
        flow_run = requests.get(f"{PREFECT_API_URL}/flow_runs/{initial_flow_run_id}").json()
    
        flow_id = flow_run["flow_id"]
        flow = safe_get_json(f"{PREFECT_API_URL}/flows/{flow_id}")
        deployment_id = flow_run.get("deployment_id")
        deploymentName = safe_get_json(f"{PREFECT_API_URL}/deployments/{deployment_id}")
        print("DEBUG flow:", flow)
        print("DEBUG flow_name:", flow.get("name"))
        return jsonify({
            "flow_run_id": initial_flow_run_id,
            "deployment_id": flow_run["deployment_id"],
            "flow_id": flow_run["flow_id"],
            "flow_name": flow.get("name"),
            "work_pool_name": flow_run.get("work_pool_name"),
            "deployment_name": deploymentName.get("name")
        })
    finally:
        cursor.close()
        release_connection(conn)
# Lấy các flow run theo deployment (có phân trang).
def get_flow_runs(deployment_id):
    limit = int(request.args.get("limit", 25))
    page = int(request.args.get("page", 1))
    # print("DEBUG limit:", limit, "page:", page)
    offset = (page - 1) * limit

    response = requests.post(f"{PREFECT_API_URL}/flow_runs/filter", json={
        "flow_run_filter": {"deployment_id": {"any_": [deployment_id]}},
        "sort": "EXPECTED_START_TIME_DESC",
        "limit": limit,
        "offset": offset
    }).json()

    return jsonify(response)

# Lấy các task run của deployment.
def get_task_runs(deployment_id):
    max_tasks = int(request.args.get("max", 25))
    offset = 0
    page_size = 25
    all_tasks = []

    while offset < max_tasks:
        batch = requests.post(f"{PREFECT_API_URL}/task_runs/filter", json={
            "flow_run_filter": {"deployment_id": {"any_": [deployment_id]}},
            "sort": "EXPECTED_START_TIME_DESC",
            "limit": min(page_size, max_tasks - offset),
            "offset": offset
        }).json()
        all_tasks += batch
        if len(batch) < page_size:
            break
        offset += page_size

    # print("DEBUG all_tasks:", all_tasks)

    return jsonify(all_tasks)

# Lấy log cho một loạt flow_run_id.
def get_logs_for_runs():
    flow_run_ids = request.json.get("flow_run_ids", [])

    def fetch_logs(flow_run_id):
        try:
            flow_run_detail = requests.get(f"{PREFECT_API_URL}/flow_runs/{flow_run_id}").json()
            start_str = flow_run_detail.get("start_time") or flow_run_detail.get("expected_start_time")
            end_str = flow_run_detail.get("end_time")

            if not start_str:
                raise ValueError("Missing both start_time and expected_start_time")

            start = datetime.fromisoformat(start_str) - timedelta(minutes=15)
            end = datetime.fromisoformat(end_str) + timedelta(minutes=90) if end_str else start + timedelta(minutes=90)

            all_logs = []
            offset = 0

            while offset < 200:
                response = requests.post(f"{PREFECT_API_URL}/logs/filter", json={
                    "log_filter": {
                        "flow_run_id": {"any_": [flow_run_id]},
                        "timestamp": {
                            "after_": start.isoformat(),
                            "before_": end.isoformat()
                        }
                    },
                    "sort": "TIMESTAMP_DESC",
                    "limit": 25,
                    "offset": offset
                })

                batch = response.json()
                if not batch:
                    break

                # Lọc trùng theo log id (toàn cục)
                new_batch = []
                with seen_ids_lock:
                    for log in batch:
                        log_id = log["id"]
                        if log_id not in seen_ids:
                            seen_ids.add(log_id)
                            # print(f"[LOG ADDED] {log_id}")
                            new_batch.append(log)

                all_logs.extend(new_batch)

                if len(batch) < 25:
                    break
                offset += 25

            # Format timestamp
            for log in all_logs:
                ts = log.get("timestamp") or log.get("created")
                try:
                    ts = datetime.fromisoformat(ts.replace("Z", "+00:00")).isoformat()
                    log["timestamp"] = ts
                except Exception:
                    continue

            return {"runId": flow_run_id, "logs": all_logs}

        except Exception as e:
            # print(f"[ERROR] fetch_logs for {flow_run_id}: {e}")
            return {"runId": flow_run_id, "logs": []}

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        logs_results = list(executor.map(fetch_logs, flow_run_ids))

    # Format trả về
    logs_by_flow_run = {}
    for result in logs_results:
        for log in result["logs"]:
            run_id = log["flow_run_id"]
            ts = log["timestamp"]
            msg = log.get("message")

            level = log.get("level_name")
            if not level:
                lvl = log.get("level", 0)
                level = "ERROR" if lvl == 40 else "WARNING" if lvl == 30 else "INFO" if lvl == 20 else "DEBUG"

            logs_by_flow_run.setdefault(run_id, []).append({
                "ts": ts,
                "logger": log.get("name"),
                "level": level,
                "msg": msg
            })

    return jsonify(logs_by_flow_run)


# Lấy các variable liên quan đến job.
def get_job_variables(job_id):
    var_names = [f"job_{job_id}_tasks", f"job_{job_id}_concurrent"]
    response = safe_post_json(f"{PREFECT_API_URL}/variables/filter", json_body={
        "name": {"any_": var_names}
    })

    variables_map = {}
    for v in response:
        try:
            variables_map[v["name"]] = json.loads(v["value"])
        except:
            variables_map[v["name"]] = v["value"]

    return jsonify(variables_map)




    
def get_tasks_by_job_id_detail(job_id):
    limit = int(request.args.get("limit", 25))
    page = int(request.args.get("page", 1))
    # print("DEBUG limit:", limit, "page:", page)
    offset = (page - 1) * limit

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Step 1: Get flow_run_id from jobs
        cursor.execute("SELECT flow_run_id FROM jobs WHERE id = %s", (job_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": "Job not found"}), 404

        initial_flow_run_id = row["flow_run_id"]

        # Step 2: Get flow run info
        initial_flow_run = requests.get(f"{PREFECT_API_URL}/flow_runs/{initial_flow_run_id}").json()
        deployment_id = initial_flow_run["deployment_id"]
        flow_id = initial_flow_run["flow_id"]
        work_pool_name = initial_flow_run.get("work_pool_name")

        # Step 3: Get all flow runs of this deployment
        def fetch_flow_runs(limit, offset):
            return requests.post(f"{PREFECT_API_URL}/flow_runs/filter", json={
                "flow_run_filter": {
                    "deployment_id": {"any_": [deployment_id]}
                },
                "sort": "EXPECTED_START_TIME_DESC",
                "limit": limit,
                "offset": offset
            }).json()

        all_flow_runs = fetch_flow_runs(limit, offset)

        # Count total
        total = 0
        offset_count = 0
        page_size = 200
        while True:
            batch = fetch_flow_runs(page_size, offset_count)
            total += len(batch)
            if len(batch) < page_size:
                break
            offset_count += page_size

        # For stats
        flow_run_draw = fetch_flow_runs(200, 0)
        flow_run_by_day = fetch_flow_runs(200, 0)

        # State stats
        flow_run_state_stats = {}
        for run in flow_run_draw:
            state = (run.get("state_type") or "UNKNOWN").upper()
            flow_run_state_stats[state] = flow_run_state_stats.get(state, 0) + 1

        # Task run stats by date
        task_run_stats = {}
        for run in flow_run_by_day:
            # print("DEBUG run:", run, type(run))
            date = run["created"][:10]
            task_run_stats[date] = task_run_stats.get(date, 0) + 1

        # Count by deployment name
        flow_per_deployment = {}
        for run in flow_run_draw:
            dep = run.get("deployment_name") or run.get("deployment_id") or "Manual"
            flow_per_deployment[dep] = flow_per_deployment.get(dep, 0) + 1

        # Step 4: Fetch all task_runs
        def fetch_task_runs_with_cap(max_tasks=200):
            all_tasks = []
            offset = 0
            page_size = 200

            while offset < max_tasks:
                batch = requests.post(f"{PREFECT_API_URL}/task_runs/filter", json={
                    "flow_run_filter": {
                        "deployment_id": {"any_": [deployment_id]}
                    },
                    "sort": "EXPECTED_START_TIME_DESC",
                    "limit": min(page_size, max_tasks - offset),
                    "offset": offset
                }).json()
                all_tasks += batch
                if len(batch) < page_size:
                    break
                offset += page_size
            return all_tasks

        all_tasks = fetch_task_runs_with_cap(200)

        task_runs_by_flow_run = {}
        for t in all_tasks:
            run_id = t["flow_run_id"]
            task_runs_by_flow_run.setdefault(run_id, []).append({
                "id": t["id"],
                "name": t["name"],
                "state": t.get("state_type"),
                "state_name": t.get("state_name"),
                "start_time": t.get("start_time"),
                "end_time": t.get("end_time"),
                "duration": t.get("total_run_time"),
                "task_key": t.get("task_key"),
                "dynamic_key": t.get("dynamic_key")
            })

        # Step 5: Fetch logs with limited concurrency
        def fetch_logs(flow_run):
            try:
                start = datetime.fromisoformat(flow_run.get("start_time") or flow_run["expected_start_time"]) - timedelta(minutes=15)
                end = datetime.fromisoformat(flow_run.get("end_time") or start.isoformat()) + timedelta(minutes=90)

                logs = []
                offset = 0
                page_size = 200

                while offset < 1000:
                    response = requests.post(f"{PREFECT_API_URL}/logs/filter", json={
                        "log_filter": {
                            "flow_run_id": {"any_": [flow_run["id"]]},
                            "timestamp": {
                                "after_": start.isoformat(),
                                "before_:": end.isoformat()
                            }
                        },
                        "sort": "TIMESTAMP_DESC",
                        "limit": page_size,
                        "offset": offset
                    }).json()

                    if not response:
                        break
                    logs.extend(response)
                    if len(response) < page_size:
                        break
                    offset += page_size

                return {
                    "runId": flow_run["id"],
                    "logs": logs
                }
            except Exception as e:
                return {"runId": flow_run["id"], "logs": []}

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            logs_results = list(executor.map(fetch_logs, all_flow_runs[:limit]))

        logs_by_flow_run = {}
        for result in logs_results:
            for log in result["logs"]:
                run_id = log["flow_run_id"]
                logs_by_flow_run.setdefault(run_id, []).append({
                    "ts": log.get("timestamp") or log.get("created"),
                    "logger": log.get("name"),
                    "level": log.get("level_name", "INFO"),
                    "msg": log.get("message")
                })

        # Step 6: Fetch deployment, flow, work_pool, variables
        deployment = safe_get_json(f"{PREFECT_API_URL}/deployments/{deployment_id}")
        flow = safe_get_json(f"{PREFECT_API_URL}/flows/{flow_id}")
        work_pool = safe_get_json(f"{PREFECT_API_URL}/work_pools/{work_pool_name}")

        var_names = [f"job_{job_id}_tasks", f"job_{job_id}_concurrent"]
        variables = safe_post_json(f"{PREFECT_API_URL}/variables/filter", json_body={
            "name": {"any_": var_names}
        })
        # print("deployment:", type(deployment), deployment)
        # print("flow:", type(flow), flow)
        # print("work_pool:", type(work_pool), work_pool)
        # print("variables:", type(variables), variables)

        variables_map = {}
        for v in variables:
            try:
                variables_map[v["name"]] = json.loads(v["value"])
            except Exception:
                variables_map[v["name"]] = v["value"]

        return jsonify({
            "deploymentId": deployment_id,
            "deploymentName": deployment["name"],
            "flowName": flow["name"],
            "allFlowRuns": all_flow_runs,
            "taskRunStats": task_run_stats,
            "flowRunStateStats": flow_run_state_stats,
            "taskRunsByFlowRun": task_runs_by_flow_run,
            "totalCount": total,
            "workPool": work_pool,
            "flowPerDeployment": flow_per_deployment,
            "variables": variables_map,
            "logsByFlowRun": logs_by_flow_run,
            "parameters": {
                "jobId": int(job_id),
                "tasks": variables_map.get(f"job_{job_id}_tasks", []),
                "concurrent": variables_map.get(f"job_{job_id}_concurrent", 1)
            }
        })

    except Exception as err:
        # print("[getTasksByJobIdDetail] ERROR:", str(err))
        # print(traceback.format_exc())  # In full stack trace
        return jsonify({"error": "Internal server error"}), 500

    finally:
        cursor.close()
        release_connection(conn)
def fetch_logs_with_cap(flow_run_id, start, end, max_logs=1000):
    all_logs = []
    page_size = 100
    offset = 0

    while offset < max_logs:
        fetch_size = min(page_size, max_logs - offset)
        response = requests.post(f"{PREFECT_API_URL}/logs/filter", json={
            "log_filter": {
                "flow_run_id": {"any_": [flow_run_id]},
                "timestamp": {
                    "after_": start.isoformat(),
                    "before_:": end.isoformat()
                }
            },
            "sort": "TIMESTAMP_DESC",
            "limit": fetch_size,
            "offset": offset
        })
        response.raise_for_status()
        logs = response.json()
        all_logs.extend(logs)
        if len(logs) < fetch_size:
            break
        offset += fetch_size
    return all_logs

def limit_concurrency(tasks, limit=5):
    from concurrent.futures import ThreadPoolExecutor, as_completed
    results = []
    with ThreadPoolExecutor(max_workers=limit) as executor:
        futures = [executor.submit(task) for task in tasks]
        for future in as_completed(futures):
            results.append(future.result())
    return results

def sync_job_logs(job_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        print(f"Đã chạy syncJobLogs for jobId: {job_id}")
        
        # 1. Lấy flow_run_id từ bảng jobs
        cur.execute("SELECT flow_run_id FROM jobs WHERE id = %s", (job_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Job not found"}), 404

        initial_flow_run_id = row[0]

        # 2. Lấy deployment_id từ flow run
        r = requests.get(f"{PREFECT_API_URL}/flow_runs/{initial_flow_run_id}")
        r.raise_for_status()
        initial_flow_run = r.json()
        deployment_id = initial_flow_run.get("deployment_id")

        # 3. Lấy danh sách flow_runs liên quan
        r = requests.post(f"{PREFECT_API_URL}/flow_runs/filter", json={
            "flow_run_filter": {
                "deployment_id": {"any_": [deployment_id]}
            },
            "sort": "EXPECTED_START_TIME_DESC",
            "limit": 100,
            "offset": 0
        })
        r.raise_for_status()
        all_flow_runs = r.json()

        # 4. Gọi log song song
        def make_task(run):
            def task():
                start = (
                    datetime.fromisoformat(run["start_time"])
                    if run.get("start_time") else
                    datetime.fromisoformat(run["expected_start_time"]) - timedelta(minutes=15)
                )
                end = (
                    datetime.fromisoformat(run["end_time"])
                    if run.get("end_time") else
                    start + timedelta(hours=1)
                )
                logs = fetch_logs_with_cap(run["id"], start, end)
                return {"runId": run["id"], "logs": logs}
            return task

        all_logs = limit_concurrency(
            [make_task(run) for run in all_flow_runs], limit=5
        )

        # 5. Insert DB
       
        inserted = set()
        for item in all_logs:
            run_id = item["runId"]
            for log in item["logs"]:
                log_id = log.get("id")
                task_run_id = log.get("task_run_id")
                flow_run_id = log.get("flow_run_id", run_id)
                logger = log.get("name")
                log_level = log.get("level_name")
                message = log.get("message")
                timestamp = log.get("timestamp")

                fingerprint = f"{job_id}|{task_run_id}|{timestamp}|{message}"
                hash_value = hashlib.md5(fingerprint.encode()).hexdigest()

                if hash_value in inserted:
                    continue
                inserted.add(hash_value)

                cur.execute("""
                    INSERT INTO job_task_logs (
                        job_id, job_task_id, task_name, task_status,
                        flow_run_id, task_run_id, logger, log_level,
                        log, log_timestamp, log_id
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT ON CONSTRAINT uq_job_log DO NOTHING
                """, (
                    job_id, task_run_id, None, None,
                    flow_run_id, task_run_id,
                    logger, log_level,
                    message or '',
                    datetime.fromisoformat(timestamp) if timestamp else None,
                    log_id
                ))

        conn.commit()
        return jsonify({"message": f"Đã đồng bộ logs cho jobId = {job_id}"})
    except Exception as e:
        conn.rollback()
        print("[sync_job_logs] ERROR:", str(e))
        return jsonify({"error": "Lỗi khi sync logs"}), 500
    finally:
        cur.close()
        release_connection(conn)