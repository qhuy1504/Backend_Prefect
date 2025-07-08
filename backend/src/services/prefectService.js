// prefectService.js
import axios from 'axios';

import fetch from 'node-fetch';

const PREFECT_API_URL = process.env.PREFECT_API_URL || 'http://localhost:4200/api';

export const upsertConcurrencyLimitForTag = async (tag, concurrencyValue) => {
    // Endpoint để xóa limit theo tag
    const deleteEndpoint = `${PREFECT_API_URL}/concurrency_limits/tag/${tag}`;
    // Endpoint để tạo limit mới
    const createEndpoint = `${PREFECT_API_URL}/concurrency_limits/`;

    try {
        // 1. Luôn thử xóa limit cũ trước.
        //    Thao tác này an toàn, nếu tag không tồn tại, Prefect sẽ trả về lỗi 404
        //    nhưng chúng ta có thể bỏ qua lỗi đó.
        console.log(`Attempting to delete existing concurrency limit for tag "${tag}" (if any)...`);
        await axios.delete(deleteEndpoint);
        console.log(`Successfully deleted old limit for tag "${tag}" or it didn't exist.`);
    } catch (error) {
        // Chỉ bắt lỗi 404 (Not Found) và bỏ qua.
        // Các lỗi khác (500, lỗi mạng) vẫn sẽ được ném ra.
        if (error.response && error.response.status === 404) {
            console.log(`No existing limit found for tag "${tag}". Proceeding to create a new one.`);
        } else {
            // Ném lại các lỗi không mong muốn khác
            console.error('An unexpected error occurred while trying to delete the old concurrency limit:', error.response?.data || error.message);
            throw error;
        }
    }

    // === SỬ DỤNG node-fetch ĐỂ TẠO MỚI ===
    try {
        const payload = {
            tag: tag,
            concurrency_limit: concurrencyValue,
           
        };

        console.log('Sending payload with node-fetch:', JSON.stringify(payload, null, 2));

        const response = await fetch(createEndpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload)
        });

        const responseData = await response.json();

        if (!response.ok) {
            // Nếu không thành công, ném lỗi với body từ server
            console.error('Error from Prefect server:', responseData);
            throw new Error(`Prefect API Error (${response.status}): ${JSON.stringify(responseData)}`);
        }

        console.log(`Successfully created new concurrency limit for tag "${tag}".`);
        return responseData;

    } catch (error) {
        console.error('Error in upsertConcurrencyLimitForTag (fetch):', error);
        throw error;
    }
};

/**
 * Kích hoạt một flow run từ một deployment trong Prefect.
 * 
 * @param {string} deploymentId - ID của deployment cần kích hoạt.
 * @param {object} parameters - Một đối tượng chứa các tham số để truyền vào flow.
 * @param {string[]} [tags=[]] - (Tùy chọn) Một mảng các tags để gán cho flow run.
 * @returns {Promise<object>} Dữ liệu của flow run đã được tạo.
 */
export const triggerPrefectFlow = async (deploymentId, parameters, tags = []) => {
    // Đọc địa chỉ API của Prefect từ biến môi trường
    const prefectApiUrl = process.env.PREFECT_API_URL || 'http://localhost:4200/api';

    // Kiểm tra xem deploymentId có được truyền vào không
    if (!deploymentId) {
        throw new Error("Deployment ID is required to trigger a Prefect flow.");
    }

    // Xây dựng URL endpoint sử dụng trực tiếp deploymentId.
    // Đây là cách làm đơn giản và đáng tin cậy nhất.
    const url = `${prefectApiUrl}/deployments/${deploymentId}/create_flow_run`;
    console.log(`url:`, url);

    // Chuẩn bị body cho request
    const body = {};
    if (parameters && Object.keys(parameters).length > 0) {
        body.parameters = parameters;
    }
    if (tags && tags.length > 0) {
        body.tags = tags;
    }

    console.log(`Sending POST request to Prefect API: ${url}`);
    console.log('Request body:', JSON.stringify(body, null, 2)); // Log cả body để dễ debug

    try {
        const response = await axios.post(url, body, {
            headers: { 'Content-Type': 'application/json' }
        });
        console.log(`Flow run triggered successfully. Response:`, response.data);
        return response.data; // Trả về toàn bộ response data từ Prefect
    } catch (error) {
        // Log lỗi chi tiết hơn
        if (error.isAxiosError && error.response) {
            console.error(`Error calling Prefect API (Status: ${error.response.status}):`, error.response.data);
        } else {
            console.error('An unexpected error occurred in triggerPrefectFlow:', error.message);
        }
        // Ném lại lỗi để hàm controller có thể bắt được
        throw error;
    }
};

// Lấy trạng thái của một flow run (để biết khi nào nó kết thúc)
export const getFlowRunState = async (flowRunId) => {
    const endpoint = `${PREFECT_API_URL}/flow_runs/${flowRunId}`;
    try {
        const response = await axios.get(endpoint);
        return response.data;
    } catch (error) {
        console.error(`Error fetching state for flow run ${flowRunId}:`, error.message);
        throw error;
    }
};

// Lấy logs của một flow run
export const getFlowRunLogs = async (flowRunId) => {
    const endpoint = `${PREFECT_API_URL}/flow_runs/${flowRunId}/logs`;
    try {
        const response = await axios.post(endpoint, {}); // API logs dùng POST với body rỗng
        return response.data;
    } catch (error) {
        console.error(`Error fetching logs for flow run ${flowRunId}:`, error.message);
        // Trả về mảng rỗng nếu có lỗi (vd: flow run chưa kịp tạo log)
        return [];
    }
};

/**
 * Tạo mới hoặc cập nhật Prefect Variable.
 * @param {string} name  Tên variable (phải viết thường, a‑z, 0‑9, _)
 * @param {any}    value Dữ liệu JSON‑serializable
 */
export async function upsertVariable(name, value) {
    // 1. Tìm chính xác theo name (khuyến nghị)
    try {
        const { data: found } = await axios.post(
            `${PREFECT_API_URL}/variables/filter`,
            { name: { any_: [name] }, limit: 100 } // Tăng limit lên để lọc kỹ
        );

        const exactMatch = found.find(v => v.name === name);

        if (exactMatch) {
            // Chỉ PATCH khi đúng tên
            await axios.patch(`${PREFECT_API_URL}/variables/${exactMatch.id}`, {
                value: JSON.stringify(value)
            });
            return exactMatch.id;

        }
        // Chưa có → POST mới
        const { data: created } = await axios.post(
            `${PREFECT_API_URL}/variables/`,
            { name, value: JSON.stringify(value) }
        );
        console.log(`Created new variable with name "${name}":`, created);
        return created.id;
    }catch (error) {
        console.error(`Error upserting variable "${name}":`, error.message);
        throw error;
    }
   
}


