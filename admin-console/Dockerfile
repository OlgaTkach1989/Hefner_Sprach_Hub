FROM node:20-alpine AS build
WORKDIR /app

ARG VITE_ONLINE_API_BASE_URL=http://localhost:1212/api/online
ARG VITE_ONLINE_ADMIN_BASE_PATH=/

ENV VITE_ONLINE_API_BASE_URL=$VITE_ONLINE_API_BASE_URL
ENV VITE_ONLINE_ADMIN_BASE_PATH=$VITE_ONLINE_ADMIN_BASE_PATH

COPY package.json package-lock.json* ./
RUN [ -f package-lock.json ] && npm ci || npm install

COPY . .
RUN npm run build

FROM nginx:1.27-alpine
LABEL org.opencontainers.image.authors="Serhii TK" \
      org.opencontainers.image.vendor="Serhii TK" \
      org.opencontainers.image.title="Hefner Sprach Hub Admin Console" \
      org.opencontainers.image.licenses="LicenseRef-Proprietary"
COPY --from=build /app/dist /usr/share/nginx/html
RUN printf 'server {\n  listen 80;\n  server_name _;\n  root /usr/share/nginx/html;\n  index index.html;\n  location / { try_files $uri $uri/ /index.html; }\n}\n' > /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
