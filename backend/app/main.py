from flask import Flask
from flask_cors import CORS
from routes.job_routes import job_bp
from routes.admin_routes import admin_bp
from routes.import_routes import import_bp
from routes.auth_routes import auth_bp
from routes.ai_routes import ai_bp
from routes.env_config_routes import env_config_bp

app = Flask(__name__)
CORS(app)

# Đăng ký các blueprint
app.register_blueprint(job_bp, url_prefix='/api/jobs')
app.register_blueprint(admin_bp, url_prefix='/api/admin')
app.register_blueprint(import_bp, url_prefix='/api/import')
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(ai_bp, url_prefix='/api/ai')
app.register_blueprint(env_config_bp, url_prefix='/api/env-config')

if __name__ == '__main__':
    # app.run(debug=True, port=3001)
    app.run(host='0.0.0.0', debug=True, port=3001)
