// db.js
import pkg from 'pg';
const { Pool } = pkg;

const pool = new Pool({
    user: 'postgres',
    host: 'maglev.proxy.rlwy.net', // Địa chỉ máy chủ PostgreSQL của bạn
    database: 'railway',  // TÊN DATABASE của bạn
    password: 'gRkWEparPPhyoBSwqZCBvFQRTEPYSILc', // MẬT KHẨU PostgreSQL của bạn
    port: 25007,
});

export default pool;
