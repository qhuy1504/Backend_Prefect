// db.js
import pkg from 'pg';
const { Pool } = pkg;

const pool = new Pool({
    user: 'postgres',
    host: 'postgres', // Địa chỉ máy chủ PostgreSQL của bạn
    database: 'postgres',  // TÊN DATABASE của bạn
    password: '123456', // MẬT KHẨU PostgreSQL của bạn
    port: 5432,
});

export default pool;
