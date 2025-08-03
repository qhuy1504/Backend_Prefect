import os
import json
import re
from flask import request, jsonify
import traceback

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", "..", ".."))

FOLDER_FRONTEND = os.path.join(ROOT_DIR, "vision_ui")
FOLDER_BACKEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
FOLDER_BACKEND = os.path.abspath(FOLDER_BACKEND)
FOLDER_MCP = os.path.join(ROOT_DIR, "mcp_tools")
FOLDER_PREFECT = os.path.join(ROOT_DIR, "prefect") 

print(f"FOLDER_PREFECT: {FOLDER_PREFECT}")
print(f"FOLDER_BACKEND: {FOLDER_BACKEND}")
print(f"FOLDER_MCP: {FOLDER_MCP}")
print(f"FOLDER_FRONTEND: {FOLDER_FRONTEND}")


ENV_CONFIG_PATH = os.path.join(BASE_DIR, "..", "env-config.json")
# ENV_CONFIG_PATH = "/app/env-config.json"

# Map thư mục tương ứng cho mỗi key
FOLDER_MAP = {
    "frontend": FOLDER_FRONTEND,
    "backend": FOLDER_BACKEND,
    "mcp_tools": FOLDER_MCP,
    "prefect_flows": FOLDER_PREFECT,
}

def write_env_files(env_data: dict):
    for folder, values in env_data.items():
        folder_path = FOLDER_MAP.get(folder)
        print(f"[INFO] Writing .env for folder: {folder} at {folder_path}")
        if folder_path is None:
            print(f"[WARN] Folder '{folder}' not found in FOLDER_MAP")
            continue

        # Nếu là list -> convert sang dict trước khi ghi
        if isinstance(values, list):
            env_dict = {}
            for item in values:
                k, v = item.get("key"), item.get("value")
                if k:  # bỏ qua nếu key rỗng
                    env_dict[k] = v
            values = env_dict

        env_file_path = os.path.join(folder_path, ".env")
        with open(env_file_path, "w", encoding="utf-8") as f:
            for key, value in values.items():
                safe_value = str(value).replace(chr(10), "\\n")
                f.write(f"{key}={safe_value}\n")    

        print(f"[INFO] Wrote .env to {env_file_path}")

# Regex validators
regex_validators = {
    "REACT_APP_API_URL": r"^https?://.+",  # Cho phép http hoặc https
    "PREFECT_API_URL": r"^https?://.+",
    "PREFECT_UI_URL": r"^https?://.+",
    "JWT_SECRET": r"^.{20,}$",  # Tối thiểu 20 ký tự, không giới hạn kiểu
    "CLOUDINARY_CLOUD_NAME": r"^[\w\-]+$",  # Cho phép chữ, số, gạch ngang, gạch dưới
    "CLOUDINARY_API_KEY": r"^\d{10,}$",  # Tối thiểu 10 số
    "CLOUDINARY_API_SECRET": r"^.{10,}$",  # Tối thiểu 10 ký tự bất kỳ
    "EMAIL_FROM": r"^[^@]+@[^@]+\.[^@]+$",  # Regex email đơn giản, không quá khắt khe
    "EMAIL_PASSWORD": r"^.{8,}$",  # Tối thiểu 8 ký tự (cho thoải mái)
    "OPENROUTER_API_KEY": r"^sk-or-v1-[\w\-]{20,}$",  # Cho phép key dài, không quá bó buộc
    "DATABASE_URL": r"^postgres:\/\/.+:.+@.+:\d+\/.+$",  # Cho phép format Postgres mềm hơn
    "OPENWEATHER_API_KEY": r"^[\w]{20,}$",  # Cho phép cả chữ cái và số, tối thiểu 20 ký tự
}


def validate_field(key, value):
    pattern = regex_validators.get(key)
    return re.match(pattern, value) if pattern else True


def get_env_config():
    try:
        with open(ENV_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            print("[get_env_config] Loaded data:", data)
        return jsonify(data), 200
    except Exception as e:
        print("[get_env_config] ERROR:", str(e))
        return jsonify({"message": "Failed to read env-config.json."}), 500


def save_env_config():
    try:
        new_data = request.get_json()
        print("[save_env_config] Received data:", new_data)
        if not isinstance(new_data, dict):
            return jsonify({"message": "Invalid data format."}), 400

        # Load current config
        if os.path.exists(ENV_CONFIG_PATH):
            with open(ENV_CONFIG_PATH, "r", encoding="utf-8") as f:
                old_data = json.load(f)
        else:
            old_data = {}

        for section, kv_list in new_data.items():
            if not isinstance(kv_list, list):
                return jsonify({"message": f"Invalid format for section '{section}'"}), 400

            # Build new list of dicts (try preserve id if possible)
            new_list = []
            old_list = old_data.get(section, [])
            

            # Convert old list to map by key to preserve id
            old_map = {item["key"]: item for item in old_list if isinstance(item, dict) and "key" in item}
            # Check for duplicate keys
            seen_keys = set()
            
           
            for entry in kv_list:
                if not isinstance(entry, dict):
                    continue  # Bỏ qua entry không hợp lệ

                key = entry.get("key", "").strip()
                value = entry.get("value", "").strip()
                id_ = entry.get("id")

                # Kiểm tra key trống
                if not key:
                    return jsonify({
                        "message": f"Key trong section '{section}' không được để trống."
                    }), 400
                if key in seen_keys:  
                    return jsonify({
                        "message": f"Trùng key '{key}' trong section '{section}'."
                    }), 400
                seen_keys.add(key)

                # Kiểm tra value trống
                if not value:
                    return jsonify({
                        "message": f"Value cho key '{key}' trong '{section}' không được để trống."
                    }), 400

                if not validate_field(key, value):
                    return jsonify({
                        "message": f"Không hợp lệ '{key}': '{value}'"
                    }), 400

                item = {
                    "key": key,
                    "value": value
                }

                if id_:
                    item["id"] = id_
                elif key in old_map and "id" in old_map[key]:
                    item["id"] = old_map[key]["id"]

                new_list.append(item)

            # Update merged config
            old_data[section] = new_list

        # Save
        with open(ENV_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(old_data, f, indent=2)

        write_env_files(old_data)

        return jsonify({"message": "env-config.json saved successfully."}), 200

    except Exception as e:
        print("[save_env_config] ERROR:", str(e))
        traceback.print_exc()
        return jsonify({"message": "Failed to save env-config.json."}), 500





