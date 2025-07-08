import express from 'express';
import {
    getLogs, updateJob, deleteJob, triggerJobFlowPrefect,
    streamJobLogs, createJobWithTasks, getJobsWithTasks, getTasksByJobId,
    addTaskToJob, updateJobTask, deleteJobTask, getFlowRunStatus, getTasksByJobIdDetail, syncJobLogs
} from '../controllers/jobController.js';

import { getTableList, getTableSize, getTableEtlLog, getTableSizeByName } from '../controllers/tableController.js';

const router = express.Router();

router.post('/batch', createJobWithTasks);
router.get('/', getJobsWithTasks);
router.get('/:jobId/logs', getLogs);
router.put('/:id', updateJob);      // Sửa job
router.delete('/:id', deleteJob);   // Xóa job
router.post('/:id/trigger', triggerJobFlowPrefect); 
router.get('/:jobId/stream', streamJobLogs);
router.get('/:jobId/tasks', getTasksByJobId);

// === CÁC ROUTE MỚI CHO CRUD TRÊN JOB_TASK ===
router.post('/tasks/:job_id', addTaskToJob);
router.put('/tasks/:job_task_id', updateJobTask);
router.delete('/tasks/:job_task_id', deleteJobTask);
// === ROUTE MỚI ĐỂ LẤY TRẠNG THÁI CỦA FLOW RUN ===
router.get("/flow-run-status/:flow_run_id", getFlowRunStatus);
// === ROUTE MỚI ĐỂ LẤY LOG CỦA TẤT CẢ TASK TRONG JOB ===
// router.get('/:jobId/task-logs', getTaskLogsByJobId);
// === ROUTE MỚI ĐỂ LẤY CÁC TASK VỚI CHI TIẾT ===
router.get('/:jobId/tasks/detail', getTasksByJobIdDetail);
router.post('/:id/logs/sync', syncJobLogs);


// TABLE
router.get('/table-list', getTableList);
router.get('/table-size', getTableSize);
router.get('/table-etl-log', getTableEtlLog);
router.get('/table-size/:table_name', getTableSizeByName);

export default router;
