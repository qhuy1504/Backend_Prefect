from flask import request, jsonify
from db import get_connection, release_connection
from utils.cloudinary import cloudinary
from io import BytesIO
import bcrypt
import re

# Regex kiểm tra đầu vào
username_regex = re.compile(r"^[a-zA-Z0-9_]+$")
password_regex = re.compile(r"^(?=.*[!@#$%^&*()_+{}\[\]:;<>,.?~\\/-]).{8,}$")
name_regex = re.compile(r"^[A-Za-zÀ-Ỹà-ỹĂăÂâÊêÔôƠơƯưĐđ\s]+$")
email_regex = re.compile(r"^[a-zA-Z0-9._%+-]+@gmail\.com$")


def create_user(file=None):
    try:
        data = request.form


        username = data.get("username")
        name = data.get("name")
        password = data.get("password")
        email = data.get("email")

        if not all([username, name, password, email]):
            return jsonify({"error": "Username, name, password và email là bắt buộc."}), 400

        if not username_regex.match(username):
            return jsonify({"error": "Username không hợp lệ. Không được chứa ký tự đặc biệt hoặc khoảng trắng."}), 400
        if not password_regex.match(password):
            return jsonify({"error": "Mật khẩu phải từ 8 ký tự trở lên và chứa ít nhất 1 ký tự đặc biệt."}), 400
        if not name_regex.match(name):
            return jsonify({"error": "Tên chỉ được chứa chữ cái."}), 400
        if not email_regex.match(email):
            return jsonify({"error": "Email không hợp lệ. Chỉ chấp nhận email đuôi @gmail.com."}), 400

        conn = get_connection()
        cur = conn.cursor()

        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            return jsonify({"error": "Email đã được sử dụng."}), 400

        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        if cur.fetchone():
            return jsonify({"error": "Username đã tồn tại."}), 400

        hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        avatar_url = ""
        if file:
            file_buffer = BytesIO(file.read())
            result = cloudinary.uploader.upload(file_buffer, folder="avatars")
            avatar_url = result.get("secure_url", "")

        cur.execute(
            "INSERT INTO users (username, name, password, avatar, email) VALUES (%s, %s, %s, %s, %s) RETURNING *",
            (username, name, hashed_password, avatar_url, email)
        )
        user = cur.fetchone()
        conn.commit()
        cur.close()
        release_connection(conn)

        return jsonify({
            "id": user[0],
            "username": user[1],
            "name": user[2],
            "avatar": user[3],
            "email": user[4]
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
def list_users():
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("SELECT id, username, name, email, avatar FROM users order by id asc")
        rows = cur.fetchall()
        users = [
            {
                "id": row[0],
                "username": row[1],
                "name": row[2],
                "email": row[3],
                "avatar": row[4],
            }
            for row in rows
        ]
        return jsonify(users)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        release_connection(conn)
        
def delete_user(user_id):
    conn = get_connection()
    cur = conn.cursor()

    try:
        conn.autocommit = False  # Bắt đầu transaction

        # Xoá liên kết trong bảng user_groups trước
        cur.execute("DELETE FROM user_groups WHERE user_id = %s", (user_id,))

        # Sau đó xoá user
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))

        conn.commit()
        return jsonify({"message": "User deleted"}), 200

    except Exception as e:
        conn.rollback()
        print("Delete user error:", e)
        return jsonify({"error": "Xóa user thất bại."}), 500

    finally:
        cur.close()
        release_connection(conn)

