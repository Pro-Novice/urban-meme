# Use lightweight Node image
FROM node:20-alpine

# Set working directory
WORKDIR /app

# Copy package files first (better layer caching)
COPY package*.json ./

# Install dependencies
RUN npm install --legacy-peer-deps

# Copy rest of project
COPY . .

# Default command (overridden by docker-compose/docker-manage.sh)
CMD ["npx", "hardhat", "help"]
