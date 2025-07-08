import pool from '../db.js';
import axios from 'axios';

// Function to fetch table data from the database
export const getTableList = async (req, res) => {
    try {
        const result = await pool.query(`
        SELECT db_name, schema_name, table_name, scd_type,
         to_char(data_date, 'YYYY-MM-DD') AS data_date
  FROM table_list
  ORDER BY data_date DESC
      `);
        res.json(result.rows);
    } catch (err) {
        console.error('Error fetching table list:', err);
        res.status(500).json({ error: 'Internal server error' });
    }
};

export const getTableSize = async (req, res) => {
    try {
        const result = await pool.query(`
        SELECT database, schema_name, table_name, records, size_mb,
                   to_char(data_date, 'YYYY-MM-DD') AS data_date
            FROM table_size
            ORDER BY data_date DESC
      `);
        res.json(result.rows);
    } catch (err) {
        console.error('Error fetching table list:', err);
        res.status(500).json({ error: 'Internal server error' });
    }
};

export const getTableEtlLog = async (req, res) => {
    try {
        const result = await pool.query(`
        SELECT database_name, schema_name, table_name, cnt_row, process_second, update_time,
                   to_char(data_date, 'YYYY-MM-DD') AS data_date
            FROM table_etl_log
            ORDER BY data_date DESC
      `);
        res.json(result.rows);
    } catch (err) {
        console.error('Error fetching table list:', err);
        res.status(500).json({ error: 'Internal server error' });
    }
};

export const getTableSizeByName = async (req, res) => {
    const { table_name } = req.params;

    try {
        const result = await pool.query(
            `SELECT data_date, size_mb
         FROM table_size
         WHERE table_name = $1
         ORDER BY data_date DESC`,
            [table_name]
        );

        res.json(result.rows);
    } catch (err) {
        console.error('Error fetching size by table:', err);
        res.status(500).json({ error: 'Internal server error' });
    }
};
  