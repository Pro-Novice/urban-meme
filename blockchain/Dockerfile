# Use lightweight Node image
FROM node:20-alpine

# Set working directory
WORKDIR /app

# Copy package files first (better layer caching)
COPY package*.json ./

# Reuse the local npm cache first and contact the registry only for packages
# that are not cached yet.
RUN --mount=type=cache,target=/root/.npm,sharing=locked \
    npm ci --legacy-peer-deps --prefer-offline --no-audit --no-fund

# Copy rest of project
COPY . .

# Default command (overridden by docker-compose/docker-manage.sh)
CMD ["npx", "hardhat", "help"]
