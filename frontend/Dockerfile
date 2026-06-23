# ---- build the static dashboard ----
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
# Vite inlines env at BUILD time. The dashboard runs in the browser, so this must be
# a URL the BROWSER can reach — the backend's public LoadBalancer (http, to avoid
# mixed-content blocking since the API is http).
ARG VITE_API_BASE=http://136.109.192.193:8000
ARG VITE_ADMIN_TOKEN=dev-token
RUN printf 'VITE_API_BASE=%s\nVITE_ADMIN_TOKEN=%s\n' "$VITE_API_BASE" "$VITE_ADMIN_TOKEN" > .env.production
RUN npm run build

# ---- serve the static files with nginx ----
FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
