# Multi-stage build for the Cocoa frontend (Vite + React + TypeScript).
# Build context is ./frontend (see docker-compose.yml's `context: ./frontend`).

FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
# nginx:alpine's default server block listens on 80; retarget to 3000 to
# match docker-compose.yml's port mapping.
RUN sed -i 's/listen  *80;/listen 3000;/' /etc/nginx/conf.d/default.conf
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -qO- http://localhost:3000/ || exit 1
CMD ["nginx", "-g", "daemon off;"]
