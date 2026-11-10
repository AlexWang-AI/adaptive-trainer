/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    agentUpgrade: 'security',
  },
  // SSE 必须关掉压缩，否则 dev server 会把流缓冲到一批才下发，
  // 表现为「首字 4~6 秒」，而不是后端真实的 1~2 秒。
  compress: false,
  allowedDevOrigins: ['127.0.0.1', 'localhost'],
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
}

export default nextConfig
