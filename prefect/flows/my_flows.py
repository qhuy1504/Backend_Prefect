import time
import psycopg2
from psycopg2.extras import RealDictCursor
from prefect import flow, task, get_run_logger
from prefect.task_runners import ThreadPoolTaskRunner
from typing import List, Dict, TypedDict
from prefect.variables import Variable
from datetime import datetime
from prefect.states import State
import json
from typing import List, Optional

class TaskDict(TypedDict):
    name: str
    script_type: str
    script_content: str

DATABASE_URL = "postgresql://postgres:gRkWEparPPhyoBSwqZCBvFQRTEPYSILc@maglev.proxy.rlwy.net:25007/railway"


@task(name="Execute Single Script", retries=2, retry_delay_seconds=10)
def execute_script_task(task_info: Dict, db_url: str):
    """
    Thực thi 1 script SQL hoặc Python dựa trên dict task_info.
    """
    logger = get_run_logger()

    task_name = task_info.get("name", "Unnamed Task")
    script_type = task_info.get("script_type", "unknown")
    script_content = task_info.get("script_content", "")

    logger.info(f"--- Starting Task: '{task_name}' (Type: {script_type}) ---")
    time.sleep(5)
    
    conn = None
    try:
        if script_type == "sql":
            if not db_url:
                raise ValueError("Database URL was not provided.")

            logger.info("Connecting to database...")
            conn = psycopg2.connect(db_url)
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            logger.info(f"Executing SQL: {script_content[:200]}...")
            cursor.execute(script_content)

            if cursor.description:
                results = cursor.fetchall()
                logger.info(f"Query returned {len(results)} row(s).")
            else:
                logger.info(f"{cursor.rowcount} row(s) affected.")

            conn.commit()

        elif script_type == "python":
            logger.info("Executing Python script...")
            exec(script_content, {"logger": logger, "db_url": db_url,"conn": conn})

        else:
            logger.warning(f"Unknown script type '{script_type}'. Skipping.")
            return {"task_name": task_name, "status": "SKIPPED"}

        logger.info(f"Task '{task_name}' completed successfully.")
        return {"task_name": task_name, "status": "COMPLETED"}

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error executing task '{task_name}': {e}", exc_info=True)
        logger.error(f"Error executing task '{task_name}': {e}", exc_info=True)
        logger.error(f"Script content:\n{script_content}") 
        raise

    finally:
        if conn:
            conn.close()


def create_dynamic_flow(concurrent: int):
    @flow(
        name="dynamic_concurrency_flow",
        task_runner=ThreadPoolTaskRunner(max_workers=concurrent)
    )
    def internal_flow(jobId: int,
                      tasks: Optional[List[TaskDict]] = None,
                      concurrent: Optional[int] = None,
                      db_url: str = DATABASE_URL):
        logger = get_run_logger()
        logger.info(f"=== Job {jobId} START (concurrent={concurrent}) ===")

       
        if tasks is None:
            tasks = json.loads(Variable.get(f"job:{jobId}:tasks"))
        if concurrent is None:
            concurrent = int(Variable.get(f"job:{jobId}:concurrent", default=1))

        logger.info(f"Job {jobId} – tasks = {len(tasks)}, concurrent = {concurrent}")

      
        futures, task_names = [], []
        for task_info in tasks:
            pretty = f"Execute Single Script - {task_info['name']}"
            fut = (execute_script_task
                   .with_options(name=pretty)
                   .submit(task_info, db_url=db_url))
            futures.append(fut)
            task_names.append(pretty)

        
        results = [f.result() for f in futures]    
        states  = [f.state  for f in futures]

       
        from pprint import pformat
        for i, st in enumerate(states):
            logger.info(f"[TASK {i}] {task_names[i]} - {st.type}")

        
        failed   = [s for s in states if s and s.type == "FAILED"]
        succeeded = [r for r in results if r]

        if failed:
            logger.error(f"{len(failed)} task(s) FAILED in job {jobId}")
            raise Exception(f"{len(failed)} task(s) failed")

        return {
            "jobId": jobId,
            "status": "COMPLETED",
            "successful_results": succeeded,
            "task_names": task_names,
        }

    return internal_flow


def insert_task_log(job_id, job_task_id, name, status, log="", db_url=DATABASE_URL):
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO job_task_logs (job_task_id, job_id, task_name, task_status, log, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (job_task_id) DO UPDATE
        SET task_status = EXCLUDED.task_status,
            log = EXCLUDED.log,
            updated_at = EXCLUDED.updated_at
    """, (job_task_id, job_id, name, status, log, datetime.now()))
    conn.commit()
    cur.close()
    conn.close()
    

@flow(name="entrypoint_dynamic_job")
def multi_task_job_flow(jobId: int):
    logger = get_run_logger()

   
    try:
        concurrent = int(Variable.get(f"job_{jobId}_concurrent"))
        tasks_json = Variable.get(f"job_{jobId}_tasks")
        tasks = json.loads(tasks_json)
    except Exception as e:
        logger.error(f"Lỗi khi lấy variables cho job-{jobId}: {e}")
        raise

   
    dyn_flow = create_dynamic_flow(concurrent)
    result_data = dyn_flow(jobId=jobId, tasks=tasks, db_url=DATABASE_URL)
    logger.info(f"Kết quả sub-flow job {jobId}: {result_data}")

    if "task_names" in result_data:
        logger.info(f"Task names for job {jobId}: {result_data['task_names']}")

    if result_data.get("status") == "FAILED":
        logger.error(f"Sub-flow cho Job {jobId} thất bại!")
        raise Exception(f"Sub-flow failed with result: {result_data}")

    return result_data


if __name__ == "__main__":
    import os
    os.environ.setdefault(
        "PREFECT_API_URL",
        "http://127.0.0.1:4200/api"     
    )

    multi_task_job_flow.serve(
        name="entrypoint_dynamic_job",   
        tags=["dynamic-job"]             
    )