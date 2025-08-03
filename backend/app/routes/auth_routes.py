from flask import Blueprint
from controllers.auth_controller import (
    forgot_password,
    verify_otp,
    reset_password,
    change_password
)
from middlewares.authenticate import auth_middleware, require_api_key

auth_bp = Blueprint('auth_bp', __name__)

auth_bp.route('/forgot-password', methods=['POST'])(require_api_key(forgot_password))
auth_bp.route('/verify-otp', methods=['POST'])(require_api_key(verify_otp))
auth_bp.route('/reset-password', methods=['POST'])(require_api_key(reset_password))
auth_bp.route('/change-password', methods=['POST'])(
    require_api_key(auth_middleware(change_password))
)
