# Dockerfile
FROM node:20.16.0

# Set working directory
WORKDIR /app

# Copy package.json and package-lock.json
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy the rest of the application
COPY . .


EXPOSE 3001

# Start the application
CMD ["node", "src/index.js"]
