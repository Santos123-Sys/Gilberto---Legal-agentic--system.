# Stage 1: Build
FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .

# VITE_API_URL will be injected at build time via Railway env vars
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

# Stage 2: Serve with Nginx
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html

# nginx:alpine renders /etc/nginx/templates/*.template via envsubst at startup,
# so nginx listens on Railway's $PORT
COPY nginx.conf /etc/nginx/templates/default.conf.template

ENV PORT=80
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
