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

# Stage 2: serve
FROM nginx:alpine

# Serve SvelteKit static output; SPA fallback so /wallet etc. work
RUN echo 'server { \
  listen 80; \
  root /usr/share/nginx/html; \
  index index.html; \
  location / { try_files $uri $uri/ /index.html; } \
}' > /etc/nginx/conf.d/default.conf

COPY --from=builder /app/build /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
