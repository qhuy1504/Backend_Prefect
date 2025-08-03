# app/utils/authenticate.py
import jwt
import bcrypt
import psycopg2
from flask import request, jsonify, g
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from db import get_connection, release_connection

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_EXPIRES_IN = 60 * 60 * 3  # seconds (3 hours)




# Get menus from user id
def get_menus_by_user_id(user_id):
    conn = get_connection()
    if not conn:
        print("Could not get DB connection")
        return []

    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT m.id, m.name, m.path
            FROM users u
            JOIN user_groups ug ON u.id = ug.user_id
            JOIN group_roles gr ON ug.group_id = gr.group_id
            JOIN role_menus rm ON gr.role_id = rm.role_id
            JOIN menus m ON rm.menu_id = m.id
            WHERE u.id = %s
        """, (user_id,))
        rows = cur.fetchall()
        return [{"id": r[0], "name": r[1], "path": r[2]} for r in rows]
    except Exception as e:
        print(f"Error fetching menus: {e}")
        return []
    finally:
        cur.close()
        release_connection(conn)



# Hybrid login
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Username và password là bắt buộc"}), 400

    if not username.isalnum():
        return jsonify({"error": "Username không hợp lệ. Chỉ cho phép chữ cái và số."}), 400

    if len(password) < 8 or not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        return jsonify({"error": "Mật khẩu phải từ 8 ký tự và có ít nhất 1 ký tự đặc biệt."}), 400

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cur.fetchone()
    print(f"User found: {user}")

    if user:
        hashed_pw = user[2].encode('utf-8')  # fix: dùng user[2] thay vì user[3]
        if bcrypt.checkpw(password.encode('utf-8'), hashed_pw):
            payload = {
                "id": user[0],
                "username": user[1],
                "email": user[5],       # fix nếu cần
                "avatar": user[4],
                "exp": datetime.utcnow() + timedelta(seconds=JWT_EXPIRES_IN)
            }
            token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
            menus = get_menus_by_user_id(user[0])
            return jsonify({
                "message": "Đăng nhập thành công",
                "token": token,
                "menus": menus
            })

    return jsonify({"error": "Sai tài khoản hoặc mật khẩu"}), 401


# Middleware
def auth_middleware(f):
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Token không tồn tại"}), 401

        token = auth_header.split(" ")[1]
        try:
            decoded = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            g.user = decoded  # attach to Flask global context
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token đã hết hạn"}), 403
        except jwt.InvalidTokenError:
            return jsonify({"error": "Token không hợp lệ"}), 403

        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__  # Preserve function name
    return wrapper

# Middleware kiểm tra API Key
def require_api_key(f):
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get("X-API-KEY")
        expected_key = os.getenv("ADMIN_API_KEY")

        if not api_key or api_key != expected_key:
            return jsonify({"error": "Unauthorized: API Key không hợp lệ"}), 401

        return f(*args, **kwargs)

    return decorated
