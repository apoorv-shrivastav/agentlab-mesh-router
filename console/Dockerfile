FROM node:22-slim AS build
WORKDIR /app
COPY console/package.json console/pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile --ignore-scripts
COPY console/ ./
RUN pnpm build

FROM node:22-slim AS run
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@11.0.8 --activate
COPY --from=build /app/.next ./.next
COPY --from=build /app/public ./public
COPY --from=build /app/package.json ./package.json
COPY --from=build /app/node_modules ./node_modules
# Cloud Run injects $PORT (usually 8080). Bind to it — do NOT hardcode 3000.
ENV PORT=8080
EXPOSE 8080
CMD ["node", "node_modules/next/dist/bin/next", "start", "-H", "0.0.0.0", "-p", "8080"]
