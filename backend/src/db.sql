
DROP TABLE IF EXISTS logs;
DROP TABLE IF EXISTS job_task;
DROP TABLE IF EXISTS tasks;
DROP TABLE IF EXISTS jobs;

CREATE TABLE jobs
(
  id SERIAL PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'pending',
  concurrent INTEGER NOT NULL DEFAULT 1 CHECK (concurrent > 0),
  flow_run_id VARCHAR(255) UNIQUE,
  created_at TIMESTAMP
  WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
  WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

  CREATE TABLE tasks
  (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    script_type VARCHAR(20) NOT NULL CHECK(script_type IN ('sql', 'python')),
    script_content TEXT NOT NULL,
    created_at TIMESTAMP
    WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
    WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

    CREATE TABLE job_task
    (
      id SERIAL PRIMARY KEY,
      job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
      task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
      execution_order INTEGER NOT NULL,
      status VARCHAR(20) NOT NULL DEFAULT 'pending',
      parameters JSONB,
      created_at TIMESTAMP
      WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE
      (job_id, execution_order),
    UNIQUE
      (job_id, task_id, execution_order) -- Ràng buộc mạnh hơn
);


      CREATE TABLE job_task_logs
      (
        id SERIAL PRIMARY KEY,
        job_id INTEGER NOT NULL,
        job_task_id UUID,
        -- log.task_run_id
        task_name TEXT,
        task_status TEXT,
        -- pending | running | completed | failed
        flow_run_id UUID,
        task_run_id UUID,
        logger TEXT,
        -- log.name (e.g. prefect.task_runs)
        log_level TEXT,
        -- DEBUG | INFO | WARNING | ERROR
        log TEXT,
        log_timestamp TIMESTAMP,
        -- log.timestamp
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      );

      CREATE INDEX idx_job_task_logs_job_id ON job_task_logs(job_id);
      CREATE INDEX idx_job_task_logs_flow_run_id ON job_task_logs(flow_run_id);

      CREATE TYPE schedule_type_enum AS ENUM
      ('interval', 'cron');
      CREATE TYPE schedule_unit_enum AS ENUM
      ('minutes', 'hours', 'days');


      ALTER TABLE jobs
ADD COLUMN schedule_type schedule_type_enum,
      ADD COLUMN schedule_value VARCHAR
      (100),
      ADD COLUMN schedule_unit schedule_unit_enum;

      ALTER TABLE jobs ADD COLUMN deployment_id UUID;


      ALTER TABLE job_task_logs
ADD COLUMN log_id UUID;

      ALTER TABLE job_task_logs
ADD CONSTRAINT uq_job_log UNIQUE (job_id, log_id, log);


      CREATE TABLE table_list
      (
        db_name TEXT,
        schema_name TEXT,
        table_name TEXT,
        scd_type TEXT,
        data_date DATE
      );


      CREATE TABLE table_etl_log
      (
        database_name TEXT,
        schema_name TEXT,
        table_name TEXT,
        data_date DATE,
        cnt_row INTEGER,
        update_time TEXT,
        process_second INTEGER
      );


      CREATE TABLE table_size (
    database TEXT,
    schema_name TEXT,
    table_name TEXT,
    records BIGINT,
    size_mb INTEGER,
    data_date DATE
);



      CREATE TABLE users
      (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        name TEXT,
        avatar TEXT,
        email TEXT UNIQUE NOT NULL
      );


      CREATE TABLE roles
      (
        id SERIAL PRIMARY KEY,
        name TEXT UNIQUE NOT NULL
      );


      CREATE TABLE groups
      (
        id SERIAL PRIMARY KEY,
        name TEXT UNIQUE NOT NULL
      );


      CREATE TABLE menus
      (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        path TEXT NOT NULL
      );


      CREATE TABLE user_groups
      (
        user_id INT REFERENCES users(id),
        group_id INT REFERENCES groups(id),
        PRIMARY KEY (user_id, group_id)
      );

      CREATE TABLE group_roles
      (
        group_id INT REFERENCES groups(id),
        role_id INT REFERENCES roles(id),
        PRIMARY KEY (group_id, role_id)
      );


      CREATE TABLE role_menus
      (
        role_id INT REFERENCES roles(id),
        menu_id INT REFERENCES menus(id),
        PRIMARY KEY (role_id, menu_id)
      );


      INSERT INTO roles
        (name)
      VALUES
        ('admin'),
        ('user');
      INSERT INTO groups
        (name)
      VALUES
        ('dev'),
        ('manager');

      INSERT INTO groups
        (name)
      VALUES
        ('Phòng CNTT'),
        ('Phòng Kế toán'),
        ('Phòng Giao dịch'),
        ('Phòng Kiểm toán nội bộ'),
        ('Phòng Chăm sóc khách hàng');

      INSERT INTO menus
        (name, path)
      VALUES
        ('Dashboard', '/dashboard'),
        ('Quản lý Job', '/jobs/new'),
        ('Danh sách Job', '/jobs'),
        ('Danh sách Bảng', '/tablelist'),
        ('Profile', '/profile'),
        ('Import data', '/import-data'),
        ('Assign', '/assign-group');
      select *
      from users
      select *
      from role_menus

