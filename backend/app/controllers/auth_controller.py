from flask import request, jsonify, g
from db import get_connection, release_connection
import bcrypt
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from datetime import datetime, timedelta

otp_map = {}  # email => { otp, expires }

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@gmail\.com$")
PASSWORD_REGEX = re.compile(r"^(?=.*[!@#$%^&*()_+{}\[\]:;<>,.?~\\/-]).{8,}$")


def forgot_password():
    data = request.get_json()
    email = data.get("email", "").strip()

    if not email or not EMAIL_REGEX.match(email):
        return jsonify({"error": "Email không hợp lệ. Vui lòng nhập email @gmail.com hợp lệ."}), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        if not user:
            return jsonify({"error": "Email không tồn tại trên hệ thống"}), 404

        otp = str(__import__('random').randint(100000, 999999))
        expires = datetime.utcnow() + timedelta(minutes=5)
        otp_map[email] = {"otp": otp, "expires": expires}

        # Gửi email
        sender = os.getenv("EMAIL_FROM")
        password = os.getenv("EMAIL_PASSWORD")

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Mã OTP khôi phục mật khẩu"
        msg["From"] = sender
        msg["To"] = email

        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto;">
            <h2 style="color: red;">Khôi phục mật khẩu</h2>
            <p>OTP của bạn là:</p>
            <div style="font-size: 24px; font-weight: bold;">{otp}</div>
            <p>Hết hạn sau 5 phút.</p>
        </div>
        """
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, email, msg.as_string())

        return jsonify({"message": "OTP đã gửi qua email"}), 200

    except Exception as e:
        print("Forgot password error:", e)
        return jsonify({"error": "Server error"}), 500

    finally:
        cur.close()
        release_connection(conn)


def verify_otp():
    data = request.get_json()
    email = data.get("email")
    otp = data.get("otp")

    entry = otp_map.get(email)
    if not entry:
        return jsonify({"error": "OTP không tồn tại"}), 400
    if entry["otp"] != otp:
        return jsonify({"error": "Sai mã OTP"}), 400
    if datetime.utcnow() > entry["expires"]:
        return jsonify({"error": "Mã OTP hết hạn"}), 400

    return jsonify({"message": "OTP hợp lệ"}), 200


def reset_password():
    data = request.get_json()
    email = data.get("email")
    new_password = data.get("newPassword")

    if not email or not new_password:
        return jsonify({"error": "Thiếu email hoặc mật khẩu"}), 400
    if not PASSWORD_REGEX.match(new_password):
        return jsonify({"error": "Mật khẩu phải ≥ 8 ký tự và chứa ký tự đặc biệt"}), 400

    # Hash mật khẩu và decode sang UTF-8
    hashed_password = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode('utf-8')

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE users SET password = %s WHERE email = %s", (hashed_password, email))
        conn.commit()
        otp_map.pop(email, None)
        return jsonify({"message": "Đổi mật khẩu thành công"}), 200

    except Exception as e:
        print("Reset password error:", e)
        return jsonify({"error": "Server error"}), 500

    finally:
        cur.close()
        release_connection(conn)



def change_password():
    data = request.get_json()
    current_password = data.get("currentPassword")
    new_password = data.get("newPassword")
    confirm_password = data.get("confirmPassword")
    user_id = g.user["id"]  # Middleware gán vào request

    if not all([current_password, new_password, confirm_password]):
        return jsonify({"error": "Vui lòng điền đầy đủ thông tin"}), 400
    if new_password != confirm_password:
        return jsonify({"error": "Mật khẩu xác nhận không khớp"}), 400
    if not PASSWORD_REGEX.match(new_password):
        return jsonify({"error": "Mật khẩu mới phải ≥ 8 ký tự và có ký tự đặc biệt"}), 400

    conn = get_connection()
    if not conn:
        return jsonify({"error": "Không thể kết nối đến cơ sở dữ liệu"}), 500
    cur = conn.cursor()
    try:
        cur.execute("SELECT password FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()
        if not user:
            return jsonify({"error": "Người dùng không tồn tại"}), 404

        if not bcrypt.checkpw(current_password.encode(), user[0].encode()):
            return jsonify({"error": "Mật khẩu hiện tại không đúng"}), 401

        new_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode('utf-8')
        print("New password hash:", new_hash)
        cur.execute("UPDATE users SET password = %s WHERE id = %s", (new_hash, user_id))
        conn.commit()

        return jsonify({"message": "Đổi mật khẩu thành công"}), 200

    except Exception as e:
        print("changePassword error:", e)
        return jsonify({"error": "Lỗi hệ thống"}), 500

    finally:
        cur.close()
        release_connection(conn)
