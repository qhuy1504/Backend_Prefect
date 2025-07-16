import { Readable } from "stream";
import cloudinary from "../utils/cloudinary.js";
import csv from "csv-parser";
import xlsx from "xlsx";
import pool from '../db.js';

export const handleImportFile = async (req, res) => {
    try {
        const file = req.file;
        const { tableName, overwrite } = req.body;
        if (!file || !tableName) return res.status(400).json({ error: "Thiếu file hoặc tên bảng" });

        const fileBuffer = file.buffer;
        const fileName = file.originalname;
        const tableRegex = /^[a-zA-Z_][a-zA-Z0-9_]*$/;
        if (!tableRegex.test(tableName)) {
            return res.status(400).json({ error: "Tên bảng không hợp lệ." });
        }

        const uploadStream = cloudinary.uploader.upload_stream({
            resource_type: "raw",
            public_id: `uploads/${Date.now()}_${fileName}`
        }, async (error, result) => {
            if (error) return res.status(500).json({ error: "Upload Cloudinary thất bại" });

            const fileUrl = result.secure_url;
            let data = [];

            if (fileName.endsWith(".csv")) {
                const stream = Readable.from(fileBuffer);
                stream.pipe(csv())
                    .on("data", (row) => data.push(row))
                    .on("end", () => handleSave(data));
            } else if (fileName.endsWith(".xlsx")) {
                const workbook = xlsx.read(fileBuffer, { type: "buffer" });
                const sheet = workbook.Sheets[workbook.SheetNames[0]];
                data = xlsx.utils.sheet_to_json(sheet);
                handleSave(data);
            } else {
                return res.status(400).json({ error: "Chỉ hỗ trợ .csv và .xlsx" });
            }

            const handleSave = async (data) => {
                if (data.length === 0) return res.json({ url: fileUrl, data: [] });

                console.log("Data to save:", data.length, "rows");

                const tableExists = await pool.query(
                    `SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = $1
        )`, [tableName.toLowerCase()]
                );

                const exists = tableExists.rows[0].exists;

                if (exists && overwrite === "true") {
                    await pool.query(`DROP TABLE IF EXISTS "${tableName}"`);
                } else if (exists) {
                    return res.status(409).json({ error: "Bảng đã tồn tại." });
                }

                // Tạo bảng mới
                const columns = Object.keys(data[0]);
                const columnDefs = columns.map(col => `"${col}" TEXT`).join(", ");
                await pool.query(`CREATE TABLE "${tableName}" (${columnDefs})`);

                const batchSize = 5000;
                for (let i = 0; i < data.length; i += batchSize) {
                    const batch = data.slice(i, i + batchSize);
                    const values = [];
                    const placeholders = [];

                    batch.forEach((row, rowIndex) => {
                        const rowPlaceholders = columns.map((_, colIndex) => `$${rowIndex * columns.length + colIndex + 1}`);
                        placeholders.push(`(${rowPlaceholders.join(", ")})`);
                        columns.forEach((col) => {
                            values.push(row[col] ?? null);
                        });
                    });

                    const insertQuery = `
            INSERT INTO "${tableName}" (${columns.map(c => `"${c}"`).join(", ")})
            VALUES ${placeholders.join(", ")}
        `;

                    await pool.query(insertQuery, values);
                }

                return res.json({ message: "Lưu thành công", url: fileUrl, data });
            };

        });

        Readable.from(fileBuffer).pipe(uploadStream);
    } catch (err) {
        console.error("Import error:", err);
        return res.status(500).json({ error: "Lỗi hệ thống" });
    }
};
