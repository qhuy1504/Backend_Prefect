import pool from '../db.js';
import crypto from 'crypto';
import { triggerPrefectFlow, upsertConcurrencyLimitForTag, upsertVariable } from '../services/prefectService.js';
import axios from 'axios';
import dotenv from 'dotenv';
dotenv.config();

const PREFECT_API_URL = process.env.PREFECT_API_URL;
console.log(`Using Prefect API URL trong jobcontroller: ${PREFECT_API_URL}`);

// Tạo 1 job mới với nhiều task
export const createJobWithTasks = async (req, res) => {
    const { name, concurrent, tasks, schedule } = req.body;
    const schedule_type = schedule?.type ?? null;          // 'interval' | 'cron' | null
    const schedule_value = schedule?.value ?? null;         // số hoặc chuỗi cron
    const schedule_unit = schedule?.unit ?? null;         // 'minutes','hours',...  (chỉ khi type='interval')



    // Kiểm tra dữ liệu đầu vào.
    if (!name) {
        return res.status(400).json({ error: 'Invalid input: "name" is a required field.' });
    }


    // 2. Sử dụng một client từ pool để quản lý transaction.
    const client = await pool.connect();

    try {
        // === BƯỚC KIỂM TRA MỚI ===
        // 1. Kiểm tra xem job với tên này đã tồn tại chưa
        const existingJobQuery = 'SELECT id, name FROM jobs WHERE name = $1';

        const existingJobResult = await client.query(existingJobQuery, [name]);

        // 2. Nếu job đã tồn tại, trả về lỗi 409 Conflict
        if (existingJobResult.rows.length > 0) {
            return res.status(409).json({
                message: `Job with name "${name}" already exists.`,
                // Trả về cả ID của job đã có để frontend có thể sử dụng
                existing_job_id: existingJobResult.rows[0].id,
                error_code: 'JOB_NAME_EXISTS' // Một mã lỗi tùy chỉnh
            });
        }



        // 3. Bắt đầu transaction.
        await client.query('BEGIN');

        // 4. Tạo record chính trong bảng `jobs` và lấy về `id`.
        const jobQuery = `
INSERT INTO jobs (name, concurrent, schedule_type, schedule_value, schedule_unit)
VALUES ($1, $2, $3, $4, $5)
RETURNING id
`;
        const jobResult = await client.query(jobQuery, [
            name,
            concurrent,
            schedule_type,
            schedule_value ? schedule_value.toString() : null, // toString phòng khi là số
            schedule_unit
        ]);

        const jobId = jobResult.rows[0].id;


        // 5. Lặp qua các task trong request để tạo liên kết.
        for (let i = 0; i < tasks.length; i++) {
            const task = tasks[i];

            // 5a. UPSERT một record trong bảng `tasks` (thư viện template).
            // Câu lệnh này sẽ:
            // - INSERT một task mới nếu chưa có task nào trùng tên.
            // - Nếu có task trùng tên (ON CONFLICT), nó sẽ không làm gì (DO NOTHING) và vẫn trả về `id` của task đã tồn tại.
            //   (Chúng ta cũng có thể dùng DO UPDATE nếu muốn cập nhật script_content của template).
            const taskUpsertQuery = `
INSERT INTO tasks (name, script_type, script_content)
VALUES ($1, $2, $3)
ON CONFLICT (name) DO NOTHING
RETURNING id;
`;
            let taskResult = await client.query(taskUpsertQuery, [task.name, task.script_type, task.script_content]);

            // Nếu INSERT bị skip do conflict, query trên sẽ không trả về row nào.
            // Ta cần chạy một câu SELECT để lấy id của task đã có.
            if (taskResult.rows.length === 0) {
                taskResult = await client.query('SELECT id FROM tasks WHERE name = $1', [task.name]);
            }
            const taskId = taskResult.rows[0].id;

            // 5b. Tạo record liên kết trong bảng `job_task`.
            const jobTaskQuery = `
INSERT INTO job_task (job_id, task_id, execution_order, parameters)
VALUES ($1, $2, $3, $4);
`;
            // Chuyển đổi parameters thành chuỗi JSON nếu nó là object.
            const parametersAsJson = task.parameters ? JSON.stringify(task.parameters) : null;
            await client.query(jobTaskQuery, [jobId, taskId, i, parametersAsJson]);
        }

        const prefectTag = `job-${name.toLowerCase().replace(/[\s_]+/g, '-').replace(/[^a-z0-9-]/g, '')}`;

        // 2. Gọi hàm để tạo hoặc cập nhật Concurrency Limit trong Prefect.
        //    Sử dụng giá trị `concurrent` mà người dùng đã nhập.


        await upsertConcurrencyLimitForTag(prefectTag, concurrent);

        // 3. Chuẩn bị các tham số cần thiết để truyền cho flow của Prefect.
        const flowParameters = {
            jobId: jobId,
            // job_name: name,
            tasks: tasks,
            concurrent: concurrent,
            // Bạn có thể thêm bất kỳ tham số nào khác mà flow của bạn cần ở đây
        };



        // 6. Nếu mọi thứ thành công, commit transaction.
        await client.query('COMMIT');

        // 7. Trả về response thành công.
        res.status(201).json({
            message: 'Job and its tasks links created successfully!',
            jobId: jobId,
            jobName: name,
            tasksLinked: tasks.length,
            prefect: {
                tag: prefectTag,
                concurrencyLimit: concurrent,
            }
        });

    } catch (error) {
        // 8. Nếu có lỗi, rollback tất cả các thay đổi.
        await client.query('ROLLBACK');
        console.error('Error in createJobWithTasks:', error);
        res.status(500).json({ error: 'Failed to create job and tasks' });

    } finally {
        // 9. Luôn luôn giải phóng client về lại pool.
        client.release();
    }
};




