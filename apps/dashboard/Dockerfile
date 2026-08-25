# Next.js NEXT_PUBLIC_* vars are baked in at build time, so they arrive as
# build args here, not just runtime environment -- set them at deploy time,
# e.g. `docker build --build-arg NEXT_PUBLIC_COMPUTELAYER_API_URL=https://...`

FROM node:20-slim AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install

FROM node:20-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

ARG NEXT_PUBLIC_COMPUTELAYER_API_URL
ARG NEXT_PUBLIC_COMPUTELAYER_API_KEY
ARG NEXT_PUBLIC_COMPUTELAYER_PROJECT
ENV NEXT_PUBLIC_COMPUTELAYER_API_URL=$NEXT_PUBLIC_COMPUTELAYER_API_URL \
    NEXT_PUBLIC_COMPUTELAYER_API_KEY=$NEXT_PUBLIC_COMPUTELAYER_API_KEY \
    NEXT_PUBLIC_COMPUTELAYER_PROJECT=$NEXT_PUBLIC_COMPUTELAYER_PROJECT

RUN npm run build

FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000
CMD ["node", "server.js"]
