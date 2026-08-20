# Groundwork web.
#
# The runtime stage carries only Next.js's standalone output — no node_modules,
# no package manager, no source. That is the whole point of `output: standalone`
# and it is why this image is a fraction of the build stage's size.

# ---------------------------------------------------------------------- deps --
FROM node:24-alpine AS deps

RUN corepack enable
WORKDIR /srv

# .npmrc must land before install — it sets node-linker=hoisted, without which
# the standalone build produces an image that starts and immediately crashes.
COPY package.json pnpm-lock.yaml .npmrc ./
RUN pnpm install --frozen-lockfile

# ----------------------------------------------------------------------- dev --
FROM node:24-alpine AS dev

RUN corepack enable
WORKDIR /srv
ENV NEXT_TELEMETRY_DISABLED=1

COPY --from=deps /srv/node_modules ./node_modules
COPY . .

EXPOSE 3000
CMD ["pnpm", "dev"]

# --------------------------------------------------------------------- build --
FROM node:24-alpine AS build

RUN corepack enable
WORKDIR /srv
ENV NEXT_TELEMETRY_DISABLED=1

COPY --from=deps /srv/node_modules ./node_modules
COPY . .
RUN pnpm build

# ------------------------------------------------------------------- runtime --
FROM node:24-alpine AS runtime

WORKDIR /srv
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN addgroup --system --gid 10001 groundwork \
    && adduser --system --uid 10001 --ingroup groundwork groundwork

COPY --from=build --chown=10001:10001 /srv/.next/standalone ./
COPY --from=build --chown=10001:10001 /srv/.next/static ./.next/static
COPY --from=build --chown=10001:10001 /srv/public ./public

USER 10001:10001
EXPOSE 3000
CMD ["node", "server.js"]