// Get job with tasks

export const getJobsWithTasks = async (req, res) => {
    try {
        // Câu lệnh SQL để gom nhóm
        const query = `
SELECT
j.id,
j.name,
j.status,
j.concurrent,
j.flow_run_id,
j.created_at,
j.updated_at,
j.schedule_type,
j.schedule_value,
j.schedule_unit,
COALESCE(
-- json_agg sẽ gom tất cả các dòng kết quả thành một mảng JSON.
json_agg(
-- json_build_object tạo một đối tượng JSON cho mỗi task.
json_build_object(
    'job_task_id', jt.id,
    
    'task_id', t.id,
    'task_name', t.name,
    'status', jt.status,
    'execution_order', jt.execution_order,
    'script_type', t.script_type
    -- Lưu ý: Chúng ta không lấy script_content ở đây để response gọn nhẹ.
    -- Chỉ lấy chi tiết khi người dùng xem một job cụ thể.
)
-- Quan trọng: Sắp xếp các task trong mảng theo đúng thứ tự thực thi.
ORDER BY jt.execution_order ASC
) FILTER (WHERE t.id IS NOT NULL), 
'[]'::json
) AS tasks
FROM
jobs j
-- Dùng LEFT JOIN để đảm bảo những job chưa có task nào vẫn được trả về.
LEFT JOIN
job_task jt ON j.id = jt.job_id
LEFT JOIN
tasks t ON jt.task_id = t.id
-- Gom nhóm tất cả các dòng theo job id.
GROUP BY
j.id
-- Sắp xếp danh sách jobs, job mới nhất lên đầu.
ORDER BY
j.id DESC;
`;

        const result = await pool.query(query);

        // result.rows bây giờ đã là một mảng các đối tượng job hoàn chỉnh.
        res.json(result.rows);

    } catch (error) {
        console.error('Error fetching jobs with tasks:', error);
        res.status(500).json({ error: 'Failed to fetch jobs' });
    }
};

// Get logs for a specific job
export const getLogs = async (req, res) => {
    try {
        const { jobId } = req.params;

        const result = await pool.query(
            `SELECT * FROM logs WHERE job_id = $1 ORDER BY log_time DESC`,
            [jobId]
        );

        res.json(result.rows);
    } catch (error) {
        console.error(error);
        res.status(500).json({ error: 'Failed to fetch logs' });
    }
};
export const updateJob = async (req, res) => {
    try {
        const { id } = req.params;
        const {
            name,
            concurrent,
            schedule_type,
            schedule_value,
            schedule_unit

        } = req.body;


        const cleaned = {
            schedule_type,
            schedule_value,
            schedule_unit:
                schedule_type === 'cron' ? null : schedule_unit   // cron ⇒ unit NULL
        };

        // Câu query UPDATE
        const result = await pool.query(
            `UPDATE jobs SET 
name = $1,
concurrent = $2,
schedule_type = $3,
schedule_value = $4,
schedule_unit = $5
WHERE id = $6
RETURNING *`,
            [name, concurrent, cleaned.schedule_type, cleaned.schedule_value, cleaned.schedule_unit, id]
        );

        if (result.rows.length === 0) {
            return res.status(404).json({ error: 'Job not found' });
        }

        res.json(result.rows[0]);
    } catch (error) {
        console.error(error);
        res.status(500).json({ error: 'Failed to update job' });
    }
};

// === XÓA MỘT JOB (VÀ CÁC TASK LIÊN KẾT) ===
export const deleteJob = async (req, res) => {
    const { id: jobId } = req.params; // Lấy id từ URL

    const client = await pool.connect();
    try {
        // Bắt đầu một transaction để đảm bảo an toàn
        await client.query('BEGIN');

        // --- BƯỚC KIỂM TRA (TÙY CHỌN NHƯNG NÊN CÓ) ---
        // Lấy thông tin về job và số lượng task liên quan trước khi xóa
        const checkQuery = `
SELECT j.name, COUNT(jt.id) as task_count
FROM jobs j
LEFT JOIN job_task jt ON j.id = jt.job_id
WHERE j.id = $1
GROUP BY j.name;
`;
        const checkResult = await client.query(checkQuery, [jobId]);

        if (checkResult.rows.length === 0) {
            client.release();
            return res.status(404).json({ error: 'Job not found' });
        }

        const jobName = checkResult.rows[0].name;
        const taskCount = checkResult.rows[0].task_count;



        // --- BƯỚC XÓA ---
        // Chỉ cần xóa job. `ON DELETE CASCADE` sẽ lo phần còn lại.
        const deleteResult = await client.query('DELETE FROM jobs WHERE id = $1', [jobId]);

        // Kiểm tra lại để chắc chắn đã xóa thành công
        if (deleteResult.rowCount === 0) {
            // Trường hợp này hiếm khi xảy ra nếu logic check ở trên đã chạy
            throw new Error('Deletion failed unexpectedly.');
        }

        // Nếu mọi thứ ổn, commit transaction
        await client.query('COMMIT');



        // Trả về status 204 No Content, đây là response chuẩn cho DELETE thành công
        res.status(204).send();

    } catch (error) {
        // Nếu có lỗi, rollback transaction
        await client.query('ROLLBACK');
        console.error(`Error deleting job ${jobId}:`, error);
        res.status(500).json({ error: 'Failed to delete job' });
    } finally {
        if (client) {
            client.release();
        }
    }
};



