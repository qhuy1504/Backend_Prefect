from flask import Blueprint
from controllers import job_controller, table_controller
from middlewares.authenticate import  require_api_key

job_bp = Blueprint("jobs", __name__)

# JOB ROUTES
job_bp.route("/batch", methods=["POST"])(require_api_key(job_controller.create_job_with_tasks))
job_bp.route("/", methods=["GET"])(require_api_key(job_controller.get_jobs_with_tasks))
job_bp.route("/<int:job_id>/logs", methods=["GET"])(require_api_key(job_controller.get_logs))
job_bp.route("/<int:job_id>", methods=["PUT"])(require_api_key(job_controller.update_job))
job_bp.route("/<int:job_id>", methods=["DELETE"])(require_api_key(job_controller.delete_job))
job_bp.route("/<int:job_id>/trigger", methods=["POST"])(require_api_key(job_controller.trigger_job_flow_prefect))
job_bp.route("/<int:job_id>/stream", methods=["GET"])(require_api_key(job_controller.stream_job_logs))
job_bp.route("/<int:job_id>/tasks", methods=["GET"])(require_api_key(job_controller.get_tasks_by_job_id))

# JOB_TASK CRUD
job_bp.route("/tasks/<int:job_id>", methods=["POST"])(require_api_key(job_controller.add_task_to_job))
job_bp.route("/tasks/<int:job_task_id>", methods=["PUT"])(require_api_key(job_controller.update_job_task))
job_bp.route("/tasks/<int:job_task_id>", methods=["DELETE"])(require_api_key(job_controller.delete_job_task))

# FLOW STATUS
job_bp.route("/flow-run-status/<string:flow_run_id>", methods=["GET"])(require_api_key(job_controller.get_flow_run_status))

# TASKS DETAIL
job_bp.route("/<int:job_id>/tasks/detail", methods=["GET"])(require_api_key(job_controller.get_tasks_by_job_id_detail))
job_bp.route("/<int:job_id>/logs/sync", methods=["POST"])(require_api_key(job_controller.sync_job_logs))

job_bp.route("/<int:job_id>/info", methods=["GET"])(require_api_key(job_controller.get_job_info))
job_bp.route("/<string:deployment_id>/flow-runs", methods=["GET"])(require_api_key(job_controller.get_flow_runs))
job_bp.route("/<string:deployment_id>/task-runs", methods=["GET"])(require_api_key(job_controller.get_task_runs))
job_bp.route("/logs", methods=["POST"])(require_api_key(job_controller.get_logs_for_runs))
job_bp.route("/<int:job_id>/variables", methods=["GET"])(require_api_key(job_controller.get_job_variables))


# TABLE
job_bp.route("/table-list", methods=["GET"])(require_api_key(table_controller.get_table_list))
job_bp.route("/table-size", methods=["GET"])(require_api_key(table_controller.get_table_size))
job_bp.route("/table-etl-log", methods=["GET"])(require_api_key(table_controller.get_table_etl_log))
job_bp.route("/table-size/<string:table_name>", methods=["GET"])(require_api_key(table_controller.get_table_size_by_name))
