import axios from 'axios';

const MCP_API_TOOL = 'http://mcp_tools:5001/search';
// Gửi prompt đến MCP (Python Server)
export const askLlamaViaMCP = async (prompt) => {
    try {
        const res = await axios.post(MCP_API_TOOL, { prompt });
        return res.data.response;
    } catch (err) {
        console.error('MCP error:', err.message);
        throw err;
    }
};
