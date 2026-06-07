FROM node:20-alpine AS build
WORKDIR /app

ARG VITE_ONLINE_API_BASE_URL=http://localhost:1212/api/online
ARG VITE_ONLINE_PUBLIC_URL=http://localhost:5182
ARG VITE_ONLINE_STUDENT_BASE_PATH=/
ARG VITE_GOOGLE_CLIENT_ID=
ARG VITE_SUPPORT_EMAIL=support@internal-academy.demo
ARG VITE_PRIVACY_URL=http://localhost:5182
ARG VITE_IMPRESSUM_URL=http://localhost:5182
ARG VITE_TEAMS_URL=https://teams.microsoft.com/v2/
ARG VITE_OUTLOOK_CALENDAR_URL=https://outlook.office.com/calendar/view/week
ARG VITE_JUPYTER_URL=/lab/

ENV VITE_ONLINE_API_BASE_URL=$VITE_ONLINE_API_BASE_URL
ENV VITE_ONLINE_PUBLIC_URL=$VITE_ONLINE_PUBLIC_URL
ENV VITE_ONLINE_STUDENT_BASE_PATH=$VITE_ONLINE_STUDENT_BASE_PATH
ENV VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID
ENV VITE_SUPPORT_EMAIL=$VITE_SUPPORT_EMAIL
ENV VITE_PRIVACY_URL=$VITE_PRIVACY_URL
ENV VITE_IMPRESSUM_URL=$VITE_IMPRESSUM_URL
ENV VITE_TEAMS_URL=$VITE_TEAMS_URL
ENV VITE_OUTLOOK_CALENDAR_URL=$VITE_OUTLOOK_CALENDAR_URL
ENV VITE_JUPYTER_URL=$VITE_JUPYTER_URL

COPY package.json package-lock.json* ./
RUN [ -f package-lock.json ] && npm ci || npm install

COPY . .
RUN npm run build

FROM nginx:1.27-alpine
LABEL org.opencontainers.image.authors="Serhii TK" \
      org.opencontainers.image.vendor="Serhii TK" \
      org.opencontainers.image.title="Learning Hub Learner Portal" \
      org.opencontainers.image.licenses="LicenseRef-Proprietary"
COPY --from=build /app/dist /usr/share/nginx/html
RUN printf 'server {\n  listen 80;\n  server_name _;\n  root /usr/share/nginx/html;\n  index index.html;\n  location / { try_files $uri $uri/ /index.html; }\n}\n' > /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
