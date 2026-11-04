FROM node:22-slim

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev || npm install --omit=dev

COPY . .
ENV DATA_DIR=/data
CMD ["node", "src/index.js"]
