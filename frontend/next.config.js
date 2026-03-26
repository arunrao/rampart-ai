/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone', // Enables standalone build for Docker (much smaller image)
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1',
  },
  // Default Next dev uses eval-source-map, which duplicates sources per module and can push
  // webpack far past normal V8 heaps on large graphs — looks like a "leak" but is tooling.
  webpack: (config, { dev, isServer }) => {
    if (dev && !isServer) {
      config.devtool = 'cheap-module-source-map';
    }
    return config;
  },
}

module.exports = nextConfig
