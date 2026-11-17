# BiletFlow web app. Built from the repo root (it needs packages/api-types):
#   docker build -f apps/web/Dockerfile .
FROM node:22-alpine AS deps
WORKDIR /repo
COPY package.json package-lock.json ./
COPY apps/web/package.json apps/web/
COPY packages/api-types/package.json packages/api-types/
# Install only the web app's tree. Dropping the Expo scanner from the workspace list (inside
# the image only) skips more than half of the lockfile and keeps memory low enough for small
# Docker VMs. Versions still come from package-lock.json.
ENV NODE_OPTIONS=--max-old-space-size=768
RUN node -e "const f='package.json',p=require('./'+f);p.workspaces=p.workspaces.filter(w=>w!=='apps/scanner');require('fs').writeFileSync(f,JSON.stringify(p))" \
 && npm install --no-audit --no-fund --maxsockets=4

# Local development stage, used by docker-compose.yml. `next build` needs more memory than a
# 2 GB Docker VM has, while `next dev` compiles each route on demand and fits. For the
# production image, build the `runtime` stage instead:
#   docker build -f apps/web/Dockerfile --target runtime .
FROM node:22-alpine AS dev
WORKDIR /repo
COPY --from=deps /repo/node_modules ./node_modules
COPY package.json package-lock.json ./
COPY packages/api-types packages/api-types
COPY apps/web apps/web
ENV NEXT_TELEMETRY_DISABLED=1 NODE_OPTIONS=--max-old-space-size=1024
EXPOSE 3000
HEALTHCHECK --interval=10s --timeout=10s --start-period=60s --retries=10 \
    CMD wget -qO- http://127.0.0.1:3000/api/health || exit 1
CMD ["npm", "run", "dev", "-w", "@biletflow/web", "--", "--hostname", "0.0.0.0", "--port", "3000"]

FROM node:22-alpine AS build
WORKDIR /repo
COPY --from=deps /repo/node_modules ./node_modules
COPY package.json package-lock.json ./
COPY packages/api-types packages/api-types
COPY apps/web apps/web
# The browser calls the API directly, so its public URL is baked into the bundle.
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL NEXT_TELEMETRY_DISABLED=1
# Fit `next build` into a 2 GB Docker VM: cap the Node heap, and skip the type check
# (DOCKER_BUILD, see next.config.ts). CI still runs tsc, eslint and a full `next build`.
ENV NODE_OPTIONS=--max-old-space-size=1536 DOCKER_BUILD=1
RUN npm run build -w @biletflow/web

FROM node:22-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000
RUN addgroup -S app && adduser -S app -G app
# `output: "standalone"` mirrors the monorepo layout under .next/standalone.
COPY --from=build --chown=app:app /repo/apps/web/.next/standalone ./
COPY --from=build --chown=app:app /repo/apps/web/.next/static ./apps/web/.next/static
COPY --from=build --chown=app:app /repo/apps/web/public ./apps/web/public
USER app
EXPOSE 3000
HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=5 \
    CMD wget -qO- http://127.0.0.1:3000/api/health || exit 1
CMD ["node", "apps/web/server.js"]
