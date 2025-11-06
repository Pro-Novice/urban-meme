# stress_test/Dockerfile
FROM python:3.11-slim AS base

# Install system deps
RUN apt-get update && apt-get install -y \
    curl git ca-certificates jq bash \
    && rm -rf /var/lib/apt/lists/*

# Install Locust + Node (for k6)
RUN pip install --no-cache-dir locust==2.31.3

# Install k6 CLI
RUN curl -sSL https://github.com/grafana/k6/releases/download/v0.49.0/k6-v0.49.0-linux-amd64.tar.gz \
    | tar xz -C /usr/local/bin --strip-components=1 k6-v0.49.0-linux-amd64/k6

# Copy test files
WORKDIR /app
COPY stress_test/ ./
RUN chmod +x run_test.sh

# Default environment
ENV BASE_URL=http://host.docker.internal:8000/api/blockchain
ENV RPC_URLS=http://host.docker.internal:8545,http://host.docker.internal:8546,http://host.docker.internal:8547,http://host.docker.internal:8548

# Run the test script interactively (choose 1 or 2)
ENTRYPOINT ["./run_test.sh"]
