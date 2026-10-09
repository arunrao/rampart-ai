/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone', // Enables standalone build for Docker (much smaller image)
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1',
  },
  // Next 16 builds with Turbopack by default. The previous webpack `devtool` override
  // (to avoid eval-source-map heap blowups) is no longer needed and would error here.
}

module.exports = nextConfig
