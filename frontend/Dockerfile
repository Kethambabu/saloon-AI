# ==============================================================================
# SalonAI Frontend - Multi-Stage Production Dockerfile
# Optimized for Render Web Service (supports dynamic $PORT & SPA Routing)
# ==============================================================================

# Stage 1: Build the React + Vite application
FROM node:20-alpine AS builder

WORKDIR /app

# Allow passing backend API URL during build time, defaulting to production backend
ARG VITE_API_URL=https://saloon-ai-6blp.onrender.com/api/v1
ENV VITE_API_URL=$VITE_API_URL

# Copy dependency specifications
COPY package*.json ./

# Install npm dependencies cleanly (falls back to npm install if lockfile needs sync)
RUN npm ci || npm install

# Copy frontend source code and configuration files
COPY . .

# Build production assets
RUN npm run build

# Stage 2: Serve production bundle with Nginx
FROM nginx:alpine

# Default PORT if not provided by Render
ENV PORT=80

# Clean out default Nginx assets and configs
RUN rm -rf /etc/nginx/conf.d/* /usr/share/nginx/html/*

# Copy built static files from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy Nginx server configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose default HTTP port
EXPOSE 80

# Dynamically substitute ${PORT} using sed (safe: will not strip Nginx $uri variables) and launch Nginx
CMD ["sh", "-c", "sed -i \"s/\\${PORT}/${PORT:-80}/g\" /etc/nginx/conf.d/default.conf && exec nginx -g 'daemon off;'"]
