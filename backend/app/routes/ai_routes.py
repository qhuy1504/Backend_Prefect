from flask import Blueprint, request, jsonify
from controllers.ai_controller import ask_ai_with_ollama
from middlewares.authenticate import  require_api_key

ai_bp = Blueprint('ai_bp', __name__)


@ai_bp.route('/ask-ollama', methods=['POST'])
@require_api_key
def handle_ask_ollama():
    return ask_ai_with_ollama(request)
