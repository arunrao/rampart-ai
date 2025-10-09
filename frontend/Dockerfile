# Stage 1: Dependencies
FROM node:18-alpine AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app

# Install dependencies based on the preferred package manager
COPY package*.json ./
RUN npm ci

# Stage 2: Builder
FROM node:18-alpine AS builder
WORKDIR /app

# Copy dependencies from deps stage
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Accept build arguments for public environment variables
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

ARG NEXT_PUBLIC_GITHUB_URL=https://github.com/arunrao/rampart-ai
ENV NEXT_PUBLIC_GITHUB_URL=${NEXT_PUBLIC_GITHUB_URL}

# Next.js collects anonymous telemetry data about general usage.
# Uncomment the following line to disable telemetry during the build.
ENV NEXT_TELEMETRY_DISABLED=1

# Build the application with standalone output (much smaller)
RUN npm run build

# Stage 3: Production runner
FROM node:18-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Create a non-root user
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copy only necessary files from builder
# Copy public directory if it exists
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
# Public folder is optional - copy if exists
RUN mkdir -p ./public

# Set correct permissions
RUN chown -R nextjs:nodejs /app

USER nextjs

# Expose port
EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD node -e "require('http').get('http://localhost:3000', (r) => {process.exit(r.statusCode === 200 ? 0 : 1)}).on('error', () => process.exit(1))"

# Run the application
CMD ["node", "server.js"]
