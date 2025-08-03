from flask import Blueprint, request, jsonify
from controllers.import_controller import handle_import_file
from middlewares.upload import upload_file
from middlewares.authenticate import  require_api_key


import_bp = Blueprint("import_bp", __name__)

@import_bp.route("/upload", methods=["POST"])
@require_api_key  # middleware yêu cầu API key
@upload_file  # middleware xử lý file upload
def upload_route(file):
    file = request.uploaded_file  # Lấy file đã được middleware xử lý
    print(f"Received file: {file.filename if file else 'No file uploaded'}")
    return handle_import_file(request, file)
