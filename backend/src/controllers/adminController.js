import pool from '../db.js';
import bcrypt from "bcrypt";

import stream from "stream";
import cloudinary from '../utils/cloudinary.js';
// User
const usernameRegex = /^[a-zA-Z0-9_]+$/;
const passwordRegex = /^(?=.*[!@#$%^&*()_+{}\[\]:;<>,.?~\\/-]).{8,}$/;
const nameRegex = /^[A-Za-zÀ-Ỹà-ỹĂăÂâÊêÔôƠơƯưĐđ\s]+$/;
const emailRegex = /^[a-zA-Z0-9._%+-]+@gmail\.com$/;


export const createUser = async (req, res) => {
    const { username, name, password, email } = req.body;
    const file = req.file;
    //Kiểm tra rỗng
    if (!username || !name || !password || !email) {
        return res.status(400).json({ error: "Username, name và password, email là bắt buộc." });
    }

    try {
        // Validate username
        if (!usernameRegex.test(username)) {
            return res.status(400).json({ error: "Username không hợp lệ. Không được chứa ký tự đặc biệt hoặc khoảng trắng." });
        }

        // Validate password
        if (!passwordRegex.test(password)) {
            return res.status(400).json({ error: "Mật khẩu phải từ 8 ký tự trở lên và chứa ít nhất 1 ký tự đặc biệt." });
        }

        // Validate name
        if (!nameRegex.test(name)) {
            return res.status(400).json({ error: "Tên chỉ được chứa chữ cái." });
        }

        if (!emailRegex.test(email)) {
            return res.status(400).json({ error: "Email không hợp lệ. Chỉ chấp nhận email đuôi @gmail.com." });
        }

        const emailExists = await pool.query("SELECT * FROM users WHERE email = $1", [email]);
        if (emailExists.rows.length > 0) {
            return res.status(400).json({ error: "Email đã được sử dụng." });
        }

        // Check username trùng trong DB
        const existing = await pool.query("SELECT * FROM users WHERE username = $1", [username]);
        if (existing.rows.length > 0) {
            return res.status(400).json({ error: "Username đã tồn tại." });
        }
        


        // Mã hóa mật khẩu
        const hashedPassword = await bcrypt.hash(password, 10);

        // Upload avatar nếu có
        let avatarUrl = "";
        if (file) {
            const bufferStream = new stream.PassThrough();
            bufferStream.end(file.buffer);

            const uploadResult = await new Promise((resolve, reject) => {
                const cloudStream = cloudinary.uploader.upload_stream(
                    { folder: "avatars" },
                    (error, result) => {
                        if (error) return reject(error);
                        return resolve(result);
                    }
                );

                bufferStream.pipe(cloudStream);
            });

            avatarUrl = uploadResult.secure_url;
        }

        // Lưu vào DB
        const { rows } = await pool.query(
            'INSERT INTO users (username, name, password, avatar, email) VALUES ($1, $2, $3, $4, $5) RETURNING *',
            [username, name, hashedPassword, avatarUrl, email]
        );

        res.json(rows[0]);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
  };

export const listUsers = async (_req, res) => {
    const { rows } = await pool.query('SELECT id, username, name, email, avatar FROM users');
    res.json(rows);
};

export const deleteUser = async (req, res) => {
    const client = await pool.connect();
    try {
        await client.query("BEGIN");

        // Xóa liên kết trong bảng user_groups trước
        await client.query("DELETE FROM user_groups WHERE user_id = $1", [req.params.id]);

        // Sau đó xóa user
        await client.query("DELETE FROM users WHERE id = $1", [req.params.id]);

        await client.query("COMMIT");
        res.json({ message: "User deleted" });
    } catch (err) {
        await client.query("ROLLBACK");
        console.error("Delete user error:", err);
        res.status(500).json({ error: "Xóa user thất bại." });
    } finally {
        client.release();
    }
};

export const getUserById = async (req, res) => {
    const { id } = req.params;
    const { rows } = await pool.query('SELECT id, username, name FROM users WHERE id = $1', [id]);
    if (rows.length === 0) {
        return res.status(404).json({ error: 'User not found' });
    }   
    res.json(rows[0]);
};


//Update user
// Nếu có pass thì sẽ update pass, nếu không thì sẽ không update pass
export const updateUser = async (req, res) => {
    console.log("Cập nhật user:", req.params.id, req.body, req.file);
    const { id } = req.params;
    const body = req.body;
    const file = req.file; // multer middleware

    const fields = [];
    const values = [];
    let index = 1;

    // Validate name nếu có
    if (body.name && !nameRegex.test(body.name)) {
        return res.status(400).json({ error: "Tên không hợp lệ. Chỉ được chứa chữ cái." });
    }

    // Validate email nếu có
    if (body.email && !emailRegex.test(body.email)) {
        return res.status(400).json({ error: "Email không hợp lệ. Chỉ chấp nhận email @gmail.com" });
    }

    // Add các trường hợp có
    if (body.name !== undefined) {
        fields.push(`name = $${index}`);
        values.push(body.name);
        index++;
    }

    if (body.email !== undefined) {
        fields.push(`email = $${index}`);
        values.push(body.email);
        index++;
    }

    // Upload avatar nếu có
    if (file) {
        const bufferStream = new stream.PassThrough();
        bufferStream.end(file.buffer);

        try {
            const uploadResult = await new Promise((resolve, reject) => {
                const cloudStream = cloudinary.uploader.upload_stream(
                    { folder: "avatars" },
                    (error, result) => {
                        if (error) return reject(error);
                        resolve(result);
                    }
                );
                bufferStream.pipe(cloudStream);
            });

            fields.push(`avatar = $${index}`);
            values.push(uploadResult.secure_url);
            index++;
        } catch (err) {
            return res.status(500).json({ error: "Lỗi khi upload avatar" });
        }
    }

    // Nếu không có trường nào cần cập nhật
    if (fields.length === 0) {
        return res.status(400).json({ error: "Không có trường nào được cung cấp để cập nhật." });
    }

    values.push(id); // Thêm ID vào cuối
    const query = `UPDATE users SET ${fields.join(", ")} WHERE id = $${index} RETURNING id, name, email, avatar`;

    try {
        const { rows } = await pool.query(query, values);
        res.json(rows[0]);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
};
  

// Group
export const createGroup = async (req, res) => {
    const { name } = req.body;
    const { rows } = await pool.query('INSERT INTO groups (name) VALUES ($1) RETURNING *', [name]);
    res.json(rows[0]);
};

export const listGroups = async (_req, res) => {
    const { rows } = await pool.query('SELECT * FROM groups');
    res.json(rows);
};

export const deleteGroup = async (req, res) => {
    await pool.query('DELETE FROM groups WHERE id = $1', [req.params.id]);
    res.json({ message: 'Group deleted' });
};

// Update group
export const updateGroup = async (req, res) => {
    const { id } = req.params;
    const { name } = req.body;

    if (!name) {
        return res.status(400).json({ error: 'Name is required' });
    }

    const { rows } = await pool.query('UPDATE groups SET name = $1 WHERE id = $2 RETURNING *', [name, id]);
    
    if (rows.length === 0) {
        return res.status(404).json({ error: 'Group not found' });
    }

    res.json(rows[0]);
};

// Role
export const createRole = async (req, res) => {
    const { name } = req.body;
    const { rows } = await pool.query('INSERT INTO roles (name) VALUES ($1) RETURNING *', [name]);
    res.json(rows[0]);
};

export const listRoles = async (_req, res) => {
    const { rows } = await pool.query('SELECT * FROM roles');
    res.json(rows);
};

export const deleteRole = async (req, res) => {
    await pool.query('DELETE FROM roles WHERE id = $1', [req.params.id]);
    res.json({ message: 'Role deleted' });
};
// Update role
export const updateRole = async (req, res) => {
    
    const { id } = req.params;
    const { name } = req.body;

    if (!name) {
        return res.status(400).json({ error: 'Name is required' });
    }

    const { rows } = await pool.query('UPDATE roles SET name = $1 WHERE id = $2 RETURNING *', [name, id]);
    
    if (rows.length === 0) {
        return res.status(404).json({ error: 'Role not found' });
    }

    res.json(rows[0]);
};

// Menu
export const createMenu = async (req, res) => {
    const { name, path } = req.body;
    const { rows } = await pool.query('INSERT INTO menus (name, path) VALUES ($1, $2) RETURNING *', [name, path]);
    res.json(rows[0]);
};

export const listMenus = async (_req, res) => {
    const { rows } = await pool.query('SELECT * FROM menus');
    res.json(rows);
};

export const deleteMenu = async (req, res) => {
    await pool.query('DELETE FROM menus WHERE id = $1', [req.params.id]);
    res.json({ message: 'Menu deleted' });
};
// Update menu
export const updateMenu = async (req, res) => {
    const { id } = req.params;
    const fields = [];
    const values = [];
    let index = 1;

    const allowedFields = ['name', 'path'];

    for (const key of allowedFields) {
        if (req.body[key] !== undefined) {
            fields.push(`${key} = $${index}`);
            values.push(req.body[key]);
            index++;
        }
    }

    if (fields.length === 0) {
        return res.status(400).json({ error: 'No fields provided for update' });
    }

    values.push(id);
    const query = `UPDATE menus SET ${fields.join(', ')} WHERE id = $${index} RETURNING *`;

    try {
        const { rows } = await pool.query(query, values);

        if (rows.length === 0) {
            return res.status(404).json({ error: 'Menu not found' });
        }

        res.json(rows[0]);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
};
  

// Phân quyền


// controllers/userGroupController.js

export const removeUserFromGroup = async (req, res) => {
    try {
        const { user_id, group_id } = req.body;

        if (!user_id || !group_id) {
            return res.status(400).json({ error: "Missing user_id or group_id" });
        }

        await pool.query(
            "DELETE FROM user_groups WHERE user_id = $1 AND group_id = $2",
            [user_id, group_id]
        );

        res.json({ message: "User removed from group" });
    } catch (err) {
        console.error("Error removing user from group:", err);
        res.status(500).json({ error: "Internal Server Error" });
    }
};
  


export const removeRoleFromGroup = async (req, res) => {
    try {
        const { group_id } = req.body;
       
        if (!group_id) {
            return res.status(400).json({ error: "Missing group_id" });
        }

        await pool.query(
            "DELETE FROM group_roles WHERE group_id = $1",
            [group_id]
        );

        res.json({ message: "Role removed from group" });
    } catch (err) {
        console.error("Error removing role from group:", err);
        res.status(500).json({ error: "Internal Server Error" });
    }
};
  


export const removeMenuFromRole = async (req, res) => {
    try {
        const { role_id } = req.body;

        if (!role_id) {
            return res.status(400).json({ error: "Missing role_id" });
        }

        await pool.query(
            "DELETE FROM role_menus WHERE role_id = $1",
            [role_id]
        );

        res.json({ message: "Menus removed from role" });
    } catch (err) {
        console.error("Error removing menus from role:", err);
        res.status(500).json({ error: "Internal Server Error" });
    }
};


export const updateMenusOfRole = async (req, res) => {
    const { id } = req.params; // role_id
    const { menuIds } = req.body;

    if (!id || !Array.isArray(menuIds)) {
        return res.status(400).json({ error: "Thiếu role ID hoặc menuIds không hợp lệ" });
    }

    const client = await pool.connect();

    try {
        await client.query("BEGIN");

        // Lấy các menu hiện có
        const { rows: currentMenus } = await client.query(
            "SELECT menu_id FROM role_menus WHERE role_id = $1",
            [id]
        );

        const currentMenuIds = currentMenus.map((m) => m.menu_id);

        // So sánh để thêm mới và xóa bớt
        const menusToAdd = menuIds.filter(menuId => !currentMenuIds.includes(menuId));
        const menusToRemove = currentMenuIds.filter(menuId => !menuIds.includes(menuId));

        // Thêm mới
        for (const menuId of menusToAdd) {
            await client.query(
                "INSERT INTO role_menus (role_id, menu_id) VALUES ($1, $2)",
                [id, menuId]
            );
        }

        // Xóa bớt
        for (const menuId of menusToRemove) {
            await client.query(
                "DELETE FROM role_menus WHERE role_id = $1 AND menu_id = $2",
                [id, menuId]
            );
        }

        await client.query("COMMIT");

        res.json({
            success: true,
            added: menusToAdd,
            removed: menusToRemove,
            message: "Cập nhật menu cho role thành công",
        });
    } catch (err) {
        await client.query("ROLLBACK");
        console.error("Lỗi cập nhật menu:", err);
        res.status(500).json({ error: "Lỗi máy chủ khi cập nhật menu" });
    } finally {
        client.release();
    }
};
//END SET MENU TO ROLE




export const getUserGroups = async (req, res) => {
    const { id } = req.params;
    try {
        const result = await pool.query(
            `SELECT g.* FROM user_groups ug JOIN groups g ON ug.group_id = g.id WHERE ug.user_id = $1`,
            [id]
        );
        res.json(result.rows);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
};

export const assignGroupsToUser = async (req, res) => {
    const { id } = req.params;
    const { groupIds } = req.body; // array of group IDs
    try {
        await pool.query("DELETE FROM user_groups WHERE user_id = $1", [id]);
        for (const groupId of groupIds) {
            await pool.query("INSERT INTO user_groups (user_id, group_id) VALUES ($1, $2)", [id, groupId]);
        }
        res.json({ success: true });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
};

export const getGroupRoles = async (req, res) => {
    const { id } = req.params;
    try {
        const result = await pool.query(
            `SELECT r.* FROM group_roles gr JOIN roles r ON gr.role_id = r.id WHERE gr.group_id = $1`,
            [id]
        );
        res.json(result.rows);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
};

export const assignRolesToGroup = async (req, res) => {
    const { id } = req.params; // group_id
    const { roleIds } = req.body; // array of role IDs

    if (!id || !Array.isArray(roleIds)) {
        return res.status(400).json({ error: "Missing group ID or role IDs" });
    }

    try {
        // Kiểm tra xem có role nào đã tồn tại trong group
        const checkQuery = `
            SELECT roles.id, roles.name
            FROM group_roles
            JOIN roles ON group_roles.role_id = roles.id
            WHERE group_roles.group_id = $1 AND group_roles.role_id = ANY($2)
        `;
        const checkResult = await pool.query(checkQuery, [id, roleIds]);

        if (checkResult.rowCount > 0) {
            const existingRoleNames = checkResult.rows.map(r => r.name);
            return res.status(400).json({
                error: `Các vai trò đã tồn tại trong nhóm: ${existingRoleNames.join(", ")}`
            });
        }

        // Nếu không có role nào bị trùng, tiến hành insert
        for (const roleId of roleIds) {
            await pool.query(
                "INSERT INTO group_roles (group_id, role_id) VALUES ($1, $2)",
                [id, roleId]
            );
        }

        res.json({
            success: true,
            message: `${roleIds.length} role(s) assigned successfully.`
        });

    } catch (err) {
        console.error("Error assigning roles to group:", err);
        res.status(500).json({ error: "Internal Server Error" });
    }
};

  
// SET MENU TO ROLE
export const getRoleMenus = async (req, res) => {
    try {
        const result = await pool.query(`
            SELECT 
                r.id AS role_id,
                r.name AS role_name,
                ARRAY_AGG(DISTINCT m.name) AS menus
            FROM role_menus rm
            JOIN roles r ON r.id = rm.role_id
            JOIN menus m ON m.id = rm.menu_id
            GROUP BY r.id, r.name
        `);

        res.json(result.rows);
    } catch (err) {
        console.error("Lỗi khi lấy danh sách menu theo role:", err);
        res.status(500).json({ error: err.message });
    }
};


export const assignMenusToRole = async (req, res) => {
    const { id } = req.params; // role_id
    const { menuIds } = req.body; // array of menu IDs

    if (!id || !Array.isArray(menuIds)) {
        return res.status(400).json({ error: "Thiếu role ID hoặc menuIds không hợp lệ" });
    }

    try {
        // Kiểm tra xem menu nào đã tồn tại trong role
        const checkQuery = `
            SELECT menus.id, menus.name
            FROM role_menus
            JOIN menus ON role_menus.menu_id = menus.id
            WHERE role_menus.role_id = $1 AND role_menus.menu_id = ANY($2)
        `;
        const checkResult = await pool.query(checkQuery, [id, menuIds]);

        if (checkResult.rowCount > 0) {
            const existingMenuNames = checkResult.rows.map(m => m.name);
            return res.status(400).json({
                error: `Các menu đã tồn tại trong role: ${existingMenuNames.join(", ")}`
            });
        }

        // Thêm các menu chưa tồn tại
        for (const menuId of menuIds) {
            await pool.query(
                "INSERT INTO role_menus (role_id, menu_id) VALUES ($1, $2)",
                [id, menuId]
            );
        }

        res.json({
            success: true,
            message: `${menuIds.length} menu(s) đã được gán thành công.`,
        });

    } catch (err) {
        console.error("Lỗi khi gán menu cho role:", err);
        res.status(500).json({ error: "Lỗi máy chủ nội bộ" });
    }
};
// END SET MENU TO ROLE


//DANH SÁCH USER ĐÃ GÁN GROUPS
export const getUsersWithGroups = async (req, res) => {
    try {
        const result = await pool.query(`
            SELECT 
        ug.user_id,
        u.username,
        u.name,
        g.id AS group_id,
        g.name AS group_name
      FROM user_groups ug
      JOIN users u ON u.id = ug.user_id
      JOIN groups g ON g.id = ug.group_id
      ORDER BY g.name, u.username;
        `);
        res.json(result.rows);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
};

// Danh sách role đã gán cho group
export const getRolesWithGroups = async (req, res) => {
    try {
        const result = await pool.query(`
             SELECT 
        g.id AS group_id,
        g.name AS group_name,
        ARRAY_AGG(r.name) AS roles
      FROM group_roles gr
      JOIN groups g ON g.id = gr.group_id
      JOIN roles r ON r.id = gr.role_id
      GROUP BY g.id, g.name;
      
        `);
        res.json(result.rows);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
};


export const getRolesOfGroupWithGroupId = async (req, res) => {
    const { groupId } = req.params;
    try {
        const result = await pool.query(`
        SELECT roles.id, roles.name
        FROM group_roles
        JOIN roles ON group_roles.role_id = roles.id
        WHERE group_roles.group_id = $1
      `, [groupId]);

        res.json({ roles: result.rows });
    } catch (err) {
        console.error("Error fetching group roles:", err);
        res.status(500).json({ error: "Internal Server Error" });
    }
};
export const updateRolesOfGroup = async (req, res) => {
    const { id } = req.params; // group_id
    const { roleIds } = req.body; // mảng role_id mới muốn gán
    console.log("Cập nhật vai trò cho group:", id, roleIds);

    if (!id || !Array.isArray(roleIds)) {
        return res.status(400).json({ error: "Thiếu group ID hoặc roleIds không hợp lệ" });
    }

    const client = await pool.connect();

    try {
        await client.query("BEGIN");

        // Lấy danh sách role_id hiện tại của group
        const { rows: currentRoles } = await client.query(
            "SELECT role_id FROM group_roles WHERE group_id = $1",
            [id]
        );

        const currentRoleIds = currentRoles.map(r => r.role_id);
        // Ép roleIds từ client thành number[]
        const roleIdsNumber = roleIds.map(id => Number(id));
        
        // Tìm role cần thêm mới
        const rolesToAdd = roleIdsNumber.filter(id => !currentRoleIds.includes(id));

        // Tìm role cần xóa
        const rolesToRemove = currentRoleIds.filter(id => !roleIdsNumber.includes(id));

        // Thêm các role mới
        for (const roleId of rolesToAdd) {
            await client.query(
                "INSERT INTO group_roles (group_id, role_id) VALUES ($1, $2)",
                [id, roleId]
            );
        }

        // Xóa các role không còn nữa
        for (const roleId of rolesToRemove) {
            await client.query(
                "DELETE FROM group_roles WHERE group_id = $1 AND role_id = $2",
                [id, roleId]
            );
        }

        await client.query("COMMIT");

        res.json({
            success: true,
            added: rolesToAdd,
            removed: rolesToRemove,
            message: "Cập nhật vai trò thành công"
        });
    } catch (err) {
        await client.query("ROLLBACK");
        console.error("Lỗi khi cập nhật vai trò:", err);
        res.status(500).json({ error: "Lỗi máy chủ khi cập nhật vai trò" });
    } finally {
        client.release();
    }
};



  