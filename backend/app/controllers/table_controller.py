from flask import jsonify, request
from db import get_connection, release_connection
from psycopg2.extras import RealDictCursor

def get_table_list():
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT db_name, schema_name, table_name, scd_type,
                   to_char(data_date::DATE, 'YYYY-MM-DD') AS data_date
            FROM table_list
            ORDER BY data_date DESC
        """)
        result = cur.fetchall()
        cur.close()
        release_connection(conn)
        return jsonify(result)
    except Exception as e:
        print("Error fetching table list:", e)
        return jsonify({'error': 'Internal server error'}), 500


def get_table_size():
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT database, schema_name, table_name, records, size_mb,
                   to_char(data_date::DATE, 'YYYY-MM-DD') AS data_date
            FROM table_size
            ORDER BY data_date DESC
        """)
        result = cur.fetchall()
        cur.close()
        release_connection(conn)
        return jsonify(result)
    except Exception as e:
        print("Error fetching table size:", e)
        return jsonify({'error': 'Internal server error'}), 500


def get_table_etl_log():
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT database_name, schema_name, table_name, cnt_row, process_second, update_time,
                   to_char(data_date::DATE, 'YYYY-MM-DD') AS data_date
            FROM table_etl_log
            ORDER BY data_date DESC
        """)
        result = cur.fetchall()
        cur.close()
        release_connection(conn)
        return jsonify(result)
    except Exception as e:
        print("Error fetching table etl log:", e)
        return jsonify({'error': 'Internal server error'}), 500


def get_table_size_by_name(table_name):
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT data_date, size_mb
            FROM table_size
            WHERE table_name = %s
            ORDER BY data_date DESC
        """, (table_name,))
        result = cur.fetchall()
        cur.close()
        release_connection(conn)
        return jsonify(result)
    except Exception as e:
        print("Error fetching size by table:", e)
        return jsonify({'error': 'Internal server error'}), 500
