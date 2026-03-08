# Frontend: SvelteKit static build served with nginx
# Build from repo root: docker build -f frontend/Dockerfile frontend/
# Or from frontend: docker build -t tritone-cards-frontend .

# Stage 1: build
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# Optional: pass API URL at build time for production (e.g. --build-arg VITE_API_URL=https://api.example.com)
ARG VITE_API_URL=
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

# Fail the image build if static assets are missing (would cause "MIME type text/html" for .js in browser)
RUN test -d /app/build/_app && test -f /app/build/index.html || (echo "Build output missing _app/ or index.html" && exit 1)

# Stage 2: serve
FROM nginx:alpine

# Serve SvelteKit static output. Serve real files first; only then SPA fallback.
# /_app/ must never return index.html (would break JS/CSS with wrong MIME type).
RUN echo 'server { \
  listen 80; \
  root /usr/share/nginx/html; \
  index index.html; \
  include /etc/nginx/mime.types; \
  location /_app/ { \
    try_files $uri =404; \
    add_header Cache-Control "public, max-age=31536000, immutable"; \
  } \
  location / { \
    try_files $uri $uri/ /index.html; \
  } \
}' > /etc/nginx/conf.d/default.conf

COPY --from=builder /app/build /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
