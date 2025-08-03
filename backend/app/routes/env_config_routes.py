from flask import Blueprint
from controllers import env_config_controller
from middlewares.authenticate import  require_api_key

env_config_bp = Blueprint("env_config_bp", __name__)

env_config_bp.route("", methods=["GET"])(require_api_key(env_config_controller.get_env_config))
env_config_bp.route("", methods=["POST"])(require_api_key(env_config_controller.save_env_config))
