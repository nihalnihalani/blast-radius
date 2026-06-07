FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund

FROM node:20-alpine AS build
WORKDIR /app
ARG NEXT_PUBLIC_AGENT_HTTP_URL=http://localhost:8000/agent
ARG NEXT_PUBLIC_AGENT_NAME=infra_orchestrator
ENV NEXT_PUBLIC_AGENT_HTTP_URL=$NEXT_PUBLIC_AGENT_HTTP_URL NEXT_PUBLIC_AGENT_NAME=$NEXT_PUBLIC_AGENT_NAME
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:20-alpine AS run
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
EXPOSE 3000
CMD ["node", "server.js"]