export const streamJobLogs = async (req, res) => {
    const { id } = req.params;

    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');
    res.flushHeaders();

    const sendLog = (logData) => {
        res.write(`data: ${JSON.stringify(logData)}\n\n`);
    };

    let flowRunId = null;
    const MAX_RETRIES = 5; // Thử tối đa 5 lần
    const RETRY_DELAY = 1000; // Chờ 1 giây giữa các lần thử

    try {
        // === PHẦN SỬA LỖI RACE CONDITION ===
        for (let i = 0; i < MAX_RETRIES; i++) {
            const jobResult = await pool.query(`SELECT flow_run_id FROM job WHERE id = $1`, [id]);
            if (jobResult.rows[0]?.flow_run_id) {
                flowRunId = jobResult.rows[0].flow_run_id;
                break; // Tìm thấy flow_run_id, thoát khỏi vòng lặp
            }
            // Nếu không tìm thấy, chờ một chút rồi thử lại
            await new Promise(resolve => setTimeout(resolve, RETRY_DELAY));
        }

        if (!flowRunId) {
            throw new Error('Could not find a running flow for this job after multiple attempts.');
        }
        // === KẾT THÚC PHẦN SỬA LỖI ===

        sendLog({ message: `Connected to log stream for flow run: ${flowRunId}`, type: 'info' });

        let lastLogTimestamp = '1970-01-01T00:00:00.000000+00:00';
        let isFlowRunning = true;

        const intervalId = setInterval(async () => {
            if (!isFlowRunning) {
                clearInterval(intervalId);
                res.end();
                return;
            }
            try {
                const logs = await getFlowRunLogs(flowRunId);
                const newLogs = logs.filter(log => log.timestamp > lastLogTimestamp);

                if (newLogs.length > 0) {
                    newLogs.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
                    newLogs.forEach(log => {
                        sendLog({ message: log.message, type: 'log' });
                    });
                    lastLogTimestamp = newLogs[newLogs.length - 1].timestamp;
                }

                const flowRun = await getFlowRunState(flowRunId);
                const terminalStates = ['COMPLETED', 'FAILED', 'CANCELLED', 'CRASHED'];
                if (terminalStates.includes(flowRun.state_type)) {
                    isFlowRunning = false;
                    sendLog({ message: `Flow finished with state: ${flowRun.state_type}`, type: 'info' });
                }
            } catch (pollError) {
                sendLog({ message: `Polling error: ${pollError.message}`, type: 'error' });
                isFlowRunning = false;
            }
        }, 3000);

        req.on('close', () => {
            clearInterval(intervalId);
            res.end();
        });

    } catch (error) {
        sendLog({ message: `Error: ${error.message}`, type: 'error' });
        res.end();
    }
};

export const getTasksByJobId = async (req, res) => {
    // Lấy jobId từ URL parameters
    const { jobId } = req.params;


    try {
        // Câu query này sẽ JOIN 3 bảng để lấy thông tin đầy đủ
        // Tuy nhiên, để đơn giản, ta chỉ cần JOIN `job_task` và `tasks`
        const query = `
SELECT
t.id AS task_template_id, -- ID của task trong thư viện
t.name,
t.description,
t.script_type,
t.script_content,
jt.id AS job_task_id, -- ID của bản ghi liên kết, rất quan trọng
jt.execution_order,
jt.status AS task_status, -- Trạng thái của task trong job này
jt.parameters
FROM
job_task jt -- Bắt đầu từ bảng kết nối
JOIN
tasks t ON jt.task_id = t.id -- Nối với bảng tasks để lấy thông tin chi tiết
WHERE
jt.job_id = $1 -- Lọc theo job_id
ORDER BY
jt.execution_order ASC; -- Sắp xếp theo thứ tự thực thi
`;

        const result = await pool.query(query, [jobId]);

        // Kiểm tra xem job có tồn tại không (nếu không có task nào được trả về)
        if (result.rows.length === 0) {
            // Chạy một query phụ để phân biệt giữa "job không có task" và "job không tồn tại"
            const jobExists = await pool.query('SELECT id FROM jobs WHERE id = $1', [jobId]);
            if (jobExists.rows.length === 0) {
                return res.status(404).json({ error: 'Job not found' });
            }
        }

        res.status(200).json(result.rows);

    } catch (error) {
        console.error(`Error fetching tasks for job ${jobId}:`, error);
        res.status(500).json({ error: 'Failed to fetch tasks for the job' });
    }
};

