from psycopg2 import pool
import sys

try:
    connection_pool = pool.SimpleConnectionPool(
        1, 20,  # minconn, maxconn
        user='postgres',
        password='123456',
        host='postgres',  # Nếu bạn dùng Docker, thì thay 'localhost' bằng 'postgres'
        port='5432',
        database='postgres'
    )

    if connection_pool:
        print("PostgreSQL connection pool created successfully")

except Exception as e:
    print(f"Error creating connection pool: {e}")
    sys.exit(1)


def get_connection():
    try:
        if connection_pool:
            return connection_pool.getconn()
        else:
            print("Connection pool is not initialized.")
            return None
    except Exception as e:
        print(f"Error getting connection: {e}")
        return None



def release_connection(conn):
    try:
        if conn:
            connection_pool.putconn(conn)
    except Exception as e:
        print(f"Error releasing connection: {e}")


def close_all_connections():
    try:
        connection_pool.closeall()
        print("All connections closed")
    except Exception as e:
        print(f"Error closing connections: {e}")
