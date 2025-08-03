from flask import request, jsonify
from db import get_connection, release_connection
import pandas as pd
import cloudinary.uploader
import io
import re
import psycopg2

def handle_import_file(req, file):
    try:
       
        table_name = req.form.get('tableName')
        overwrite = req.form.get('overwrite', 'false').lower()
        print(f"file: {file}")
        print(f"table_name: {table_name}")

        if not file or not table_name:
            return jsonify({"error": "Thiếu file hoặc tên bảng"}), 400

        table_regex = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
        if not table_regex.match(table_name):
            return jsonify({"error": "Tên bảng không hợp lệ."}), 400

        file_buffer = file.read()
        file_name = file.filename

        # Upload lên Cloudinary
        upload_result = cloudinary.uploader.upload(
            io.BytesIO(file_buffer),
            resource_type="raw",
            public_id=f"uploads/{int(__import__('time').time())}_{file_name}"
        )

        file_url = upload_result.get("secure_url")
        if not file_url:
            return jsonify({"error": "Upload Cloudinary thất bại"}), 500

        # Đọc file vào DataFrame
        if file_name.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(file_buffer))
        elif file_name.endswith(".xlsx"):
            df = pd.read_excel(io.BytesIO(file_buffer))
        else:
            return jsonify({"error": "Chỉ hỗ trợ .csv và .xlsx"}), 400

        if df.empty:
            return jsonify({"url": file_url, "data": []}), 200

        print(f"Data to save: {len(df)} rows")

        columns = df.columns.tolist()
        conn = get_connection()
        cur = conn.cursor()

        # Kiểm tra bảng tồn tại
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = %s
            )
        """, (table_name.lower(),))
        exists = cur.fetchone()[0]

        if exists:
            if overwrite == "true":
                cur.execute(f'DROP TABLE IF EXISTS "{table_name}"')
            else:
                return jsonify({"error": "Bảng đã tồn tại."}), 409

        # Tạo bảng mới
        col_defs = ", ".join([f'"{col}" TEXT' for col in columns])
        cur.execute(f'CREATE TABLE "{table_name}" ({col_defs})')

        # Chèn dữ liệu theo batch
        batch_size = 5000
        for i in range(0, len(df), batch_size):
            batch_df = df.iloc[i:i+batch_size]
            values = batch_df.where(pd.notnull(batch_df), None).values.tolist()

            args_str = ','.join(
                cur.mogrify(f"({','.join(['%s'] * len(columns))})", tuple(row)).decode('utf-8')
                for row in values
            )

            # Sửa f-string tại đây: tạo column list trước
            column_list = ','.join([f'"{c}"' for c in columns])
            insert_query = f'INSERT INTO "{table_name}" ({column_list}) VALUES {args_str}'

            cur.execute(insert_query)

        conn.commit()
        return jsonify({
            "message": "Lưu thành công",
            "url": file_url,
            "data": df.head(10).to_dict(orient="records")
        }), 200

    except Exception as e:
        print("Import error:", e)
        return jsonify({"error": "Lỗi hệ thống"}), 500

    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            release_connection(conn)