// === THÊM MỘT TASK MỚI VÀO JOB ĐÃ CÓ ===
export const addTaskToJob = async (req, res) => {
    const { job_id } = req.params;
    const { name, script_type, script_content } = req.body;
    // console.log("Adding task to job:", { job_id, name, script_type, script_content });

    const client = await pool.connect();
    try {
        await client.query('BEGIN');

        // 1. UPSERT template task vào thư viện
        const taskUpsertQuery = `INSERT INTO tasks (name, script_type, script_content)
VALUES ($1, $2, $3)
ON CONFLICT (name) DO UPDATE SET
    script_type = EXCLUDED.script_type,
    script_content = EXCLUDED.script_content
    
`;
        await client.query(taskUpsertQuery, [name, script_type, script_content || null]);

        // 2. Lấy task_id của template
        const getTaskQuery = 'SELECT id FROM tasks WHERE name = $1';
        const taskResult = await client.query(getTaskQuery, [name]);
        const task_id = taskResult.rows[0].id;

        // 3. Tìm execution_order lớn nhất hiện tại và cộng thêm 1
        const orderRes = await client.query('SELECT MAX(execution_order) as max_order FROM job_task WHERE job_id = $1', [job_id]);
        const new_order = (orderRes.rows[0].max_order === null ? -1 : orderRes.rows[0].max_order) + 1;

        // 4. Tạo liên kết job_task
        const jobTaskQuery = `INSERT INTO job_task (job_id, task_id, execution_order) VALUES ($1, $2, $3) RETURNING *;`;
        const newJobTask = await client.query(jobTaskQuery, [job_id, task_id, new_order]);

        await client.query('COMMIT');
        res.status(201).json(newJobTask.rows[0]); // Trả về task vừa tạo
    } catch (error) {
        await client.query('ROLLBACK');
        console.error('Error adding task to job:', error);
        res.status(500).json({ error: 'Failed to add task' });
    } finally {
        client.release();
    }
};

// === SỬA MỘT TASK CỤ THỂ TRONG JOB ===
export const updateJobTask = async (req, res) => {
    const { job_task_id } = req.params;
    const { name, script_type, script_content, description } = req.body;
    try {
        // Lấy task_id (template id) từ job_task để cập nhật template
        const linkRes = await pool.query('SELECT task_id FROM job_task WHERE id = $1', [job_task_id]);
        if (linkRes.rows.length === 0) return res.status(404).json({ error: 'Job-Task link not found.' });
        const task_id = linkRes.rows[0].task_id;


        // Cập nhật bảng `tasks` (template)
        const updatedTask = await pool.query(
            'UPDATE tasks SET name = $1, script_type = $2, script_content = $3, description = $4 WHERE id = $5 RETURNING *',
            [name, script_type, script_content, description, task_id]
        );
        res.status(200).json(updatedTask.rows[0]);
    } catch (error) {
        console.error('Error updating job task:', error);
        res.status(500).json({ error: 'Failed to update task' });
    }
};

// === XÓA MỘT TASK KHỎI JOB ===
export const deleteJobTask = async (req, res) => {
    const { job_task_id } = req.params;
    try {
        await pool.query('DELETE FROM job_task WHERE id = $1', [job_task_id]);
        res.status(204).send(); // 204 No Content là response chuẩn cho DELETE thành công
    } catch (error) {
        console.error('Error deleting job task:', error);
        res.status(500).json({ error: 'Failed to remove task' });
    }
};

export const createPrefectDeployment = async ({ flow_id, name, tags = [], parameters = {}, schedules = [] }) => {
    const prefectApiUrl =
        process.env.PREFECT_API_URL;

    if (!flow_id || !name) {
        throw new Error("flow_id và name là bắt buộc");
    }
    const parameterSchema = {
        title: "Parameters",
        type: "object",
        properties: {
            jobId: { type: "integer" },
            tasks: {
                type: "array",
                items: { $ref: "#/components/schemas/TaskDict" }
            },
            concurrent: { type: "integer" },
            db_url: { type: "string", default: "postgresql://postgres:123456@localhost:5432/myappdb" }
        },
        required: ["jobId", "tasks", "concurrent"],
        components: {
            schemas: {
                TaskDict: {
                    type: "object",
                    properties: {
                        name: { type: "string" },
                        script_type: { type: "string" },
                        script_content: { type: "string" },
                        // job_task_id: { type: "string" },
                        // job_id: { type: "integer" },
                    },
                    required: ["name", "script_type", "script_content"]
                }
            }
        }
    };
    // Nhớ phải tạo pool trước trên prefect UI
    // prefect work-pool create local-process-pool --type process
    //prefect worker start --pool 'local-process-pool' --type 'process'
    const body = {
        name,
        flow_id,
        work_pool_name: "local-process-pool",
        entrypoint: "my_flows.py:multi_task_job_flow",
        path: "F:/THUC_TAP2/APP_JOB/prefect/flows",
        tags,
        parameter_openapi_schema: parameterSchema,
        enforce_parameter_schema: false,
        schedules,
        parameters

    };


    const { data } = await axios.post(`${prefectApiUrl}/deployments/`, body, {
        headers: { "Content-Type": "application/json" }
    });



    return data;
};
const fetchFlowIdByName = async (flowName) => {
    const PREFECT_API_URL = process.env.PREFECT_API_URL;

    const res = await axios.post(`${PREFECT_API_URL}/flows/filter`, {
        flows: { name: { any_: [flowName] } },
        limit: 1
    });

    return res.data?.[0]?.id;
};

//Chuyển đổi schudule

