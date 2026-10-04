FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm config set fetch-retry-maxtimeout 120000 && npm config set fetch-timeout 300000 && npm ci --registry=https://registry.npmmirror.com
COPY . .
# Next bakes the /api rewrite target in at build time, so these are build arguments.
ARG BACKEND_URL=http://backend:8000
ARG NEXT_PUBLIC_DEMO_MODE=false
ENV BACKEND_URL=$BACKEND_URL NEXT_PUBLIC_DEMO_MODE=$NEXT_PUBLIC_DEMO_MODE NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-alpine
WORKDIR /app
ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
