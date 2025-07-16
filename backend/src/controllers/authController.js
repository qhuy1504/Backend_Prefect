import pool from "../db.js";
import bcrypt from "bcrypt";
import nodemailer from "nodemailer";

const otpMap = new Map(); // email => { otp, expires }

export const forgotPassword = async (req, res) => {
    const { email } = req.body;

    const emailRegex = /^[a-zA-Z0-9._%+-]+@gmail\.com$/;
    if (!email || !emailRegex.test(email.trim())) {
        return res.status(400).json({ error: "Email không hợp lệ. Vui lòng nhập email @gmail.com hợp lệ." });
    }

    try {
        const user = await pool.query("SELECT * FROM users WHERE email = $1", [email]);
        if (user.rows.length === 0) return res.status(404).json({ error: "Email không tồn tại trên hệ thống" });

        const otp = Math.floor(100000 + Math.random() * 900000).toString();
        const expires = Date.now() + 5 * 60 * 1000; // 5 phút
        otpMap.set(email, { otp, expires });

        const transporter = nodemailer.createTransport({
            host: "smtp.gmail.com",
            port: 587,
            secure: false, 
            auth: {
                user: process.env.EMAIL_FROM,
                pass: process.env.EMAIL_PASSWORD,
            },
        });

        await transporter.sendMail({
            from: process.env.EMAIL_FROM,
            to: email,
            subject: "Mã OTP khôi phục mật khẩu của bạn",
            html: `
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; border: 1px solid #ddd; border-radius: 10px; padding: 20px;">
        <h2 style="color: #ff0000ff;">Khôi phục mật khẩu</h2>
        <p>Xin chào,</p>
        <p>Bạn vừa yêu cầu khôi phục mật khẩu cho tài khoản của mình. Đây là mã OTP của bạn:</p>
        <div style="font-size: 24px; font-weight: bold; background-color: #f0f0f0; padding: 15px; text-align: center; border-radius: 5px; letter-spacing: 2px; margin: 20px 0;">
            ${otp}
        </div>
        <p>Mã OTP này sẽ hết hạn sau <strong>5 phút</strong>. Vui lòng không chia sẻ mã này với bất kỳ ai.</p>
        <p>Nếu bạn không yêu cầu khôi phục mật khẩu, vui lòng bỏ qua email này.</p>
        <hr style="margin: 30px 0;">
        <p style="font-size: 12px; color: #888;">Trân trọng,<br>Đội ngũ hỗ trợ</p>
    </div>
    `
        });


        res.json({ message: "OTP đã gửi qua email" });
    } catch (err) {
        console.error("Forgot password error:", err);
        res.status(500).json({ error: "Server error" });
    }
};

export const verifyOtp = (req, res) => {
    const { email, otp } = req.body;
    const entry = otpMap.get(email);
    if (!entry) return res.status(400).json({ error: "OTP không tồn tại" });
    if (entry.otp !== otp) return res.status(400).json({ error: "Sai mã OTP" });
    if (Date.now() > entry.expires) return res.status(400).json({ error: "Mã OTP hết hạn" });

    return res.json({ message: "OTP hợp lệ" });
};

export const resetPassword = async (req, res) => {
    const { email, newPassword } = req.body;

    if (!email || !newPassword) {
        return res.status(400).json({ error: "Thiếu email hoặc mật khẩu, vui lòng nhập đầy đủ" });
    }

    const passwordRegex = /^(?=.*[!@#$%^&*()_+{}\[\]:;<>,.?~\\/-]).{8,}$/;
    if (!passwordRegex.test(newPassword)) {
        return res.status(400).json({ error: "Mật khẩu phải có ít nhất 8 ký tự và 1 ký tự đặc biệt." });
    }

    try {
        const hashedPassword = await bcrypt.hash(newPassword, 10);
        await pool.query("UPDATE users SET password = $1 WHERE email = $2", [hashedPassword, email]);
        otpMap.delete(email);
        res.json({ message: "Đổi mật khẩu thành công" });
    } catch (err) {
        console.error("Reset password error:", err);
        res.status(500).json({ error: "Server error" });
    }
};

// Đổi mật khẩu
export const changePassword = async (req, res) => {
    const { currentPassword, newPassword, confirmPassword } = req.body;

    const userId = req.user.id;

    if (!currentPassword || !newPassword || !confirmPassword) {
        return res.status(400).json({ error: "Vui lòng điền đầy đủ thông tin" });
    }

    if (newPassword !== confirmPassword) {
        return res.status(400).json({ error: "Mật khẩu xác nhận không khớp" });
    }

    if (!/^(?=.*[!@#$%^&*()_+{}\[\]:;<>,.?~\\/-]).{8,}$/.test(newPassword)) {
        return res.status(400).json({ error: "Mật khẩu mới phải ≥ 8 ký tự và có ký tự đặc biệt" });
    }

    try {
        const result = await pool.query("SELECT * FROM users WHERE id = $1", [userId]);
        const user = result.rows[0];

        const match = await bcrypt.compare(currentPassword, user.password);
        if (!match) {
            return res.status(401).json({ error: "Mật khẩu hiện tại không đúng" });
        }

        const hashedNew = await bcrypt.hash(newPassword, 10);
        await pool.query("UPDATE users SET password = $1 WHERE id = $2", [hashedNew, userId]);

        return res.json({ message: "Đổi mật khẩu thành công" });
    } catch (err) {
        console.error("changePassword error:", err);
        return res.status(500).json({ error: "Lỗi hệ thống" });
    }
};
