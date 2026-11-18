# Multi-stage Dockerfile for Web GIS Frontend
# Stage 1: Build React/Vite application
FROM node:20-alpine AS build

WORKDIR /app

# Copy dependency manifests
COPY package.json ./

# Install dependencies
RUN npm install --legacy-peer-deps --no-audit --no-fund

# Copy source files
COPY . .

# Build for production
RUN npm run build

# Stage 2: Serve with Nginx Alpine
FROM nginx:alpine

# Copy custom Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy compiled assets from build stage
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