export const buildPrefectSchedule = (job) => {
    if (!job.schedule_type || !job.schedule_value) return [];

    const tz = "Asia/Ho_Chi_Minh";
    const now = new Date().toISOString();

    if (job.schedule_type === "cron") {
        return [
            {
                schedule: {
                    cron: job.schedule_value,   // ví dụ "0 9 * * *"
                    timezone: tz
                },
                active: true
            }
        ];
    }

    if (job.schedule_type === "interval") {
        const unit = job.schedule_unit?.toLowerCase();
        const n = parseInt(job.schedule_value, 10);
        if (isNaN(n) || n <= 0) return [];

        const seconds =
            unit === "seconds" ? n :
                unit === "minutes" ? n * 60 :
                    unit === "hours" ? n * 3600 :
                        unit === "days" ? n * 86400 : 0;

        return [
            {
                schedule: {
                    interval: seconds,          // số giây, KHÔNG bọc {seconds:…}
                    anchor_date: now,
                    timezone: tz
                },
                active: true
            }
        ];
    }

    return [];
};




// === TRIGGER MỘT JOB ===
export const triggerJobFlowPrefect = async (req, res) => {
    const { id: jobId } = req.params;

    const client = await pool.connect();
    try {
        // --- BƯỚC 1: LẤY JOB VÀ TASKS ---
        const jobRes = await client.query('SELECT * FROM jobs WHERE id = $1', [jobId]);
        if (jobRes.rows.length === 0) {
            return res.status(404).json({ error: 'Job not found' });
        }
        const job = jobRes.rows[0];

        const tasksRes = await client.query(
            `SELECT t.name, t.script_type, t.script_content
FROM job_task jt 
JOIN tasks t ON jt.task_id = t.id 
WHERE jt.job_id = $1 
ORDER BY jt.execution_order ASC`,
            [jobId]
        );
        const tasks = tasksRes.rows;

        // --- BƯỚC 1: LẤY flow_id từ flow name ---
        const flowName = `entrypoint_dynamic_job`;
        const flow_id = await fetchFlowIdByName(flowName);

        if (!flow_id) {
            throw new Error(`Không tìm thấy flow với tên '${flowName}' trong Prefect.`);
        }

        await upsertVariable(`job_${jobId}_tasks`, tasks);             // mảng task
        await upsertVariable(`job_${jobId}_concurrent`, job.concurrent); // số lượng concurrent

        // --- BƯỚC 2: TẠO DEPLOYMENT ---
        const deploymentName = `job_${jobId}_deployment`;
        const scheduleObj = buildPrefectSchedule(job);

        const deployment = await createPrefectDeployment({
            flow_id,
            name: deploymentName,
            parameters: {
                jobId: parseInt(jobId, 10),
            },
            tags: ['auto-deploy', `job-${jobId}`],
            schedules: scheduleObj,



        });


        const deploymentId = deployment.id;
        if (!deploymentId) {
            throw new Error('Failed to create Prefect deployment.');
        }

        // --- BƯỚC 3: TRIGGER FLOW RUN ---
        const flowResponse = await triggerPrefectFlow(deploymentId, {
            jobId: parseInt(jobId, 10),

            // job_id: jobId,
            // job_task_ids: tasks.map(t => t.job_task_id),

        });


        const flowRunId = flowResponse.id;
        if (!flowRunId) {
            throw new Error('Failed to trigger flow run from deployment.');
        }

        // --- BƯỚC 4: CẬP NHẬT DB ---
        await client.query(
            `UPDATE jobs 
SET status = 'running',
flow_run_id = $1,
deployment_id = $2,
updated_at = NOW()
WHERE id = $3`,
            [flowRunId, deploymentId, jobId]
        );

        // --- BƯỚC 5: TRẢ VỀ KẾT QUẢ ---
        res.status(200).json({
            message: `Job ${jobId} triggered successfully.`,
            deployment_id: deploymentId,
            flow_run_id: flowRunId
        });

    } catch (error) {
        console.error(`Error triggering job ${jobId}:`, error.response?.data || error.message);
        res.status(500).json({ error: 'Failed to trigger job flow' });
    } finally {
        client.release();
    }
};

export const getFlowRunStatus = async (req, res) => {
    const { flow_run_id } = req.params;


    const PREFECT_API_URL = process.env.PREFECT_API_URL;
    const client = await pool.connect();

    try {
        const response = await axios.get(`${PREFECT_API_URL}/flow_runs/${flow_run_id}`);

        const { id, name, state } = response.data;
        const status = state?.type || null;
        // --- BƯỚC 4: CẬP NHẬT DB ---
        await client.query(
            `UPDATE jobs 
SET status = $1,
updated_at = NOW()
WHERE flow_run_id = $2`,
            [status, flow_run_id]
        );

        res.status(200).json({
            id,
            name,
            status: state?.type, // đổi từ state sang status
            timestamp: state?.timestamp,
        });
    } catch (error) {
        console.error("Lỗi khi lấy trạng thái flow run:", error.message);
        res.status(500).json({ error: "Không thể lấy trạng thái flow run" });
    }
    finally {
        client.release();
    }
};

// export const getTaskLogsByJobId = async (req, res) => {

//     try {
//         const { jobId } = req.params;

//         const result = await pool.query(
//             `SELECT * FROM job_task_logs WHERE job_id = $1 ORDER BY created_at DESC`,
//             [jobId]
//         );
//         res.json(result.rows);
//     } catch (err) {
//         console.error("Lỗi getTaskLogsByJobId:", err);
//         res.status(500).json({ error: "Lỗi truy vấn logs" });
//     }
// };

