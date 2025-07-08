import axios from 'axios';

const trinoUrl = process.env.TRINO_URL;

export const runTrinoQuery = async (query) => {
    try {
        const response = await axios.post(trinoUrl, query, {
            headers: {
                'X-Trino-User': 'your_username',
                'X-Trino-Schema': 'default',
                'X-Trino-Catalog': 'your_catalog',
            },
        });
        return response.data;
    } catch (error) {
        console.error('Error running Trino query:', error.message);
        throw error;
    }
};
