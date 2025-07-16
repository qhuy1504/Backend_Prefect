
import jwt from "jsonwebtoken";
import bcrypt from "bcrypt"; // Thêm dòng này
import pool from "../db.js";
import ldap from "ldapjs";
import dotenv from "dotenv";
dotenv.config();

const SECRET = process.env.JWT_SECRET;

// Hàm kết nối và kiểm tra LDAP
export const authenticateLDAP = (username, password) => {
    return new Promise((resolve, reject) => {
        const adminClient = ldap.createClient({ url: "ldap://localhost:389" });

        adminClient.bind("cn=admin,dc=example,dc=com", "admin", (err) => {
            if (err) return reject(new Error("LDAP admin bind failed"));

            const searchOptions = {
                scope: "sub",
                filter: `(uid=${username})`,
            };

            adminClient.search("dc=example,dc=com", searchOptions, (err, result) => {
                if (err) return reject(new Error("LDAP search error"));

                let userDN = null;

                result.on("searchEntry", (entry) => {
                    userDN = entry.objectName.toString();
                });

                result.on("end", () => {
                    adminClient.unbind();

                    if (!userDN) return reject(new Error("User not found"));

                    const userClient = ldap.createClient({ url: "ldap://localhost:389" });

                    userClient.bind(userDN, password, (err) => {
                        userClient.unbind();
                        if (err) {
                            return reject(new Error("Invalid LDAP credentials"));
                        } else {
                            return resolve(userDN); // Thành công
                        }
                    });
                });
            });
        });
    });
};

// Hàm lấy menu của user từ DB
const getMenusByUserId = async (userId) => {
    const result = await pool.query(`
      SELECT DISTINCT m.id, m.name, m.path
      FROM users u
      JOIN user_groups ug ON u.id = ug.user_id
      JOIN group_roles gr ON ug.group_id = gr.group_id
      JOIN role_menus rm ON gr.role_id = rm.role_id
      JOIN menus m ON rm.menu_id = m.id
      WHERE u.id = $1
    `, [userId]);

    return result.rows; // [{id, name, path}]
};


// Middleware: xử lý login hỗn hợp
export const login = async (req, res) => {
    const { username, password } = req.body;
    if (!username || !password) {
        return res.status(400).json({ error: "Username và password là bắt buộc" });
    }
    // Kiểm tra định dạng username
    const usernameRegex = /^[a-zA-Z0-9_]+$/;
    if (!usernameRegex.test(username)) {
        return res.status(400).json({ error: "Username không hợp lệ. Chỉ cho phép chữ cái, số và dấu gạch dưới." });
    }
    // Kiểm tra định dạng password
    const passwordRegex = /^(?=.*[!@#$%^&*()_+{}\[\]:;<>,.?~\\/-]).{8,}$/;
    if (!passwordRegex.test(password)) {
        return res.status(400).json({ error: "Mật khẩu phải từ 8 ký tự trở lên và chứa ít nhất 1 ký tự đặc biệt." });
    }

    try {
        // Check user trong DB
        const userRes = await pool.query("SELECT * FROM users WHERE username = $1", [username]);
        const user = userRes.rows[0];

        // Nếu có user và có password trong DB → kiểm tra bằng bcrypt
        if (user && user.password) {
            const match = await bcrypt.compare(password, user.password);

            if (match) {
                const token = jwt.sign({ id: user.id, username: user.username, avatar: user?.avatar, email: user?.email }, SECRET, { expiresIn: "1h" });
                const menus = await getMenusByUserId(user.id);
             
                return res.json({ message: "Đăng nhập thành công", token, menus });
            }
        }

        // Nếu không login được → thử LDAP
        await authenticateLDAP(username, password);

        // Nếu login LDAP thành công → thêm user nếu chưa có
        let userId = user?.id;

        if (!userId) {
            const insertRes = await pool.query(
                "INSERT INTO users (username, name, password) VALUES ($1, $2, $3) RETURNING id",
                [username, username, ""] // Không lưu password từ LDAP
            );
            userId = insertRes.rows[0].id;
        }

        const token = jwt.sign({ id: userId, username, avatar: user?.avatar }, SECRET, { expiresIn: "1h" });
        const menus = await getMenusByUserId(userId);
        return res.json({ message: "Đăng nhập thành công LDAP", token, menus });
    } catch (err) {
        console.error("Login error:", err);
        return res.status(401).json({ error: "Đăng nhập thất bại, sai tài khoản hoặc mật khẩu" });
    }
};

export const authMiddleware = (req, res, next) => {
    const authHeader = req.headers["authorization"];
    const token = authHeader && authHeader.split(" ")[1]; // Bearer <token>

    if (!token) return res.status(401).json({ error: "Token không tồn tại" });

    try {
        const decoded = jwt.verify(token, process.env.JWT_SECRET);
        req.user = decoded; // lưu thông tin vào req để dùng tiếp
        next();
    } catch (err) {
        return res.status(403).json({ error: "Token không hợp lệ hoặc đã hết hạn" });
    }
};