def get_user_by_id(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT id, username, name FROM users WHERE id = %s', (user_id,))
    row = cur.fetchone()
    cur.close()

    if row is None:
        return jsonify({'error': 'User not found'}), 404

    user = {
        'id': row[0],
        'username': row[1],
        'name': row[2]
    }
    return jsonify(user)     

def update_user(user_id, file):
    conn = get_connection()
    cur = conn.cursor()
    # print("Received file:", file)

    body = request.form


    fields = []
    values = []
    index = 1

    name = body.get('name')
    email = body.get('email')
    
     # Validate name nếu có
    if name is not None:
        if name.strip() == "":
            return jsonify({"error": "Tên không được để trống."}), 400
        if not name_regex.match(name):
            return jsonify({"error": "Tên không hợp lệ. Chỉ được chứa chữ cái."}), 400
        fields.append("name = %s")
        values.append(name)

    # Validate email nếu có
    if email is not None:
        if email.strip() == "":
            return jsonify({"error": "Email không được để trống."}), 400
        if not email_regex.match(email):
            return jsonify({"error": "Email không hợp lệ. Chỉ chấp nhận email @gmail.com"}), 400
        fields.append("email = %s")
        values.append(email)


    # Upload avatar nếu có
    if file:
        try:
            # Cloudinary upload
            result = cloudinary.uploader.upload(file, folder="avatars")
            avatar_url = result.get('secure_url')
            fields.append(f"avatar = %s")
            values.append(avatar_url)
        except Exception as e:
            return jsonify({"error": "Lỗi khi upload avatar"}), 500

    # Nếu không có trường nào cần cập nhật
    if not fields:
        return jsonify({"error": "Không có trường nào được cung cấp để cập nhật."}), 400

    values.append(user_id)
    query = f"""
        UPDATE users
        SET {', '.join(fields)}
        WHERE id = %s
        RETURNING id, name, email, avatar
    """

    try:
        cur.execute(query, values)
        user = cur.fetchone()
        conn.commit()
        cur.close()
        release_connection(conn)

        if user:
            return jsonify({
                "id": user[0],
                "name": user[1],
                "email": user[2],
                "avatar": user[3]
            }), 200
        else:
            return jsonify({"error": "Không tìm thấy user"}), 404
    except Exception as e:
        conn.rollback()
        cur.close()
        release_connection(conn)
        return jsonify({"error": str(e)}), 500   
def create_group():
    try:
        data = request.get_json()
        name = data.get('name')

        if not name or not name_regex.match(name):
            return jsonify({'error': 'Tên nhóm không hợp lệ'}), 400

        conn = get_connection()
        cur = conn.cursor()
        cur.execute('INSERT INTO groups (name) VALUES (%s) RETURNING *', (name,))
        new_group = cur.fetchone()
        conn.commit()
        cur.close()
        release_connection(conn)

        return jsonify({
            'id': new_group[0],
            'name': new_group[1]
        }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500
def list_groups():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM groups")
        rows = cursor.fetchall()

        # Chuyển dữ liệu thành dict nếu cần
        group_list = []
        columns = [desc[0] for desc in cursor.description]
        for row in rows:
            group_list.append(dict(zip(columns, row)))

        cursor.close()
        release_connection(conn)
        return jsonify(group_list), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
def delete_group(group_id):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute('DELETE FROM groups WHERE id = %s', (group_id,))
        conn.commit()
        cur.close()
        release_connection(conn)
        return jsonify({"message": "Group deleted"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
def update_group(id):
    data = request.get_json()
    name = data.get("name")

    if not name:
        return jsonify({"error": "Name is required"}), 400

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("UPDATE groups SET name = %s WHERE id = %s RETURNING *", (name, id))
        row = cursor.fetchone()
        conn.commit()

        if row is None:
            return jsonify({"error": "Group not found"}), 404

        # Bạn có thể sửa lại tùy cấu trúc cột group trong bảng
        group = {
            "id": row[0],
            "name": row[1]
        }

        return jsonify(group)
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        release_connection(conn)

def create_role():
    data = request.get_json()
    name = data.get("name")

    if not name:
        return jsonify({"error": "Name is required"}), 400

    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO roles (name) VALUES (%s) RETURNING *", (name,))
        new_role = cur.fetchone()
        conn.commit()
        cur.close()
        release_connection(conn)
        return jsonify(new_role), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Get all roles
def list_roles():
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM roles")
        rows = cur.fetchall()
        cur.close()
        release_connection(conn)
        roles = [{"id": row[0], "name": row[1]} for row in rows]
        return jsonify(roles)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Delete a role
def delete_role(role_id):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM roles WHERE id = %s", (role_id,))
        conn.commit()
        cur.close()
        release_connection
        return jsonify({"message": "Role deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Update role
def update_role(role_id):
    data = request.get_json()
    name = data.get("name")

    if not name:
        return jsonify({"error": "Name is required"}), 400

    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE roles SET name = %s WHERE id = %s RETURNING *", (name, role_id))
        updated = cur.fetchone()
        conn.commit()
        cur.close()
        release_connection(conn)

        if updated:
            return jsonify(updated)
        else:
            return jsonify({"error": "Role not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
def create_menu():
    data = request.get_json()
    name = data.get('name')
    path = data.get('path')

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO menus (name, path) VALUES (%s, %s) RETURNING *", (name, path))
    new_menu = cursor.fetchone()
    conn.commit()
    cursor.close()
    release_connection(conn)

    return jsonify({
        "id": new_menu[0],
        "name": new_menu[1],
        "path": new_menu[2]
    })


def list_menus():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM menus")
    rows = cursor.fetchall()
    cursor.close()
    release_connection(conn)

    menus = [{"id": row[0], "name": row[1], "path": row[2]} for row in rows]
    return jsonify(menus)


def delete_menu(id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM menus WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    release_connection(conn)
    return jsonify({"message": "Menu deleted"})


def update_menu(id):
    data = request.get_json()
    allowed_fields = ['name', 'path']
    fields = []
    values = []

    for key in allowed_fields:
        if key in data:
            fields.append(f"{key} = %s")
            values.append(data[key])

    if not fields:
        return jsonify({"error": "No fields provided for update"}), 400

    values.append(id)

    query = f"UPDATE menus SET {', '.join(fields)} WHERE id = %s RETURNING *"

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(query, values)
    updated = cursor.fetchone()
    conn.commit()
    cursor.close()
    release_connection(conn)

    if not updated:
        return jsonify({"error": "Menu not found"}), 404

    return jsonify({
        "id": updated[0],
        "name": updated[1],
        "path": updated[2]
    })
def remove_user_from_group():
    data = request.get_json()
    user_id = data.get("user_id")
    group_id = data.get("group_id")

    if not user_id or not group_id:
        return jsonify({"error": "Missing user_id or group_id"}), 400

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM user_groups WHERE user_id = %s AND group_id = %s",
            (user_id, group_id)
        )
        conn.commit()
        cursor.close()
        release_connection(conn)
        return jsonify({"message": "User removed from group"})
    except Exception as e:
        print("Error removing user from group:", e)
        return jsonify({"error": "Internal Server Error"}), 500


def remove_role_from_group():
    data = request.get_json()
    group_id = data.get("group_id")

    if not group_id:
        return jsonify({"error": "Missing group_id"}), 400

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM group_roles WHERE group_id = %s",
            (group_id,)
        )
        conn.commit()
        cursor.close()
        release_connection(conn)
        return jsonify({"message": "Role removed from group"})
    except Exception as e:
        print("Error removing role from group:", e)
        return jsonify({"error": "Internal Server Error"}), 500


def remove_menu_from_role(role_id):
    data = request.get_json()
    role_id = data.get("role_id")

    if not role_id:
        return jsonify({"error": "Missing role_id"}), 400

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM role_menus WHERE role_id = %s",
            (role_id,)
        )
        conn.commit()
        cursor.close()
        release_connection(conn)
        return jsonify({"message": "Menus removed from role"})
    except Exception as e:
        print("Error removing menus from role:", e)
        return jsonify({"error": "Internal Server Error"}), 500
def update_menus_of_role(role_id):
    data = request.get_json()
    menu_ids = data.get("menuIds")
    print("Received menuIds:", menu_ids, type(menu_ids))

    if not role_id or not isinstance(menu_ids, list):
        return jsonify({"error": "Thiếu role ID hoặc menuIds không hợp lệ"}), 400

    conn = get_connection()
    cursor = conn.cursor()

    try:
        conn.autocommit = False

        # Lấy các menu hiện tại
        cursor.execute("SELECT menu_id FROM role_menus WHERE role_id = %s", (role_id,))
        current_menus = cursor.fetchall()
        current_menu_ids = [menu[0] for menu in current_menus]

        # Xác định menu cần thêm và xóa
        menus_to_add = [mid for mid in menu_ids if mid not in current_menu_ids]
        menus_to_remove = [mid for mid in current_menu_ids if mid not in menu_ids]

        # Thêm mới
        for menu_id in menus_to_add:
            cursor.execute(
                "INSERT INTO role_menus (role_id, menu_id) VALUES (%s, %s)",
                (role_id, menu_id)
            )

        # Xóa bớt
        for menu_id in menus_to_remove:
            cursor.execute(
                "DELETE FROM role_menus WHERE role_id = %s AND menu_id = %s",
                (role_id, menu_id)
            )

        conn.commit()

        return jsonify({
            "success": True,
            "added": menus_to_add,
            "removed": menus_to_remove,
            "message": "Cập nhật menu cho role thành công"
        })

    except Exception as e:
        conn.rollback()
        print("Lỗi cập nhật menu:", e)
        return jsonify({"error": "Lỗi máy chủ khi cập nhật menu"}), 500

    finally:
        cursor.close()
        release_connection(conn)
def assign_groups_to_user(user_id):
    data = request.get_json()
    group_ids = data.get("groupIds")

    if not isinstance(group_ids, list):
        return jsonify({"error": "groupIds phải là danh sách"}), 400

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM user_groups WHERE user_id = %s", (user_id,))

        for group_id in group_ids:
            cursor.execute(
                "INSERT INTO user_groups (user_id, group_id) VALUES (%s, %s)",
                (user_id, group_id)
            )

        conn.commit()
        return jsonify({"success": True})

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        release_connection(conn)


def assign_roles_to_group(group_id):
    data = request.get_json()
    role_ids = [int(rid) for rid in data.get("roleIds", [])]

    if not group_id or not isinstance(role_ids, list):
        return jsonify({"error": "Thiếu group ID hoặc role IDs không hợp lệ"}), 400

    conn = get_connection()
    cursor = conn.cursor()

    try:
        check_query = """
            SELECT roles.id, roles.name
            FROM group_roles
            JOIN roles ON group_roles.role_id = roles.id
            WHERE group_roles.group_id = %s AND group_roles.role_id = ANY(%s)
        """
        cursor.execute(check_query, (group_id, role_ids))
        existing_roles = cursor.fetchall()

        if existing_roles:
            role_names = [row[1] for row in existing_roles]
            return jsonify({
                "error": f"Các vai trò đã tồn tại trong nhóm: {', '.join(role_names)}"
            }), 400

        for role_id in role_ids:
            cursor.execute(
                "INSERT INTO group_roles (group_id, role_id) VALUES (%s, %s)",
                (group_id, role_id)
            )

        conn.commit()
        return jsonify({
            "success": True,
            "message": f"{len(role_ids)} role(s) assigned successfully."
        })

    except Exception as e:
        conn.rollback()
        print("Lỗi khi gán role:", e)
        return jsonify({"error": "Internal Server Error"}), 500

    finally:
        cursor.close()
        release_connection(conn)


def get_role_menus():
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT 
                r.id AS role_id,
                r.name AS role_name,
                ARRAY_AGG(DISTINCT m.name) AS menus
            FROM role_menus rm
            JOIN roles r ON r.id = rm.role_id
            JOIN menus m ON m.id = rm.menu_id
            GROUP BY r.id, r.name
        """)
        result = cursor.fetchall()

        # Format kết quả thành danh sách từ tuple
        data = [{
            "role_id": row[0],
            "role_name": row[1],
            "menus": row[2]
        } for row in result]

        return jsonify(data)

    except Exception as e:
        print("Lỗi khi lấy danh sách menu theo role:", e)
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        release_connection(conn)
def assign_menus_to_role(role_id):
    data = request.get_json()
    menu_ids = data.get("menuIds")

    if not role_id or not isinstance(menu_ids, list):
        return jsonify({"error": "Thiếu role ID hoặc menuIds không hợp lệ"}), 400

    conn = get_connection()
    cursor = conn.cursor()

    try:
        check_query = """
            SELECT menus.id, menus.name
            FROM role_menus
            JOIN menus ON role_menus.menu_id = menus.id
            WHERE role_menus.role_id = %s AND role_menus.menu_id = ANY(%s)
        """
        cursor.execute(check_query, (role_id, menu_ids))
        existing = cursor.fetchall()

        if existing:
            existing_names = [row[1] for row in existing]
            return jsonify({
                "error": f"Các menu đã tồn tại trong role: {', '.join(existing_names)}"
            }), 400

        for menu_id in menu_ids:
            cursor.execute(
                "INSERT INTO role_menus (role_id, menu_id) VALUES (%s, %s)",
                (role_id, menu_id)
            )

        conn.commit()
        return jsonify({
            "success": True,
            "message": f"{len(menu_ids)} menu(s) đã được gán thành công.",
        })

    except Exception as e:
        conn.rollback()
        print("Lỗi khi gán menu cho role:", e)
        return jsonify({"error": "Lỗi máy chủ nội bộ"}), 500

    finally:
        cursor.close()
        release_connection(conn)


def get_users_with_groups():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT 
                ug.user_id,
                u.username,
                u.name,
                g.id AS group_id,
                g.name AS group_name
            FROM user_groups ug
            JOIN users u ON u.id = ug.user_id
            JOIN groups g ON g.id = ug.group_id
            ORDER BY g.name, u.username;
        """)
        result = cursor.fetchall()
        data = [
            {
                "user_id": row[0],
                "username": row[1],
                "name": row[2],
                "group_id": row[3],
                "group_name": row[4]
            }
            for row in result
        ]
        return jsonify(data)
    except Exception as e:
        print("Lỗi get_users_with_groups:", e)
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        release_connection(conn)


def get_roles_with_groups():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT 
                g.id AS group_id,
                g.name AS group_name,
                ARRAY_AGG(r.name) AS roles
            FROM group_roles gr
            JOIN groups g ON g.id = gr.group_id
            JOIN roles r ON r.id = gr.role_id
            GROUP BY g.id, g.name;
        """)
        result = cursor.fetchall()
        data = [
            {
                "group_id": row[0],
                "group_name": row[1],
                "roles": row[2]
            }
            for row in result
        ]
        return jsonify(data)
    except Exception as e:
        print("Lỗi get_roles_with_groups:", e)
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        release_connection(conn)
def get_roles_of_group_with_group_id(group_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT roles.id, roles.name
            FROM group_roles
            JOIN roles ON group_roles.role_id = roles.id
            WHERE group_roles.group_id = %s
        """, (group_id,))
        rows = cursor.fetchall()
        roles = [{"id": row[0], "name": row[1]} for row in rows]
        return jsonify({"roles": roles})
    except Exception as e:
        print("Error fetching group roles:", e)
        return jsonify({"error": "Internal Server Error"}), 500
    finally:
        cursor.close()
        release_connection(conn)


def update_roles_of_group(group_id):
    data = request.get_json()
    role_ids = data.get("roleIds")

    if not group_id or not isinstance(role_ids, list):
        return jsonify({"error": "Thiếu group ID hoặc roleIds không hợp lệ"}), 400

    conn = get_connection()
    cursor = conn.cursor()

    try:
        conn.autocommit = False

        cursor.execute(
            "SELECT role_id FROM group_roles WHERE group_id = %s",
            (group_id,)
        )
        current_roles = cursor.fetchall()
        current_role_ids = [r[0] for r in current_roles]
        role_ids_number = [int(rid) for rid in role_ids]

        roles_to_add = [rid for rid in role_ids_number if rid not in current_role_ids]
        roles_to_remove = [rid for rid in current_role_ids if rid not in role_ids_number]

        for role_id in roles_to_add:
            cursor.execute(
                "INSERT INTO group_roles (group_id, role_id) VALUES (%s, %s)",
                (group_id, role_id)
            )

        for role_id in roles_to_remove:
            cursor.execute(
                "DELETE FROM group_roles WHERE group_id = %s AND role_id = %s",
                (group_id, role_id)
            )

        conn.commit()

        return jsonify({
            "success": True,
            "added": roles_to_add,
            "removed": roles_to_remove,
            "message": "Cập nhật vai trò thành công"
        })

    except Exception as e:
        conn.rollback()
        print("Lỗi khi cập nhật vai trò:", e)
        return jsonify({"error": "Lỗi máy chủ khi cập nhật vai trò"}), 500
    finally:
        cursor.close()
        release_connection(conn)