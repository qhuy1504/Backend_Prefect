import express from 'express';
import jobRoutes from './routes/jobRoutes.js';
import adminRoutes from './routes/adminRoutes.js';
import importRoutes from './routes/importRoutes.js';
import authRoutes from './routes/authRoutes.js';
import bodyParser from 'body-parser';
import cors from 'cors';
import aiRoutes from './routes/aiRoutes.js';
import envConfigRoutes from "./routes/envConfig.route.js";
// import dotenv from 'dotenv';
// dotenv.config();
import 'dotenv/config'; 

const app = express();
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ limit: '50mb', extended: true }));


app.use(cors({
    origin: '*', // tất cả origin
    methods: ['GET', 'POST', 'PUT', 'DELETE'],
    credentials: true
}));

app.use('/api/jobs', jobRoutes);
app.use('/api/admin', adminRoutes);
app.use('/api/import', importRoutes);
app.use('/api/auth', authRoutes);
app.use('/api/ai', aiRoutes);
app.use('/api/env-config', envConfigRoutes);


app.listen(3001, () => {
    console.log('Backend running on port 3001');
});
