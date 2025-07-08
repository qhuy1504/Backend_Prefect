import express from 'express';
import jobRoutes from './routes/jobRoutes.js';
import bodyParser from 'body-parser';
import cors from 'cors';

// import dotenv from 'dotenv';
// dotenv.config();
import 'dotenv/config'; 

const app = express();
app.use(bodyParser.json());
app.use(cors({
    origin: '*', // tất cả origin
    methods: ['GET', 'POST', 'PUT', 'DELETE'],
    credentials: true
}));

app.use('/api/jobs', jobRoutes);

app.listen(3001, () => {
    console.log('Backend running on port 3001');
});
