# Build stage
FROM node:24-alpine AS builder

WORKDIR /src

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --frozen-lockfile

COPY frontend/ ./
RUN npm run build

# Runtime stage — nginx serving static files
FROM nginx:1.27-alpine AS runtime

# Security: run as nonroot nginx user
RUN addgroup -S app && adduser -S -G app app

COPY --from=builder /src/dist /usr/share/nginx/html
COPY frontend/.docker/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost/ || exit 1

USER app
CMD ["nginx", "-g", "daemon off;"]