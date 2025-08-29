# Using 'alpine' for a smaller image size.
FROM node:20-alpine

# Set the working directory in the container
WORKDIR /app

# Copy package.json and package-lock.json
# This leverages Docker's layer caching. The npm install step will only be re-run if these files change.
COPY package*.json ./

# Install project dependencies
RUN npm install

# Copy the rest of your project files into the container
COPY . .

# The command to run when the container starts.
CMD ["npx", "hardhat", "run", "scripts/deploy.ts", "--network", "besu"]