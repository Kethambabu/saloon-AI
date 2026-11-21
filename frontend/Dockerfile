# ==============================================================================
# SalonAI Frontend - Multi-Stage Production Dockerfile
# Optimized for Render Web Service (supports dynamic $PORT & SPA Routing)
# ==============================================================================

# Stage 1: Build the React + Vite application
FROM node:20-alpine AS builder

WORKDIR /app

# Allow passing backend API URL during build time
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

# Copy dependency specifications
COPY package*.json ./

# Install npm dependencies cleanly
RUN npm ci

# Copy frontend source code
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

# Copy Nginx template for dynamic $PORT injection by official docker-entrypoint
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Expose default HTTP port
EXPOSE 80

# Run Nginx in foreground
CMD ["nginx", "-g", "daemon off;"]