export const getTasksByJobIdDetail = async (req, res) => {
    const { jobId } = req.params;
    let limit = parseInt(req.query.limit) || 25;
    const page = parseInt(req.query.page) || 1;
    let offset = (page - 1) * limit;


    // console.log("offset", offset);
    // console.log("limit", limit);
    // console.log("page", page);

    try {
        /* ------------------------------------------------------------------ *
        * 1. Lấy flow_run_id gốc từ bảng jobs (được lưu khi bạn trigger run) *
        * ------------------------------------------------------------------ */
        const { rows } = await pool.query(
            `SELECT flow_run_id FROM jobs WHERE id = $1`,
            [jobId],
        );
        if (!rows.length) return res.status(404).json({ error: "Job not found" });

        const initialFlowRunId = rows[0].flow_run_id;

        /* --------------------------------------------------------------- *
        * 2. Lấy thông tin flow run đầu tiên để suy ra deployment_id      *
        * --------------------------------------------------------------- */
        const { data: initialFlowRun } = await axios.get(
            `${PREFECT_API_URL}/flow_runs/${initialFlowRunId}`,
        );
        const { deployment_id: deploymentId, work_pool_name, parameters } = initialFlowRun;


        /* --------------------------------------------------------------- *
        * 3. Lấy danh sách các flow run khác cùng deployment              *
        *    - sort: EXPECTED_START_TIME_DESC (mới nhất trước)            *
        *    - limit: cho phép chỉnh qua query ?limit=                    *
        * --------------------------------------------------------------- */



        let allFlowRuns = [];


        const { data: flowRuns } = await axios.post(
            `${PREFECT_API_URL}/flow_runs/filter`,
            {
                flow_run_filter: {
                    deployment_id: { any_: [deploymentId] },
                },
                sort: "EXPECTED_START_TIME_DESC",
                limit,
                offset,
            }
        );
        allFlowRuns = flowRuns;

        let total = 0;
        offset = 0;
        const pageSize = 200;
        let keepCounting = true;

        while (keepCounting) {
            const { data: runs } = await axios.post(
                `${PREFECT_API_URL}/flow_runs/filter`,
                {
                    flow_run_filter: {
                        deployment_id: { any_: [deploymentId] },
                    },
                    limit: pageSize,
                    offset,
                }
            );
            total += runs.length;

            if (runs.length < pageSize) {
                keepCounting = false;
            } else {
                offset += pageSize;
            }
        }

        const { data: flowRunDraw } = await axios.post(
            `${PREFECT_API_URL}/flow_runs/filter`,
            {
                flow_run_filter: {
                    deployment_id: { any_: [deploymentId] },
                },
                sort: "EXPECTED_START_TIME_DESC",
                // limit,
                // offset,
            }
        );

        const { data: flowRunByDay } = await axios.post(
            `${PREFECT_API_URL}/flow_runs/filter`,
            {
                flow_run_filter: {
                    deployment_id: { any_: [deploymentId] },
                },
                // sort: "EXPECTED_START_TIME_DESC",
                // limit,
                // offset,
            }
        );
      
        // console.log("flowRunDraw:", flowRunDraw);
        // Thống kê trạng thái flow_run
        const flowRunStateStats = flowRunDraw.reduce((acc, run) => {
            const state = (run.state_type || "UNKNOWN").toUpperCase();
            acc[state] = (acc[state] || 0) + 1;
            return acc;
        }, {});

        // Số lượng Task run theo thời gian
        const taskRunStats = flowRunByDay.reduce((acc, run) => {
            const date = new Date(run.created).toISOString().split("T")[0]; // yyyy-mm-dd
            acc[date] = (acc[date] || 0) + 1;
            return acc;
        }, {});

        //Tổng số flow mỗi deployment

        const flowPerDeployment = flowRunDraw.reduce((acc, run) => {
            const deployment = run.deployment_name || run.deployment_id || "Manual";
            acc[deployment] = (acc[deployment] || 0) + 1;
            return acc;
        }, {});
        // console.log("flowPerDeployment:", flowPerDeployment);

        // Lấy thông tin Deployment
        const { data: deployment } = await axios.get(
            `${PREFECT_API_URL}/deployments/${deploymentId}`
        );

        // Lấy thông tin Flow
        const { data: flow } = await axios.get(
            `${PREFECT_API_URL}/flows/${initialFlowRun.flow_id}`
        );


        /* --------------------------------------------------------------- *
        * 4. Với mỗi flow run, gọi song song /task_runs/filter            *
        *    để gom task run cho nhanh                                    *
        * --------------------------------------------------------------- */
        
        async function fetchTaskRunsWithCap(deploymentId, maxTasks = 1000) {
            const pageSize = 200; // hoặc 100 tuỳ Prefect
            let offset = 0;
            let allTasks = [];

            while (offset < maxTasks) {
                const remaining = maxTasks - offset;
                const fetchSize = Math.min(pageSize, remaining);

                const { data: tasks } = await axios.post(
                    `${PREFECT_API_URL}/task_runs/filter`,
                    {
                        flow_run_filter: {
                            deployment_id: { any_: [deploymentId] }
                        },
                        sort: "EXPECTED_START_TIME_DESC",
                        limit: fetchSize,
                        offset,
                    }
                );

                allTasks.push(...tasks);

                if (tasks.length < fetchSize) break; // hết rồi
                offset += fetchSize;
            }

            return allTasks;
        }
        let allTasks = await fetchTaskRunsWithCap(deploymentId, 1000);        

        // console.log("allTasks:", allTasks);


        const taskRunsByFlowRun = allTasks.reduce((acc, t) => {
            const key = t.flow_run_id;
            (acc[key] ??= []).push({
                id: t.id,
                name: t.name,
                state: t.state_type,
                state_name: t.state_name,
                start_time: t.start_time,
                end_time: t.end_time,
                duration: t.total_run_time,
                task_key: t.task_key,
                dynamic_key: t.dynamic_key
            });
            return acc;
        }, {});
    //    console.log("taskRunsByFlowRun:", taskRunsByFlowRun);
        async function fetchLogsWithCap(flowRunId, start, end, maxLogs = 2000) {
            const pageSize = 200;
            let offset = 0;
            let allLogs = [];

            while (offset < maxLogs) {
                const remaining = maxLogs - offset;
                const fetchSize = Math.min(pageSize, remaining);


                const { data: logs } = await axios.post(`${PREFECT_API_URL}/logs/filter`, {
                    log_filter: {
                        flow_run_id: { any_: [flowRunId] },
                        timestamp: {
                            after_: start.toISOString(),
                            before_: end.toISOString()
                        }
                    },
                    sort: "TIMESTAMP_DESC",
                    limit: fetchSize,
                    offset
                });

                allLogs.push(...logs);
                if (logs.length < fetchSize) break;
                offset += fetchSize;
            }

            return allLogs;
        }

        // Hàm giới hạn số luồng xử lý song song
        function limitConcurrency(tasks, limit = 5) {
            const results = [];
            let running = 0;
            let currentIndex = 0;

            return new Promise((resolve, reject) => {
                function runNext() {
                    if (currentIndex >= tasks.length && running === 0) {
                        resolve(results);
                        return;
                    }

                    while (running < limit && currentIndex < tasks.length) {
                        const i = currentIndex++;
                        running++;
                        tasks[i]()
                            .then(result => results[i] = result)
                            .catch(err => results[i] = { error: err })
                            .finally(() => {
                                running--;
                                runNext();
                            });
                    }
                }

                runNext();
            });
        }





        const allLogs = await limitConcurrency(
            allFlowRuns.map(run => async () => {
                try {
                    const start = run.start_time
                        ? new Date(run.start_time)
                        : new Date(new Date(run.expected_start_time).getTime() - 15 * 60 * 1000);
                    const end = run.end_time
                        ? new Date(new Date(run.end_time).getTime() + 10 * 60 * 1000)
                        : new Date(start.getTime() + 90 * 60 * 1000);

                    const logs = await fetchLogsWithCap(run.id, start, end, 2000);
                    return { runId: run.id, logs };
                } catch (err) {
                    console.error(`Lỗi lấy log flowRun ${run.id}:`, err.message);
                    return { runId: run.id, logs: [] };
                }
            }),

        );

        // Gộp logs theo flow_run_id
        const logsByFlowRun = {};

        allLogs.forEach(({ logs }) => {
            logs.forEach(log => {
                const runId = log.flow_run_id;
                if (!logsByFlowRun[runId]) {
                    logsByFlowRun[runId] = [];
                }
                // Lưu toàn bộ allLogs vào db bảng job_task_logs



                // Kiểm tra log.id đã tồn tại chưa
                const isDuplicate = logsByFlowRun[runId].some(l => l.id === log.id);
                if (isDuplicate) return;


                logsByFlowRun[runId].push({
                    id: log.id, // thêm id để kiểm tra trùng lặp
                    ts: log.timestamp || log.created,
                    logger: log.name,
                    level: log.level_name ??
                        (log.level === 40 ? "ERROR" :
                            log.level === 30 ? "WARNING" :
                                log.level === 20 ? "INFO" : "DEBUG"),
                    msg: log.message
                });
            });
        });
        // await saveLogsToJobTaskLogs(jobId, allLogs);

        // Nếu bạn không cần `id` trong kết quả trả về:
        for (const runId in logsByFlowRun) {
            logsByFlowRun[runId] = logsByFlowRun[runId].map(({ id, ...rest }) => rest);
        }


        const { data: workPool } = await axios.get(
            `${PREFECT_API_URL}/work_pools/${work_pool_name}`,
        );

        const variableNames = [`job_${jobId}_tasks`, `job_${jobId}_concurrent`];

        const { data: variables } = await axios.post(
            `${PREFECT_API_URL}/variables/filter`,
            { name: { any_: variableNames } },
        );

        const variablesMap = {};
        for (const v of variables) {
            try {
                variablesMap[v.name] = JSON.parse(v.value);
            } catch {
                variablesMap[v.name] = v.value;
            }
        }

        res.json({
            deploymentId,
            deploymentName: deployment.name,
            flowName: flow.name,
            allFlowRuns,
            taskRunStats,
            flowRunStateStats,
            taskRunsByFlowRun,
            totalCount: total,
            workPool,
            flowPerDeployment,
            variables: variablesMap,
            logsByFlowRun,
            parameters: {
                jobId: parseInt(jobId, 10),
                tasks: variablesMap[`job_${jobId}_tasks`] || [],
                concurrent: variablesMap[`job_${jobId}_concurrent`] || 1
            },
        });
    } catch (err) {
        console.error("[getTasksByJobIdDetail] ERROR:", err.message);
        res.status(500).json({ error: "Internal server error" });
    }
};
//Lưu log riêng tránh load chậm
export const syncJobLogs = async (req, res) => {
    const { id: jobId } = req.params;
    console.log("đã chạy syncJobLogs for jobId:", jobId);

    const client = await pool.connect();
    try {
        // 1. Lấy flow_run_id từ bảng jobs
        const { rows } = await client.query(
            `SELECT flow_run_id FROM jobs WHERE id = $1`,
            [jobId]
        );
        if (!rows.length) return res.status(404).json({ error: "Job not found" });

        const initialFlowRunId = rows[0].flow_run_id;

        // 2. Lấy deployment_id từ flow_run
        const { data: initialFlowRun } = await axios.get(
            `${PREFECT_API_URL}/flow_runs/${initialFlowRunId}`
        );
        const deploymentId = initialFlowRun.deployment_id;

        // 3. Lấy danh sách flow runs liên quan đến deployment
        const { data: allFlowRuns } = await axios.post(
            `${PREFECT_API_URL}/flow_runs/filter`,
            {
                flow_run_filter: {
                    deployment_id: { any_: [deploymentId] }
                },
                sort: "EXPECTED_START_TIME_DESC",
                limit: 100,
                offset: 0
            }
        );

        // 4. Hàm fetch log cho mỗi flow run
        async function fetchLogsWithCap(flowRunId, start, end, maxLogs = 1000) {
            const pageSize = 100;
            let offset = 0;
            let allLogs = [];

            while (offset < maxLogs) {
                const remaining = maxLogs - offset;
                const fetchSize = Math.min(pageSize, remaining);

                const { data: logs } = await axios.post(`${PREFECT_API_URL}/logs/filter`, {
                    log_filter: {
                        flow_run_id: { any_: [flowRunId] },
                        timestamp: {
                            after_: start.toISOString(),
                            before_: end.toISOString()
                        }
                    },
                    sort: "TIMESTAMP_DESC",
                    limit: fetchSize,
                    offset
                });

                allLogs.push(...logs);
                if (logs.length < fetchSize) break;
                offset += fetchSize;
            }

            return allLogs;
        }

        // 5. Hạn chế số lượng đồng thời
        function limitConcurrency(tasks, limit = 5) {
            const results = [];
            let running = 0;
            let currentIndex = 0;

            return new Promise((resolve, reject) => {
                function runNext() {
                    if (currentIndex >= tasks.length && running === 0) {
                        resolve(results);
                        return;
                    }

                    while (running < limit && currentIndex < tasks.length) {
                        const i = currentIndex++;
                        running++;
                        tasks[i]()
                            .then(result => results[i] = result)
                            .catch(err => results[i] = { error: err })
                            .finally(() => {
                                running--;
                                runNext();
                            });
                    }
                }

                runNext();
            });
        }

        // 6. Gọi API lấy log song song
        const allLogs = await limitConcurrency(
            allFlowRuns.map(run => async () => {
                const start = run.start_time
                    ? new Date(run.start_time)
                    : new Date(new Date(run.expected_start_time).getTime() - 15 * 60 * 1000);
                const end = run.end_time
                    ? new Date(run.end_time)
                    : new Date(start.getTime() + 60 * 60 * 1000); // +1h nếu chưa kết thúc

                const logs = await fetchLogsWithCap(run.id, start, end, 1000);
                return { runId: run.id, logs };
            }),
            5
        );

        // 7. Lưu vào DB với logic lọc trùng (hash)
        await client.query('BEGIN');
        const insertedSet = new Set();

        for (const { runId: flowRunId, logs } of allLogs) {
            for (const log of logs) {
                const {
                    id: log_id,
                    task_run_id,
                    flow_run_id,
                    name: logger,
                    level: log_level,
                    message: logMessage,
                    timestamp: log_timestamp
                } = log;

                const fingerprint = `${jobId}|${task_run_id}|${log_timestamp}|${logMessage}`;
                const hash = crypto.createHash('md5').update(fingerprint).digest('hex');

                if (insertedSet.has(hash)) continue;
                insertedSet.add(hash);

                await client.query(
                    `INSERT INTO job_task_logs (
                        job_id, job_task_id, task_name, task_status,
                        flow_run_id, task_run_id, logger, log_level,
                        log, log_timestamp, log_id
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                    ON CONFLICT ON CONSTRAINT uq_job_log DO NOTHING`,
                    [
                        jobId,
                        task_run_id || null,
                        null,
                        null,
                        flow_run_id || flowRunId,
                        task_run_id || null,
                        logger || null,
                        log_level || null,
                        logMessage || '',
                        log_timestamp ? new Date(log_timestamp) : null,
                        log_id || null
                    ]
                );
            }
        }

        await client.query('COMMIT');
        res.status(200).json({ message: `Đã đồng bộ logs cho jobId = ${jobId}` });

    } catch (err) {
        await client.query('ROLLBACK');
        console.error(`[syncJobLogs] Error:`, err.message);
        res.status(500).json({ error: "Lỗi khi sync logs" });
    } finally {
        client.release();
    }
};